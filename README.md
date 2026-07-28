![InSAR Explorer](icon.png)

# InSAR Explorer

## Description
InSAR Explorer is a QGIS plugin that allows for dynamic visualization and analysis of InSAR time series data. It was originally developed to visualize outputs of [SARvey](https://github.com/luhipi/sarvey), but has since been expanded to support [MintPy](https://github.com/insarlab/MintPy), [MiaplPy](https://github.com/insarlab/MiaplPy), [GMTSAR](https://topex.ucsd.edu/gmtsar/), [SARscape](https://www.sarmap.ch/index.php/software/sarscape/) and [EGMS products](https://egms.land.copernicus.eu/).
Check the full [documentation](https://insar-explorer.eodeck.com) for a list of all supported software and instructions on how to create the required input data.

## How to use
### Install the plugin
Install InSAR Explorer. You can install the plugin from the QGIS Plugin Repository. Search for `InSAR Explorer` in the QGIS Plugin Manager and click `Install`.
More information about different installation methods can be found [here](https://insar-explorer.eodeck.com/en/latest/#installation).

### Prepare time series data
Prepare the time series data as a vector or raster file in the [required format](https://insar-explorer.eodeck.com/en/latest/#data-structure).
You can prepare the data using [different software](https://insar-explorer.eodeck.com/en/latest/#data-preparation).
You can use the sample data provided [here](https://insar-explorer.eodeck.com/en/latest/readme.html#sample-data) for testing the plugin.

### Use the plugin to plot time series
Open a vector or raster layer with InSAR time series data in QGIS. Open the plugin and click on any point in the map to display the time series data.
More information [here](https://insar-explorer.eodeck.com/en/latest/readme.html#usage)

## Contributing
We welcome contributions to the project. Please follow the guidelines [here](https://insar-explorer.eodeck.com/en/latest/readme.html#contributing).

## License
This plugin is licensed under the GPL-3.0 license. See the [LICENSE](https://insar-explorer.eodeck.com/en/latest/readme.html#license) file for more details. 
If you use InSAR Explorer in your research, please cite the following paper:

- M. H. Haghighi et al., “SARvey and InSAR Explorer: Open-source tools for InSAR data processing and visualization,” in Proc. 2025 IEEE Int. Geosci. Remote Sens. Symp. (IGARSS), Brisbane, Australia, 2025, pp. 9414–9417. [doi: 10.1109/IGARSS55030.2025.11313961](https://ieeexplore.ieee.org/abstract/document/11313961)

To cite a specific version of InSAR Explorer, you can use the DOI available in the  
[InSAR Explorer Zenodo repository](https://doi.org/10.5281/zenodo.14052813)

This project relies on several third-party libraries, and their licenses can be found in the [external_licenses/](https://github.com/eodeck/insar-explorer/tree/main/external_licenses) directory.

## Authors
[Mahmud Haghighi](https://github.com/mahmud1)

## Contributors
[Andreas Piter](https://github.com/Andreas-Piter),
[Erik Rivas](https://github.com/esrivas17)

## Contact
For any questions or issues, please create an issue on the GitHub repository.
