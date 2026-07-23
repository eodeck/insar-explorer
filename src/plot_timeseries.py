import calendar
import os
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, time, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np
from ..external import pyqtgraph as pg
from qgis.PyQt.QtGui import QColor, QFont

from .model_fitting import calculateFitStatistics, FittingModels, ModelFitError
from .export_plot import TimeSeriesPlotExporter
from .time_series.settings.model import AxisManualRange, ResidualStyleSettings
from .time_series.y_axis_range import (
    resolve_manual_y_range, resolve_y_axis_display_range,
)
from .time_series.settings.persistence import TimeSeriesSettingsPersistence, build_legacy_plot_params
from .time_series.fit_style_controller import FitStyle
from .models.time_series import (
    TimeSeriesData,
    TimeSeriesGraphics,
    TimeSeriesRecord,
    TimeSeriesSnapshot,
    DefaultTimeSeriesStyle,
    TimeSeriesStyle,
    buildTimeSeriesData,
    randomTimeSeriesColor,
)

try:
    from .. import __version__
except ImportError:
    __version__ = "xx.xx.xx"


class FormattedDateAxisItem(pg.DateAxisItem):
    """Date axis that honors the configured label format and calendar granularity."""

    YEAR_ONLY_FORMAT = "%Y"
    YEAR_INTERVALS = (1, 2, 5, 10, 20, 25, 50, 100)
    YEAR_LABEL_WIDTH = 52

    def __init__(self, *args, date_format=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.date_format = date_format

    def setDateFormat(self, date_format):
        """Set the display format and invalidate cached axis rendering."""
        if self.date_format == date_format:
            return
        self.date_format = date_format
        self.picture = None
        self.update()

    def tickValues(self, minVal, maxVal, size):
        if self.date_format == self.YEAR_ONLY_FORMAT:
            return self._calendarYearTickValues(minVal, maxVal, size)
        return super().tickValues(minVal, maxVal, size)

    def tickStrings(self, values, scale, spacing):
        if not self.date_format:
            return super().tickStrings(values, scale, spacing)

        labels = []
        for value in values:
            try:
                display_datetime = self._axisValueToCalendarDatetime(value)
                labels.append(display_datetime.strftime(self.date_format))
            except (OverflowError, OSError, ValueError, TypeError):
                labels.append("")
        return labels

    def _axisValueToCalendarDatetime(self, value):
        """Convert an axis coordinate to its displayed calendar datetime."""
        return datetime.fromtimestamp(
            float(value) - float(self.utcOffset), timezone.utc
        ).replace(tzinfo=None)

    def _calendarDatetimeToAxisValue(self, value):
        """Convert a displayed calendar datetime to a date-axis coordinate."""
        timestamp = calendar.timegm(value.utctimetuple()) + value.microsecond / 1e6
        return timestamp + float(self.utcOffset)

    def _calendarYearTickValues(self, min_value, max_value, pixel_size):
        """Return calendar-year ticks aligned to January 1."""
        try:
            lower = float(min(min_value, max_value))
            upper = float(max(min_value, max_value))
            start = self._axisValueToCalendarDatetime(lower)
            end = self._axisValueToCalendarDatetime(upper)
        except (OverflowError, OSError, ValueError, TypeError):
            return []

        visible_years = max(1, end.year - start.year + 1)
        available_labels = max(1, int(max(float(pixel_size), 1.0) // self.YEAR_LABEL_WIDTH))
        interval = self.YEAR_INTERVALS[-1]
        for candidate in self.YEAR_INTERVALS:
            if (visible_years + candidate - 1) // candidate <= available_labels:
                interval = candidate
                break

        first_year = ((start.year + interval - 1) // interval) * interval
        ticks = []
        for year in range(first_year, end.year + 1, interval):
            try:
                tick = self._calendarDatetimeToAxisValue(datetime(year, 1, 1))
            except (OverflowError, OSError, ValueError, TypeError):
                continue
            if lower <= tick <= upper:
                ticks.append(tick)

        if not ticks:
            return []
        nominal_spacing = interval * 365.2425 * 24 * 60 * 60
        return [(nominal_spacing, ticks)]


class PlotTs():

    def __init__(self, ui, settings_model=None):
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
        self.series_history: List[TimeSeriesRecord] = []
        self._graphics_by_series_id: Dict[UUID, TimeSeriesGraphics] = {}
        self.default_style = None
        self.fit_models = []
        self.fit_seasonal_flag = False
        self.ax_residuals = None
        self.plot_residuals_flag = False
        self.hold_on_flag = False
        self.random_marker_color_flag = False
        self.parms = {}
        self.settings_persistence = TimeSeriesSettingsPersistence(self.config_file)
        self.settings_model = settings_model or self.settings_persistence.load()
        self.style_config = self.settings_persistence.style_config
        self._settings_unsubscribe = self.settings_model.subscribe(self._onSettingsChanged)
        self.refreshCompatibilityViews()
        self.coords = None
        self.ref_coords = None
        self._y_data_ranges = {}
        self._last_replica_y_data = []
        self._axis_view_update_depth = 0
        self.axis_view_changed_callback = None
        self.axis_state_sync_callback = None
        self.fit_failure_callback = None
        self.fit_success_callback = None
        self._last_axis_ranges = {}


    @contextmanager
    def axisViewUpdateGuard(self):
        """Ignore ViewBox range signals caused by application-driven updates."""
        self._axis_view_update_depth += 1
        try:
            yield
        finally:
            self._axis_view_update_depth -= 1

    def _axisViewChangeAllowed(self):
        """Return whether a range signal represents an interactive viewport change."""
        return self._axis_view_update_depth == 0

    @staticmethod
    def rangesAreClose(first, second, *, rel_tol=1e-9, abs_tol=1e-7):
        """Return whether two axis ranges differ only by floating-point noise."""
        if first is None or second is None or len(first) != 2 or len(second) != 2:
            return False
        span = max(abs(first[1] - first[0]), abs(second[1] - second[0]), 1.0)
        tolerance = max(abs_tol, span * rel_tol)
        return all(abs(float(a) - float(b)) <= tolerance for a, b in zip(first, second))

    def _handleAxisRangeChanged(self, axis_name, view_box, axis_index):
        """Record one axis-specific range and report only material user changes."""
        current = tuple(float(value) for value in view_box.viewRange()[axis_index])
        previous = self._last_axis_ranges.get(axis_name)
        self._last_axis_ranges[axis_name] = current
        if previous is None or self.rangesAreClose(previous, current):
            return
        if not self._axisViewChangeAllowed() or self.axis_view_changed_callback is None:
            return
        self.axis_view_changed_callback(axis_name)

    def _notifyAxisViewChanged(self, axis_name):
        """Report one interactive axis viewport change without redrawing."""
        if not self._axisViewChangeAllowed() or self.axis_view_changed_callback is None:
            return
        self.axis_view_changed_callback(axis_name)


    @property
    def replicate_flag(self):
        """Compatibility view backed by runtime Replica settings."""
        return self.settings_model.replica.enabled

    @replicate_flag.setter
    def replicate_flag(self, value):
        self.settings_model.update_property("replica", "enabled", bool(value))

    @property
    def replicate_value(self):
        """Compatibility view backed by runtime Replica interval."""
        return self.settings_model.replica.interval_mm

    @replicate_value.setter
    def replicate_value(self, value):
        self.settings_model.update_property("replica", "interval_mm", float(value))

    @property
    def plot_y_axis(self):
        return self.settings_model.y_axis.policy

    @plot_y_axis.setter
    def plot_y_axis(self, value):
        self.settings_model.update_property("y_axis", "policy", value)

    residual_y_axis_mode = plot_y_axis

    @property
    def manual_y_lower(self):
        return self.settings_model.y_axis.series_manual.lower

    @manual_y_lower.setter
    def manual_y_lower(self, value):
        axis = self.settings_model.y_axis
        self.settings_model.replace_domain("y_axis", replace(axis, series_manual=replace(axis.series_manual, lower=value)))

    @property
    def manual_y_upper(self):
        return self.settings_model.y_axis.series_manual.upper

    @manual_y_upper.setter
    def manual_y_upper(self, value):
        axis = self.settings_model.y_axis
        self.settings_model.replace_domain("y_axis", replace(axis, series_manual=replace(axis.series_manual, upper=value)))

    @property
    def residual_manual_y_lower(self):
        return self.settings_model.y_axis.residual_manual.lower

    @residual_manual_y_lower.setter
    def residual_manual_y_lower(self, value):
        axis = self.settings_model.y_axis
        self.settings_model.replace_domain("y_axis", replace(axis, residual_manual=replace(axis.residual_manual, lower=value)))

    @property
    def residual_manual_y_upper(self):
        return self.settings_model.y_axis.residual_manual.upper

    @residual_manual_y_upper.setter
    def residual_manual_y_upper(self, value):
        axis = self.settings_model.y_axis
        self.settings_model.replace_domain("y_axis", replace(axis, residual_manual=replace(axis.residual_manual, upper=value)))

    @staticmethod
    def _validateReplicaPairCount(value):
        """Return a safe symmetric Replica pair count for rendering.

        Only integer configuration values are accepted. Invalid values fall
        back to one pair, while valid integers are clamped to the supported
        range of one through ten pairs.
        """
        if isinstance(value, bool) or not isinstance(value, int):
            return 1
        return max(1, min(10, value))

    def _onSettingsChanged(self, change_set):
        """Refresh compatibility views once for domains represented by legacy objects."""
        compatibility_domains = {
            "series_defaults", "fit_defaults", "residual_defaults",
            "fit_current", "residual_current", "ensemble_defaults",
            "replica", "appearance", "export",
        }
        if change_set.domains & compatibility_domains:
            self.refreshCompatibilityViews()
        if "appearance" in change_set.domains:
            self.applyAppearanceSettings(change_set.properties.get("appearance", frozenset()))

    def refreshCompatibilityViews(self):
        """Rebuild all temporary compatibility views from the runtime model.

        This method deliberately performs no redraw. Callers coordinate a single redraw
        after model, snapshot, and UI synchronization is complete.

        ``parms`` and ``default_style`` are derived compatibility views only; persistence
        is loaded once by ``TimeSeriesSettingsPersistence`` during model initialization.
        """
        self.parms = build_legacy_plot_params(self.settings_model)
        self.default_style = DefaultTimeSeriesStyle.fromParams(self.parms)

    def refreshLegacyPlotParams(self):
        """Compatibility alias for the centralized compatibility refresh path."""
        self.refreshCompatibilityViews()

    def updateSettings(self):
        """Compatibility alias that never reads persistence from the renderer."""
        self.refreshCompatibilityViews()

    def clear(self):
        """Clear all stored series and renderer-owned graphics."""
        if self.hold_on_flag:
            for record in list(self.series_history):
                self._remove_snapshot_graphics(record)
        else:
            self._clearPlotWidget()
        self._discardAllSeriesState()
        self._set_current_series(None)
        self._draw()

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
        """Initialize the pyqtgraph plot items for the requested layout."""
        layout_matches = (
            self.ax is not None
            and ((self.plot_residuals_flag and self.ax_residuals is not None)
                 or (not self.plot_residuals_flag and self.ax_residuals is None))
        )
        if layout_matches:
            return

        if not self.hold_on_flag:
            self._clearPlotWidget()
            self._discardAllSeriesState()
            self._createAxesForCurrentLayout()
            return

        self._rebuild_axes_and_rerender_history()

    def _createAxesForCurrentLayout(self) -> None:
        """Create axes matching the current residual-layout flag."""
        self.ax = self._addPlot(row=0)
        if self.plot_residuals_flag:
            self.ax_residuals = self._addPlot(row=1)
            self.ax_residuals.setXLink(self.ax)
        else:
            self.ax_residuals = None

    def _rebuild_axes_and_rerender_history(self) -> None:
        """Recreate axes and re-render retained records with stable identity."""
        retained_records = list(self.series_history)
        self._clearPlotWidget()
        self._graphics_by_series_id.clear()
        self._createAxesForCurrentLayout()

        rebuilt_records = []
        try:
            for record in retained_records:
                graphics, residuals = self._render_time_series(
                    record.data, record.style
                )
                rebuilt_record = record
                if residuals is not None:
                    rebuilt_record = replace(
                        record, data=record.data.withResiduals(residuals)
                    )
                rebuilt_records.append(rebuilt_record)
                self._register_series_graphics(rebuilt_record, graphics)
        except Exception:
            # Clearing the widget destroys any partially created canvas items.
            # Records and registry are then discarded together so callers never
            # observe a partially rebuilt retained-series state.
            self._clearPlotWidget()
            self._discardAllSeriesState()
            self._createAxesForCurrentLayout()
            raise

        self.series_history[:] = rebuilt_records
        if rebuilt_records:
            self._set_current_series(rebuilt_records[-1].data)
        self._rebuildYDataRanges()

    def plotTs(self, *, dates=None, ts_values=None, ref_values=None, plot_multiple=True, coords=None, ref_coords=None,
               update=False, report_statistics=False):
        """Render under the nested-safe axis guard and normalize first-plot state."""
        initial_plot = self.ax is None
        with self.axisViewUpdateGuard():
            result = self._plotTsGuarded(
                dates=dates, ts_values=ts_values, ref_values=ref_values,
                plot_multiple=plot_multiple, coords=coords, ref_coords=ref_coords,
                update=update, report_statistics=report_statistics,
            )
        if initial_plot and self.ax is not None:
            x_state = replace(self.settings_model.x_axis, custom_view=False)
            y_state = replace(
                self.settings_model.y_axis, policy="from_data",
                series_custom_view=False, residual_custom_view=False,
            )
            with self.settings_model.batch_update():
                self.settings_model.replace_domain("x_axis", x_state)
                self.settings_model.replace_domain("y_axis", y_state)
            if self.axis_state_sync_callback is not None:
                self.axis_state_sync_callback()
        return result

    def _plotTsGuarded(self, *, dates=None, ts_values=None, ref_values=None, plot_multiple=True, coords=None, ref_coords=None,
               update=False, report_statistics=False):
        # update: flag indicating if the plot should be updated or a new one created

        self.updateSettings()
        source_snapshot = self.current_series() if update else None

        if update:
            if source_snapshot is None:
                return
            source_data = source_snapshot.data
            dates = source_data.dates if dates is None else dates
            ts_values = source_data.ts_values if ts_values is None else ts_values
            ref_values = source_data.ref_values if ref_values is None else ref_values
            coords = source_data.coords if coords is None else coords
            ref_coords = source_data.ref_coords if ref_coords is None else ref_coords
            random_marker_color_flag = False
            style = TimeSeriesStyle.fromParams(
                source_snapshot.style.params,
                label=source_snapshot.style.label,
                visible=source_snapshot.style.visible,
                z_order=source_snapshot.style.z_order,
            )
        else:
            random_marker_color_flag = self.random_marker_color_flag
            style = self.default_style.snapshotStyle()
            if not self.hold_on_flag:
                self._discardAllSeriesState()

        if dates is None and self.dates is None:
            return

        # build and validate before changing the existing record or its graphics.
        series = self._buildTimeSeriesData(
            dates=dates,
            ts_values=ts_values,
            ref_values=ref_values,
            coords=coords if coords is not None else self.coords,
            ref_coords=ref_coords if ref_coords is not None else self.ref_coords,
        )
        if not series.hasFinitePlotValues():
            return

        self.initializeAxes()

        if random_marker_color_flag:
            rand_color = randomTimeSeriesColor()
            style.params['time series plot']['marker color'] = rand_color
            style.params['time series plot']['line color'] = rand_color

        if update:
            graphics, residuals_values = self._render_time_series(
                series, style, plot_multiple=plot_multiple,
                report_statistics=report_statistics,
            )
            if residuals_values is not None:
                series = series.withResiduals(residuals_values)
            replacement = replace(source_snapshot, data=series, style=style)
            self._commit_rendered_record_replacement(
                source_snapshot, replacement, graphics
            )
        else:
            self._render_and_store_series(
                series, style, plot_multiple=plot_multiple,
                report_statistics=report_statistics,
                replacement=not self.hold_on_flag,
            )
        self._draw()

    def _commit_rendered_record_replacement(
        self,
        previous: TimeSeriesRecord,
        replacement: TimeSeriesRecord,
        graphics: TimeSeriesGraphics,
    ) -> None:
        """Atomically swap one rendered record after replacement rendering succeeds."""
        if previous.id != replacement.id:
            raise ValueError("replacement record must preserve the original UUID")
        index = next(
            (i for i, record in enumerate(self.series_history) if record.id == previous.id),
            None,
        )
        self._remove_snapshot_graphics(previous)
        if index is None:
            self.series_history.append(replacement)
        else:
            self.series_history[index] = replacement
        self._register_series_graphics(replacement, graphics)
        self._set_current_series(self.current_series().data)
        self._rebuildYDataRanges()

    def _render_and_store_series(
        self, series: TimeSeriesData, style: TimeSeriesStyle, *,
        plot_multiple: bool = True, report_statistics: bool = False,
        replacement: bool = False,
    ) -> TimeSeriesRecord:
        """Render and atomically register one record, cleaning failed replacements."""
        try:
            items, residuals_values = self._render_time_series(
                series, style, plot_multiple=plot_multiple,
                report_statistics=report_statistics
            )
        except Exception:
            if replacement:
                # A renderer can fail after creating some canvas items. Destroy
                # the canvas and authoritative state together, recreate an empty
                # layout, and preserve the original exception for existing error
                # handling.
                self._clearPlotWidget()
                self._discardAllSeriesState()
                self._createAxesForCurrentLayout()
            raise
        if residuals_values is not None:
            series = series.withResiduals(residuals_values)
            self._set_current_series(series)
        record = TimeSeriesRecord(data=series, style=style)
        self._add_rendered_series(record, items)
        return record

    @staticmethod
    def _alphaOrDefault(value, default):
        """Return an alpha value without treating explicit zero as missing."""
        if value is None:
            return float(default)
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return float(default)

    def _render_time_series(
        self, series: TimeSeriesData, style: TimeSeriesStyle, *,
        plot_multiple=True, report_statistics=False
    ) -> Tuple[TimeSeriesGraphics, Optional[np.ndarray]]:
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
            if series_fill_alpha > 0:
                lower_line = pg.PlotCurveItem(x, lower_bound, pen=None)
                upper_line = pg.PlotCurveItem(x, upper_bound, pen=None)
                fill = pg.FillBetweenItem(
                    lower_line, upper_line,
                    brush=self._brush(series_fill_color, series_fill_alpha)
                )
                self.ax.addItem(lower_line)
                self.ax.addItem(upper_line)
                self.ax.addItem(fill)
                items.plot_multiple_fill = [lower_line, upper_line, fill]
            main_y_data.extend([lower_bound, upper_bound])

        if series.plot_multiple_values is not None:
            series_line_style = '-'
            series_line_color = parms['series line color']
            series_line_alpha = parms['series line alpha']
            series_line_width = parms['series line width']
            if series_line_width > 0 and series_line_alpha > 0:
                for i in range(series.plot_multiple_values.shape[1]):
                    item = self.ax.plot(
                        x, series.plot_multiple_values[:, i],
                        pen=self._pen(series_line_color, series_line_width, series_line_alpha, series_line_style)
                    )
                    items.plot_multiple_lines.append(item)
            for i in range(series.plot_multiple_values.shape[1]):
                main_y_data.append(series.plot_multiple_values[:, i])

        if marker_size > 0 and marker_alpha > 0:
            items.scatter = pg.ScatterPlotItem(x=x, y=series.plot_values, symbol=self._symbol(marker),
                                               size=marker_size,
                                               pen=self._pen(edge_color, 0.2, marker_alpha),
                                               brush=self._brush(marker_color, marker_alpha))
            self.ax.addItem(items.scatter)

        main_y_data.append(series.plot_values)

        if line_style and line_width > 0 and line_alpha > 0:
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
        items.fit_plot, residuals_values = self.fitModel(
            series, style, items, report_statistics=report_statistics
        )

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
        """Render global Replica overlays from the authoritative runtime model.

        ``style`` remains in the signature for compatibility with older callers, but
        Replica appearance is intentionally not required in snapshot-owned payloads.
        """
        replica = self.settings_model.replica
        x = self._datesToX(series.dates)
        marker_color_1 = replica.color_1  # replica up
        marker_color_2 = replica.color_2  # replica down
        marker_alpha = replica.opacity
        marker_size_replica = replica.marker_size
        marker_replica = replica.marker
        replica_pair_count = self._validateReplicaPairCount(replica.pair_count)
        self._last_replica_y_data = []

        # Plot symmetric positive/negative replica pairs around the source series.
        replicate_up_list = []
        replicate_dn_list = []
        for i in range(replica_pair_count):
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

            down_color = marker_color_2 if i % 2 == 0 else marker_color_1
            replicate_dn = pg.ScatterPlotItem(
                x=x,
                y=series.plot_values - replicate_value,
                symbol=self._symbol(marker_replica),
                size=marker_size_replica,
                pen=None,
                brush=self._brush(down_color, marker_alpha),
            )
            self.ax.addItem(replicate_dn)
            replicate_dn_list.append(replicate_dn)
            self._last_replica_y_data.append(series.plot_values - replicate_value)

        return replicate_up_list, replicate_dn_list

    def fitModel(
        self, series: TimeSeriesData, style: TimeSeriesStyle, graphics=None, *,
        report_statistics=False
    ):
        if series.plot_values is None:
            return None, None
        if series.dates is None:
            return None, None
        if not self.fit_models:
            return None, None

        parms = style.params['model fit']
        fit_style = FitStyle.fromParams(style.params)
        fit_line_type = fit_style.line_style
        fit_line_color = fit_style.line_color
        fit_line_alpha = parms['line alpha']
        fit_line_width = fit_style.line_width
        fit_seasonal = self.fit_seasonal_flag
        if len(self.fit_models) != 1:
            return None, None
        else:
            fit_model = self.fit_models[0]
            try:
                model_values, model_x, model_y = (
                    FittingModels(series.dates, series.plot_values, model=fit_model).fit(
                        seasonal=fit_seasonal
                    )
                )
            except ModelFitError as error:
                if self.fit_failure_callback is not None:
                    self.fit_failure_callback(error, seasonal=fit_seasonal)
                return None, None
            fit_plot = None
            if fit_line_type and fit_line_width > 0 and fit_line_alpha > 0:
                fit_plot = self.ax.plot(
                    self._datesToX(model_x),
                    model_y,
                    pen=self._pen(fit_line_color, fit_line_width, fit_line_alpha, fit_line_type)
                )
            observed_values = np.asarray(series.plot_values, dtype=np.float64)
            fitted_values = np.asarray(model_values, dtype=np.float64)
            finite_mask = np.isfinite(observed_values) & np.isfinite(fitted_values)
            try:
                statistics = calculateFitStatistics(
                    observed_values[finite_mask], fitted_values[finite_mask]
                )
            except ValueError:
                error = ModelFitError(
                    fit_model,
                    f"{fit_model} fit returned invalid statistics.",
                    finite_observation_count=int(np.count_nonzero(finite_mask)),
                )
                if self.fit_failure_callback is not None:
                    self.fit_failure_callback(error, seasonal=fit_seasonal)
                return None, None

            residuals_values = observed_values - fitted_values
            self.plotResiduals(series, style, graphics, residuals_values)
            if report_statistics and self.fit_success_callback is not None:
                self.fit_success_callback(
                    fit_model, statistics, seasonal=fit_seasonal
                )

        return fit_plot, residuals_values

    def _normalizedResidualStyle(self, style: TimeSeriesStyle):
        """Return snapshot-owned residual appearance with runtime-default fallbacks."""
        values = self.settings_model.residual_current.asParams()
        snapshot_params = style.params if isinstance(style.params, dict) else {}
        snapshot_residual = snapshot_params.get("residual plot", {})
        if isinstance(snapshot_residual, dict):
            values.update(snapshot_residual)
        return ResidualStyleSettings.fromParams({"residual plot": values})

    def plotResiduals(self, series: TimeSeriesData, style: TimeSeriesStyle, items=None, residuals_values=None):
        if items is None:
            items = TimeSeriesGraphics()
        if residuals_values is None:
            residuals_values = series.residuals_values
        if self.plot_residuals_flag and self.ax_residuals is not None and residuals_values is not None:
            residual_style = self._normalizedResidualStyle(style)
            marker = residual_style.marker
            marker_size = residual_style.marker_size
            marker_color = residual_style.marker_color
            marker_alpha = residual_style.marker_alpha
            edge_color = residual_style.marker_edge_color
            line_style = residual_style.line_style
            line_color = residual_style.line_color
            line_alpha = residual_style.line_alpha
            line_width = residual_style.line_width
            parms = deepcopy(self.parms.get("residual plot", {}))
            parms.update(residual_style.asParams())

            x = self._datesToX(series.dates)
            marker_size = marker_size or 0
            if marker_size > 0 and marker_alpha > 0:
                items.residual_scatter = pg.ScatterPlotItem(
                    x=x,
                    y=residuals_values,
                    symbol=self._symbol(marker),
                    size=marker_size,
                    pen=self._pen(edge_color, 0.2, marker_alpha),
                    brush=self._brush(marker_color, marker_alpha)
                )
                self.ax_residuals.addItem(items.residual_scatter)
            if line_style and line_width > 0 and line_alpha > 0:
                items.residual_line = self.ax_residuals.plot(
                    x,
                    residuals_values,
                    pen=self._pen(line_color, line_width, line_alpha, line_style)
                )
            items.residual_y_data = [residuals_values]
            self.updateYlim(ax=self.ax_residuals, y_data=items.residual_y_data)
            self.decoratePlot(ax=self.ax_residuals, parms=parms)


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


    def resolveXAxisRange(self, state=None, *, use_data_xlim=True, padding=30):
        """Resolve the effective X limits used by preview and committed rendering."""
        if self.dates is None or len(self.dates) == 0:
            return None
        state = self.settings_model.x_axis if state is None else state
        min_date, max_date = self.availableDateRange()
        if use_data_xlim:
            data_start = min_date - timedelta(days=padding)
            data_end = max_date + timedelta(days=padding)
        else:
            data_start = datetime(min_date.year, 1, 1)
            data_end = datetime(max_date.year + 1, 1, 1)
        return state.effective_range(data_start, data_end)

    def setXlims(self, *, ax=None, use_data_xlim=True, padding=30):
        """Apply the same resolved X limits used by transactional preview."""
        if not ax:
            ax = self.ax
        effective = self.resolveXAxisRange(
            use_data_xlim=use_data_xlim, padding=padding
        )
        if effective is None:
            return False
        x_min = self._dateToX(effective[0])
        x_max = self._dateToX(effective[1])
        with self.axisViewUpdateGuard():
            ax.setXRange(x_min, x_max, padding=0)
        return True

    def resetSharedXAxisFromData(self):
        """Restore the linked X domain from the complete canonical date extent."""
        if self.ax is None:
            return False
        state = replace(
            self.settings_model.x_axis,
            start_policy="from_data",
            end_policy="from_data",
            custom_view=False,
        )
        effective = self.resolveXAxisRange(state)
        if effective is None:
            return False
        self.ax.setXRange(
            self._dateToX(effective[0]), self._dateToX(effective[1]), padding=0
        )
        return True

    def applyXAxisViewport(self, start, end, *, draw=True):
        """Apply only the existing main X viewport with zero padding."""
        if self.ax is None:
            return False
        with self.axisViewUpdateGuard():
            self.ax.setXRange(self.datetimeToPlotX(start), self.datetimeToPlotX(end), padding=0)
        if draw:
            self._draw()
        return True

    def availableDateRange(self):
        """Return the nearest Python datetime endpoints available in current data."""
        dates = [self._asDatetime(value) for value in self.dates]
        return min(dates), max(dates)

    def currentVisibleDateRange(self):
        """Return date bounds covering the complete visible X viewport."""
        if self.ax is None:
            raise ValueError("A plotted time series is required")
        visible_start, visible_end = self.ax.viewRange()[0]
        start_datetime = self.plotXToDatetime(visible_start)
        end_datetime = self.plotXToDatetime(visible_end)
        start = datetime.combine(start_datetime.date(), time.min)
        end_date = end_datetime.date()
        if end_datetime.time() != time.min:
            end_date += timedelta(days=1)
        end = datetime.combine(end_date, time.min)
        return start, end

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
        with self.axisViewUpdateGuard():
            ax.setYRange(y_min, y_max, padding=0.05)

    def dataYAxisRange(self, ax=None):
        """Return the canonical finite plotted-data extent for one Y axis."""
        if ax is None:
            ax = self.ax
        if ax is None:
            return None
        data_range = self._y_data_ranges.get(id(ax))
        if data_range is None:
            return None
        y_min, y_max = (float(value) for value in data_range)
        if not np.isfinite(y_min) or not np.isfinite(y_max) or y_min > y_max:
            return None
        return y_min, y_max

    def resolveManualYAxisRange(self, ax=None, manual=None):
        """Resolve one axis Manual range from the same data extent as From Data."""
        if ax is None:
            ax = self.ax
        data_range = self.dataYAxisRange(ax)
        if data_range is None:
            return None
        if manual is None:
            manual = (self.settings_model.y_axis.series_manual if ax is self.ax
                      else self.settings_model.y_axis.residual_manual)
        return resolve_manual_y_range(*data_range, manual.lower, manual.upper)

    def resolveYAxisDisplayRange(self, ax=None, mode=None, manual=None):
        """Resolve one axis independently for preview and committed rendering."""
        if ax is None:
            ax = self.ax
        if ax is None:
            return None
        if mode is None:
            state = self.settings_model.y_axis
            if state.policy in {"symmetric", "adaptive"}:
                mode = state.policy
            else:
                axis_name = "series_y" if ax is self.ax else "residual_y"
                mode = state.display_mode_for_axis(axis_name)
        data_range = self.dataYAxisRange(ax)
        if data_range is None:
            return None

        y_min, y_max = data_range
        if mode == "manual":
            if manual is None:
                manual = (self.settings_model.y_axis.series_manual if ax is self.ax
                          else self.settings_model.y_axis.residual_manual)
            return resolve_y_axis_display_range(
                y_min, y_max, manual.lower, manual.upper
            )

        if mode in {"symmetric", "adaptive"}:
            y_max = np.abs([y_min, y_max]).max()
            y_min = -y_max

        if mode == "adaptive":
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

        if y_min == y_max:
            y_min -= 1
            y_max += 1
        return y_min, y_max, 0.05

    def setYlims(self, ax=None, parms={}):
        if not ax:
            ax = self.ax
        resolved = self.resolveYAxisDisplayRange(ax=ax)
        if resolved is None:
            return False
        ymin, ymax, padding = resolved
        with self.axisViewUpdateGuard():
            ax.setYRange(ymin, ymax, padding=padding)
        return True

    def resetYAxisFromData(self, ax=None):
        """Restore one local Y axis using its canonical From Data display range."""
        if ax is None:
            ax = self.ax
        resolved = self.resolveYAxisDisplayRange(ax=ax, mode="from_data")
        if resolved is None:
            return False
        ymin, ymax, padding = resolved
        ax.setYRange(ymin, ymax, padding=padding)
        return True

    def setManualYRanges(self, series_manual, residual_manual, residual_available):
        """Preview the complete Y editor draft through the committed render paths."""
        state = replace(
            self.settings_model.y_axis,
            series_manual=series_manual,
            residual_manual=residual_manual,
            series_display_mode=(
                "manual" if series_manual.lower is not None or series_manual.upper is not None
                else "from_data"
            ),
        )
        if residual_available:
            state = replace(
                state, residual_display_mode=(
                    "manual" if residual_manual.lower is not None or residual_manual.upper is not None
                    else "from_data"
                ),
            )
        state = replace(
            state, policy=state.policy_for_effective_display(residual_available)
        )
        self.settings_model.replace_domain("y_axis", state)
        with self.axisViewUpdateGuard():
            if self.ax is not None:
                self.setYlims(ax=self.ax, parms=self.parms["time series plot"])
            if residual_available and self.ax_residuals is not None:
                self.setYlims(ax=self.ax_residuals, parms=self.parms["residual plot"])
        self._draw()

    def captureViewport(self):
        """Return current plot ranges for restoration after graphics-only redraws."""
        viewport = {}
        for name, axis in (("main", self.ax), ("residual", self.ax_residuals)):
            if axis is not None:
                ranges = axis.viewRange()
                viewport[name] = (tuple(ranges[0]), tuple(ranges[1]))
        return viewport

    def restoreViewport(self, viewport):
        """Restore a viewport previously returned by :meth:`captureViewport`."""
        for name, axis in (("main", self.ax), ("residual", self.ax_residuals)):
            ranges = viewport.get(name)
            if axis is None or ranges is None:
                continue
            with self.axisViewUpdateGuard():
                axis.setXRange(ranges[0][0], ranges[0][1], padding=0)
                axis.setYRange(ranges[1][0], ranges[1][1], padding=0)

    @contextmanager
    def preserveViewport(self):
        """Preserve main and residual plot ranges across a graphics redraw."""
        viewport = self.captureViewport()
        try:
            yield
        finally:
            self.restoreViewport(viewport)

    def setAxisStyle(self, ax=None, parms={}):
        if not ax:
            ax = self.ax
        background_color = self._color(parms['background color'])
        ax.getViewBox().setBackgroundColor(background_color)
        self._applyDateFormat(ax=ax, parms=parms)

    def setFigureStyle(self, parms={}):
        background_color = self._color(parms['background color'])
        self.ui.plot_widget.setBackground(background_color)

    def applyAppearanceSettings(self, changed_properties=None):
        """Apply runtime appearance changes without recreating plots or changing ranges."""
        appearance = self.settings_model.appearance
        axes = [axis for axis in (self.ax, self.ax_residuals) if axis is not None]
        if not axes:
            return
        viewport = self.captureViewport()
        try:
            for axis in axes:
                font = QFont()
                font.setPointSize(int(appearance.font_size))
                for axis_name in ("left", "bottom"):
                    axis.getAxis(axis_name).setTickFont(font)
                axis.showGrid(
                    x=appearance.grid_mode in ("vertical", "both"),
                    y=appearance.grid_mode in ("horizontal", "both"),
                    alpha=0.25,
                )
                axis.getViewBox().setBackgroundColor(
                    self._color(appearance.plot_background)
                )
                date_axis = axis.getAxis("bottom")
                if isinstance(date_axis, FormattedDateAxisItem):
                    date_axis.setDateFormat(appearance.date_format)

            font_size = f"{int(appearance.font_size)}pt"
            self.ax.setTitle(appearance.time_series_title, size=font_size)
            self.ax.setLabel(
                "bottom", appearance.time_series_x_label,
                **{"font-size": font_size}
            )
            self.ax.setLabel(
                "left", appearance.time_series_y_label,
                **{"font-size": font_size}
            )
            if self.ax_residuals is not None:
                self.ax_residuals.setTitle(appearance.residual_title, size=font_size)
                self.ax_residuals.setLabel(
                    "bottom", appearance.residual_x_label,
                    **{"font-size": font_size}
                )
                self.ax_residuals.setLabel(
                    "left", appearance.residual_y_label,
                    **{"font-size": font_size}
                )
            self.ui.plot_widget.setBackground(
                self._color(appearance.canvas_background)
            )
        finally:
            self.restoreViewport(viewport)
        self._draw()

    def savePlotAsImage(self, filename):
        """Export the current plot and return the export result."""
        return TimeSeriesPlotExporter(self).export(filename)

    def _addPlot(self, row=0):
        axis = FormattedDateAxisItem(
            orientation='bottom', date_format=self.settings_model.appearance.date_format
        )
        plot_item = self.ui.plot_widget.addPlot(row=row, col=0, axisItems={'bottom': axis})
        self._stylePlotFrame(plot_item)
        self._connectAxisViewSignals(plot_item, row=row)
        self._connectAutoButton(plot_item)
        plot_item.showButtons()
        self.ui.plot_widget.plot_items.append(plot_item)
        return plot_item


    def _connectAxisViewSignals(self, plot_item, *, row):
        """Track interactive ViewBox changes while ignoring guarded updates."""
        view_box = plot_item.getViewBox()
        if row == 0:
            view_box.sigXRangeChanged.connect(
                lambda *args, vb=view_box: self._handleAxisRangeChanged("x", vb, 0)
            )
            view_box.sigYRangeChanged.connect(
                lambda *args, vb=view_box: self._handleAxisRangeChanged("series_y", vb, 1)
            )
        else:
            view_box.sigYRangeChanged.connect(
                lambda *args, vb=view_box: self._handleAxisRangeChanged("residual_y", vb, 1)
            )

    def _connectAutoButton(self, plot_item):
        """Replace all native Auto receivers with one application-owned handler."""
        auto_button = getattr(plot_item, 'autoBtn', None)
        if auto_button is None:
            return
        try:
            auto_button.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        auto_button.clicked.connect(
            lambda *args, plot_item=plot_item: self._resetPlotView(plot_item)
        )

    def _resetPlotView(self, plot_item):
        """Route pyqtgraph Auto through one guarded application reset transaction."""
        if self.dates is None:
            return
        callback = getattr(self, "auto_view_requested_callback", None)
        if callback is not None:
            callback()
        else:
            with self.axisViewUpdateGuard():
                self.updateSettings()
                self.resetSharedXAxisFromData()
                self.resetYAxisFromData(self.ax)
                if self.ax_residuals is not None:
                    self.resetYAxisFromData(self.ax_residuals)
            self._draw()
        auto_button = getattr(plot_item, 'autoBtn', None)
        if auto_button is not None:
            auto_button.hide()

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
        """Destroy plot axes and canvas items without deciding record lifetime."""
        self.ui.plot_widget.clear()
        self.ui.plot_widget.plot_items = []
        self.ax = None
        self.ax_residuals = None
        self._y_data_ranges = {}
        self._last_replica_y_data = []

    def _discardAllSeriesState(self) -> None:
        """Remove rendered graphics and discard all stored series state."""
        for record in list(self.series_history):
            self._remove_snapshot_graphics(record)
        self.series_history.clear()
        self._graphics_by_series_id.clear()
        self._set_current_series(None)
        self._y_data_ranges = {}
        self._last_replica_y_data = []

    def _graphics_for_series(
        self, series: TimeSeriesRecord
    ) -> Optional[TimeSeriesGraphics]:
        """Return runtime graphics registered for a stored series."""
        return self._graphics_by_series_id.get(series.id)

    def _register_series_graphics(
        self, series: TimeSeriesRecord, graphics: TimeSeriesGraphics
    ) -> None:
        """Register or replace runtime graphics for a stored series."""
        self._graphics_by_series_id[series.id] = graphics

    def _pop_series_graphics(
        self, series: TimeSeriesRecord
    ) -> Optional[TimeSeriesGraphics]:
        """Remove and return runtime graphics registered for a stored series."""
        return self._graphics_by_series_id.pop(series.id, None)

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

    def _remove_snapshot_graphics(self, snapshot: TimeSeriesRecord) -> None:
        """Remove and unregister all plot items owned by a stored time series."""
        graphics = self._pop_series_graphics(snapshot)
        if graphics is None:
            return
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
            graphics = self._graphics_for_series(snapshot)
            if graphics is not None:
                self.updateYlim(ax=self.ax, y_data=graphics.main_y_data)
        if self.ax_residuals is not None:
            for snapshot in self.series_history:
                graphics = self._graphics_for_series(snapshot)
                if graphics is not None:
                    self.updateYlim(
                        ax=self.ax_residuals, y_data=graphics.residual_y_data
                    )

    def _applyDateFormat(self, ax=None, parms={}):
        if ax is None:
            ax = self.ax
        axis = ax.getAxis('bottom')
        if isinstance(axis, FormattedDateAxisItem):
            axis.setDateFormat(parms.get('date format'))

    @staticmethod
    def _asDatetime(value):
        """Normalize supported date-like values to Python datetime."""
        if isinstance(value, np.datetime64):
            return value.astype('datetime64[ms]').astype(datetime)
        if isinstance(value, datetime):
            return value
        return datetime(value.year, value.month, value.day)

    @staticmethod
    def plotXToDatetime(value):
        """Convert a pyqtgraph date-axis coordinate to a Python datetime."""
        return datetime.fromtimestamp(float(value))

    @classmethod
    def datetimeToPlotX(cls, value):
        """Convert a supported date-like value to a pyqtgraph date-axis coordinate."""
        return cls._asDatetime(value).timestamp()

    def _dateToX(self, value):
        """Compatibility wrapper for :meth:`datetimeToPlotX`."""
        return self.datetimeToPlotX(value)

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

    def replace_series_records(self, records) -> None:
        """Replace stored records by UUID while preserving order and graphics keys."""
        replacements = {record.id: record for record in records}
        if not replacements:
            return
        for index, current in enumerate(self.series_history):
            replacement = replacements.get(current.id)
            if replacement is not None:
                self.series_history[index] = replacement
        current = self.current_series()
        self._set_current_series(current.data if current is not None else None)

    def rerenderTimeSeriesSnapshots(
        self, snapshots: List[TimeSeriesSnapshot], *, draw: bool = True
    ) -> None:
        """Transactionally replace and re-render selected snapshots by UUID.

        TODO(runtime-settings): remove this compatibility redraw path after plot
        layers support scoped in-place updates. ``draw=False`` allows callers to
        compose graphics and axis-policy changes into one visual transaction.
        """
        replacements = {snapshot.id: snapshot for snapshot in snapshots}
        with self.preserveViewport():
            for index, current in enumerate(list(self.series_history)):
                requested = replacements.get(current.id)
                if requested is None:
                    continue
                graphics, residuals = self._render_time_series(
                    requested.data, requested.style
                )
                replacement = requested
                if residuals is not None:
                    replacement = replace(
                        requested, data=requested.data.withResiduals(residuals)
                    )
                self._remove_snapshot_graphics(current)
                self.series_history[index] = replacement
                self._register_series_graphics(replacement, graphics)
            current = self.current_series()
            self._set_current_series(current.data if current is not None else None)
            self._rebuildYDataRanges()
        if draw:
            self._draw()

    def selectedTimeSeriesSnapshots(self) -> List[TimeSeriesSnapshot]:
        """Return the snapshots currently targeted for editing."""
        snapshot = self.current_series()
        return [snapshot] if snapshot is not None else []

    def hasSelectedTimeSeries(self) -> bool:
        """Return whether at least one time-series snapshot is selected."""
        return bool(self.selectedTimeSeriesSnapshots())

    def selectedTimeSeriesCount(self) -> int:
        """Return the number of selected time-series snapshots."""
        return len(self.selectedTimeSeriesSnapshots())

    def setCurrentSeriesStyleAsDefault(self) -> bool:
        """Copy the current series style into the new-series default source."""
        snapshot = self.current_series()
        if snapshot is None:
            return False
        if self.default_style is None:
            self.default_style = DefaultTimeSeriesStyle.fromParams(snapshot.style.params)
        else:
            self.default_style.replaceFromSeries(snapshot.style)
        return True

    def defaultTimeSeriesStyle(self) -> TimeSeriesStyle:
        """Return a defensive copy of the style used for future series."""
        if self.default_style is None:
            self.refreshCompatibilityViews()
        return self.default_style.snapshotStyle()

    def _add_rendered_series(
        self, snapshot: TimeSeriesRecord, graphics: TimeSeriesGraphics
    ) -> None:
        """Store a rendered record and roll back if graphics registration fails."""
        self.add_series(snapshot)
        try:
            self._register_series_graphics(snapshot, graphics)
        except Exception:
            self.remove_series_by_id(snapshot.id)
            raise

    def add_series(self, snapshot: TimeSeriesSnapshot) -> None:
        """Store a time-series record; callers remain responsible for graphics."""
        self.series_history.append(snapshot)

    def current_series(self) -> Optional[TimeSeriesSnapshot]:
        """Return the active stored time-series snapshot, if available."""
        if self.series_history:
            return self.series_history[-1]
        return None

    def remove_series(self, index: int = -1) -> Optional[TimeSeriesSnapshot]:
        """Remove and return a record without changing registered graphics."""
        if not self.series_history:
            return None
        return self.series_history.pop(index)

    def remove_series_by_id(self, series_id: UUID) -> Optional[TimeSeriesSnapshot]:
        """Remove and return the record with the supplied stable identity."""
        for index, snapshot in enumerate(self.series_history):
            if snapshot.id == series_id:
                return self.series_history.pop(index)
        return None

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
                            "https://luhipi.github.io/insar-explorer\n"
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
