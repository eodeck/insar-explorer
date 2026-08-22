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
