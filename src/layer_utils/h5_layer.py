import hashlib
import os
import tempfile
from datetime import datetime
import numpy as np
from osgeo import gdal, osr

try:
    import h5py
except ImportError:
    h5py = None


def unwrap_h5_or_gdal_path(uri: str) -> str:
    """Extract the filesystem path from a QGIS/GDAL layer source URI."""
    if not isinstance(uri, str) or not uri:
        return ""

    cleaned = uri.split("|")[0].strip()

    for prefix in ("HDF5:", "NETCDF:"):
        if cleaned.upper().startswith(prefix):
            remainder = cleaned[len(prefix):]
            if remainder.startswith('"'):
                end = remainder.find('"', 1)
                if end != -1:
                    return remainder[1:end]
                remainder = remainder[1:]
            last_colon = remainder.rfind(":")
            if last_colon != -1:
                last_slash = max(remainder.rfind("/"), remainder.rfind("\\"))
                if last_colon > last_slash:
                    return remainder[:last_colon]
            return remainder

    if (
        len(cleaned) >= 2
        and cleaned[0] == '"'
        and cleaned[-1] == '"'
    ):
        cleaned = cleaned[1:-1]

    return cleaned


def _parse_imdate(raw_value):
    """Parse one imdates entry (int or bytes/str in YYYYMMDD format) into datetime, or None if empty/invalid."""
    if raw_value is None:
        return None
    if isinstance(raw_value, bytes):
        text = raw_value.decode("utf-8", errors="ignore").strip()
    elif isinstance(raw_value, (int, np.integer)):
        if int(raw_value) <= 0:
            return None
        text = f"{int(raw_value):08d}"
    elif isinstance(raw_value, (float, np.floating)):
        if not np.isfinite(raw_value) or float(raw_value) <= 0:
            return None
        text = f"{int(round(float(raw_value))):08d}"
    else:
        text = str(raw_value).strip()

    if not text:
        return None

    digits = "".join(ch for ch in text if ch.isdigit())
    try:
        if len(digits) >= 8:
            return datetime.strptime(digits[:8], "%Y%m%d")
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None


def _read_scalar_md(root_group, name: str):
    """Read a scalar float dataset from a GDAL multidimensional group if present."""
    try:
        arr = root_group.OpenMDArray(name)
        if arr is None:
            return None
        val = arr.ReadAsArray()
        return float(np.asarray(val).ravel()[0])
    except Exception:
        return None


def _read_imdates_md(dates_md):
    """Read 1D imdates array from a GDAL MDArray supporting both numeric and string types."""
    if dates_md is None:
        return None
    try:
        dt = dates_md.GetDataType()
        if (
            dt is not None
            and hasattr(gdal, "GEDTC_STRING")
            and dt.GetClass() == gdal.GEDTC_STRING
        ):
            raw = dates_md.Read()
            if isinstance(raw, (list, tuple)):
                return list(raw)
    except Exception:
        pass
    try:
        arr = dates_md.ReadAsArray()
        if arr is not None:
            dims = [d.GetSize() for d in dates_md.GetDimensions()]
            if len(dims) == 1 and len(arr) == dims[0]:
                return list(arr)
    except Exception:
        pass
    try:
        raw = dates_md.Read()
        if isinstance(raw, (list, tuple)):
            return list(raw)
    except Exception:
        pass
    return None


def _read_root_geotransform_and_crs(root_group):
    """Read (geotransform, crs_wkt) from root group attributes (e.g. 'transform', 'crs_wkt') if present."""
    if root_group is None:
        return None, ""
    try:
        attrs = root_group.GetAttributes() or []
    except Exception:
        attrs = []
    attr_map = {}
    for attr in attrs:
        try:
            attr_map[attr.GetName()] = attr.Read()
        except Exception:
            continue

    gt = None
    for key in ("transform", "geotransform", "GeoTransform"):
        val = attr_map.get(key)
        if val is not None:
            try:
                vals = [float(x) for x in val]
                if len(vals) >= 6:
                    cand = tuple(vals[:6])
                    if cand[1] == 0.0 and cand[3] == 0.0 and cand[0] != 0.0 and cand[4] != 0.0:
                        cand = (cand[2], cand[0], cand[1], cand[5], cand[3], cand[4])
                    if cand != (0.0, 1.0, 0.0, 0.0, 0.0, 1.0) and cand[1] != 0 and cand[5] != 0:
                        gt = cand
                        break
            except Exception:
                pass

    crs_wkt = ""
    for key in ("crs_wkt", "spatial_ref", "crs", "projection"):
        val = attr_map.get(key)
        if isinstance(val, str) and val.strip():
            crs_wkt = val.strip()
            break

    return gt, crs_wkt


