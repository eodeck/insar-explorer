**MintPy**
^^^^^^^^^^

    You can visualize `MintPy <https://github.com/insarlab/MintPy>`_ results in InSAR Explorer by converting the time series data from HDF5 format to a GMT `grd` file or shapefile.
    Since MintPy processes data in raster format, converting to `grd` is the recommended method for visualization in InSAR Explorer.
    However, Method 2 provides more fields for the quality of points.

    **Method 1: Convert HDF5 to GMT grd (recommended)**

    *Note:* `save_explorer.py` script is currently available in the `insar-explorer` branch of this `clone of MintPy repository <https://github.com/mahmud1/MintPy/tree/insar-explorer>`_.

    1. Convert the velocity and time series to GMT `grd` format using the `save_explorer.py` script. For example:

    .. code-block:: shell

      $ save_explorer.py geo_timeseries.h5 -v geo_velocity.h5 -o geo_maskTempCoh.h5 -o timeseries/

    This command will create the `timeseries` directory with the following structure:

    .. code-block:: none

      -| timeseries/
        -| velocity_mm.grd
        -| timeseries-YYYYMMDD.grd
        -| timeseries-YYYYMMDD.grd
        -| ...

    You can then open the velocity_mm.grd file in QGIS and use InSAR Explorer to visualize the velocity and plot time series. InSAR Explorer will automatically detect the associated time series files and handle them accordingly.


    **Method 2: Convert HDF5 to shapefiles**

    Use the `save_qgis` script to export the time series data to a shapefile. For example:

    .. code-block:: shell

        $ mintpy save_qgis timeseries_ERA5_ramp_demErr.h5 -g inputs/geometrygeo.h5

