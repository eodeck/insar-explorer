import calendar
import inspect
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, time, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np
from ..external import pyqtgraph as pg
from qgis.PyQt.QtCore import QPointF
from qgis.PyQt.QtGui import QColor, QFont, QPalette
from qgis.PyQt.QtWidgets import QApplication

from .model_fitting import calculateFitStatistics, FittingModels, ModelFitError
from .export_plot import TimeSeriesPlotExporter
from .time_series.y_axis_range import (
    resolve_manual_y_range, resolve_y_axis_display_range,
)
from .time_series.hover import (
    HoverObservation, format_hover_text, select_nearest_hover_observation,
)
from .time_series.settings.persistence import build_legacy_plot_params
from .time_series.persistence import NullProjectStateRepository
from .time_series.store import TimeSeriesStore
from .time_series.pending_session import PendingTimeSeriesSession, resolve_editable_record
from .models.time_series import (
    FitConfiguration,
    ReplicaConfiguration,
    TimeSeriesAnalysis,
    TimeSeriesData,
    TimeSeriesGraphics,
    TimeSeriesRecord,
    SpatialSelection,
    SpatialSelectionKind,
    TimeSeriesSnapshot,
    DefaultTimeSeriesStyle,
    TimeSeriesStyle,
    TimeSeriesPresentation,
    buildTimeSeriesData,
    randomTimeSeriesColor,
)

_UNSET = object()


@dataclass(frozen=True)
class CommittedRemovalResult:
    """Result of one committed-record batch removal."""

    removed_record_ids: Tuple[UUID, ...]
    graphics_errors: Tuple[Exception, ...] = ()


@dataclass(frozen=True)
class CommittedVisibilityBatchResult:
    """Result of one atomic committed-visibility batch transaction."""

    changed_record_ids: Tuple[UUID, ...]
    graphics_errors: Tuple[Exception, ...] = ()
    refresh_errors: Tuple[Exception, ...] = ()


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


@dataclass
class _GraphicsRenderTransaction:
    """Track canvas attachments so a failed render can remove them completely."""

    plotter: object

    def __post_init__(self):
        self._attachments = []
        self._committed = False

    def add_item(self, axis, item):
        """Attach one item and remember its owning axis for rollback."""
        axis.addItem(item)
        self._attachments.append((axis, item))
        return item

    def rollback(self):
        """Remove every item attached by this attempt in reverse order."""
        if self._committed:
            return
        for axis, item in reversed(self._attachments):
            self.plotter._removeItem(axis, item)
        self._attachments.clear()

    def commit(self):
        """Mark the tracked attachments as authoritative."""
        self._committed = True


