import os
import sys
from copy import deepcopy
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import numpy as np
from ..external import pyqtgraph as pg
from qgis.PyQt.QtGui import QColor, QFont

from .model_fitting import FittingModels
from ..external.setting_manager_ui.json_settings import JsonSettings
from .export_plot import TimeSeriesPlotExporter
from .models.time_series import (
    TimeSeriesData,
    TimeSeriesGraphics,
    TimeSeriesSnapshot,
    TimeSeriesStyle,
    buildTimeSeriesData,
)

try:
    from .. import __version__
except ImportError:
    __version__ = "xx.xx.xx"


class FormattedDateAxisItem(pg.DateAxisItem):
    """Date axis that honors the user-configured strftime label format."""

    def __init__(self, *args, date_format=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.date_format = date_format

    def tickStrings(self, values, scale, spacing):
        if not self.date_format:
            return super().tickStrings(values, scale, spacing)

        labels = []
        for value in values:
            try:
                labels.append(datetime.fromtimestamp(value).strftime(self.date_format))
            except (OverflowError, OSError, ValueError, TypeError):
                labels.append("")
        return labels


class PlotTs():

    def __init__(self, ui):
        self.ui = ui
        self.ax = None
        self.dates = None
        self.ts_values = 0
        self.ref_values = 0
        self.plot_values = None
        self.plot_multiple_values = None
        self.min_plot_values = None
        self.max_plot_values = None
        self.residuals_values = None
        script_path = os.path.abspath(__file__)
        json_file = "config.json"
        self.config_file = os.path.join(os.path.dirname(script_path), 'config', json_file)
        self.series_history: List[TimeSeriesSnapshot] = []
        self.fit_models = []
        self.fit_seasonal_flag = False
        self.replicate_flag = False
        self.plot_y_axis = "from_data"
        self.replicate_value = 5.6 / 2
        self.ax_residuals = None
        self.plot_residuals_flag = False
        self.hold_on_flag = False
        self.random_marker_color_flag = False
        self.parms = {}
        self.updateSettings()
        self.coords = None
        self.ref_coords = None
        self._y_data_ranges = {}
        self._last_replica_y_data = []

    def modifySettings(self, block_key, value):
        params = JsonSettings(self.config_file)
        params.save(block_key, value)

    def updateSettings(self):
        parms_ts = JsonSettings(self.config_file)
        parms_ts.load("timeseries settings")

        parms = {}
        parms['title'] = parms_ts.get(["time series plot", "title"]) or ""
        parms['xlabel'] = parms_ts.get(["time series plot", "xlabel"]) or ""
        parms['ylabel'] = parms_ts.get(["time series plot", "ylabel"]) or ""
        parms['font size'] = parms_ts.get(["time series plot", "font size"]) or 12
        parms['marker'] = parms_ts.get(["time series plot", "marker"]) or "."
        parms['marker color'] = parms_ts.get(["time series plot", "marker color"]) or None
        parms['marker alpha'] = parms_ts.get(["time series plot", "marker alpha"]) or 1.0
        parms['marker edge color'] = parms_ts.get(["time series plot", "marker edge color"]) or None
        parms['marker size'] = parms_ts.get(["time series plot", "marker size"])
        parms['line style'] = parms_ts.get(["time series plot", "line style"]) or ''
        parms['line color'] = parms_ts.get(["time series plot", "line color"]) or None
        parms['line alpha'] = parms_ts.get(["time series plot", "line alpha"]) or 1.0
        parms['line width'] = parms_ts.get(["time series plot", "line width"]) or 1

        parms['series fill color'] = parms_ts.get(["time series plot", "series fill color"]) or 'blue'
        parms['series fill alpha'] = parms_ts.get(["time series plot", "series fill alpha"]) or 0.2
        parms['series line style'] = parms_ts.get(["time series plot", "series line style"]) or ''
        parms['series line color'] = parms_ts.get(["time series plot", "series line color"]) or None
        parms['series line alpha'] = parms_ts.get(["time series plot", "series line alpha"]) or 1.0
        parms['series line width'] = parms_ts.get(["time series plot", "series line width"]) or 0.2

        parms['ymin'] = parms_ts.get(["time series plot", "ymin"])
        parms['ymax'] = parms_ts.get(["time series plot", "ymax"])
        parms['grid'] = parms_ts.get(["time series plot", "grid"])
        parms['background color'] = parms_ts.get(["time series plot", "background color"]) or 'white'
        parms['date format'] = parms_ts.get(["time series plot", "date format"]) or None

        # replica
        parms['replica color 1'] = parms_ts.get(["time series plot", "replica color 1"]) or 'gray'
        parms['replica color 2'] = parms_ts.get(["time series plot", "replica color 2"]) or 'gray'
        parms['replica alpha'] = parms_ts.get(["time series plot", "replica alpha"]) or 1.0
        parms['replica marker size'] = parms_ts.get(["time series plot", "replica marker size"]) or 5
        parms['replica marker'] = parms_ts.get(["time series plot", "replica marker"]) or 'o'
        parms['number of up replicas'] = parms_ts.get(["time series plot", "number of up replicas"])
        parms['number of down replicas'] = parms_ts.get(["time series plot", "number of down replicas"])

        self.parms['time series plot'] = parms

        # figure settings
        parms = {}
        parms['background color'] = parms_ts.get(["figure", "background color"]) or 'white'

        self.parms['figure'] = parms

        # export settings
        parms = {}
        parms['dpi'] = parms_ts.get(["export", "dpi"]) or 300
        parms['aspect ratio'] = parms_ts.get(["export", "aspect ratio"]) or 4.0

        credit = parms_ts.get(["export", "credit"])
        parms['credit'] = credit if credit is not None else "Powered by InSAR Explorer"

        self.parms['export'] = parms

        # residual plot
        parms = {}
        parms['title'] = parms_ts.get(["residual plot", "title"]) or ""
        parms['xlabel'] = parms_ts.get(["residual plot", "xlabel"]) or ""
        parms['ylabel'] = parms_ts.get(["residual plot", "ylabel"]) or ""
        parms['marker'] = parms_ts.get(["residual plot", "marker"]) or "."
        parms['marker color'] = parms_ts.get(["residual plot", "marker color"]) or None
        parms['marker alpha'] = parms_ts.get(["residual plot", "marker alpha"]) or 1.0
        parms['marker edge color'] = parms_ts.get(["residual plot", "marker edge color"]) or None
        parms['marker size'] = parms_ts.get(["residual plot", "marker size"])
        parms['line style'] = parms_ts.get(["residual plot", "line style"]) or ''
        parms['line color'] = parms_ts.get(["residual plot", "line color"]) or None
        parms['line alpha'] = parms_ts.get(["residual plot", "line alpha"]) or 1.0
        parms['line width'] = parms_ts.get(["residual plot", "line width"])
        parms['ymin'] = parms_ts.get(["residual plot", "ymin"])
        parms['ymax'] = parms_ts.get(["residual plot", "ymax"])

        # other parameters from time series plot
        parms['grid'] = parms_ts.get(["time series plot", "grid"])
        parms['background color'] = parms_ts.get(["time series plot", "background color"]) or 'white'
        parms['font size'] = parms_ts.get(["time series plot", "font size"]) or 12
        parms['date format'] = parms_ts.get(["time series plot", "date format"]) or None
        self.parms['residual plot'] = parms

        # fit model
        parms = {}
        parms['line style'] = parms_ts.get(["model fit", "line style"]) or '--'
        parms['line color'] = parms_ts.get(["model fit", "line color"]) or 'black'
        parms['line alpha'] = parms_ts.get(["model fit", "line alpha"]) or 1.0
        parms['line width'] = parms_ts.get(["model fit", "line width"]) or 2.0
        self.parms['model fit'] = parms

    def clear(self):
        if not self.hold_on_flag:
            self._clearPlotWidget()
        self._draw()
        self.series_history = []
        self._set_current_series(None)

    def preparePlotValues(self):
        """Recompute plot values from the active arrays for compatibility callers."""
        series = buildTimeSeriesData(
            dates=self.dates,
            ts_values=self.ts_values,
            ref_values=self.ref_values,
            coords=self.coords,
            ref_coords=self.ref_coords,
        )
        self._set_current_series(series)

    def _buildTimeSeriesData(self, *, dates=None, ts_values=None, ref_values=None, coords=None, ref_coords=None) -> TimeSeriesData:
        if dates is None:
            dates = self.dates
        if ts_values is None:
            ts_values = self.ts_values
        if ref_values is None:
            ref_values = self.ref_values
        if coords is None:
            coords = self.coords
        if ref_coords is None:
            ref_coords = self.ref_coords
        if dates is None:
            raise ValueError("dates are required to build time-series data")
        return buildTimeSeriesData(
            dates=dates,
            ts_values=ts_values,
            ref_values=ref_values,
            coords=coords,
            ref_coords=ref_coords,
        )

    def _set_current_series(self, series: Optional[TimeSeriesData]):
        if series is None:
            self.dates = None
            self.ts_values = 0
            self.ref_values = 0
            self.plot_values = None
            self.plot_multiple_values = None
            self.min_plot_values = None
            self.max_plot_values = None
            self.residuals_values = None
            self.coords = None
            self.ref_coords = None
            return
        self.dates = series.dates
        self.ts_values = series.ts_values
        self.ref_values = series.ref_values
        self.plot_values = series.plot_values
        self.plot_multiple_values = series.plot_multiple_values
        self.min_plot_values = series.min_plot_values
        self.max_plot_values = series.max_plot_values
        self.residuals_values = series.residuals_values
        self.coords = series.coords
        self.ref_coords = series.ref_coords

    def initializeAxes(self):
        """
        Initialize the pyqtgraph plot items.
        :param update: bool
            If True, clear the latest plot.
        """
        if not self.hold_on_flag:
            self.series_history = []
            self._clearPlotWidget()

            if self.plot_residuals_flag:
                self.ax = self._addPlot(row=0)
                self.ax_residuals = self._addPlot(row=1)
                self.ax_residuals.setXLink(self.ax)
            else:
                self.ax = self._addPlot(row=0)
                self.ax_residuals = None
            return

        if self.plot_residuals_flag:
            if self.ax is None or self.ax_residuals is None:
                self._clearPlotWidget()
                self.ax = self._addPlot(row=0)
                self.ax_residuals = self._addPlot(row=1)
                self.ax_residuals.setXLink(self.ax)
        else:
            if self.ax is None or self.ax_residuals is not None:
                self._clearPlotWidget()
                self.ax = self._addPlot(row=0)
                self.ax_residuals = None

    def plotTs(self, *, dates=None, ts_values=None, ref_values=None, plot_multiple=True, coords=None, ref_coords=None,
               update=False):
        # update: flag indicating if the plot should be updated or a new one created

        self.updateSettings()

        if update:
            source_snapshot = self._remove_rendered_snapshot_for_update()
            if source_snapshot is None:
                return
            source_data = source_snapshot.data
            if dates is None:
                dates = source_data.dates
            if ts_values is None:
                ts_values = source_data.ts_values
            if ref_values is None:
                ref_values = source_data.ref_values
            if coords is None:
                coords = source_data.coords
            if ref_coords is None:
                ref_coords = source_data.ref_coords
            random_marker_color_flag = False
        else:
            random_marker_color_flag = self.random_marker_color_flag

        self.initializeAxes()

        # coords
        if ts_values is not None:
            self.coords = coords
        if ref_values is not None:
            self.ref_coords = ref_coords

        if dates is None and self.dates is None:
            return

        series = self._buildTimeSeriesData(
            dates=dates,
            ts_values=ts_values,
            ref_values=ref_values,
            coords=coords if coords is not None else self.coords,
            ref_coords=ref_coords if ref_coords is not None else self.ref_coords,
        )
        self._set_current_series(series)

        if self.dates is None:
            return

        if not series.hasFinitePlotValues():
            return

        if random_marker_color_flag:
            rand_color = np.random.rand(3, )
            self.parms['time series plot']['marker color'] = self.parms['time series plot']['line color'] = rand_color

        style = TimeSeriesStyle.fromParams(self.parms)
        items, residuals_values = self._render_time_series(series, style, plot_multiple=plot_multiple)
        if residuals_values is not None:
            series = series.withResiduals(residuals_values)
            self._set_current_series(series)
        snapshot = TimeSeriesSnapshot(data=series, style=style, graphics=items)
        self.add_series(snapshot)
        self._draw()

    def _render_time_series(self, series: TimeSeriesData, style: TimeSeriesStyle, *, plot_multiple=True) -> Tuple[TimeSeriesGraphics, Optional[np.ndarray]]:
        items = TimeSeriesGraphics()
        main_y_data = []
        parms = style.params['time series plot']
        marker = parms['marker']
        marker_size = parms['marker size']
        marker_color = parms['marker color']
        marker_alpha = parms['marker alpha']
        edge_color = parms['marker edge color']
        line_style = parms['line style']
        line_color = parms['line color']
        line_alpha = parms['line alpha']
        line_width = parms['line width']
        x = self._datesToX(series.dates)

        if plot_multiple and series.min_plot_values is not None:
            lower_bound = series.min_plot_values
            upper_bound = series.max_plot_values
            series_fill_color = parms['series fill color']
            series_fill_alpha = parms['series fill alpha']
            lower_line = pg.PlotCurveItem(x, lower_bound, pen=None)
            upper_line = pg.PlotCurveItem(x, upper_bound, pen=None)
            fill = pg.FillBetweenItem(
                lower_line,
                upper_line,
                brush=self._brush(series_fill_color, series_fill_alpha)
            )
            self.ax.addItem(lower_line)
            self.ax.addItem(upper_line)
            self.ax.addItem(fill)
            items.plot_multiple_fill = [lower_line, upper_line, fill]
            main_y_data.extend([lower_bound, upper_bound])

        if series.plot_multiple_values is not None:
            series_line_style = parms['series line style']
            series_line_color = parms['series line color']
            series_line_alpha = parms['series line alpha']
            series_line_width = parms['series line width']
            for i in range(series.plot_multiple_values.shape[1]):
                item = self.ax.plot(
                    x,
                    series.plot_multiple_values[:, i],
                    pen=self._pen(series_line_color, series_line_width, series_line_alpha, series_line_style)
                )
                items.plot_multiple_lines.append(item)
                main_y_data.append(series.plot_multiple_values[:, i])

        if marker_size > 0:
            items.scatter = pg.ScatterPlotItem(x=x, y=series.plot_values, symbol=self._symbol(marker),
                                               size=marker_size,
                                               pen=self._pen(edge_color, 0.2, marker_alpha),
                                               brush=self._brush(marker_color, marker_alpha))
            self.ax.addItem(items.scatter)

        main_y_data.append(series.plot_values)

        if line_style != '':
            items.line = self.ax.plot(
                x,
                series.plot_values,
                pen=self._pen(line_color, line_width, line_alpha, line_style))

        if self.replicate_flag:
            items.replicate_up, items.replicate_dn = self.plotReplicas(series, style)
        else:
            items.replicate_up, items.replicate_dn = [None], [None]

        main_y_data.extend(self._last_replica_y_data)
        self._last_replica_y_data = []
        items.main_y_data = main_y_data
        self.updateYlim(ax=self.ax, y_data=main_y_data)

        self.decoratePlot(parms=parms)
        items.fit_plot, residuals_values = self.fitModel(series, style, items)

        parms_figure = style.params['figure']
        self.decorateFigure(parms=parms_figure)
        return items, residuals_values

    def removeLastPlot(self, n=1, update=False):
        if update:
            snapshot = self._remove_rendered_snapshot_for_update()
            return snapshot is not None
        if len(self.series_history) < n:
            return False

        for _ in range(n):
            snapshot = self.remove_series()
            if snapshot is None:
                break
            self._remove_snapshot_graphics(snapshot)

        if self.series_history:
            restored_snapshot = self.series_history[-1]
            self._set_current_series(restored_snapshot.data)
            self.parms = deepcopy(restored_snapshot.style.params)
        else:
            self._set_current_series(None)

        self._rebuildYDataRanges()
        self._draw()
        return True

    def plotReplicas(self, series: TimeSeriesData, style: TimeSeriesStyle):
        parms = style.params['time series plot']
        x = self._datesToX(series.dates)
        marker_color_1 = parms['replica color 1']  # replica up
        marker_color_2 = parms['replica color 2']  # replica down
        marker_alpha = parms['replica alpha']
        marker_size_replica = parms['replica marker size']
        marker_replica = parms['replica marker']
        number_of_up_replicas = parms['number of up replicas']
        number_of_down_replicas = parms['number of down replicas']
        self._last_replica_y_data = []

        # plot multiple replicas
        replicate_up_list = []
        for i in range(number_of_up_replicas):
            replicate_value = self.replicate_value * (i + 1)

            if i % 2 == 0:
                marker_replica_color = marker_color_1
            else:
                marker_replica_color = marker_color_2

            replicate_up = pg.ScatterPlotItem(
                x=x,
                y=series.plot_values + replicate_value,
                symbol=self._symbol(marker_replica),
                size=marker_size_replica,
                pen=None,
                brush=self._brush(marker_replica_color, marker_alpha)
            )
            self.ax.addItem(replicate_up)
            replicate_up_list.append(replicate_up)
            self._last_replica_y_data.append(series.plot_values + replicate_value)

        replicate_dn_list = []
        for i in range(number_of_down_replicas):
            replicate_value = self.replicate_value * (i + 1)

            if i % 2 == 0:
                marker_replica_color = marker_color_2
            else:
                marker_replica_color = marker_color_1

            replicate_dn = pg.ScatterPlotItem(x=x, y=series.plot_values - replicate_value,
                                              symbol=self._symbol(marker_replica), size=marker_size_replica,
                                              pen=None,
                                              brush=self._brush(marker_replica_color, marker_alpha))
            self.ax.addItem(replicate_dn)
            replicate_dn_list.append(replicate_dn)
            self._last_replica_y_data.append(series.plot_values - replicate_value)

        return replicate_up_list, replicate_dn_list

    def fitModel(self, series: TimeSeriesData, style: TimeSeriesStyle, graphics=None):
        if series.plot_values is None:
            return None, None
        if series.dates is None:
            return None, None
        if not self.fit_models:
            return None, None

        parms = style.params['model fit']
        fit_line_type = parms['line style']
        fit_line_color = parms['line color']
        fit_line_alpha = parms['line alpha']
        fit_line_width = parms['line width']
        fit_seasonal = self.fit_seasonal_flag
        if len(self.fit_models) != 1:
            return None, None
        else:
            fit_model = self.fit_models[0]
            model_values, model_x, model_y = (
                FittingModels(series.dates, series.plot_values, model=fit_model).fit(seasonal=fit_seasonal))
            fit_plot = self.ax.plot(
                self._datesToX(model_x),
                model_y,
                pen=self._pen(fit_line_color, fit_line_width, fit_line_alpha, fit_line_type)
            )
            residuals_values = series.plot_values - model_values
            self.plotResiduals(series, style, graphics, residuals_values)
            self._draw()

        return fit_plot, residuals_values

    def plotResiduals(self, series: TimeSeriesData, style: TimeSeriesStyle, items=None, residuals_values=None):
        if items is None:
            items = TimeSeriesGraphics()
        if residuals_values is None:
            residuals_values = series.residuals_values
        if self.plot_residuals_flag and self.ax_residuals is not None and residuals_values is not None:
            parms = style.params['residual plot']
            marker = parms['marker']
            marker_size = parms['marker size']
            marker_color = parms['marker color']
            marker_alpha = parms['marker alpha']
            edge_color = parms['marker edge color']
            line_style = parms['line style']
            line_color = parms['line color']
            line_alpha = parms['line alpha']
            line_width = parms['line width']

            x = self._datesToX(series.dates)
            marker_size = marker_size or 0
            if marker_size > 0:
                items.residual_scatter = pg.ScatterPlotItem(
                    x=x,
                    y=residuals_values,
                    symbol=self._symbol(marker),
                    size=marker_size,
                    pen=self._pen(edge_color, 0.2, marker_alpha),
                    brush=self._brush(marker_color, marker_alpha)
                )
                self.ax_residuals.addItem(items.residual_scatter)
            if line_style:
                items.residual_line = self.ax_residuals.plot(
                    x,
                    residuals_values,
                    pen=self._pen(line_color, line_width, line_alpha, line_style)
                )
            items.residual_y_data = [residuals_values]
            self.updateYlim(ax=self.ax_residuals, y_data=items.residual_y_data)
            self.decoratePlot(ax=self.ax_residuals, parms=parms)
            self._draw()


    def decorateFigure(self, parms={}):
        self.setFigureStyle(parms=parms)

    def decoratePlot(self, ax=None, parms={}):
        if not ax:
            ax = self.ax
        # First set lims then ticks
        self.setFontSize(ax=ax, parms=parms)
        self.setXlims(ax=ax)
        self.setXticks(ax=ax, parms=parms)
        self.setYlims(ax=ax, parms=parms)
        self.setGrid(ax=ax, parms=parms)
        self.setLabels(ax=ax, parms=parms)
        self.setAxisStyle(ax=ax, parms=parms)

    def setFontSize(self, ax=None, parms={}):
        if not ax:
            ax = self.ax
        font_size = parms['font size']
        font = QFont()
        font.setPointSize(int(font_size))
        for axis_name in ('left', 'bottom'):
            ax.getAxis(axis_name).setTickFont(font)

    def setGrid(self, ax=None, parms={}):
        if not ax:
            ax = self.ax
        grid_type = parms['grid']
        ax.showGrid(x=grid_type in ('vertical', 'both'), y=grid_type in ('horizontal', 'both'), alpha=0.25)

    def setLabels(self, ax=None, parms={}):
        if not ax:
            ax = self.ax

        font_size = f"{int(parms['font size'])}pt"
        if parms['title'] != "":
            ax.setTitle(parms['title'], size=font_size)
        if parms['xlabel'] != "":
            ax.setLabel('bottom', parms['xlabel'], **{'font-size': font_size})
        if parms['ylabel'] != "":
            ax.setLabel('left', parms['ylabel'], **{'font-size': font_size})


    def setXticks(self, ax=None, parms={}):
        if not ax:
            ax = self.ax
        self._applyDateFormat(ax=ax, parms=parms)


    def setXlims(self, *, ax=None, use_data_xlim=True, padding=30):
        """
        Set the x-axis limits.

        :param use_data_xlim: bool
            If True, set the x-axis limits to the min and max of the data.
            If False, set the x-axis limits to the start and end of the year.
        :param padding: int
            Number of days to pad the x-axis limits.
        """
        if not ax:
            ax = self.ax
        min_date = np.nanmin(self.dates)
        max_date = np.nanmax(self.dates)

        if use_data_xlim:
            x_min = self._dateToX(min_date - timedelta(days=padding))
            x_max = self._dateToX(max_date + timedelta(days=padding))
        else:
            x_min = self._dateToX(datetime(min_date.year, 1, 1))
            x_max = self._dateToX(datetime(max_date.year + 1, 1, 1))
        ax.setXRange(x_min, x_max, padding=0)

    def updateYlim(self, *, ax=None, y_data):
        if not ax:
            ax = self.ax
        data_range = self._finiteRange(y_data)
        if data_range is None:
            return

        key = id(ax)
        current = self._y_data_ranges.get(key)
        if current is None:
            y_min, y_max = data_range
        else:
            y_min = min(current[0], data_range[0])
            y_max = max(current[1], data_range[1])
        self._y_data_ranges[key] = (y_min, y_max)
        if y_min == y_max:
            y_min -= 1
            y_max += 1
        ax.setYRange(y_min, y_max, padding=0.05)

    def setYlims(self, ax=None, parms={}):
        if not ax:
            ax = self.ax

        # get min/max from axis
        y_min, y_max = self._y_data_ranges.get(id(ax), ax.viewRange()[1])
        if self.plot_y_axis != "from_data":
            y_max = np.abs([y_min, y_max]).max()
            y_min = -y_max

        if self.plot_y_axis == "adaptive":
            y_range = y_max - y_min
            y_min_rounded = -5
            y_max_rounded = 5
            for i in [10000, 1000, 100, 10]:
                if y_range >= i:
                    y_min_rounded = np.floor(y_min / i) * i
                    y_max_rounded = np.ceil(y_max / i) * i
                    break

            y_min = np.min([y_min_rounded, -5])
            y_max = np.max([y_max_rounded, 5])

        ymin = parms['ymin'] if parms['ymin'] is not None else y_min
        ymax = parms['ymax'] if parms['ymax'] is not None else y_max
        if ymin == ymax:
            ymin -= 1
            ymax += 1
        ax.setYRange(ymin, ymax, padding=0.05)

    def setAxisStyle(self, ax=None, parms={}):
        if not ax:
            ax = self.ax
        background_color = self._color(parms['background color'])
        ax.getViewBox().setBackgroundColor(background_color)
        self._applyDateFormat(ax=ax, parms=parms)

    def setFigureStyle(self, parms={}):
        background_color = self._color(parms['background color'])
        self.ui.plot_widget.setBackground(background_color)

    def savePlotAsImage(self, filename=None):
        TimeSeriesPlotExporter(self).export(filename)

    def _addPlot(self, row=0):
        axis = FormattedDateAxisItem(orientation='bottom', date_format=self.parms['time series plot'].get('date format'))
        plot_item = self.ui.plot_widget.addPlot(row=row, col=0, axisItems={'bottom': axis})
        self._stylePlotFrame(plot_item)
        self._connectAutoButton(plot_item)
        plot_item.showButtons()
        self.ui.plot_widget.plot_items.append(plot_item)
        return plot_item

    def _connectAutoButton(self, plot_item):
        auto_button = getattr(plot_item, 'autoBtn', None)
        if auto_button is None:
            return
        try:
            auto_button.clicked.disconnect(plot_item.autoBtnClicked)
        except (TypeError, RuntimeError):
            pass
        auto_button.clicked.connect(lambda *args, plot_item=plot_item: self._resetPlotView(plot_item))

    def _resetPlotView(self, plot_item):
        if self.dates is None:
            return

        self.updateSettings()
        if self.ax is not None:
            self.setXlims(ax=self.ax)

        if plot_item is self.ax_residuals:
            self.setYlims(ax=self.ax_residuals, parms=self.parms['residual plot'])
        else:
            self.setYlims(ax=self.ax, parms=self.parms['time series plot'])

        auto_button = getattr(plot_item, 'autoBtn', None)
        if auto_button is not None:
            auto_button.hide()
        self._draw()

    def _stylePlotFrame(self, plot_item):
        plot_item.showAxis('top')
        plot_item.showAxis('right')
        for name in ('left', 'bottom', 'top', 'right'):
            axis = plot_item.getAxis(name)
            axis.setPen(pg.mkPen('k', width=1))
            axis.setTextPen(pg.mkPen('k'))
        for name in ('top', 'right'):
            axis = plot_item.getAxis(name)
            axis.setStyle(showValues=False)
            axis.setTicks([])

    def _clearPlotWidget(self):
        self.ui.plot_widget.clear()
        self.ui.plot_widget.plot_items = []
        self.ax = None
        self.ax_residuals = None
        self._y_data_ranges = {}
        self._last_replica_y_data = []

    def _draw(self):
        self.ui.plot_widget.update()

    def _removeItem(self, ax, item):
        if ax is not None and item is not None:
            try:
                ax.removeItem(item)
            except (ValueError, RuntimeError):
                pass

    def _finiteRange(self, y_data):
        arrays = y_data if isinstance(y_data, (list, tuple)) else [y_data]
        finite_values = []
        for values in arrays:
            if values is None:
                continue
            array = np.asarray(values, dtype=float).ravel()
            finite = array[np.isfinite(array)]
            if finite.size:
                finite_values.append(finite)
        if not finite_values:
            return None
        merged = np.concatenate(finite_values)
        return float(np.nanmin(merged)), float(np.nanmax(merged))

    def _remove_rendered_snapshot_for_update(self):
        """Remove graphics for the active snapshot and return it for settings-driven re-rendering.

        Unlike user-driven remove-last, settings-driven update must preserve the
        freshly loaded settings in ``self.parms`` so the active/latest series is
        re-rendered with the new style. Restoring the previous snapshot style
        here makes settings changes apply only to future plots when hold-on mode
        contains multiple series.
        """
        snapshot = self.remove_series()
        if snapshot is None:
            return None
        self._remove_snapshot_graphics(snapshot)
        if self.series_history:
            self._set_current_series(self.series_history[-1].data)
        else:
            self._set_current_series(snapshot.data)
        self._rebuildYDataRanges()
        self._draw()
        return snapshot

    def _remove_snapshot_graphics(self, snapshot):
        """Remove all plot items owned by a stored time-series snapshot."""
        graphics = snapshot.graphics
        for item in (graphics.scatter, graphics.line, graphics.fit_plot):
            self._removeItem(self.ax, item)
        for item in (graphics.residual_scatter, graphics.residual_line):
            self._removeItem(self.ax_residuals, item)
        for item_list in (graphics.plot_multiple_fill, graphics.plot_multiple_lines,
                          graphics.replicate_up, graphics.replicate_dn):
            for item in item_list or []:
                self._removeItem(self.ax, item)

    def _rebuildYDataRanges(self):
        self._y_data_ranges = {}
        for snapshot in self.series_history:
            self.updateYlim(ax=self.ax, y_data=snapshot.graphics.main_y_data)
        if self.ax_residuals is not None:
            for snapshot in self.series_history:
                self.updateYlim(ax=self.ax_residuals, y_data=snapshot.graphics.residual_y_data)

    def _applyDateFormat(self, ax=None, parms={}):
        if ax is None:
            ax = self.ax
        axis = ax.getAxis('bottom')
        if isinstance(axis, FormattedDateAxisItem):
            axis.date_format = parms.get('date format')

    def _dateToX(self, value):
        if isinstance(value, np.datetime64):
            value = value.astype('datetime64[ms]').astype(datetime)
        return value.timestamp()

    def _datesToX(self, values):
        return np.array([self._dateToX(value) for value in values], dtype=float)

    def _symbol(self, marker):
        return {
            '.': 'o', ',': 'o', 'o': 'o', 's': 's', '^': 't1', 'v': 't', '<': 't3', '>': 't2',
            '+': '+', 'x': 'x', 'd': 'd', 'D': 'd', '*': 'star', 'p': 'p', 'h': 'h'
        }.get(marker, 'o')

    def _color(self, color, alpha=1.0):
        if color is None:
            color = 'black'
        if isinstance(color, np.ndarray):
            color = color.tolist()
        if isinstance(color, (list, tuple)):
            values = [float(c) for c in color]
            if max(values) <= 1.0:
                values = [int(c * 255) for c in values]
            if len(values) == 3:
                values.append(int(alpha * 255))
            return QColor(*values)
        qcolor = QColor(color)
        qcolor.setAlphaF(float(alpha))
        return qcolor

    def _pen(self, color=None, width=1, alpha=1.0, line_style='-'):
        if color is None:
            color = 'black'
        pen = pg.mkPen(self._color(color, alpha), width=width or 1)
        if line_style in ('--', ':', '-.'):
            from .qt_compat import PEN_STYLE_BY_NAME
            styles = PEN_STYLE_BY_NAME
            pen.setStyle(styles[line_style])
        return pen

    def _brush(self, color=None, alpha=1.0):
        return pg.mkBrush(self._color(color, alpha))

    def add_series(self, snapshot: TimeSeriesSnapshot) -> None:
        """Store a plotted time-series snapshot."""
        self.series_history.append(snapshot)

    def current_series(self) -> Optional[TimeSeriesSnapshot]:
        """Return the active stored time-series snapshot, if available."""
        if self.series_history:
            return self.series_history[-1]
        return None

    def remove_series(self, index: int = -1) -> Optional[TimeSeriesSnapshot]:
        """Remove and return a plotted time-series snapshot."""
        if not self.series_history:
            return None
        return self.series_history.pop(index)

    def _dateStrings(self):
        date_strings = []
        for d in self.dates:
            date_strings.append(d.strftime('%Y-%m-%d'))
        return date_strings

    def exportAscii(self, filename=None):
        if filename is None:
            return
        snapshot = self.current_series()
        series = snapshot.data if snapshot is not None else None
        if series is None:
            if self.dates is None or self.plot_values is None:
                return
            series = self._buildTimeSeriesData(dates=self.dates, ts_values=self.ts_values, ref_values=self.ref_values,
                                               coords=self.coords, ref_coords=self.ref_coords)
        if series.dates is None or series.plot_values is None:
            return

        data_to_save = np.column_stack((series.dateStrings(), series.plot_values))

        coords = series.coords
        ref_coords = series.ref_coords

        separator = "\n*********************************************************************************************\n"
        header_lines = [separator]
        header_lines.append(f"InSAR Explorer (v{__version__}) - Time Series Export\n")
        header_lines.append("This file contains a time series produced with InSAR Explorer. InSAR Explorer is a free "
                            "QGIS \nplugin for interactive visualization and analysis of InSAR time-series. "
                            "Visit the project website \nfor installation, documentation, license, and examples: "
                            "https://insar-explorer.eodeck.com/\n"
                            "If you use InSAR Explorer, please cite the paper: "
                            "https://doi.org/10.1109/IGARSS55030.2025.11313961")
        header_lines.append(separator)

        # we either have point or polygons.
        coords_type = "polygon" if hasattr(coords, "geom") else "point"
        ref_coords_type = "polygon" if hasattr(ref_coords, "geom") else "point"
        wgs84 = "CRS=EPSG:4326"

        header_lines.append("Layer CRS\n")
        header_lines.append(f"Time series {coords_type}:")
        header_lines.append(f"{coords.crs_str() if coords else 'None'}")
        header_lines.append(f"{coords.as_wkt() if coords else 'None'}\n")
        header_lines.append(f"Reference {ref_coords_type}:")
        header_lines.append(f"{ref_coords.crs_str() if ref_coords else 'None'}")
        header_lines.append(f"{ref_coords.as_wkt() if ref_coords else 'None'}")

        header_lines.append(separator)
        header_lines.append("WGS84 Lon/Lat\n")
        header_lines.append(f"Time series {coords_type}:")
        header_lines.append(f"{wgs84 if coords else 'None'}")
        header_lines.append(f"{coords.as_wkt_wgs84() if coords else 'None'}\n")
        header_lines.append(f"Reference {ref_coords_type}:")
        header_lines.append(f"{wgs84 if ref_coords else 'None'}")
        header_lines.append(f"{ref_coords.as_wkt_wgs84() if ref_coords else 'None'}")
        header_lines.append(separator)

        header_lines.append("Time series data\n")
        header_lines.append("date, ts_value")

        header = "\n".join(header_lines)
        np.savetxt(filename, data_to_save, fmt="%s", delimiter=",", header=header, comments="# ")
