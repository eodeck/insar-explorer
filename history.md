### History

v2.8.0
- Support exporting one or multiple time series data.
- Added an offset-reset button.
- Improve reference offset behavior and apply only when user explicitly clicks on apply or live apply is active.
- Added support for continuous colormaps.
- Added fast calculation mode for field statistics.
- Simplified map settings panel.
- Move symbology controls into popup.
- Used Turbo instead of reversed Turbo in colormaps.
- Improved field search and filtering.
- Recompute derived ranges on field/layer change.
- Allow adaptive precision in data range spinboxes.
- Enhanced map settings panel.
- Added distinct color assignment to record list context menu.
- Added time series rename actions using F2 and context menu.
- Added map indicator settings popup.
- Added map indicator for selected record.
- Added copy/paste button/context menu for time series record list.
- Added remove button/context menu to remove records from the time series record list.
- Added time series record list.
- Retire hold on options and TS and Settings tabs.
- Move sync offset button to the map settings panel.
- Added pending time series selection to the time series selection panel.
- Introduced time series selection panel

v2.7.1
- Removed false QGIS 4 persistence warnings for Fit and Replica settings.
- Fixed Fit statistics refresh when enabling or updating Fit.
- Restored reference-point persistence across new time-series selections.

v2.7.0
- Introduced an immutable TimeSeriesRecord domain model and centralized TimeSeriesStore.
- Decoupled rendering, controller, persistence, and analysis responsibilities.
- Migrated user preferences to QSettings and retired configuration through config.json .
- Added persistent analysis defaults for newly created time series.
- Report r2 and rmse in status bar.
- Update exponential model icon.
- Add logarithm model fitting.
- Fix exponential fit: remove fallback to linear and report failure. 
- Fix time series plot to align year labels to calendar boundaries.
- Move plot settings to time series toolbar.
- Move replica to time series toolbar.
- Move fit curve to time series toolbar.
- Move time series setting and exports to time series toolbar.

v2.6.0
- Transfer the repo to eodeck.

v2.5.0
- Support for Qt6 for compatibility with QGIS 4.
- Remove "." from marker options.
- Refactor time-series state management in backend.

v2.4.0
- Add credit text to exports.
- Remember the last export directory and format.
- Fix missing polygon time series fill.
- Fix incorrect plot scaling in SVG export.

v2.3.0
- Remove pdf and jpeg from the list of supported export formats.
- Add Aspect ratio for plot export.
- Add a tab for fit model style in settings.
- Migrate from Matplotlib to PyQtGraph for time series plotting.

v2.2.0
- Improve grd file handling.
- Update reference paper details.
- Centralize version and date in project init.
- Show a list of available formats for saving time series plot.
- Add push button to export time series as ascii file.

v2.1.1
- Disable automatic symbology application when opening the plugin.
- Update tooltips of GUI elements.

v2.1.0
- Add opacity setting for time series plots.
- Enhance UI.
- Make the colormap in the UI larger.
- Reverse Turbo default colormap to have red for low and blue for high values.
- Set default checked for applying symbology on the fly.
- Fix: reverse colorbar in UI.
- Fix: hold on plot on windows.
- Enable hold on plots for polygons.
- Fix: resolved error during time series curve fitting.

v2.0.0
- Fix: Sort time series data by date before plotting.
- Introduce new time series setting in the UI.
- Add Settings Panel for managing time series settings.
- Add citation information.
- Add status bar messages for different UI components.
- Enhance status bar updates by a signal-based mechanism.
- Fix: remove old clicked points, so they do not reappear after changing CSR.
- Check the selected layer and deactivate plugin if the layer is not compatible with InSAR Explorer.
- Add support for polygon selection for vector data.
- Change the reference point for the map on the fly.
- Enhance labeling of the map plot
- Enhance curve fitting by a prior normalizing of dates.

v1.0.0
- Sync colorbar icon with reverse button
- Disable log
- Update documentation for SARscape and MintPy support.
- Add a menubar for selecting data range
- Support MintPy time series data created via save_explorer command
- Removed default ylabe units from time series plot to avoid confusion for data from different sources
- Enhance display of icons to differentiate between checkable and non-checkable buttons
- Add about dialog
- New icon designs for the plugin
- New icon for symbology and add icon for live symbology 
- Add gray to the list of colormaps
- Handle NULL values in time series data
- Add different options to control y-axis limits
- Make field selector editable to improve user experience
- Ignore non-numerical fields in the field selector
- A hold-on button to keep the plot after selecting a new point
- Keep the time series plot when layer changed
- New icon for residual plot button

v0.8.0
- Allow D_YYYYMMDD time series date format
- Add combobox to select field for visualization
- Change Groupbox name: Range to Value
- Add linting to improve code readability, consistency, and maintainability.
- Upgrade to SettingsManagerUI v0.5.0
- Move external libraries to `external` folder.


v0.7.0
- Read settings from a JSON file
- Integrate SettingsManagerUI for managing settings
- Add setting button to the time series tab

v0.6.1
- Fix bug in initial import
- Fix bugs in icon
- Correct link to documentation


v0.6.0
- Add support for EGMS products.
- Add support for GMTSAR grd time series.
- Reset parameters after layer change.


v0.5.0
- Add toolbar to time series plot for zooming, panning, etc.
- Add push buttons for getting map symbology range from data
- Resurface the gui with a new design.
- Check layer validity before plotting.

v0.4.0
- Add save button for time series plot supporting png, jpg, pdf, svg.
- Set Y-axis ticks adaptively based on the data range.
- Enhance the style of the time series plot.
- Add support for MintPy and MiaplPy software.
- Introduce a new website theme.