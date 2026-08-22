![InSAR Explorer](icon.png)

# InSAR Explorer

## Description
InSAR Explorer is a QGIS plugin for interactive visualization and analysis of InSAR time-series data. It supports the documented preparation workflows for [SARvey](https://github.com/luhipi/sarvey), [MintPy](https://github.com/insarlab/MintPy), [MiaplPy](https://github.com/insarlab/MiaplPy), [GMTSAR](https://topex.ucsd.edu/gmtsar/), [SARscape](https://www.sarmap.ch/index.php/software/sarscape/), and [EGMS](https://egms.land.copernicus.eu/).
Check the full [documentation](https://insar-explorer.eodeck.com) for supported data formats and preparation instructions.

## How to use
### Install the plugin
Install InSAR Explorer from the QGIS Plugin Repository. Search for `InSAR Explorer` in the QGIS Plugin Manager and click `Install`.
More information about installation methods is available in the [documentation](https://insar-explorer.eodeck.com/en/latest/#installation).

### Prepare time-series data
Prepare the time-series data as a supported vector or raster layer in the [required format](https://insar-explorer.eodeck.com/en/latest/#data-structure).
Preparation instructions are available for the [documented processing workflows](https://insar-explorer.eodeck.com/en/latest/#data-preparation).
Sample data are available from the [documentation](https://insar-explorer.eodeck.com/en/latest/#sample-data).

### Explore time series
Open a supported vector or raster InSAR layer, launch InSAR Explorer, and use the Target/Reference selection tools to interactively inspect time series. Selected time series can be retained and compared, styled, fitted, and exported.
See the full [usage documentation](https://insar-explorer.eodeck.com/en/latest/#usage) for the current workflow.

## Contributing
We welcome contributions to the project. Please follow the guidelines in the [documentation](https://insar-explorer.eodeck.com/en/latest/#contributing).

## License
This plugin is licensed under the GPL-3.0 license. See the [LICENSE](https://github.com/eodeck/insar-explorer/blob/main/LICENSE) file for more details.

If you use InSAR Explorer, please cite the following paper:

- M. H. Haghighi et al., “SARvey and InSAR Explorer: Open-source tools for InSAR data processing and visualization,” in Proc. 2025 IEEE Int. Geosci. Remote Sens. Symp. (IGARSS), Brisbane, Australia, 2025, pp. 9414–9417. [doi: 10.1109/IGARSS55030.2025.11313961](https://ieeexplore.ieee.org/abstract/document/11313961)

To refer to a specific version of InSAR Explorer, use the [Zenodo DOI](https://doi.org/10.5281/zenodo.14052813).

This project relies on several third-party libraries, and their licenses can be found in the [external_licenses/](https://github.com/eodeck/insar-explorer/tree/main/external_licenses) directory.

## Authors
[Mahmud Haghighi](https://github.com/mahmud1)

## Contributors
[Andreas Piter](https://github.com/Andreas-Piter),
[Erik Rivas](https://github.com/esrivas17)

## Contact
For any questions or issues, please create an issue on the [GitHub issue tracker](https://github.com/eodeck/insar-explorer/issues).