def checkH5File(file_path: str, *, dates_key: str = "imdates", cum_key: str = "cum"):
    """Validate that file_path is a readable HDF5 file with imdates and cum datasets."""
    resolved = unwrap_h5_or_gdal_path(file_path)
    if not resolved:
        return False, "No H5 file selected."
    if not os.path.isfile(resolved):
        return False, f"H5 file not found: {resolved}"

    # Try GDAL Multidimensional Raster API first (built into QGIS)
    if hasattr(gdal, "OpenEx") and hasattr(gdal, "OF_MULTIDIM_RASTER"):
        try:
            ds = gdal.OpenEx(resolved, gdal.OF_MULTIDIM_RASTER)
        except Exception:
            ds = None
        if ds is not None:
            try:
                rg = ds.GetRootGroup()
                if rg is not None:
                    names = set(rg.GetMDArrayNames() or [])
                    if dates_key not in names or cum_key not in names:
                        return (
                            False,
                            f"H5 file must contain '{dates_key}' and '{cum_key}' datasets.",
                        )
                    cum_arr = rg.OpenMDArray(cum_key)
                    dates_arr = rg.OpenMDArray(dates_key)
                    if cum_arr is None or dates_arr is None:
                        return False, f"Unable to open '{dates_key}' or '{cum_key}' in H5 file."
                    cum_dims = [d.GetSize() for d in cum_arr.GetDimensions()]
                    dates_dims = [d.GetSize() for d in dates_arr.GetDimensions()]
                    if len(cum_dims) != 3 or len(dates_dims) != 1:
                        return (
                            False,
                            f"Expected 3D '{cum_key}' and 1D '{dates_key}' datasets in H5 file.",
                        )
                    if cum_dims[0] != dates_dims[0] or cum_dims[0] == 0:
                        return (
                            False,
                            f"Length of '{dates_key}' ({dates_dims[0]}) does not match '{cum_key}' time dimension ({cum_dims[0]}).",
                        )
                    return True, ""
            except Exception as exc:
                return False, f"Error reading H5 file: {exc}"

    # Fallback to h5py if available
    if h5py is not None:
        try:
            with h5py.File(resolved, "r") as f:
                if dates_key not in f or cum_key not in f:
                    return (
                        False,
                        f"H5 file must contain '{dates_key}' and '{cum_key}' datasets.",
                    )
                cum_shape = f[cum_key].shape
                dates_shape = f[dates_key].shape
                if len(cum_shape) != 3 or len(dates_shape) != 1 or cum_shape[0] != dates_shape[0]:
                    return False, "Invalid dataset dimensions in H5 file."
                return True, ""
        except Exception as exc:
            return False, f"Error reading H5 file: {exc}"

    return False, "Unable to open H5 file with GDAL or h5py."


def format_h5_display_name(file_path: str) -> str:
    """Return a concise, disambiguated display name for an H5 file path."""
    cleaned = unwrap_h5_or_gdal_path(file_path or "").strip()
    if not cleaned:
        return ""
    norm = os.path.normpath(cleaned)
    base = os.path.basename(norm)
    parent_dir = os.path.dirname(norm)
    parent_name = os.path.basename(parent_dir) if parent_dir else ""
    if parent_name and parent_name not in ("", ".", os.path.sep):
        grandparent_dir = os.path.dirname(parent_dir)
        grandparent_name = os.path.basename(grandparent_dir) if grandparent_dir else ""
        if parent_name.upper().startswith("TS_") and grandparent_name:
            return f"{base} ({grandparent_name}/{parent_name})"
        return f"{base} ({parent_name})"
    return base


def findAutoH5FileForLayer(layer) -> str:
    """Search for a matching H5 time-series file (e.g. cum.h5) near the given layer."""
    if layer is None:
        return ""
    try:
        custom_h5 = layer.customProperty("insar_explorer/h5_velocity_source", "")
        if custom_h5:
            ok, _ = checkH5File(str(custom_h5))
            if ok:
                return os.path.abspath(unwrap_h5_or_gdal_path(str(custom_h5)))
    except Exception:
        pass
    try:
        source = layer.source()
    except (AttributeError, RuntimeError):
        return ""

    file_path = unwrap_h5_or_gdal_path(source)
    if not file_path:
        return ""

    if file_path.lower().endswith((".h5", ".hdf5", ".he5")):
        ok, _ = checkH5File(file_path)
        if ok:
            return os.path.abspath(file_path)

    directory = os.path.dirname(file_path) if os.path.isfile(file_path) else file_path
    if not directory or not os.path.isdir(directory):
        return ""

    search_dirs = [directory]
    parent_dir = os.path.dirname(directory)
    if parent_dir and os.path.isdir(parent_dir) and parent_dir != directory:
        search_dirs.append(parent_dir)

    preferred_names = ("cum_filt.h5", "cum.h5")
    for d in search_dirs:
        for name in preferred_names:
            candidate = os.path.join(d, name)
            if os.path.isfile(candidate):
                ok, _ = checkH5File(candidate)
                if ok:
                    return os.path.abspath(candidate)

        try:
            entries = sorted(os.listdir(d))
        except OSError:
            continue
        for entry in entries:
            if entry.lower().endswith((".h5", ".hdf5", ".he5")):
                candidate = os.path.join(d, entry)
                if os.path.isfile(candidate):
                    ok, _ = checkH5File(candidate)
                    if ok:
                        return os.path.abspath(candidate)

    return ""


