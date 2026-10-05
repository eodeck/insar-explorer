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
time series. The **Y** column shows whether each stored time series is assigned
to the Left or Right Y axis using the corresponding axis icon. The icon is
informational; change the assignment with **Y axis** in the time-series toolbar.

Rename, remove, and copy settings
---------------------------------

Use the selection list controls or context menu to rename or remove stored time
series. Settings can be copied from one time series and pasted as **Style**,
**Fit**, **Replica**, **Y axis,**, **Legend entry**, or **All** presentation settings.

Configure the plot
==================

Appearance
----------

The time-series toolbar separates per-series controls from plot-level controls.
Use **Style**, **Fit**, **Replica**, **Y axis**, and **Legend entry** for the
selected or pending time series. Use **Plot legend**, **X range**, **Y range**,
**Appearance**, and **Export** for the plot as a whole.

Appearance also provides independent labels for **Main left Y**, **Main right Y**,
**Residual left Y**, and **Residual right Y**. A label for an inactive axis is
preserved and appears again when that axis becomes active.

Style
-----

Use **Style** to configure the appearance of the selected or pending time
series.

Legend entry
------------

Use **Legend entry** to edit the text and related legend entries for the
selected or pending time series.

Main
~~~~

The **Main** tab controls the text used for the primary series legend entry.
Use **Include label** to include the series label. Point series can also use
**Include field** and select a **Field** value to include in the legend, then
use **Prefix** and **Suffix** to format it. Polygon and raster-like series
without usable fields use the series label only. When relevant, target/reference
series can include both target and reference field values. **Preview** shows the
text that will appear in the legend. Use **Defaults** to manage the saved Main
settings for future series.

Related
~~~~~~~

The **Related** tab controls whether associated **Fit**, **Replica**, and
**Ensemble** graphics contribute their own legend entries. When **Use label
only** is unchecked, related entries use the fully formatted Main legend text
where applicable, such as ``Point 2 · vel: -4.6 mm/yr fit``. When it is
checked, they use only the base series label, such as ``Point 2 fit``. Use
**Defaults** to manage the saved Related settings for future series.

Plot legend
-----------

Use **Plot legend** for the global presentation of plot legends. It controls
whether a legend is shown, its location, text size, whether it matches the plot
text size, and its background opacity. Use **Defaults** to manage these
plot-level settings. **Legend entry** controls per-series legend content;
**Plot legend** controls the presentation and layout of the overall legend.

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

Y axis
------

Use **Y axis** to assign the selected or pending time series to the **Left axis**
or **Right axis**. The toolbar button shows the current assignment as an icon.
The assignment applies to the complete time-series presentation, including its
main series, Fit, Replica, Ensemble, and residual graphics where applicable.

New time series start on the Left axis. A pending time series can be moved to
the Right axis before it is added to **Selections**. For example, assign one
time series to the Left axis and another to the Right axis when they have
different value ranges but should be compared over the same time interval.

Y range
-------

Use **Y range** to control the vertical range of the time-series and residual
plots. Left and Right Y axes keep independent ranges. Available modes include
**Data range**, **Symmetric**, and **Manual**. Manual ranges are remembered
separately for **Main left Y**, **Main right Y**, **Residual left Y**, and
**Residual right Y**.

When a saved Manual range exists for an active axis, choosing **Manual**
restores that range. If no active axis has a saved Manual range yet, the range
editor opens. If only some active axes have saved Manual ranges, those axes
switch to their saved Manual ranges while unconfigured axes keep their current
range mode.

When both Left and Right axes are visible, plot-body pan and zoom keep the two
scales visually synchronized while preserving their independent numeric
ranges.

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
