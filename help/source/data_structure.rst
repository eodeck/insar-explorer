Data Structure
**************

    The plugin supports both vector and raster data.

    **Vector data**

    A vector file (e.g., a `shapefile <https://en.wikipedia.org/wiki/Shapefile>`_ or `geopackage <https://www.geopackage.org/>`_) containing time series data can be visualized in InSAR Explorer. The file should have the following attributes:

    .. list-table::
       :header-rows: 1

       * - Field Name
         - Description
       * - ``velocity``, ``VEL``, or ``mean_velocity``
         - Or a similar field containing the InSAR velocity data.
       * - ``DYYYYMMDD`` or ``YYYYMMDD`` or ``D_YYYYMMDD``
         - Multiple fields for time series data, where ``YYYYMMDD`` is the date of the data, e.g., ``D20190101``, ``D20190201``, etc.
       * - ``Additional fields``
         - Optional fields for additional data, such as coherence, errors, etc.

    **Raster data**

    The plugin also supports raster data in `GMT GRD <https://docs.generic-mapping-tools.org/6.2/cookbook/features.html#grid-file-format-specifications>`_ format for specific time series outputs.
    For each time stamp, the plugin expects a separate raster file with the following naming convention: ``timeseries-YYYYMMDD*.grd`` or ``YYYYMMDD_*.grd``.
    The velocity file should be named ``vel_*.grd`` or ``velocity_*.grd``.

      .. code-block:: none

          -| timeseries files/
            -| vel_*.grd
            -| YYYYMMDD_*.grd
            -| YYYYMMDD_*.grd
            -| ...
            -| timeseries-YYYYMMDD*.grd
            -| timeseries-YYYYMMDD*.grd
            -| timeseries-YYYYMMDD*.grd
            -| ...

    Once one of the `grd` files is opened in QGIS, the plugin automatically detects the associated time series files and handles them accordingly.