class H5TimeseriesReader:
    """Reader for pixel and polygon time-series data from LiCSBAS/InSAR HDF5 files."""

    def __init__(self, dates_key: str = "imdates", cum_key: str = "cum"):
        self.dates_key = dates_key
        self.cum_key = cum_key
        self.selected_field_name = cum_key
        self._cached_path = None
        self._cached_mtime = None
        self._md_dataset = None
        self._cum_md_array = None
        self._vel_md_array = None
        self.dates = None
        self.shape = None  # (n_valid_dates, n_y, n_x)
        self._raw_n_dates = 0
        self._valid_time_indices = None
        self.geotransform = None  # (ul_lon, post_lon, 0.0, ul_lat, 0.0, post_lat)
        self.crs_wkt = ""

    def reset(self):
        self._cached_path = None
        self._cached_mtime = None
        self._md_dataset = None
        self._cum_md_array = None
        self._vel_md_array = None
        self.dates = None
        self.shape = None
        self._raw_n_dates = 0
        self._valid_time_indices = None
        self.geotransform = None
        self.crs_wkt = ""

    def _ensure_loaded(self, h5_path: str) -> bool:
        resolved = unwrap_h5_or_gdal_path(h5_path)
        if not resolved or not os.path.isfile(resolved):
            self.reset()
            return False

        resolved = os.path.abspath(resolved)
        try:
            mtime = os.path.getmtime(resolved)
        except OSError:
            mtime = None

        if (
            self._cached_path == resolved
            and self._cached_mtime == mtime
            and self.dates is not None
            and self.shape is not None
        ):
            return True

        self.reset()

        # Load via GDAL Multidimensional Raster API
        if hasattr(gdal, "OpenEx") and hasattr(gdal, "OF_MULTIDIM_RASTER"):
            try:
                ds = gdal.OpenEx(resolved, gdal.OF_MULTIDIM_RASTER)
            except Exception:
                ds = None
            if ds is not None:
                rg = ds.GetRootGroup()
                if rg is not None:
                    names = set(rg.GetMDArrayNames() or [])
                    if self.dates_key in names and self.cum_key in names:
                        dates_md = rg.OpenMDArray(self.dates_key)
                        cum_md = rg.OpenMDArray(self.cum_key)
                        if dates_md is not None and cum_md is not None:
                            raw_dates = _read_imdates_md(dates_md)
                            dims = tuple(int(d.GetSize()) for d in cum_md.GetDimensions())
                            if (
                                raw_dates is not None
                                and len(dims) == 3
                                and len(raw_dates) == dims[0]
                                and dims[0] > 0
                            ):
                                parsed = [_parse_imdate(d) for d in raw_dates]
                                valid_idx = [i for i, dt in enumerate(parsed) if dt is not None]
                                if not valid_idx:
                                    return False
                                self._raw_n_dates = int(dims[0])
                                self._valid_time_indices = (
                                    np.array(valid_idx, dtype=int)
                                    if len(valid_idx) < dims[0]
                                    else None
                                )
                                self.dates = np.array(
                                    [parsed[i] for i in valid_idx], dtype=object
                                )
                                self.shape = (len(valid_idx), int(dims[1]), int(dims[2]))
                                self._md_dataset = ds
                                self._cum_md_array = cum_md
                                if "vel" in names:
                                    try:
                                        self._vel_md_array = rg.OpenMDArray("vel")
                                    except Exception:
                                        self._vel_md_array = None

                                corner_lat = _read_scalar_md(rg, "corner_lat")
                                corner_lon = _read_scalar_md(rg, "corner_lon")
                                post_lat = _read_scalar_md(rg, "post_lat")
                                post_lon = _read_scalar_md(rg, "post_lon")
                                if (
                                    corner_lat is not None
                                    and corner_lon is not None
                                    and post_lat is not None
                                    and post_lon is not None
                                    and post_lat != 0
                                    and post_lon != 0
                                ):
                                    # In LiCSBAS, corner_lon/corner_lat are the center of the top-left pixel
                                    ul_lon = corner_lon - 0.5 * post_lon
                                    ul_lat = corner_lat - 0.5 * post_lat
                                    self.geotransform = (
                                        ul_lon,
                                        post_lon,
                                        0.0,
                                        ul_lat,
                                        0.0,
                                        post_lat,
                                    )
                                else:
                                    attr_gt, attr_crs = _read_root_geotransform_and_crs(rg)
                                    if attr_gt is not None:
                                        self.geotransform = attr_gt
                                    if attr_crs:
                                        self.crs_wkt = attr_crs

                                self._cached_path = resolved
                                self._cached_mtime = mtime
                                return True

        # Fallback to h5py if available
        if h5py is not None:
            try:
                with h5py.File(resolved, "r") as f:
                    if self.dates_key in f and self.cum_key in f:
                        raw_dates = f[self.dates_key][()]
                        dims = tuple(int(s) for s in f[self.cum_key].shape)
                        if len(dims) == 3 and len(raw_dates) == dims[0] and dims[0] > 0:
                            parsed = [_parse_imdate(d) for d in raw_dates]
                            valid_idx = [i for i, dt in enumerate(parsed) if dt is not None]
                            if not valid_idx:
                                return False
                            self._raw_n_dates = int(dims[0])
                            self._valid_time_indices = (
                                np.array(valid_idx, dtype=int)
                                if len(valid_idx) < dims[0]
                                else None
                            )
                            self.dates = np.array(
                                [parsed[i] for i in valid_idx], dtype=object
                            )
                            self.shape = (len(valid_idx), int(dims[1]), int(dims[2]))
                            if all(k in f for k in ("corner_lat", "corner_lon", "post_lat", "post_lon")):
                                corner_lat = float( np.asarray(f["corner_lat"][()]).ravel()[0] )
                                corner_lon = float( np.asarray(f["corner_lon"][()]).ravel()[0] )
                                post_lat = float( np.asarray(f["post_lat"][()]).ravel()[0] )
                                post_lon = float( np.asarray(f["post_lon"][()]).ravel()[0] )
                                if post_lat != 0 and post_lon != 0:
                                    ul_lon = corner_lon - 0.5 * post_lon
                                    ul_lat = corner_lat - 0.5 * post_lat
                                    self.geotransform = (
                                        ul_lon,
                                        post_lon,
                                        0.0,
                                        ul_lat,
                                        0.0,
                                        post_lat,
                                    )
                            self._cached_path = resolved
                            self._cached_mtime = mtime
                            return True
            except Exception:
                pass

        return False

    def get_summary(self, h5_path: str):
        """Return (n_dates, n_y, n_x) if valid, else None."""
        if not self._ensure_loaded(h5_path):
            return None
        return self.shape

    def resolve_geotransform(self, h5_path: str, layer=None):
        """Return (geotransform, use_layer_crs) for mapping coordinates to H5 pixels."""
        if not self._ensure_loaded(h5_path):
            return None, False

        if self.geotransform is not None:
            return self.geotransform, False

        _, n_y, n_x = self.shape

        if layer is not None:
            try:
                layer_path = unwrap_h5_or_gdal_path(layer.source())
                if layer_path and os.path.isfile(layer_path):
                    ds = gdal.Open(layer_path)
                    if ds is not None:
                        gt = ds.GetGeoTransform()
                        if (
                            gt is not None
                            and gt != (0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
                            and ds.RasterXSize == n_x
                            and ds.RasterYSize == n_y
                        ):
                            return gt, True
            except Exception:
                pass

        # Last-resort fallback if raster layer has any valid GeoTransform
        if layer is not None:
            try:
                layer_path = unwrap_h5_or_gdal_path(layer.source())
                ds = gdal.Open(layer_path) if layer_path else None
                if ds is not None:
                    gt = ds.GetGeoTransform()
                    if gt is not None and gt != (0.0, 1.0, 0.0, 0.0, 0.0, 1.0):
                        return gt, True
            except Exception:
                pass

        return None, False

    def coord_to_pixel(self, h5_path: str, x: float, y: float, geotransform):
        """Convert (x, y) in the geotransform's CRS to (px, py) pixel indices, or (None, None)."""
        if geotransform is None or not self._ensure_loaded(h5_path):
            return None, None

        try:
            inv_gt = gdal.InvGeoTransform(geotransform)
            if inv_gt is None:
                return None, None
            # GDAL InvGeoTransform can return (success_flag, inv_gt) or inv_gt depending on bindings
            if isinstance(inv_gt, tuple) and len(inv_gt) == 2 and isinstance(inv_gt[1], (tuple, list)):
                if not inv_gt[0]:
                    return None, None
                inv_gt = inv_gt[1]
            px_f, py_f = gdal.ApplyGeoTransform(inv_gt, float(x), float(y))
            px = int(np.floor(px_f))
            py = int(np.floor(py_f))
        except Exception:
            return None, None

        _, n_y, n_x = self.shape
        if 0 <= px < n_x and 0 <= py < n_y:
            return px, py
        return None, None

    def get_h5_fields(self, h5_path: str):
        """Return ordered list of (field_name, is_spatial) for all datasets in the H5 file, prioritizing 'cum'."""
        if not self._ensure_loaded(h5_path):
            return []

        _, n_y, n_x = self.shape
        raw_fields = {}

        if self._md_dataset is not None:
            try:
                rg = self._md_dataset.GetRootGroup()
                if rg is not None:
                    for name in rg.GetMDArrayNames() or []:
                        try:
                            arr = rg.OpenMDArray(name)
                            dims = tuple(int(d.GetSize()) for d in arr.GetDimensions()) if arr is not None else ()
                            raw_fields[str(name)] = dims
                        except Exception:
                            raw_fields[str(name)] = ()
            except Exception:
                pass

        if not raw_fields and h5py is not None:
            try:
                with h5py.File(self._cached_path, "r") as f:
                    for name in f.keys():
                        try:
                            raw_fields[str(name)] = tuple(int(s) for s in f[name].shape)
                        except Exception:
                            raw_fields[str(name)] = ()
            except Exception:
                pass

        if not raw_fields:
            return [(self.cum_key, True)]

        def _sort_key(item):
            name, dims = item
            is_spatial = len(dims) in (2, 3) and dims[-2:] == (n_y, n_x)
            if name == self.cum_key:
                return (0, name.lower())
            if name == "vel" and is_spatial:
                return (1, name.lower())
            if is_spatial and len(dims) == 3:
                return (2, name.lower())
            if is_spatial and len(dims) == 2:
                return (3, name.lower())
            return (4, name.lower())

        ordered = []
        for name, dims in sorted(raw_fields.items(), key=_sort_key):
            is_spatial = len(dims) in (2, 3) and dims[-2:] == (n_y, n_x)
            ordered.append((name, is_spatial))
        return ordered

    def _resolve_active_3d_dataset(self, field_name: str = None):
        """Return (dataset_name, dates_array) for 3D time-series extraction, defaulting to cum."""
        candidate = (field_name or self.selected_field_name or self.cum_key).strip()
        n_dates, n_y, n_x = self.shape
        if candidate and candidate != self.cum_key:
            if self._md_dataset is not None:
                try:
                    rg = self._md_dataset.GetRootGroup()
                    arr = rg.OpenMDArray(candidate) if rg is not None else None
                    if arr is not None:
                        dims = tuple(int(d.GetSize()) for d in arr.GetDimensions())
                        if len(dims) == 3 and dims[1:] == (n_y, n_x):
                            if dims[0] == n_dates:
                                return candidate, self.dates
                            if dims[0] == n_dates - 1 and n_dates > 1:
                                return candidate, self.dates[1:]
                except Exception:
                    pass
            if h5py is not None:
                try:
                    with h5py.File(self._cached_path, "r") as f:
                        if candidate in f:
                            dims = tuple(int(s) for s in f[candidate].shape)
                            if len(dims) == 3 and dims[1:] == (n_y, n_x):
                                if dims[0] == n_dates:
                                    return candidate, self.dates
                                if dims[0] == n_dates - 1 and n_dates > 1:
                                    return candidate, self.dates[1:]
                except Exception:
                    pass
        return self.cum_key, self.dates

    def read_pixel_values(self, h5_path: str, px: int, py: int, field_name: str = None) -> np.ndarray:
        """Read the 1D time-series array for pixel (px, py)."""
        if not self._ensure_loaded(h5_path):
            return np.array([])

        _, n_y, n_x = self.shape
        if not (0 <= px < n_x and 0 <= py < n_y):
            return np.array([])

        ds_name, dates_arr = self._resolve_active_3d_dataset(field_name)
        n_steps = len(dates_arr)

        values = None
        if self._md_dataset is not None:
            try:
                md_arr = (
                    self._cum_md_array
                    if ds_name == self.cum_key
                    else self._md_dataset.GetRootGroup().OpenMDArray(ds_name)
                )
                if md_arr is not None:
                    raw_t = int(md_arr.GetDimensions()[0].GetSize())
                    raw = md_arr.ReadAsArray(
                        array_start_idx=[0, int(py), int(px)],
                        count=[raw_t, 1, 1],
                    )
                    if raw is not None:
                        values = np.asarray(raw, dtype=float).ravel()
                        if (
                            ds_name == self.cum_key
                            and self._valid_time_indices is not None
                            and values.size == self._raw_n_dates
                        ):
                            values = values[self._valid_time_indices]
            except Exception:
                values = None

        if values is None and h5py is not None:
            try:
                with h5py.File(self._cached_path, "r") as f:
                    values = np.asarray(f[ds_name][:, int(py), int(px)], dtype=float).ravel()
                    if (
                        ds_name == self.cum_key
                        and self._valid_time_indices is not None
                        and values.size == self._raw_n_dates
                    ):
                        values = values[self._valid_time_indices]
            except Exception:
                values = None

        if values is None or values.size != n_steps:
            return np.array([])
        return values

    def get_pixel_timeseries_attributes(self, h5_path: str, px: int, py: int) -> np.ndarray:
        """Return (N, 2) object array of (datetime, float) for pixel (px, py)."""
        if not self._ensure_loaded(h5_path):
            return np.array([])
        _, dates_arr = self._resolve_active_3d_dataset(self.selected_field_name)
        values = self.read_pixel_values(h5_path, px, py, field_name=self.selected_field_name)
        if values.size == 0 or not np.isfinite(values).any():
            return np.array([])

        pairs = [(d, float(v)) for d, v in zip(dates_arr, values)]
        return np.array(pairs, dtype=object)

    def read_pixel_velocity(self, h5_path: str, px: int, py: int, field_name: str = None):
        """Read scalar map value (or velocity) at (px, py) for the active H5 field."""
        if not self._ensure_loaded(h5_path):
            return None
        _, n_y, n_x = self.shape
        if not (0 <= px < n_x and 0 <= py < n_y):
            return None

        target_field = (field_name or self.selected_field_name or self.cum_key).strip()
        if target_field and target_field not in (self.cum_key, "vel"):
            if self._md_dataset is not None:
                try:
                    rg = self._md_dataset.GetRootGroup()
                    arr = rg.OpenMDArray(target_field) if rg is not None else None
                    if arr is not None:
                        dims = tuple(int(d.GetSize()) for d in arr.GetDimensions())
                        if len(dims) == 2 and dims == (n_y, n_x):
                            val = arr.ReadAsArray(
                                array_start_idx=[int(py), int(px)],
                                count=[1, 1],
                            )
                            if val is not None:
                                v = float(np.asarray(val).ravel()[0])
                                return v if np.isfinite(v) else None
                except Exception:
                    pass

        if self._vel_md_array is not None:
            try:
                val = self._vel_md_array.ReadAsArray(
                    array_start_idx=[int(py), int(px)],
                    count=[1, 1],
                )
                if val is not None:
                    v = float(np.asarray(val).ravel()[0])
                    return v if np.isfinite(v) else None
            except Exception:
                pass

        if h5py is not None:
            try:
                with h5py.File(self._cached_path, "r") as f:
                    if target_field in f and len(f[target_field].shape) == 2:
                        v = float(f[target_field][int(py), int(px)])
                        return v if np.isfinite(v) else None
                    if "vel" in f:
                        v = float(f["vel"][int(py), int(px)])
                        return v if np.isfinite(v) else None
            except Exception:
                pass
        return None

    def get_frame_corners(self, h5_path: str, layer=None):
        """Return (corners, use_layer_crs) for the 4 outer corners of the H5 pixel grid."""
        if not self._ensure_loaded(h5_path):
            return None, False

        gt, use_layer_crs = self.resolve_geotransform(h5_path, layer=layer)
        _, n_y, n_x = self.shape
        if gt is None:
            gt = (0.0, 1.0, 0.0, float(n_y), 0.0, -1.0)
            use_layer_crs = False

        pixel_corners = [
            (0.0, 0.0),
            (float(n_x), 0.0),
            (float(n_x), float(n_y)),
            (0.0, float(n_y)),
        ]
        geo_corners = [
            (
                gt[0] + px * gt[1] + py * gt[2],
                gt[3] + px * gt[4] + py * gt[5],
            )
            for px, py in pixel_corners
        ]
        return geo_corners, use_layer_crs

    def read_or_compute_velocity_grid(self, h5_path: str):
        """Return 2D float32 velocity grid (n_y, n_x) in mm/yr from 'vel' or OLS fit of 'cum'."""
        if not self._ensure_loaded(h5_path):
            return None

        n_dates, n_y, n_x = self.shape
        vel_grid = None

        if self._vel_md_array is not None:
            try:
                raw_vel = self._vel_md_array.ReadAsArray()
                if raw_vel is not None:
                    arr = np.asarray(raw_vel, dtype=np.float32)
                    if arr.shape == (n_y, n_x) and np.isfinite(arr).any():
                        vel_grid = arr
            except Exception:
                vel_grid = None

        if vel_grid is None and h5py is not None:
            try:
                with h5py.File(self._cached_path, "r") as f:
                    if "vel" in f:
                        arr = np.asarray(f["vel"][()], dtype=np.float32)
                        if arr.shape == (n_y, n_x) and np.isfinite(arr).any():
                            vel_grid = arr
            except Exception:
                vel_grid = None

        if vel_grid is not None:
            return np.where(np.isfinite(vel_grid), vel_grid, np.nan).astype(np.float32)

        # Fallback: compute linear velocity (mm/yr) from 'cum' and 'imdates'
        cum_cube = None
        if self._cum_md_array is not None:
            try:
                raw_cum = self._cum_md_array.ReadAsArray()
                if raw_cum is not None:
                    cum_cube = np.asarray(raw_cum, dtype=np.float32)
            except Exception:
                cum_cube = None

        if cum_cube is None and h5py is not None:
            try:
                with h5py.File(self._cached_path, "r") as f:
                    cum_cube = np.asarray(f[self.cum_key][()], dtype=np.float32)
            except Exception:
                cum_cube = None

        if cum_cube is not None and self._valid_time_indices is not None and cum_cube.shape[0] == self._raw_n_dates:
            cum_cube = cum_cube[self._valid_time_indices, :, :]

        if cum_cube is None or cum_cube.shape != (n_dates, n_y, n_x) or n_dates < 2:
            return None

        t0 = self.dates[0]
        t_years = np.array([(d - t0).days / 365.25 for d in self.dates], dtype=np.float64)
        valid = np.isfinite(cum_cube)
        w = valid.astype(np.float64)
        c = np.where(valid, cum_cube, 0.0).astype(np.float64)

        count = w.sum(axis=0)
        safe_count = np.maximum(count, 1.0)
        sum_t = np.tensordot(t_years, w, axes=(0, 0))
        sum_t2 = np.tensordot(t_years * t_years, w, axes=(0, 0))
        sum_c = c.sum(axis=0)
        sum_tc = np.tensordot(t_years, c, axes=(0, 0))

        denom = sum_t2 - (sum_t * sum_t) / safe_count
        num = sum_tc - (sum_t * sum_c) / safe_count
        with np.errstate(divide="ignore", invalid="ignore"):
            vel_grid = np.where((count >= 2) & (denom > 1e-12), num / denom, np.nan)
        return vel_grid.astype(np.float32)

    def read_field_2d_grid(self, h5_path: str, field_name: str = None):
        """Return a 2D float32 grid (n_y, n_x) for the given H5 field name."""
        if not self._ensure_loaded(h5_path):
            return None

        target_field = (field_name or self.selected_field_name or self.cum_key).strip()
        if not target_field or target_field in (self.cum_key, "vel"):
            return self.read_or_compute_velocity_grid(h5_path)

        n_dates, n_y, n_x = self.shape
        raw = None

        if self._md_dataset is not None:
            try:
                rg = self._md_dataset.GetRootGroup()
                arr = rg.OpenMDArray(target_field) if rg is not None else None
                if arr is not None:
                    raw = arr.ReadAsArray()
            except Exception:
                raw = None

        if raw is None and h5py is not None:
            try:
                with h5py.File(self._cached_path, "r") as f:
                    if target_field in f:
                        raw = f[target_field][()]
            except Exception:
                raw = None

        if raw is None:
            return self.read_or_compute_velocity_grid(h5_path)

        data = np.asarray(raw, dtype=np.float32)
        if data.ndim == 2 and data.shape == (n_y, n_x):
            return np.where(np.isfinite(data), data, np.nan).astype(np.float32)

        if data.ndim == 3 and data.shape[1:] == (n_y, n_x):
            if data.shape[0] == n_dates and target_field != "gap" and n_dates >= 2:
                t0 = self.dates[0]
                t_years = np.array([(d - t0).days / 365.25 for d in self.dates], dtype=np.float64)
                valid = np.isfinite(data)
                w = valid.astype(np.float64)
                c = np.where(valid, data, 0.0).astype(np.float64)
                count = w.sum(axis=0)
                safe_count = np.maximum(count, 1.0)
                sum_t = np.tensordot(t_years, w, axes=(0, 0))
                sum_t2 = np.tensordot(t_years * t_years, w, axes=(0, 0))
                sum_c = c.sum(axis=0)
                sum_tc = np.tensordot(t_years, c, axes=(0, 0))
                denom = sum_t2 - (sum_t * sum_t) / safe_count
                num = sum_tc - (sum_t * sum_c) / safe_count
                with np.errstate(divide="ignore", invalid="ignore"):
                    grid = np.where((count >= 2) & (denom > 1e-12), num / denom, np.nan)
                return grid.astype(np.float32)

            valid = np.isfinite(data)
            any_valid = valid.any(axis=0)
            summed = np.where(valid, data, 0.0).sum(axis=0)
            return np.where(any_valid, summed, np.nan).astype(np.float32)

        return self.read_or_compute_velocity_grid(h5_path)

    def export_velocity_geotiff(self, h5_path: str, layer=None, field_name: str = None) -> str:
        """Create a georeferenced single-band Float32 GeoTIFF of the active H5 field."""
        if not self._ensure_loaded(h5_path):
            return ""

        target_field = (field_name or self.selected_field_name or self.cum_key).strip()
        grid = self.read_field_2d_grid(h5_path, field_name=target_field)
        if grid is None:
            return ""

        _, n_y, n_x = self.shape
        gt, use_layer_crs = self.resolve_geotransform(h5_path, layer=layer)
        if gt is None:
            gt = (0.0, 1.0, 0.0, float(n_y), 0.0, -1.0)
            use_layer_crs = False

        wkt = ""
        if use_layer_crs and layer is not None:
            try:
                if layer.crs().isValid():
                    wkt = layer.crs().toWkt()
            except Exception:
                wkt = ""
        if not wkt and self.crs_wkt:
            wkt = self.crs_wkt
        if not wkt:
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(4326)
            wkt = srs.ExportToWkt()

        cache_dir = os.path.join(tempfile.gettempdir(), "insar_explorer_h5_cache")
        os.makedirs(cache_dir, exist_ok=True)
        resolved = self._cached_path or os.path.abspath(unwrap_h5_or_gdal_path(h5_path))
        stem = os.path.splitext(os.path.basename(resolved))[0]
        path_hash = hashlib.md5(resolved.encode("utf-8", errors="ignore")).hexdigest()[:8]
        safe_field = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in target_field) or "velocity"
        out_path = os.path.join(cache_dir, f"{stem}_{path_hash}_{safe_field}.tif")

        driver = gdal.GetDriverByName("GTiff")
        if driver is None:
            return ""

        # If out_path is locked by an active QGIS layer, try writing or fallback to a versioned name
        ds = None
        for attempt in range(5):
            candidate = out_path if attempt == 0 else os.path.join(
                cache_dir, f"{stem}_{path_hash}_{safe_field}_{attempt}.tif"
            )
            try:
                ds = driver.Create(candidate, int(n_x), int(n_y), 1, gdal.GDT_Float32)
                if ds is not None:
                    out_path = candidate
                    break
            except Exception:
                ds = None

        if ds is None:
            return ""

        try:
            ds.SetGeoTransform(gt)
            if wkt:
                ds.SetProjection(wkt)
            band = ds.GetRasterBand(1)
            band.SetNoDataValue(float("nan"))
            band.WriteArray(grid)
            try:
                band.ComputeStatistics(False)
            except Exception:
                pass
            ds.FlushCache()
        finally:
            ds = None

        return out_path

    def get_polygon_timeseries(self, h5_path: str, polygon_geom, geotransform):
        """Return (dates, values_2d) for all valid H5 pixels inside polygon_geom."""
        if polygon_geom is None or geotransform is None or not self._ensure_loaded(h5_path):
            return np.array([]), np.array([])

        try:
            inv_gt = gdal.InvGeoTransform(geotransform)
            if inv_gt is None:
                return np.array([]), np.array([])
            if isinstance(inv_gt, tuple) and len(inv_gt) == 2 and isinstance(inv_gt[1], (tuple, list)):
                if not inv_gt[0]:
                    return np.array([]), np.array([])
                inv_gt = inv_gt[1]
        except Exception:
            return np.array([]), np.array([])

        bbox = polygon_geom.boundingBox()
        corners = [
            (bbox.xMinimum(), bbox.yMinimum()),
            (bbox.xMinimum(), bbox.yMaximum()),
            (bbox.xMaximum(), bbox.yMinimum()),
            (bbox.xMaximum(), bbox.yMaximum()),
        ]
        px_coords = []
        py_coords = []
        for cx, cy in corners:
            px_f, py_f = gdal.ApplyGeoTransform(inv_gt, float(cx), float(cy))
            px_coords.append(px_f)
            py_coords.append(py_f)

        _, n_y, n_x = self.shape
        ds_name, dates_arr = self._resolve_active_3d_dataset(self.selected_field_name)
        n_steps = len(dates_arr)

        px_min = max(0, int(np.floor(min(px_coords))))
        px_max = min(n_x - 1, int(np.ceil(max(px_coords))))
        py_min = max(0, int(np.floor(min(py_coords))))
        py_max = min(n_y - 1, int(np.ceil(max(py_coords))))

        if px_min > px_max or py_min > py_max:
            return np.array([]), np.array([])

        from qgis.core import QgsPointXY

        selected_offsets = []
        for py in range(py_min, py_max + 1):
            for px in range(px_min, px_max + 1):
                cx = geotransform[0] + (px + 0.5) * geotransform[1] + (py + 0.5) * geotransform[2]
                cy = geotransform[3] + (px + 0.5) * geotransform[4] + (py + 0.5) * geotransform[5]
                if polygon_geom.contains(QgsPointXY(cx, cy)):
                    selected_offsets.append((py - py_min, px - px_min))

        if not selected_offsets:
            return np.array([]), np.array([])

        win_y = py_max - py_min + 1
        win_x = px_max - px_min + 1
        block = None
        if self._md_dataset is not None:
            try:
                md_arr = (
                    self._cum_md_array
                    if ds_name == self.cum_key
                    else self._md_dataset.GetRootGroup().OpenMDArray(ds_name)
                )
                if md_arr is not None:
                    raw_t = int(md_arr.GetDimensions()[0].GetSize())
                    raw = md_arr.ReadAsArray(
                        array_start_idx=[0, int(py_min), int(px_min)],
                        count=[raw_t, int(win_y), int(win_x)],
                    )
                    if raw is not None:
                        block = np.asarray(raw, dtype=float)
                        if (
                            ds_name == self.cum_key
                            and self._valid_time_indices is not None
                            and block.shape[0] == self._raw_n_dates
                        ):
                            block = block[self._valid_time_indices, :, :]
            except Exception:
                block = None

        if block is None and h5py is not None:
            try:
                with h5py.File(self._cached_path, "r") as f:
                    block = np.asarray(
                        f[ds_name][:, int(py_min):int(py_max) + 1, int(px_min):int(px_max) + 1],
                        dtype=float,
                    )
                    if (
                        ds_name == self.cum_key
                        and self._valid_time_indices is not None
                        and block.shape[0] == self._raw_n_dates
                    ):
                        block = block[self._valid_time_indices, :, :]
            except Exception:
                block = None

        if block is None or block.ndim != 3:
            return np.array([]), np.array([])

        columns = []
        for dy, dx in selected_offsets:
            col = block[:, dy, dx]
            if np.isfinite(col).any():
                columns.append(col)

        if not columns:
            return np.array([]), np.array([])

        values_2d = np.stack(columns, axis=1)
        return dates_arr.copy(), values_2d

