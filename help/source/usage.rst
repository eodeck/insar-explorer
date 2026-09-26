Usage
*****

Open InSAR Explorer
===================

Open a supported vector or raster InSAR time-series layer in QGIS, then click
the InSAR Explorer toolbar icon or choose ``Plugins > InSAR Explorer``.

Configure the map
=================

Use **Map Settings** to choose the map field and configure how InSAR values are
visualized. The panel provides the display range, colormap, and related
symbology controls. Apply the settings when you want the map styling to update.
Use live apply when immediate updates are preferred.

Select time series
==================

Target point
------------

Use the **Target** point tool in **Selection**, then click the map to create a
pending time series. Review the pending selection and add it to **Selections**
when you want to retain it for comparison.

Reference point
---------------

Use the **Reference** point tool to select a reference area. The reference
can be reset from the Selection panel.

Polygon selection where supported
---------------------------------

For supported vector layers, use the Target or Reference polygon tools to work
with an area rather than a single point. Click to add vertices and finish the
polygon with a double-click or right-click.

Work with selected time series
==============================

Time-series list
----------------

Added time series remain in **Selections**, allowing multiple series to be
retained and compared while you work with other layers or create another
pending selection. Select one or more rows to use actions that apply to stored
time series.

Rename, remove, and copy settings
---------------------------------

Use the selection list controls or context menu to rename or remove stored time
series. Settings can be copied from one time series and pasted as Style, Fit,
Replica, or all presentation settings.

Configure the plot
==================

Appearance
----------

Use **Plot style** for the current time-series style and **Appearance** for
plot-level presentation. The time-series toolbar also provides X- and Y-range
controls for fitting the displayed range or using configured manual ranges.

Labels
------

Use the **Labels** split button to show or hide plot legends. Its arrow opens
the Labels popup, which has **General** and **Entries** tabs. **General**
controls legend placement, background opacity, and legend text size.
**Match Appearance text size** is enabled by default; when it is disabled, you
can choose a custom legend text size. **Entries** controls Fit, Replica, and
Ensemble legend inclusion, together with their prefixes and suffixes. Base
time-series and residual samples show both their marker and line when both are
enabled. Ensemble entries show their rendered member line and/or spread band.
Legends show only currently visible time series. Residual labels appear in the
residual plot when it is displayed. Main and residual legends use the configured
text size and opacity in the plot and in exported SVG and PNG figures.

Labels defaults
~~~~~~~~~~~~~~~

Labels edits apply to the current plot immediately. Each tab has its own
**Defaults** menu. **Default**, **Factory default**, and **Set as default**
apply only to settings in that tab; editing a setting alone does not change the
saved default. The Labels toolbar enable/disable button is independent and is
not changed by Defaults actions in either tab.

Fit
---

Use **Fit** to enable a fitted model for the current time series. The Fit menu
selects the model and opens Fit settings, including fit and residual appearance.
Residual display is available through the Fit controls when applicable.

Replica
-------

Use **Replica** to toggle replicas for the current time series. Open
**Replica settings** from the split-button arrow to configure replica behavior
and appearance.

Export
======

Plot export
-----------

Use **Export plot** in the time-series toolbar to save the current plot. The
adjacent export-settings control configures plot-export options.

Time-series data export
-----------------------

Select one or more stored time series in **Selections** and use **Export data**
to export their time-series values.
