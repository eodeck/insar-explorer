import os
import re
from osgeo import gdal
from ..qt_compat import VECTOR_LAYER
from . import h5_layer as h5_layer_utils


def checkGrdLayer(layer):
    if layer is None:
        message = 'No layer selected: Please select a raster layer.'
        return False, message
    elif not layer.isValid():
        message = 'Invalid Layer: Please select a valid raster layer.'
        return False, message
    elif layer.type() == VECTOR_LAYER:
        message = 'This is a vector layers. Please select a raster layer.'
        return False, message

    provider_name = ""
    try:
        provider = layer.dataProvider()
        provider_name = provider.name() if provider is not None else ""
    except (AttributeError, RuntimeError):
        provider_name = ""
    if not provider_name:
        try:
            provider_name = layer.providerType()
        except (AttributeError, RuntimeError):
            provider_name = ""

    if provider_name != "gdal":
        message = "The selected raster layer is not a supported local time-series raster."
        return False, message

    file_path = layer.source()
    try:
        dataset = gdal.Open(file_path)
    except RuntimeError:
        dataset = None

    if dataset is None:
        unwrapped = h5_layer_utils.unwrap_h5_or_gdal_path(file_path)
        if unwrapped and os.path.isfile(unwrapped):
            try:
                dataset = gdal.Open(unwrapped)
            except RuntimeError:
                dataset = None

    if dataset is None:
        message = 'Invalid Layer: Unable to open the file with GDAL.'
        return False, message

    driver = dataset.GetDriver().ShortName
    if driver in ['netCDF', 'GMT', 'GTiff', 'HDF5', 'VRT']:
        return True, ""
    else:
        message = 'Invalid Layer: The file is not a GMT grd or GeoTIFF file.'
        return False, message


def checkGrdTimeseries(layer, h5_file_path=None):
    """ check layer is a valid raster with time-series data (.h5 or .grd) """
    message = ""
    if h5_file_path:
        h5_ok, _ = h5_layer_utils.checkH5File(h5_file_path)
        if h5_ok:
            if layer is None:
                return True, ""
            try:
                if layer.type() != VECTOR_LAYER:
                    return True, ""
            except (AttributeError, RuntimeError):
                return True, ""

    status, message = checkGrdLayer(layer)
    if status is False:
        return status, message

    file_path = layer.source()

    # remove NETCDF: wrapper if present and get an actual filesystem path
    file_path = _unwrap_netcdf_path(file_path)

    directory = os.path.dirname(file_path)
    pattern = re.compile(r'^\d{8}_.*\.grd$|timeseries-\d{8}.*\.grd$')

    try:
        grd_files = [f for f in os.listdir(directory) if pattern.match(f)]
    except Exception:
        # directory might not exist or not be accessible
        grd_files = []

    count = len(grd_files)

    if count > 0:
        status = True
    else:
        message = ('Invalid Layer: Please select a vector or raster layer with valid '
                   'timeseries data.')
        status = False

    return status, message


def getGrdInfo(directory) -> (list, list):
    """
    Get the list of grd time series files and their dates
    """
    pattern = re.compile(r'^\d{8}_.*\.grd$|timeseries-\d{8}.*\.grd$')

    # remove NETCDF: wrapper if present and get actual filesystem path
    directory = _unwrap_netcdf_path(directory)

    # If a file path was passed instead of a directory, use its containing directory
    if os.path.isfile(directory):
        directory = os.path.dirname(directory)

    if not os.path.isdir(directory):
        return [], []

    grd_files = sorted([f for f in os.listdir(directory) if pattern.match(f)])
    if not grd_files:
        return [], []

    # full paths
    grd_file_paths = [os.path.join(directory, f) for f in grd_files]

    date_pattern = re.compile(r'^\d{8}|timeseries-\d{8}')
    band_names = []
    for grd_file in grd_file_paths:
        match = date_pattern.match(os.path.basename(grd_file))
        if match:
            date_str = match.group(0)
            date_str = removeTimeseriesPrefix(date_str)
            band_name = f'D{date_str}'
            band_names.append(band_name)

    if len(grd_file_paths) != len(band_names):
        raise ValueError("Number of .grd files and band names do not match.")

    return grd_file_paths, band_names


def removeTimeseriesPrefix(filename):
    pattern = re.compile(r'^timeseries-')
    return re.sub(pattern, '', filename)


def _unwrap_netcdf_path(uri: str) -> str:
    """
    If uri is a GDAL NETCDF-style string (e.g. NETCDF:"/path/to/file.nc":var),
    return the inner path (/path/to/file.nc). Otherwise return uri unchanged.

    Also handles simple NETCDF:/path/without/quotes fallback and Windows paths.
    """
    if not isinstance(uri, str):
        return uri

    for prefix in ('NETCDF:', 'HDF5:'):
        if uri.upper().startswith(prefix):
            remainder = uri[len(prefix):]
            if remainder.startswith('"'):
                end = remainder.find('"', 1)
                if end != -1:
                    return remainder[1:end]
                remainder = remainder[1:]

            last_colon = remainder.rfind(':')
            if last_colon == -1:
                return remainder

            last_slash = max(remainder.rfind('/'), remainder.rfind('\\'))
            if last_colon > last_slash:
                return remainder[:last_colon]

            return remainder

    return uri