class PlotTs():

    def __init__(
        self, ui, settings_model=None, user_preferences=None,
        project_state_repository=None, pending_session=None,
    ):
        """Create the renderer from injected runtime and persistence dependencies."""
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
        self._series_store = TimeSeriesStore()
        if pending_session is None:
            pending_session = PendingTimeSeriesSession()
        self._pending_session = pending_session
        self._graphics_by_series_id: Dict[UUID, TimeSeriesGraphics] = {}
        self._pending_graphics_by_series_id: Dict[UUID, TimeSeriesGraphics] = {}
        self.pending_changed_callback = None
        self.committed_changed_callback = None
        self._hidden_committed_ids = set()
        self.default_style = None
        self.fit_models = []
        self.fit_seasonal_flag = False
        self.ax_residuals = None
        self.plot_residuals_flag = False
        self.random_marker_color_flag = False
        self.parms = {}
        if settings_model is None or user_preferences is None:
            raise ValueError(
                "PlotTs requires composed settings_model and user_preferences"
            )
        self.user_preferences = user_preferences
        # Transitional alias for external callers; the concrete type is not assumed.
        self.settings_persistence = user_preferences
        self.project_state_repository = (
            project_state_repository or NullProjectStateRepository()
        )
        self.settings_model = settings_model
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
        self.analysis_state_sync_callback = None
        self._last_axis_ranges = {}
        self._new_record_analysis = self._snapshotAnalysisDefaults()
        self._hover_scene = None
        self._hover_widget = None
        self._hover_marker = None
        self._hover_marker_plot = None
        self._hover_tolerance_px = 10.0

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
    def series_history(self) -> List[TimeSeriesRecord]:
        """Return a compatibility copy of stored records in render order."""
        return list(self._series_store.records())

    @property
    def replicate_flag(self):
        """Compatibility view of the active record or new-record default."""
        current = self.current_series()
        return current.analysis.replica.enabled if current is not None else self.settings_model.replica.enabled

    @replicate_flag.setter
    def replicate_flag(self, value):
        """Set the Replica enabled default used only for future records."""
        self.settings_model.update_property("replica", "enabled", bool(value))

    @property
    def replicate_value(self):
        """Compatibility view of the active record or new-record default."""
        current = self.current_series()
        return current.analysis.replica.interval_mm if current is not None else self.settings_model.replica.interval_mm

    @replicate_value.setter
    def replicate_value(self, value):
        """Set the Replica interval default used only for future records."""
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
        self.settings_model.replace_domain(
            "y_axis", replace(axis, series_manual=replace(axis.series_manual, lower=value))
        )

    @property
    def manual_y_upper(self):
        return self.settings_model.y_axis.series_manual.upper

    @manual_y_upper.setter
    def manual_y_upper(self, value):
        axis = self.settings_model.y_axis
        self.settings_model.replace_domain(
            "y_axis", replace(axis, series_manual=replace(axis.series_manual, upper=value))
        )

    @property
    def residual_manual_y_lower(self):
        return self.settings_model.y_axis.residual_manual.lower

    @residual_manual_y_lower.setter
    def residual_manual_y_lower(self, value):
        axis = self.settings_model.y_axis
        self.settings_model.replace_domain(
            "y_axis", replace(axis, residual_manual=replace(axis.residual_manual, lower=value))
        )

    @property
    def residual_manual_y_upper(self):
        return self.settings_model.y_axis.residual_manual.upper

    @residual_manual_y_upper.setter
    def residual_manual_y_upper(self, value):
        axis = self.settings_model.y_axis
        self.settings_model.replace_domain(
            "y_axis", replace(axis, residual_manual=replace(axis.residual_manual, upper=value))
        )

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
        is loaded once by ``the injected user-preferences repository`` during model initialization.
        """
        self.parms = build_legacy_plot_params(self.settings_model)
        self.default_style = DefaultTimeSeriesStyle.fromParams(self.parms)

    def refreshLegacyPlotParams(self):
        """Compatibility alias for the centralized compatibility refresh path."""
        self.refreshCompatibilityViews()

    def updateSettings(self):
        """Compatibility alias that never reads persistence from the renderer."""
        self.refreshCompatibilityViews()

    def dispose(self):
        """Disconnect renderer-owned subscriptions and hover signal handlers."""
        self._disconnectHoverSignals()
        self._discardHoverMarker()
        unsubscribe = self._settings_unsubscribe
        self._settings_unsubscribe = None
        if unsubscribe is not None:
            unsubscribe()

    def clear(self):
        """Clear all stored series and renderer-owned graphics."""
        self._clearHoverReadout()
        self._clearPlotWidget()
        self._discardAllSeriesState()
        self._pending_session.clear()
        self._pending_graphics_by_series_id.clear()
        self._notify_pending_changed()
        self._notify_committed_changed()
        self._set_current_series(None)
        self._draw()

    def preparePlotValues(self):
        """Recompute plot values from active compatibility arrays."""
        data = self._buildTimeSeriesData(
            dates=self.dates, ts_values=self.ts_values, ref_values=self.ref_values
        )
        current = self.current_series()
        record = self._buildTimeSeriesRecord(
            data=data,
            presentation=current.presentation if current is not None else self.default_style.snapshotPresentation(),
            coords=self.coords,
            ref_coords=self.ref_coords,
            record_id=current.id if current is not None else None,
            source=current,
        )
        self._set_current_series(record)

    def _buildTimeSeriesData(self, *, dates=None, ts_values=None, ref_values=_UNSET) -> TimeSeriesData:
        """Build immutable numeric data without spatial-selection ownership."""
        if dates is None:
            dates = self.dates
        if ts_values is None:
            ts_values = self.ts_values
        if ref_values is _UNSET:
            ref_values = self.ref_values
        if dates is None:
            raise ValueError("dates are required to build time-series data")
        return buildTimeSeriesData(
            dates=dates, ts_values=ts_values, ref_values=ref_values
        )

    def _snapshotAnalysisDefaults(self) -> TimeSeriesAnalysis:
        """Copy persisted/session defaults without consulting the active record."""
        fit_defaults = self.settings_model.fit_analysis_defaults
        fit = FitConfiguration(
            enabled=fit_defaults.enabled,
            model=fit_defaults.model,
            seasonal=fit_defaults.seasonal,
            show_residuals=fit_defaults.show_residuals,
        )
        replica_defaults = self.settings_model.replica_analysis_defaults
        replica = ReplicaConfiguration(
            enabled=replica_defaults.enabled,
            interval_mm=replica_defaults.interval_mm,
            pair_count=self._validateReplicaPairCount(replica_defaults.pair_count),
        )
        return TimeSeriesAnalysis(fit=fit, replica=replica)

    def setNewRecordAnalysis(self, analysis: TimeSeriesAnalysis) -> None:
        """Set the explicit immutable analysis snapshot for genuine new records."""
        if not isinstance(analysis, TimeSeriesAnalysis):
            raise TypeError("analysis must be a TimeSeriesAnalysis")
        self._new_record_analysis = analysis

    def analysisForNewRecord(self) -> TimeSeriesAnalysis:
        """Return the controller-captured analysis used by the next new record."""
        return self._new_record_analysis

    def updateActiveAnalysis(
        self, *, fit=_UNSET, replica=_UNSET,
        report_statistics: bool = False,
    ) -> bool:
        """Transactionally replace active analysis and optionally report fit statistics."""
        current = self.editable_time_series_record()
        if current is None:
            return False
        analysis = current.analysis
        if fit is not _UNSET:
            analysis = replace(analysis, fit=fit)
        if replica is not _UNSET:
            analysis = replace(analysis, replica=replica)
        self.rerender_editable_record(
            replace(current, analysis=analysis),
            report_statistics=bool(report_statistics),
        )
        return True

    def updateActiveReplicaState(self, *, configuration, presentation) -> bool:
        """Replace active Replica calculation and visual state in one rerender."""
        current = self.editable_time_series_record()
        if current is None:
            return False
        updated = replace(
            current,
            analysis=replace(current.analysis, replica=configuration),
            presentation=replace(current.presentation, replica=presentation),
        )
        self.rerender_editable_record(updated)
        return True

    def _buildTimeSeriesRecord(
        self, *, data: TimeSeriesData, presentation: TimeSeriesPresentation,
        coords=_UNSET, ref_coords=_UNSET, record_id=None, source=None,
        analysis=_UNSET, fit=_UNSET, replica=_UNSET,
    ) -> TimeSeriesRecord:
        """Build one normalized record with explicit immutable analysis ownership."""
        if source is not None and record_id is not None and source.id != record_id:
            raise ValueError("source record UUID does not match requested record UUID")
        target = source.target if source is not None and coords is _UNSET else SpatialSelection.from_legacy(
            None if coords is _UNSET else coords
        )
        reference = source.reference if source is not None and ref_coords is _UNSET else SpatialSelection.from_legacy(
            None if ref_coords is _UNSET else ref_coords
        )
        if analysis is _UNSET:
            base_analysis = source.analysis if source is not None else self.analysisForNewRecord()
        else:
            base_analysis = analysis
        if fit is not _UNSET:
            base_analysis = replace(base_analysis, fit=fit)
        if replica is not _UNSET:
            base_analysis = replace(base_analysis, replica=replica)
        kwargs = {
            "data": data, "presentation": presentation, "analysis": base_analysis,
            "target": target, "reference": reference,
        }
        if record_id is not None:
            kwargs["id"] = record_id
        elif source is not None:
            kwargs["id"] = source.id
        return TimeSeriesRecord(**kwargs)

    def _set_current_series(self, record: Optional[TimeSeriesRecord]):
        """Refresh compatibility fields from the explicitly active record."""
        if record is None:
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
            self.fit_models = []
            self.fit_seasonal_flag = False
            self.plot_residuals_flag = False
            return
        series = record.data
        self.dates = series.dates
        self.ts_values = series.ts_values
        self.ref_values = series.ref_values
        self.plot_values = series.plot_values
        self.plot_multiple_values = series.plot_multiple_values
        self.min_plot_values = series.min_plot_values
        self.max_plot_values = series.max_plot_values
        self.residuals_values = series.residuals_values
        self.coords = record.target.value if record.target is not None else None
        self.ref_coords = record.reference.value if record.reference is not None else None
        fit = record.analysis.fit
        self.fit_models = [fit.model] if fit.enabled and fit.model else []
        self.fit_seasonal_flag = fit.seasonal
        self.plot_residuals_flag = fit.show_residuals and fit.enabled
        if self.analysis_state_sync_callback is not None:
            self.analysis_state_sync_callback(record)

    def initializeAxes(self):
        """Initialize plot items while preserving any stored records."""
        layout_matches = (
            self.ax is not None
            and ((self.plot_residuals_flag and self.ax_residuals is not None)
                 or (not self.plot_residuals_flag and self.ax_residuals is None))
        )
        if layout_matches:
            return

        if self._series_store.records() or self.pending_record() is not None:
            self._rebuild_axes_and_rerender_history()
            return

        self._clearPlotWidget()
        self._graphics_by_series_id.clear()
        self._createAxesForCurrentLayout()

    def _createAxesForCurrentLayout(self) -> None:
        """Create axes matching the current residual-layout flag."""
        self._connectHoverSignals()
        self.ax = self._addPlot(row=0)
        self._ensureHoverMarker()
        if self.plot_residuals_flag:
            self.ax_residuals = self._addPlot(row=1)
            self.ax_residuals.setXLink(self.ax)
        else:
            self.ax_residuals = None

    def _rebuild_axes_and_rerender_history(self) -> None:
        """Recreate axes and re-render retained records with stable identity."""
        retained_records = self._series_store.records()
        retained_pending = self.pending_record()
        active_id = self._series_store.active_id()
        self._clearPlotWidget()
        self._graphics_by_series_id.clear()
        self._pending_graphics_by_series_id.clear()
        self._createAxesForCurrentLayout()

        rebuilt_records = []
        rebuilt_pending = None
        try:
            for record in retained_records:
                if record.id in self._hidden_committed_ids:
                    rebuilt_records.append(record)
                    continue
                graphics, rebuilt_record, transaction = self._build_record_graphics(record)
                rebuilt_records.append(rebuilt_record)
                self._register_series_graphics(rebuilt_record, graphics)
                transaction.commit()
            if retained_pending is not None:
                graphics, rebuilt_pending, transaction = self._build_record_graphics(retained_pending)
                self._pending_graphics_by_series_id[rebuilt_pending.id] = graphics
                transaction.commit()
        except Exception:
            # Clearing the widget destroys any partially created canvas items.
            # Records and registry are then discarded together so callers never
            # observe a partially rebuilt retained-series state.
            self._clearPlotWidget()
            self._discardAllSeriesState()
            self._createAxesForCurrentLayout()
            raise

        self._series_store.replace_many(rebuilt_records)
        if rebuilt_pending is not None:
            self._pending_session.set(rebuilt_pending)
        if active_id is not None:
            self._series_store.set_active(active_id)
        active = self.editable_time_series_record()
        self._set_current_series(active)
        self._rebuildYDataRanges()
        self.applyYAxisPolicy()

    def plotTs(self, *, dates=None, ts_values=None, ref_values=_UNSET, plot_multiple=True, coords=_UNSET,
               ref_coords=_UNSET, update=False, analysis=_UNSET, report_statistics=False):
        """Render under the nested-safe axis guard and normalize first-plot state."""
        initial_plot = self.ax is None
        with self.axisViewUpdateGuard():
            result = self._plotTsGuarded(
                dates=dates, ts_values=ts_values, ref_values=ref_values,
                plot_multiple=plot_multiple, coords=coords, ref_coords=ref_coords,
                update=update, analysis=analysis, report_statistics=report_statistics,
            )
        if initial_plot and self.ax is not None:
            x_state = replace(self.settings_model.x_axis, custom_view=False)
            y_state = replace(
                self.settings_model.y_axis,
                series_custom_view=False, residual_custom_view=False,
            )
            with self.settings_model.batch_update():
                self.settings_model.replace_domain("x_axis", x_state)
                self.settings_model.replace_domain("y_axis", y_state)
            if self.axis_state_sync_callback is not None:
                self.axis_state_sync_callback()
        return result

    def _plotTsGuarded(self, *, dates=None, ts_values=None, ref_values=_UNSET, plot_multiple=True, coords=_UNSET,
                       ref_coords=_UNSET, update=False, analysis=_UNSET, report_statistics=False):
        # update: flag indicating if the plot should be updated or a new one created

        self.updateSettings()
        source_snapshot = self.editable_time_series_record() if update else None

        if update:
            if source_snapshot is None:
                return
            source_data = source_snapshot.data
            dates = source_data.dates if dates is None else dates
            ts_values = source_data.ts_values if ts_values is None else ts_values
            ref_values = source_data.ref_values if ref_values is _UNSET else ref_values
            random_marker_color_flag = False
            presentation = source_snapshot.presentation
        else:
            random_marker_color_flag = self.random_marker_color_flag
            presentation = self.default_style.snapshotPresentation()

        if dates is None and self.dates is None:
            return

        # Build the complete immutable record before selecting the axes layout.
        # In particular, a genuine new record's residual intent must determine
        # whether the residual axis exists before any graphics are attached.
        series = self._buildTimeSeriesData(
            dates=dates, ts_values=ts_values, ref_values=ref_values,
        )
        if not series.hasFinitePlotValues():
            return

        if random_marker_color_flag:
            rand_color = randomTimeSeriesColor()
            presentation = replace(
                presentation,
                series=replace(
                    presentation.series,
                    marker_color=rand_color,
                    line_color=rand_color,
                ),
            )

        record_analysis = _UNSET if update or analysis is None else analysis
        # explicit update actions may omit one spatial field.  Preserve all
        # unrelated ownership from the complete source record instead of
        # interpreting a reference-only update as a target clear.
        if update and coords is None:
            coords = _UNSET

        record = self._buildTimeSeriesRecord(
            data=series, presentation=presentation, coords=coords, ref_coords=ref_coords,
            record_id=source_snapshot.id if source_snapshot is not None else None,
            source=source_snapshot, analysis=record_analysis,
        )
        fit = record.analysis.fit
        self.plot_residuals_flag = bool(fit.enabled and fit.show_residuals)
        self.initializeAxes()
        if update:
            self.rerender_editable_record(
                record, plot_multiple=plot_multiple,
                report_statistics=report_statistics,
            )
        else:
            if not (record.presentation.label or "").strip():
                record = replace(
                    record,
                    presentation=replace(
                        record.presentation, label=self._default_pending_label(record)
                    ),
                )
            self.set_pending_record(
                record, plot_multiple=plot_multiple,
                report_statistics=report_statistics,
            )
        self.applyYAxisPolicy()
        self._draw()

    def _commit_rendered_record_replacement(
        self,
        previous: TimeSeriesRecord,
        replacement: TimeSeriesRecord,
        graphics: TimeSeriesGraphics = None,
    ) -> TimeSeriesGraphics:
        """Compatibility adapter for the canonical UUID rerender transaction."""
        if previous.id != replacement.id:
            raise ValueError("replacement record must preserve the original UUID")
        current = self._series_store.get(previous.id)
        if current is None:
            raise KeyError(f"time-series record not found: {previous.id}")
        return self.rerender_record(replacement)

    def _render_and_store_series(
        self, record: TimeSeriesRecord, *,
        plot_multiple: bool = True, report_statistics: bool = False,
        replacement: bool = False,
    ) -> TimeSeriesRecord:
        """Render and atomically register one normalized record."""
        try:
            self.render_record(
                record,
                plot_multiple=plot_multiple,
                report_statistics=report_statistics,
                add_to_store=True,
            )
        except Exception:
            if replacement:
                self._clearPlotWidget()
                self._discardAllSeriesState()
                self._createAxesForCurrentLayout()
            raise
        rendered_record = self._series_store.get(record.id)
        if rendered_record is None:
            raise RuntimeError(f"rendered record was not stored: {record.id}")
        self._set_current_series(rendered_record)
        return rendered_record

    def _build_record_graphics(
        self, record: TimeSeriesRecord, *, plot_multiple: bool = True,
        report_statistics: bool = False,
    ) -> Tuple[TimeSeriesGraphics, TimeSeriesRecord, _GraphicsRenderTransaction]:
        """Build complete graphics with tracked attachment and guaranteed rollback."""
        transaction = _GraphicsRenderTransaction(self)
        try:
            render = self._render_time_series
            parameters = inspect.signature(render).parameters
            accepts_keywords = any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in parameters.values()
            )
            if "transaction" in parameters or accepts_keywords:
                graphics, residuals = render(
                    record,
                    plot_multiple=plot_multiple,
                    report_statistics=report_statistics,
                    transaction=transaction,
                )
            else:
                graphics, residuals = render(record)
        except Exception:
            transaction.rollback()
            raise
        rendered_record = record if residuals is None else replace(
            record, data=record.data.withResiduals(residuals)
        )
        # Presentation visibility is authoritative. Apply it to every newly
        # created graphics bundle before registry/store commit so no render or
        # rerender path can temporarily publish the wrong visibility state.
        self._set_graphics_visible(graphics, rendered_record.presentation.visible)
        return graphics, rendered_record, transaction

    def render_record(
        self, record: TimeSeriesRecord, *, plot_multiple: bool = True,
        report_statistics: bool = False, add_to_store: bool = False,
    ) -> TimeSeriesGraphics:
        """Transactionally render and register one explicit record by UUID."""
        if record.id in self._graphics_by_series_id:
            raise ValueError(f"time-series record is already rendered: {record.id}")
        existing = self._series_store.get(record.id)
        if add_to_store and existing is not None:
            raise ValueError(f"time-series record already exists: {record.id}")
        if not add_to_store and existing is None:
            raise KeyError(f"time-series record not found: {record.id}")

        graphics, rendered_record, transaction = self._build_record_graphics(
            record, plot_multiple=plot_multiple,
            report_statistics=report_statistics,
        )
        store_changed = False
        try:
            if add_to_store:
                self._series_store.add(rendered_record, make_active=True)
                store_changed = True
            elif rendered_record is not record:
                if not self._series_store.replace(rendered_record):
                    raise KeyError(f"time-series record not found: {record.id}")
                store_changed = True
            self._register_series_graphics(rendered_record, graphics)
        except Exception:
            self._graphics_by_series_id.pop(record.id, None)
            if add_to_store and store_changed:
                self._series_store.remove(record.id)
            elif store_changed and existing is not None:
                self._series_store.replace(existing)
            transaction.rollback()
            raise
        transaction.commit()
        self._rebuildYDataRanges()
        return graphics

    def rerender_record(
        self, record: TimeSeriesRecord, *, plot_multiple: bool = True,
        report_statistics: bool = False,
    ) -> TimeSeriesGraphics:
        """Replace one rendered UUID while preserving old canvas state on failure."""
        current = self._series_store.get(record.id)
        if current is None:
            raise KeyError(f"time-series record not found: {record.id}")
        old_graphics = self._graphics_by_series_id.get(record.id)
        if old_graphics is None:
            raise KeyError(f"time-series graphics not found: {record.id}")
        new_graphics, rendered_record, transaction = self._build_record_graphics(
            record, plot_multiple=plot_multiple,
            report_statistics=report_statistics,
        )
        store_replaced = False
        try:
            if not self._series_store.replace(rendered_record):
                raise KeyError(f"time-series record not found: {record.id}")
            store_replaced = True
            self._graphics_by_series_id[record.id] = new_graphics
        except Exception:
            self._graphics_by_series_id[record.id] = old_graphics
            transaction.rollback()
            if store_replaced:
                self._series_store.replace(current)
            raise

        transaction.commit()
        self._detach_graphics(old_graphics)
        active = self.current_series()
        self._set_current_series(active)
        self._rebuildYDataRanges()
        self.applyYAxisPolicy()
        return new_graphics

    def replace_and_rerender_records(self, records, *, notify=True, draw=True):
        """Atomically replace all records and rerender visible records once.

        Visibility controls canvas ownership only. Hidden replacements are
        committed to the authoritative store without constructing graphics;
        their Fit residual cache remains invalidated and is recomputed when the
        record is shown. Visible replacements are fully rendered before any
        store mutation, preserving all-or-nothing domain semantics.
        """
        replacements = tuple(records)
        if not replacements:
            return ()
        ids = [record.id for record in replacements]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate time-series replacement UUID")

        previous = []
        visible_records = []
        old_visible_graphics = {}
        old_hidden_graphics = {}
        for record in replacements:
            current = self._series_store.get(record.id)
            if current is None:
                raise KeyError(
                    "committed time-series record not found: {}".format(record.id)
                )
            previous.append(current)
            if record.id not in self._hidden_committed_ids:
                graphics = self._graphics_by_series_id.get(record.id)
                if graphics is None:
                    raise KeyError(
                        "visible committed time-series graphics not found: {}".format(
                            record.id
                        )
                    )
                visible_records.append(record)
                old_visible_graphics[record.id] = graphics
            else:
                stale = self._graphics_by_series_id.get(record.id)
                if stale is not None:
                    old_hidden_graphics[record.id] = stale

        built_by_id = {}
        try:
            for record in visible_records:
                built_by_id[record.id] = self._build_record_graphics(record)
        except Exception:
            for _graphics, _record, transaction in built_by_id.values():
                transaction.rollback()
            raise

        rendered_by_id = {
            record_id: built[1] for record_id, built in built_by_id.items()
        }
        committed_replacements = tuple(
            rendered_by_id.get(record.id, record) for record in replacements
        )
        try:
            self._series_store.replace_many(committed_replacements)
            for record_id, (graphics, _record, _transaction) in built_by_id.items():
                self._graphics_by_series_id[record_id] = graphics
            # Hidden records must never retain renderer ownership. Registry
            # cleanup is committed here; physical detachment follows after the
            # replacement transaction can no longer roll back.
            for record_id in old_hidden_graphics:
                self._graphics_by_series_id.pop(record_id, None)
        except Exception:
            self._series_store.replace_many(previous)
            for record_id, graphics in old_visible_graphics.items():
                self._graphics_by_series_id[record_id] = graphics
            for record_id, graphics in old_hidden_graphics.items():
                self._graphics_by_series_id[record_id] = graphics
            for _graphics, _record, transaction in built_by_id.values():
                transaction.rollback()
            raise

        for _graphics, _record, transaction in built_by_id.values():
            transaction.commit()
        for graphics in old_visible_graphics.values():
            self._detach_graphics(graphics)
        for graphics in old_hidden_graphics.values():
            self._detach_graphics(graphics)
        active = self.current_series()
        self._set_current_series(active)
        self._rebuildYDataRanges()
        self.applyYAxisPolicy()
        if draw:
            self._draw()
        if notify:
            self._notify_committed_changed()
        return committed_replacements

    def rerender_records(self, records, *, notify=True, draw=True):
        """Compatibility wrapper for atomic replacement and visible rerendering."""
        return self.replace_and_rerender_records(
            records, notify=notify, draw=draw
        )

    @staticmethod
    def _graphics_items(graphics: TimeSeriesGraphics):
        """Yield every renderer-owned item in one graphics bundle."""
        for item in (
            graphics.scatter, graphics.line, graphics.fit_plot,
            graphics.residual_scatter, graphics.residual_line,
        ):
            if item is not None:
                yield item
        for group in (
            graphics.plot_multiple_fill, graphics.plot_multiple_lines,
            graphics.replicate_up, graphics.replicate_dn,
        ):
            for item in group or ():
                if item is not None:
                    yield item

    def _main_graphics_item_ids(self, graphics):
        return {
            id(item) for item in (
                graphics.scatter, graphics.line, graphics.fit_plot,
                *(graphics.plot_multiple_fill or ()),
                *(graphics.plot_multiple_lines or ()),
                *(graphics.replicate_up or ()), *(graphics.replicate_dn or ()),
            ) if item is not None
        }

    def _detach_graphics(self, graphics: TimeSeriesGraphics) -> None:
        """Detach all items in a graphics bundle without changing the registry."""
        main_ids = self._main_graphics_item_ids(graphics)
        for item in self._graphics_items(graphics):
            self._removeItem(self.ax if id(item) in main_ids else self.ax_residuals, item)

    def remove_rendered_record(
        self, record_id: UUID
    ) -> Optional[TimeSeriesGraphics]:
        """Idempotently remove all canvas graphics for one UUID only."""
        graphics = self._graphics_by_series_id.pop(record_id, None)
        if graphics is None:
            return None
        self._detach_graphics(graphics)
        return graphics

    @staticmethod
    def _graphics_visible(graphics: TimeSeriesGraphics) -> bool:
        for item in PlotTs._graphics_items(graphics):
            getter = getattr(item, "isVisible", None)
            if getter is not None:
                return bool(getter())
        return True

    @staticmethod
    def _set_graphics_visible(graphics: TimeSeriesGraphics, visible: bool) -> None:
        for item in PlotTs._graphics_items(graphics):
            setter = getattr(item, "setVisible", None)
            if setter is not None:
                setter(bool(visible))

    def set_record_visible(self, record_id: UUID, visible: bool) -> bool:
        """Persist and apply visibility for one stored time-series record."""
        record = self._series_store.get(record_id)
        if record is None:
            return False

        visible = bool(visible)
        if record.presentation.visible != visible:
            updated = replace(
                record,
                presentation=replace(record.presentation, visible=visible),
            )
            if not self._series_store.replace(updated):
                raise KeyError(f"time-series record not found: {record_id}")
            record = updated

        graphics = self._graphics_by_series_id.get(record_id)
        if graphics is not None:
            self._set_graphics_visible(graphics, visible)

        if self._series_store.active_id() == record_id:
            self._set_current_series(record)
        return True

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
        self, record: TimeSeriesRecord, *,
        plot_multiple=True, report_statistics=False, transaction=None
    ) -> Tuple[TimeSeriesGraphics, Optional[np.ndarray]]:
        """Render numeric and analysis graphics from one explicit record."""
        series = record.data
        presentation = record.presentation
        analysis = record.analysis
        items = TimeSeriesGraphics()
        main_y_data = []
        series_style = presentation.series
        ensemble_style = presentation.ensemble
        marker = series_style.marker
        marker_size = series_style.marker_size
        marker_color = series_style.marker_color
        marker_alpha = series_style.marker_opacity
        edge_color = series_style.marker_edge_color
        line_style = series_style.line_style
        line_color = series_style.line_color
        line_alpha = series_style.line_opacity
        line_width = series_style.line_width
        x = self._datesToX(series.dates)

        if plot_multiple and series.min_plot_values is not None:
            lower_bound = series.min_plot_values
            upper_bound = series.max_plot_values
            series_fill_color = ensemble_style.fill_color
            series_fill_alpha = ensemble_style.fill_alpha
            if series_fill_alpha > 0:
                lower_line = pg.PlotCurveItem(x, lower_bound, pen=None)
                upper_line = pg.PlotCurveItem(x, upper_bound, pen=None)
                fill = pg.FillBetweenItem(
                    lower_line, upper_line,
                    brush=self._brush(series_fill_color, series_fill_alpha)
                )
                transaction.add_item(self.ax, lower_line)
                transaction.add_item(self.ax, upper_line)
                transaction.add_item(self.ax, fill)
                items.plot_multiple_fill = [lower_line, upper_line, fill]
            main_y_data.extend([lower_bound, upper_bound])

        if series.plot_multiple_values is not None:
            series_line_style = '-'
            series_line_color = ensemble_style.member_line_color
            series_line_alpha = ensemble_style.member_line_alpha
            series_line_width = ensemble_style.member_line_width
            if series_line_width > 0 and series_line_alpha > 0:
                for i in range(series.plot_multiple_values.shape[1]):
                    item = pg.PlotDataItem(
                        x, series.plot_multiple_values[:, i],
                        pen=self._pen(series_line_color, series_line_width, series_line_alpha, series_line_style)
                    )
                    transaction.add_item(self.ax, item)
                    items.plot_multiple_lines.append(item)
            for i in range(series.plot_multiple_values.shape[1]):
                main_y_data.append(series.plot_multiple_values[:, i])

        if marker_size > 0 and marker_alpha > 0:
            items.scatter = pg.ScatterPlotItem(x=x, y=series.plot_values, symbol=self._symbol(marker),
                                               size=marker_size,
                                               pen=self._pen(edge_color, 0.2, marker_alpha),
                                               brush=self._brush(marker_color, marker_alpha))
            transaction.add_item(self.ax, items.scatter)

        main_y_data.append(series.plot_values)

        if line_style and line_width > 0 and line_alpha > 0:
            items.line = pg.PlotDataItem(
                x,
                series.plot_values,
                pen=self._pen(line_color, line_width, line_alpha, line_style))
            transaction.add_item(self.ax, items.line)

        if analysis.replica.enabled:
            items.replicate_up, items.replicate_dn = self.plotReplicas(
                series, presentation.replica, analysis.replica, transaction=transaction
            )
        else:
            items.replicate_up, items.replicate_dn = [None], [None]

        main_y_data.extend(self._last_replica_y_data)
        self._last_replica_y_data = []
        items.main_y_data = main_y_data
        self.decoratePlot(parms=self.parms.get("time series plot", {}))
        items.fit_plot, residuals_values = self.fitModel(
            series, presentation, analysis.fit, items, report_statistics=report_statistics,
            transaction=transaction
        )

        self.decorateFigure(parms=self.parms.get("figure", {}))
        return items, residuals_values

    def plotReplicas(
        self, series: TimeSeriesData, replica_style,
        replica_config: ReplicaConfiguration, transaction=None,
    ):
        """Render Replica overlays from record-owned visual and calculation state."""
        replica = replica_style
        x = self._datesToX(series.dates)
        marker_color_1 = replica.color_1  # replica up
        marker_color_2 = replica.color_2  # replica down
        marker_alpha = replica.opacity
        marker_size_replica = replica.marker_size
        marker_replica = replica.marker
        replica_pair_count = self._validateReplicaPairCount(replica_config.pair_count)
        self._last_replica_y_data = []

        # Plot symmetric positive/negative replica pairs around the source series.
        replicate_up_list = []
        replicate_dn_list = []
        for i in range(replica_pair_count):
            replicate_value = replica_config.interval_mm * (i + 1)

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
            transaction.add_item(self.ax, replicate_up)
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
            transaction.add_item(self.ax, replicate_dn)
            replicate_dn_list.append(replicate_dn)
            self._last_replica_y_data.append(series.plot_values - replicate_value)

        return replicate_up_list, replicate_dn_list

    def fitModel(
        self, series: TimeSeriesData, presentation: TimeSeriesPresentation,
        fit_config: FitConfiguration, graphics=None, *,
        report_statistics=False, transaction=None
    ):
        if series.plot_values is None:
            return None, None
        if series.dates is None:
            return None, None
        if not fit_config.enabled or not fit_config.model:
            return None, None

        fit_style = presentation.fit
        fit_line_type = fit_style.line_style
        fit_line_color = fit_style.line_color
        fit_line_alpha = fit_style.line_alpha
        fit_line_width = fit_style.line_width
        fit_seasonal = fit_config.seasonal
        fit_model = fit_config.model
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
            fit_plot = pg.PlotDataItem(
                self._datesToX(model_x),
                model_y,
                pen=self._pen(fit_line_color, fit_line_width, fit_line_alpha, fit_line_type)
            )
            transaction.add_item(self.ax, fit_plot)
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
        self.plotResiduals(
            series, presentation, fit_config, graphics, residuals_values, transaction=transaction
        )
        if report_statistics and self.fit_success_callback is not None:
            self.fit_success_callback(
                fit_model, statistics, seasonal=fit_seasonal
            )
        return fit_plot, residuals_values

    def _normalizedResidualStyle(self, presentation: TimeSeriesPresentation):
        """Return the record-owned residual appearance."""
        return presentation.residual

    def plotResiduals(
        self, series: TimeSeriesData, presentation: TimeSeriesPresentation,
        fit_config: FitConfiguration, items=None, residuals_values=None, transaction=None,
    ):
        if items is None:
            items = TimeSeriesGraphics()
        if residuals_values is None:
            residuals_values = series.residuals_values
        if (
                fit_config.show_residuals
                and fit_config.enabled
                and self.ax_residuals is not None
                and residuals_values is not None
        ):
            residual_style = self._normalizedResidualStyle(presentation)
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
                transaction.add_item(self.ax_residuals, items.residual_scatter)
            if line_style and line_width > 0 and line_alpha > 0:
                items.residual_line = pg.PlotDataItem(
                    x,
                    residuals_values,
                    pen=self._pen(line_color, line_width, line_alpha, line_style)
                )
                transaction.add_item(self.ax_residuals, items.residual_line)
            items.residual_y_data = [residuals_values]
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

    def applyYAxisPolicy(self) -> None:
        """Apply committed canvas Y policies after all graphics/layout changes."""
        with self.axisViewUpdateGuard():
            if self.ax is not None:
                self.setYlims(ax=self.ax, parms=self.parms.get("time series plot", {}))
            if self.ax_residuals is not None:
                self.setYlims(ax=self.ax_residuals, parms=self.parms.get("residual plot", {}))

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
        marker = self._hover_marker
        marker_was_visible = False
        if marker is not None:
            try:
                marker_was_visible = bool(marker.isVisible())
                marker.hide()
            except RuntimeError:
                marker = None
        try:
            return TimeSeriesPlotExporter(self).export(filename)
        finally:
            if marker is not None and marker_was_visible:
                try:
                    marker.show()
                except RuntimeError:
                    pass

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

    def _connectHoverSignals(self):
        """Connect one plot-scene hover handler for this renderer instance."""
        plot_widget = getattr(self.ui, "plot_widget", None)
        if plot_widget is None:
            return
        try:
            scene = plot_widget.scene()
        except RuntimeError:
            return
        if plot_widget is self._hover_widget and scene is self._hover_scene:
            return
        self._disconnectHoverSignals()
        try:
            scene.sigMouseMoved.connect(self._handleHoverMouseMoved)
        except (AttributeError, RuntimeError):
            return
        mouse_left = getattr(plot_widget, "mouseLeft", None)
        if mouse_left is not None:
            try:
                mouse_left.connect(self._clearHoverReadout)
            except (AttributeError, RuntimeError):
                try:
                    scene.sigMouseMoved.disconnect(self._handleHoverMouseMoved)
                except (AttributeError, TypeError, RuntimeError):
                    pass
                return
        self._hover_widget = plot_widget
        self._hover_scene = scene

    def _disconnectHoverSignals(self):
        """Disconnect renderer-owned hover signals without affecting other users."""
        scene = self._hover_scene
        plot_widget = self._hover_widget
        if scene is not None:
            try:
                scene.sigMouseMoved.disconnect(self._handleHoverMouseMoved)
            except (TypeError, RuntimeError):
                pass
        mouse_left = getattr(plot_widget, "mouseLeft", None) if plot_widget is not None else None
        if mouse_left is not None:
            try:
                mouse_left.disconnect(self._clearHoverReadout)
            except (TypeError, RuntimeError):
                pass
        self._hover_widget = None
        self._hover_scene = None

    def _discardHoverMarker(self):
        """Detach and forget the transient hover marker without touching series graphics."""
        marker = self._hover_marker
        plot_item = self._hover_marker_plot
        if marker is not None:
            try:
                marker.hide()
            except RuntimeError:
                pass
        if marker is not None and plot_item is not None:
            try:
                plot_item.removeItem(marker)
            except (AttributeError, RuntimeError):
                pass
        self._hover_marker = None
        self._hover_marker_plot = None

    def _ensureHoverMarker(self):
        """Create the single reusable hover marker after the primary plot exists."""
        plot_item = self.ax
        if plot_item is None:
            return None
        if self._hover_marker is not None and self._hover_marker_plot is plot_item:
            return self._hover_marker
        self._discardHoverMarker()
        marker = pg.ScatterPlotItem(
            x=[], y=[], symbol='o', size=8,
            pen=pg.mkPen(self._hoverMarkerFallbackColor(), width=10),
            brush=pg.mkBrush(0, 0, 0, 0),
        )
        marker.setZValue(1e6)
        marker.hide()
        plot_item.addItem(marker)
        self._hover_marker = marker
        self._hover_marker_plot = plot_item
        return marker

    def _hoverMarkerFallbackColor(self):
        """Return the plot foreground color for a theme-safe marker fallback."""
        if self.ax is not None:
            try:
                pen = self.ax.getAxis('left').textPen()
                if pen is not None:
                    return pen.color()
            except (AttributeError, RuntimeError):
                pass
        plot_widget = getattr(self.ui, "plot_widget", None)
        if plot_widget is not None:
            try:
                return plot_widget.palette().color(QPalette.WindowText)
            except (AttributeError, RuntimeError):
                pass
        try:
            return QApplication.palette().color(QPalette.WindowText)
        except RuntimeError:
            return QColor()

    def _hoverMarkerColor(self, series_id):
        """Return a readily available series color for the hover ring."""
        record = self._series_store.get(series_id) if series_id is not None else None
        if record is None:
            pending = self.pending_record()
            if pending is not None and pending.id == series_id:
                record = pending
        if record is None:
            return self._hoverMarkerFallbackColor()
        graphics = self._graphics_by_series_id.get(series_id)
        if graphics is None:
            graphics = self._pending_graphics_by_series_id.get(series_id)
        style = record.presentation.series
        if graphics is not None and graphics.scatter is not None:
            return self._color(style.marker_color)
        if graphics is not None and graphics.line is not None:
            return self._color(style.line_color)
        return self._hoverMarkerFallbackColor()

    def _updateHoverMarker(self, observation):
        """Move the reusable hover ring to the already resolved observation."""
        if observation is None:
            self._hideHoverMarker()
            return
        marker = self._ensureHoverMarker()
        if marker is None:
            return
        marker.setData(
            x=[float(observation.plot_x)],
            y=[float(observation.plot_y)],
            pen=pg.mkPen(self._hoverMarkerColor(observation.series_id), width=1),
            brush=pg.mkBrush(0, 0, 0, 0),
            symbol='o',
            size=8,
        )
        marker.show()

    def _hideHoverMarker(self):
        """Hide the transient hover ring if it currently exists."""
        marker = self._hover_marker
        if marker is not None:
            try:
                marker.hide()
            except RuntimeError:
                pass

    def _clearHoverReadout(self):
        """Clear the plot-local hover readout if the toolbar is available."""
        self._hideHoverMarker()
        toolbar = getattr(self.ui, "time_series_toolbar", None)
        if toolbar is not None and hasattr(toolbar, "setHoverReadout"):
            toolbar.setHoverReadout("")

    @staticmethod
    def _observationGraphicsVisible(graphics):
        """Return whether the record's real observation markers or line are visible."""
        for item in (graphics.scatter, graphics.line):
            if item is None:
                continue
            is_visible = getattr(item, "isVisible", None)
            if is_visible is None or bool(is_visible()):
                return True
        return False

    def _iterHoverRecords(self):
        """Yield visible records that still own live observation graphics."""
        for record in self._series_store.records():
            graphics = self._graphics_by_series_id.get(record.id)
            if (
                graphics is not None
                and record.presentation.visible
                and self._observationGraphicsVisible(graphics)
            ):
                yield record
        pending = self.pending_record()
        if pending is not None:
            graphics = self._pending_graphics_by_series_id.get(pending.id)
            if (
                graphics is not None
                and pending.presentation.visible
                and self._observationGraphicsVisible(graphics)
            ):
                yield pending

    def _hoverObservations(self):
        """Build lightweight scene-space observations from currently plotted data."""
        if self.ax is None:
            return ()
        view_box = self.ax.getViewBox()
        observations = []
        for record in self._iterHoverRecords():
            dates = record.data.dates
            values = np.asarray(record.data.plot_values, dtype=float).reshape(-1)
            x_values = self._datesToX(dates)
            for date, x_value, value in zip(dates, x_values, values):
                if not np.isfinite(value) or not np.isfinite(x_value):
                    continue
                scene_point = view_box.mapViewToScene(
                    QPointF(float(x_value), float(value))
                )
                observations.append(HoverObservation(
                    date=date,
                    value=float(value),
                    scene_x=float(scene_point.x()),
                    scene_y=float(scene_point.y()),
                    plot_x=float(x_value),
                    plot_y=float(value),
                    series_id=record.id,
                ))
        return observations

    def _handleHoverMouseMoved(self, scene_pos):
        """Show the nearest real observation when the pointer is close enough."""
        if self.ax is None or not self.ax.sceneBoundingRect().contains(scene_pos):
            self._clearHoverReadout()
            return
        observation = select_nearest_hover_observation(
            self._hoverObservations(),
            float(scene_pos.x()),
            float(scene_pos.y()),
            tolerance_px=self._hover_tolerance_px,
        )
        toolbar = getattr(self.ui, "time_series_toolbar", None)
        if toolbar is not None and hasattr(toolbar, "setHoverReadout"):
            toolbar.setHoverReadout(format_hover_text(observation))
        self._updateHoverMarker(observation)

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
        self._clearHoverReadout()
        self._discardHoverMarker()
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
        self._series_store.clear()
        self._hidden_committed_ids.clear()
        self._graphics_by_series_id.clear()
        self._set_current_series(None)
        self._y_data_ranges = {}
        self._last_replica_y_data = []

    def _graphics_for_series(
        self, series: TimeSeriesRecord
    ) -> Optional[TimeSeriesGraphics]:
        """Return runtime graphics registered for a stored series."""
        return self._graphics_by_series_id.get(series.id) or self._pending_graphics_by_series_id.get(series.id)

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
        here would make settings changes apply only to future plots instead of
        updating the current editable or active record.
        """
        active = self.current_series()
        if active is None:
            return None
        snapshot = self.remove_series_by_id(active.id)
        if snapshot is None:
            return None
        self._remove_snapshot_graphics(snapshot)
        current = self.current_series()
        if current is not None:
            self._set_current_series(current)
        else:
            self._set_current_series(snapshot)
        self._rebuildYDataRanges()
        self._draw()
        return snapshot

    def _remove_snapshot_graphics(self, snapshot: TimeSeriesRecord) -> None:
        """Compatibility wrapper for UUID-based rendered-record removal."""
        self.remove_rendered_record(snapshot.id)

    def _rebuildYDataRanges(self):
        self._y_data_ranges = {}
        records = list(self.series_history)
        pending = self.pending_record()
        if pending is not None:
            records.append(pending)
        for snapshot in records:
            graphics = self._graphics_for_series(snapshot)
            if graphics is not None:
                self.updateYlim(ax=self.ax, y_data=graphics.main_y_data)
        if self.ax_residuals is not None:
            for snapshot in records:
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
        records = tuple(records)
        if not records:
            return
        self._series_store.replace_many(records)
        current = self.current_series()
        self._set_current_series(current)

    def rerenderTimeSeriesSnapshots(
        self, snapshots: List[TimeSeriesSnapshot], *, draw: bool = True
    ) -> None:
        """Rerender selected records by UUID without reordering store records."""
        with self.preserveViewport():
            for snapshot in snapshots:
                self.rerender_editable_record(snapshot)
        if draw:
            self._draw()

    def selectedTimeSeriesSnapshots(self) -> List[TimeSeriesSnapshot]:
        """Return pending first, otherwise the active committed record."""
        snapshot = self.editable_time_series_record()
        return [snapshot] if snapshot is not None else []

    def hasSelectedTimeSeries(self) -> bool:
        """Return whether at least one time-series snapshot is selected."""
        return bool(self.selectedTimeSeriesSnapshots())

    def selectedTimeSeriesCount(self) -> int:
        """Return the number of selected time-series snapshots."""
        return len(self.selectedTimeSeriesSnapshots())

    def setCurrentSeriesStyleAsDefault(self) -> bool:
        """Copy the current series style into the new-series default source."""
        snapshot = self.editable_time_series_record()
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
        """Store a time-series record and make it active."""
        self._series_store.add(snapshot, make_active=True)

    def pending_record(self) -> Optional[TimeSeriesRecord]:
        """Return the uncommitted record, if any."""
        return self._pending_session.record()

    def has_exportable_plot(self) -> bool:
        """Return whether renderer-owned visible time-series graphics exist."""
        graphics_groups = (
            tuple(self._pending_graphics_by_series_id.values()),
            tuple(self._graphics_by_series_id.values()),
        )
        for graphics_group in graphics_groups:
            for graphics in graphics_group:
                for item in self._graphics_items(graphics):
                    is_visible = getattr(item, "isVisible", None)
                    if is_visible is None or bool(is_visible()):
                        return True
        return False

    def editable_time_series_record(self) -> Optional[TimeSeriesRecord]:
        """Return pending first, otherwise the active committed record."""
        return resolve_editable_record(self.pending_record(), self.current_series())

    def _notify_pending_changed(self) -> None:
        if self.pending_changed_callback is not None:
            self.pending_changed_callback(self.pending_record())

    def _notify_committed_changed(self) -> None:
        if self.committed_changed_callback is not None:
            self.committed_changed_callback(self._series_store.records())

    def notify_committed_changed(self) -> None:
        """Publish the current committed-record projection."""
        self._notify_committed_changed()

    def set_pending_record(self, record, *, plot_multiple=True, report_statistics=False):
        """Transactionally render and replace the current pending record."""
        previous = self.pending_record()
        previous_graphics = None if previous is None else self._pending_graphics_by_series_id.get(previous.id)
        graphics, rendered_record, transaction = self._build_record_graphics(
            record, plot_multiple=plot_multiple, report_statistics=report_statistics
        )
        try:
            self._pending_session.set(rendered_record)
            self._pending_graphics_by_series_id = {rendered_record.id: graphics}
        except Exception:
            transaction.rollback()
            raise
        transaction.commit()
        if previous_graphics is not None:
            self._detach_graphics(previous_graphics)
        self._set_current_series(rendered_record)
        self._rebuildYDataRanges()
        self._notify_pending_changed()
        return rendered_record

    def rerender_editable_record(self, record, *, plot_multiple=True, report_statistics=False):
        """Replace the correct pending or committed owner by UUID."""
        pending = self.pending_record()
        if pending is not None and pending.id == record.id:
            old_graphics = self._pending_graphics_by_series_id.get(record.id)
            if old_graphics is None:
                raise KeyError(f"pending graphics not found: {record.id}")
            graphics, rendered_record, transaction = self._build_record_graphics(
                record, plot_multiple=plot_multiple, report_statistics=report_statistics
            )

            # Publish session and registry ownership together while the new
            # graphics transaction is still rollback-capable.  The existing
            # graphics remain attached until ownership and commit both succeed.
            try:
                self._pending_session.set(rendered_record)
                self._pending_graphics_by_series_id[record.id] = graphics
                transaction.commit()
            except Exception:
                self._pending_session.set(pending)
                self._pending_graphics_by_series_id[record.id] = old_graphics
                transaction.rollback()
                raise

            self._detach_graphics(old_graphics)
            self._set_current_series(rendered_record)
            self._rebuildYDataRanges()
            self.applyYAxisPolicy()
            self._notify_pending_changed()
            return graphics
        if record.id in self._hidden_committed_ids:
            if not self._series_store.replace(record):
                raise KeyError(f"time-series record not found: {record.id}")
            self._set_current_series(record)
            self._notify_committed_changed()
            return None
        result = self.rerender_record(
            record, plot_multiple=plot_multiple, report_statistics=report_statistics
        )
        self._notify_committed_changed()
        return result

    def update_pending_label(self, label: str) -> bool:
        """Trim and replace the pending label without touching committed records."""
        record = self.pending_record()
        if record is None:
            return False
        normalized = str(label).strip()
        updated = replace(record, presentation=replace(record.presentation, label=normalized))
        self._pending_session.set(updated)
        self._set_current_series(updated)
        self._notify_pending_changed()
        return True

    @staticmethod
    def _default_pending_label(record):
        kind = record.target.kind.value.title() if record.target is not None else "Time series"
        return kind

    def commit_pending(self) -> Optional[TimeSeriesRecord]:
        """Transfer the exact pending record and graphics into committed ownership."""
        record = self.pending_record()
        if record is None:
            return None
        graphics = self._pending_graphics_by_series_id.get(record.id)
        if graphics is None:
            raise KeyError(f"pending graphics not found: {record.id}")
        self._series_store.add(record, make_active=True)
        try:
            self._graphics_by_series_id[record.id] = graphics
            self._pending_graphics_by_series_id.pop(record.id, None)
            self._pending_session.clear()
        except Exception:
            self._series_store.remove(record.id)
            self._graphics_by_series_id.pop(record.id, None)
            self._pending_graphics_by_series_id[record.id] = graphics
            self._pending_session.set(record)
            raise
        self._hidden_committed_ids.discard(record.id)
        self._set_current_series(record)
        self._notify_pending_changed()
        self._notify_committed_changed()
        return record

    def discard_pending(self) -> Optional[TimeSeriesRecord]:
        """Remove only pending state and graphics."""
        record = self._pending_session.clear()
        if record is None:
            return None
        graphics = self._pending_graphics_by_series_id.pop(record.id, None)
        if graphics is not None:
            self._detach_graphics(graphics)
        self._set_current_series(self.current_series())
        self._rebuildYDataRanges()
        self.applyYAxisPolicy()
        self._draw()
        self._notify_pending_changed()
        return record

    def current_series(self) -> Optional[TimeSeriesSnapshot]:
        """Return the explicitly active stored record, if available."""
        return self._series_store.active_record()

    def remove_series(self, index: int = -1) -> Optional[TimeSeriesSnapshot]:
        """Remove and return a record without changing registered graphics."""
        return self._series_store.remove_at(index)

    def remove_series_by_id(self, series_id: UUID) -> Optional[TimeSeriesSnapshot]:
        """Remove and return the record with the supplied stable identity."""
        return self._series_store.remove(series_id)

    def remove_records(self, record_ids, *, notify=True) -> CommittedRemovalResult:
        """Remove committed records by UUID and return explicit diagnostics.

        Valid UUIDs are removed as one domain command. Stale UUIDs are ignored.
        Graphics detachment is best-effort after authoritative store removal;
        axes are rebuilt from surviving ownership before the single redraw.
        """
        requested = []
        seen = set()
        for value in record_ids:
            record_id = value if isinstance(value, UUID) else UUID(str(value))
            if record_id not in seen:
                seen.add(record_id)
                requested.append(record_id)
        records = tuple(
            record for record_id in requested
            for record in (self._series_store.get(record_id),)
            if record is not None
        )
        if not records:
            return CommittedRemovalResult(())
        removed = self._series_store.remove_many(record.id for record in records)
        detach_errors = []
        for record in removed:
            try:
                self._remove_snapshot_graphics(record)
            except Exception as error:
                detach_errors.append(error)
            self._graphics_by_series_id.pop(record.id, None)
            self._hidden_committed_ids.discard(record.id)
        self._set_current_series(self.pending_record() or self.current_series())
        self._rebuildYDataRanges()
        self.applyYAxisPolicy()
        self._draw()
        if notify:
            self._notify_committed_changed()
        return CommittedRemovalResult(
            removed_record_ids=tuple(record.id for record in removed),
            graphics_errors=tuple(detach_errors),
        )

    def remove_record(self, series_id: UUID) -> bool:
        """Remove one committed record through the shared batch boundary."""
        result = self.remove_records((series_id,))
        return bool(result.removed_record_ids)

    def set_committed_visibility(self, series_id: UUID, visible: bool) -> bool:
        """Show or hide one committed record through the atomic batch boundary."""
        result = self.set_committed_visibility_batch((series_id,), visible)
        return bool(result.changed_record_ids) or self.is_committed_visible(series_id) == bool(visible)

    def set_committed_visibility_batch(
        self, series_ids, visible: bool
    ) -> CommittedVisibilityBatchResult:
        """Apply one atomic authoritative visibility transition.

        Showing is fully transactional across store, graphics registry, hidden IDs,
        and newly attached graphics. Hiding publishes registry/hidden-ID state for
        the whole batch first, then treats physical detach failures as non-fatal
        graphics diagnostics so authoritative state can never become mixed.
        """
        requested = []
        seen = set()
        for value in series_ids:
            series_id = value if isinstance(value, UUID) else UUID(str(value))
            if series_id not in seen:
                seen.add(series_id)
                requested.append(series_id)
        series_ids = tuple(requested)
        records = tuple(self._series_store.get(series_id) for series_id in series_ids)
        if any(record is None for record in records):
            raise KeyError("stale committed UUID in visibility batch")

        target = bool(visible)
        if target:
            to_show = tuple(
                (series_id, record)
                for series_id, record in zip(series_ids, records)
                if series_id in self._hidden_committed_ids
            )
            if not to_show:
                return CommittedVisibilityBatchResult(())

            built = []
            try:
                for series_id, record in to_show:
                    graphics, rendered_record, transaction = self._build_record_graphics(record)
                    built.append((series_id, graphics, rendered_record, transaction))
            except Exception:
                for _series_id, _graphics, _record, transaction in reversed(built):
                    transaction.rollback()
                raise

            previous_records = tuple(record for _series_id, record in to_show)
            previous_graphics = {
                series_id: self._graphics_by_series_id.get(series_id)
                for series_id, _record in to_show
            }
            previous_hidden = {
                series_id: series_id in self._hidden_committed_ids
                for series_id, _record in to_show
            }
            store_replaced = False
            published_ids = []
            try:
                self._series_store.replace_many(
                    rendered_record
                    for _series_id, _graphics, rendered_record, _transaction in built
                )
                store_replaced = True
                for series_id, graphics, _record, _transaction in built:
                    self._graphics_by_series_id[series_id] = graphics
                    self._hidden_committed_ids.discard(series_id)
                    published_ids.append(series_id)
                for _series_id, _graphics, _record, transaction in built:
                    transaction.commit()
            except Exception:
                if store_replaced:
                    self._series_store.replace_many(previous_records)
                for series_id in published_ids:
                    previous = previous_graphics[series_id]
                    if previous is None:
                        self._graphics_by_series_id.pop(series_id, None)
                    else:
                        self._graphics_by_series_id[series_id] = previous
                    if previous_hidden[series_id]:
                        self._hidden_committed_ids.add(series_id)
                    else:
                        self._hidden_committed_ids.discard(series_id)
                for _series_id, _graphics, _record, transaction in reversed(built):
                    transaction.rollback()
                raise
            changed_ids = tuple(series_id for series_id, _record in to_show)
            graphics_errors = ()
        else:
            to_hide = tuple(
                series_id for series_id in series_ids
                if series_id not in self._hidden_committed_ids
            )
            if not to_hide:
                return CommittedVisibilityBatchResult(())

            captured_graphics = tuple(
                (series_id, self._graphics_by_series_id.get(series_id))
                for series_id in to_hide
            )
            # Publish the complete authoritative state before best-effort detach.
            for series_id in to_hide:
                self._graphics_by_series_id.pop(series_id, None)
            self._hidden_committed_ids.update(to_hide)

            detach_errors = []
            for _series_id, graphics in captured_graphics:
                if graphics is None:
                    continue
                try:
                    self._detach_graphics(graphics)
                except Exception as error:
                    detach_errors.append(error)
            changed_ids = to_hide
            graphics_errors = tuple(detach_errors)

        refresh_errors = self._refresh_after_committed_visibility_change()
        return CommittedVisibilityBatchResult(
            changed_record_ids=changed_ids,
            graphics_errors=graphics_errors,
            refresh_errors=refresh_errors,
        )

    def _refresh_after_committed_visibility_change(self):
        """Refresh presentation after commit and return non-fatal errors.

        Each presentation step is attempted independently so a later draw can
        still recover from an earlier range or axis-policy failure. Authoritative
        visibility state is never rolled back after this helper is entered.
        """
        errors = []
        for operation in (
            self._rebuildYDataRanges,
            self.applyYAxisPolicy,
            self._draw,
        ):
            try:
                operation()
            except Exception as error:
                errors.append(error)
        return tuple(errors)

    def is_committed_visible(self, series_id: UUID) -> bool:
        """Return list/canvas visibility for one committed UUID."""
        return self._series_store.get(series_id) is not None and series_id not in self._hidden_committed_ids

    def committed_record(self, series_id: UUID) -> Optional[TimeSeriesRecord]:
        """Return one committed record for read-only list projection."""
        return self._series_store.get(series_id)

    def committed_records(self):
        """Return committed records in insertion order."""
        return self._series_store.records()

    def setActiveSeries(self, series_id: UUID) -> bool:
        """Make an existing record active and refresh compatibility views."""
        record = self._series_store.get(series_id)
        if record is None:
            return False
        self._series_store.set_active(series_id)
        self._set_current_series(record)
        return True

    def _dateStrings(self):
        date_strings = []
        for d in self.dates:
            date_strings.append(d.strftime('%Y-%m-%d'))
        return date_strings

    @staticmethod
    def _selection_crs(selection: Optional[SpatialSelection]) -> str:
        """Return legacy CRS metadata for one optional spatial selection."""
        return selection.value.crs_str() if selection is not None else "None"

    @staticmethod
    def _selection_wkt(selection: Optional[SpatialSelection]) -> str:
        """Return legacy layer-CRS WKT metadata for one optional selection."""
        return selection.value.as_wkt() if selection is not None else "None"

    @staticmethod
    def _selection_wgs84_wkt(selection: Optional[SpatialSelection]) -> str:
        """Return legacy WGS84 WKT metadata for one optional selection."""
        return selection.value.as_wkt_wgs84() if selection is not None else "None"

    @staticmethod
    def _selection_label(selection: Optional[SpatialSelection]) -> str:
        """Return the legacy point/polygon label for export headers."""
        return (selection.kind.value if selection is not None else SpatialSelectionKind.POINT.value)

    def exportAscii(self, filename=None, record=None):
        """Export one explicit record, retaining the legacy active-series fallback."""
        if filename is None:
            return
        if record is None:
            record = self.editable_time_series_record()
        if record is None:
            if self.dates is None or self.plot_values is None:
                return
            data = self._buildTimeSeriesData(
                dates=self.dates, ts_values=self.ts_values, ref_values=self.ref_values
            )
            record = self._buildTimeSeriesRecord(
                data=data, presentation=self.default_style.snapshotPresentation(),
                coords=self.coords, ref_coords=self.ref_coords,
            )
        series = record.data
        if series.dates is None or series.plot_values is None:
            return

        data_to_save = np.column_stack((series.dateStrings(), series.plot_values))
        target = record.target
        reference = record.reference

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

        target_type = self._selection_label(target)
        reference_type = self._selection_label(reference)
        wgs84 = "CRS=EPSG:4326"

        header_lines.append("Layer CRS\n")
        header_lines.append(f"Time series {target_type}:")
        header_lines.append(self._selection_crs(target))
        header_lines.append(f"{self._selection_wkt(target)}\n")
        header_lines.append(f"Reference {reference_type}:")
        header_lines.append(self._selection_crs(reference))
        header_lines.append(self._selection_wkt(reference))

        header_lines.append(separator)
        header_lines.append("WGS84 Lon/Lat\n")
        header_lines.append(f"Time series {target_type}:")
        header_lines.append(wgs84 if target is not None else "None")
        header_lines.append(f"{self._selection_wgs84_wkt(target)}\n")
        header_lines.append(f"Reference {reference_type}:")
        header_lines.append(wgs84 if reference is not None else "None")
        header_lines.append(self._selection_wgs84_wkt(reference))
        header_lines.append(separator)

        header_lines.append("Time series data\n")
        header_lines.append("date, ts_value")

        header = "\n".join(header_lines)
        np.savetxt(filename, data_to_save, fmt="%s", delimiter=",", header=header, comments="# ")
