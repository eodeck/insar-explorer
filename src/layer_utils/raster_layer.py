import os
from datetime import datetime
import numpy as np
from osgeo import gdal

from . import grd_layer as grd_layer_utils
from . import h5_layer as h5_layer_utils


def createVrtFromFiles(*, raster_file_paths, band_names=None, out_file="") -> gdal.Dataset:
    """
    Create a VRT file in memory from a list of .grd files and rename each dataset based on its date.
    :param raster_file_paths: List of .grd file paths
    :param band_names: List of band names. Default is None.
    :param out_file: Output file path. Default is an empty string for in-memory vrt file.
    :return: VRT dataset
    """

    vrt_options = gdal.BuildVRTOptions(separate=True)
    vrt_dataset = gdal.BuildVRT(out_file, raster_file_paths, options=vrt_options)

    # Rename bands
    if band_names is None:
        return vrt_dataset

    for i, band_name in enumerate(band_names, start=1):
        band = vrt_dataset.GetRasterBand(i)
        if band is not None:
            band.SetDescription(band_name)

    return vrt_dataset


class RasterTimeseries:
    def __init__(self):
        self.time_series_data = None
        self.h5_file_path = ""
        self.h5_reader = h5_layer_utils.H5TimeseriesReader()

    def reset(self):
        self.time_series_data = None
        self.h5_reader.reset()

    def setH5FilePath(self, file_path: str):
        self.h5_file_path = (file_path or "").strip()
        self.h5_reader.reset()

    def resolveActiveH5FilePath(self, layer=None) -> str:
        """Return the active valid H5 path explicitly selected by the user."""
        _ = layer
        if self.h5_file_path:
            ok, _ = h5_layer_utils.checkH5File(self.h5_file_path)
            if ok:
                return os.path.abspath(h5_layer_utils.unwrap_h5_or_gdal_path(self.h5_file_path))
        return ""

    def hasValidH5Timeseries(self, layer=None) -> bool:
        return bool(self.resolveActiveH5FilePath(layer))

    def getClickedPixelValue(self, layer, point):
        """
        Get the pixel value of the clicked point from the raster layer (or H5 'vel' dataset).
        :param layer: The raster layer
        :param point: The clicked point (QgsPointXY) in layer/geotransform coordinates
        :return: Pixel value at the clicked point or None if not found
        """
        if layer is not None:
            try:
                file_path = layer.source()
            except (AttributeError, RuntimeError):
                file_path = ""

            if file_path:
                dataset = None
                try:
                    dataset = gdal.Open(file_path)
                except RuntimeError:
                    dataset = None

                if dataset is None:
                    try:
                        dataset = createVrtFromFiles(raster_file_paths=file_path, out_file="")
                    except Exception:
                        dataset = None

                if dataset is not None and dataset.RasterCount >= 1:
                    transform = dataset.GetGeoTransform()
                    inv_transform = gdal.InvGeoTransform(transform)
                    if isinstance(inv_transform, tuple) and len(inv_transform) == 2 and isinstance(inv_transform[1], (tuple, list)):
                        inv_transform = inv_transform[1] if inv_transform[0] else None

                    if inv_transform is not None:
                        x, y = point.x(), point.y()
                        px, py = gdal.ApplyGeoTransform(inv_transform, x, y)
                        px, py = int(np.floor(px)), int(np.floor(py))

                        band = dataset.GetRasterBand(1)
                        x_size = band.XSize
                        y_size = band.YSize
                        if 0 <= px < x_size and 0 <= py < y_size:
                            pixel_value = band.ReadAsArray(px, py, 1, 1)
                            if pixel_value is not None:
                                val = float(pixel_value[0, 0])
                                if np.isfinite(val):
                                    return val

        h5_path = self.resolveActiveH5FilePath(layer)
        if h5_path:
            gt, _ = self.h5_reader.resolve_geotransform(h5_path, layer=layer)
            px, py = self.h5_reader.coord_to_pixel(h5_path, point.x(), point.y(), gt)
            if px is not None and py is not None:
                return self.h5_reader.read_pixel_velocity(h5_path, px, py)

        return None

    def getRasterTimeseriesAttributes(self, layer, point):
        """
        Get the timeseries values of the clicked point from an HDF5 (cum.h5) file
        or GMTSAR .grd files.
        """
        h5_path = self.resolveActiveH5FilePath(layer)
        if h5_path:
            gt, _ = self.h5_reader.resolve_geotransform(h5_path, layer=layer)
            px, py = self.h5_reader.coord_to_pixel(h5_path, point.x(), point.y(), gt)
            if px is None or py is None:
                return np.array([])
            return self.h5_reader.get_pixel_timeseries_attributes(h5_path, px, py)

        if layer is None:
            return np.array([])

        file_path = layer.source()
        directory = os.path.dirname(grd_layer_utils._unwrap_netcdf_path(file_path))

        raster_file_paths, band_names = grd_layer_utils.getGrdInfo(directory)
        if not raster_file_paths:
            return np.array([])
        dataset = createVrtFromFiles(raster_file_paths=raster_file_paths,
                                     band_names=band_names, out_file="")

        if not dataset:
            return np.array([])

        date_value_list = self.getVrtTimeseriesAttributes(dataset, point)
        return date_value_list

    def getPolygonTimeseriesAttributes(self, layer, polygon_geom):
        """
        Get the timeseries values of all valid H5 pixels inside polygon_geom.
        Returns (dates, values_2d).
        """
        h5_path = self.resolveActiveH5FilePath(layer)
        if not h5_path:
            return np.array([]), np.array([])
        gt, _ = self.h5_reader.resolve_geotransform(h5_path, layer=layer)
        if gt is None:
            return np.array([]), np.array([])
        return self.h5_reader.get_polygon_timeseries(h5_path, polygon_geom, gt)

    def getVrtTimeseriesAttributes(self, vrt_dataset, point, memory_limit=500):
        """
        Get the timeseries values of the clicked point from a vrt file that consists of time series data.
        The vrt file should have description for each band in the format 'DYYYYMMDD'.
        :param vrt_dataset: VRT dataset
        :param point: QgsPointXY
        :param memory_limit: int in Mb
        """

        transform = vrt_dataset.GetGeoTransform()
        inv_transform = gdal.InvGeoTransform(transform)
        if isinstance(inv_transform, tuple) and len(inv_transform) == 2 and isinstance(inv_transform[1], (tuple, list)):
            if not inv_transform[0]:
                return np.array([])
            inv_transform = inv_transform[1]

        x, y = point.x(), point.y()
        px, py = gdal.ApplyGeoTransform(inv_transform, x, y)
        px, py = int(np.floor(px)), int(np.floor(py))

        band = vrt_dataset.GetRasterBand(1)
        x_size = band.XSize
        y_size = band.YSize
        if not (0 <= px < x_size and 0 <= py < y_size):
            return np.array([])

        num_bands = vrt_dataset.RasterCount
        data_type_size = gdal.GetDataTypeSize(band.DataType) // 8  # Size in bytes
        expected_size = x_size * y_size * num_bands * data_type_size

        if expected_size > memory_limit * 1024 * 1024:
            pixel_values = vrt_dataset.ReadAsArray(px, py, 1, 1)
            if pixel_values is None:
                return np.array([])
            pixel_values = pixel_values[:, 0, 0]

        else:  # read full data at once
            if self.time_series_data is None:
                self.time_series_data = vrt_dataset.ReadAsArray()
            pixel_values = self.time_series_data[:, py, px]

        if pixel_values is None:
            return np.array([])

        date_value_list = []
        date_objs = [datetime.strptime(vrt_dataset.GetRasterBand(i).GetDescription()[1:], '%Y%m%d') for i in
                     range(1, vrt_dataset.RasterCount + 1)]

        for date_obj, pixel_value in zip(date_objs, pixel_values):
            if not np.isnan(pixel_value):
                date_value_list.append((date_obj, pixel_value))

        return np.array(date_value_list, dtype=object)
