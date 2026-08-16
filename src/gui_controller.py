import os
import math
from dataclasses import replace

from qgis.gui import QgsMapToolEmitPoint
from qgis.core import QgsProject
from qgis.PyQt.QtWidgets import QFileDialog, QComboBox, QMessageBox
from qgis.PyQt.QtCore import (
    QObject, QPoint, QRect, QSettings, QSignalBlocker, QStandardPaths, QTimer, QVariant, pyqtSignal,
)
from qgis.PyQt.QtGui import QColor, QIcon, QTransform

from . import map_click_handler as cph
from . import setup_frames
from .bootstrap import ensure_time_series_services
from .map_setting import InsarMap
from .layer_utils import vector_layer as vector_layer_utils
from .about import about as insar_explorer_about
from .drawing_tools.polygon_drawing_tool import PolygonDrawingTool
from .ui.popups.time_series_style_popup import TimeSeriesStylePopup
from .ui.popups.fit_popup import FitPopup
from .ui.popups.manual_y_axis_popup import ManualYAxisPopup
from .ui.popups.manual_x_axis_popup import ManualXAxisPopup
from .ui.popups.export_settings_popup import ExportSettingsPopup
from .ui.popups.appearance_popup import AppearancePopup
from .ui.popups.replica_popup import ReplicaPopup
from .ui.popups.map_indicator_settings_popup import MapIndicatorSettingsPopup
from .ui.map_settings.range_state import RangeSource, STD_RANGE_SOURCES, StdCalculationMode
from .ui.map_settings.range_defaults import (
    RangePolicyDefaults, RangePolicyDefaultsService,
    normalize_range_policy_defaults,
)
from .ui.map_settings.symbology_defaults import (
    MapSymbologySettings, MapSymbologySettingsService,
    normalize_map_symbology_settings,
)
from .ui.widgets.split_tool_button import SplitButtonPopupHoverReconciler
from .qt_compat import (
    ITEM_IS_ENABLED,
    ITEM_IS_SELECTABLE,
    POINT_GEOMETRY,
    RASTER_LAYER,
    VECTOR_LAYER,
    available_screen_geometry,
    screen_aware_popup_position,
    exec_dialog,
    MESSAGE_ICON_WARNING,
    MESSAGE_BUTTON_OK,
    MESSAGE_ROLE_ACTION,
    MESSAGE_ROLE_DESTRUCTIVE,
    MESSAGE_ROLE_REJECT,
)
from .time_series.fit_state import TimeSeriesFitState
from .time_series.list_state import TimeSeriesListState
from .time_series.map_overlays import (
    CommittedSelectionOverlayController, PendingTimeSeriesMapOverlayController,
)
from .time_series.map_navigation import (
    ensure_canvas_navigation_crs, recenter_canvas_preserving_scale,
    resolve_selection_navigation_location, transform_navigation_point,
)
from .time_series.analysis_defaults import StickyAnalysisDefaultsCoordinator
from .models.time_series import FitConfiguration, ReplicaConfiguration
from .time_series.fit_style_controller import FitStyleController
from .time_series.ensemble_style import EnsembleStyleController
from .time_series.residual_style_controller import ResidualStyleController
from .time_series.style_availability import TimeSeriesStyleAvailability
from .time_series.style_controller import TimeSeriesStyleController
from .time_series.style_schema import percent_to_alpha
from .time_series.style_palette import (
    DISTINCT_TIME_SERIES_COLORS, with_primary_series_color,
)
from .time_series.settings.model import (
    AppearanceSettings, AxisManualRange, EnsembleStyleSettings, ExportSettings,
    FitStyleSettings, ReplicaSettings, ReplicaStyleSettings, ResidualStyleSettings, SeriesStyleSettings,
    XAxisSettings,
)
from .time_series.settings.persistence import build_legacy_plot_params
from .time_series.persistence import PreferencesPersistenceError
from .time_series.copy_paste import (
    CopyPasteCategory, TimeSeriesSettingsClipboard,
    apply_fit_snapshot, apply_replica_snapshot, apply_style_snapshot,
    capture_fit, capture_replica, capture_style,
)


class GuiController(QObject):
    msg_signal = pyqtSignal(str, str, int)

    @property
    def time_series_y_axis_mode(self):
        return self.time_series_settings.y_axis.policy

    @time_series_y_axis_mode.setter
    def time_series_y_axis_mode(self, value):
        if value not in {"from_data", "symmetric", "manual"}:
            value = "from_data"
        self.time_series_settings.update_property("y_axis", "policy", value)

    residual_y_axis_mode = time_series_y_axis_mode

    @property
    def time_series_manual_y_lower(self):
        return self.time_series_settings.y_axis.series_manual.lower

    @time_series_manual_y_lower.setter
    def time_series_manual_y_lower(self, value):
        axis = self.time_series_settings.y_axis
        self.time_series_settings.replace_domain(
            "y_axis", replace(axis, series_manual=replace(axis.series_manual, lower=value))
        )

    @property
    def time_series_manual_y_upper(self):
        return self.time_series_settings.y_axis.series_manual.upper

    @time_series_manual_y_upper.setter
    def time_series_manual_y_upper(self, value):
        axis = self.time_series_settings.y_axis
        self.time_series_settings.replace_domain(
            "y_axis", replace(axis, series_manual=replace(axis.series_manual, upper=value))
        )

    @property
    def residual_manual_y_lower(self):
        return self.time_series_settings.y_axis.residual_manual.lower

    @residual_manual_y_lower.setter
    def residual_manual_y_lower(self, value):
        axis = self.time_series_settings.y_axis
        self.time_series_settings.replace_domain(
            "y_axis", replace(axis, residual_manual=replace(axis.residual_manual, lower=value))
        )

    @property
    def residual_manual_y_upper(self):
        return self.time_series_settings.y_axis.residual_manual.upper

    @residual_manual_y_upper.setter
    def residual_manual_y_upper(self, value):
        axis = self.time_series_settings.y_axis
        self.time_series_settings.replace_domain(
            "y_axis", replace(axis, residual_manual=replace(axis.residual_manual, upper=value))
        )

    @property
    def time_series_replica_enabled(self):
        return self._replica_enabled_view

    @time_series_replica_enabled.setter
    def time_series_replica_enabled(self, value):
        self._replica_enabled_view = bool(value)

    @property
    def time_series_replica_interval_mm(self):
        return self._replica_interval_view

    @time_series_replica_interval_mm.setter
    def time_series_replica_interval_mm(self, value):
        self._replica_interval_view = float(value)

    @property
    def time_series_replica_pair_count(self):
        return self._replica_pair_count_view

    @time_series_replica_pair_count.setter
    def time_series_replica_pair_count(self, value):
        self._replica_pair_count_view = self._validateReplicaPairCount(value)

    def __init__(self, plugin):
        super().__init__()
        self.iface = plugin.iface
        self.ui = plugin.dockwidget
        self._plugin_diagnostic = getattr(
            plugin, "report_time_series_diagnostic", None
        )
        self._last_fit_statistics_message = None
        services = ensure_time_series_services(plugin)
        self.map_indicator_settings = services.map_indicator_settings
        self.map_symbology_defaults = MapSymbologySettingsService()
        self.map_range_defaults = RangePolicyDefaultsService()
        self.choose_point_click_handler = cph.ClickHandler(
            plugin,
            msg_signal=self.msg_signal,
            indicator_settings_service=self.map_indicator_settings,
        )
        self.choose_point_click_handler.new_record_analysis_provider = (
            self.choose_point_click_handler.plot_ts.analysisForNewRecord
        )
        self.time_series_settings = self.choose_point_click_handler.plot_ts.settings_model
        plotter = self.choose_point_click_handler.plot_ts
        plotter.axis_view_changed_callback = self._axisViewportChanged
        plotter.auto_view_requested_callback = self._handlePlotAutoRequest
        plotter.axis_state_sync_callback = self._syncAxisToolbarControls
        plotter.fit_failure_callback = self._handleTimeSeriesFitFailure
        plotter.fit_success_callback = self._handleTimeSeriesFitSuccess
        plotter.analysis_state_sync_callback = self._syncActiveAnalysisControls
        plotter.pending_changed_callback = self._syncPendingTimeSeriesPanel
        plotter.committed_changed_callback = self._syncCommittedTimeSeriesList
        self.time_series_list_state = TimeSeriesListState()
        settings_provider = lambda: self.map_indicator_settings.active
        self.time_series_map_overlays = CommittedSelectionOverlayController(
            self.iface.mapCanvas(), diagnostic=self._plugin_diagnostic,
            settings_provider=settings_provider,
        )
        self.pending_time_series_map_overlays = PendingTimeSeriesMapOverlayController(
            self.iface.mapCanvas(), diagnostic=self._plugin_diagnostic,
            settings_provider=settings_provider,
        )
        self.time_series_clipboard = None
        self.ui.time_series_point_panel.configure_committed_list(
            self.time_series_list_state, plotter.committed_record
        )
        self._refreshTimeSeriesClipboardProjection()
        self.click_tool = None  # target point selection tool
        self.reference_click_tool = None  # reference point selection tool
        self.drawing_tool = None  # for polygon drawing
        self.drawing_tool_reference = None  # for reference polygon drawing
        self.selection_type = "point"  # "point" or "polygon" or "reference polygon"
        fit_defaults = self.time_series_settings.fit_analysis_defaults
        self.time_series_fit_state = TimeSeriesFitState(
            fit_enabled=fit_defaults.enabled,
            selected_fit_model=fit_defaults.model,
            seasonal_enabled=fit_defaults.seasonal,
            residual_enabled=fit_defaults.show_residuals,
        )
        replica_defaults = self.time_series_settings.replica_analysis_defaults
        self._replica_enabled_view = replica_defaults.enabled
        self._replica_interval_view = replica_defaults.interval_mm
        self._replica_pair_count_view = replica_defaults.pair_count
        self._analysis_defaults = StickyAnalysisDefaultsCoordinator(
            self.time_series_settings,
            plotter.user_preferences,
            diagnostic=self._reportAnalysisDefaultsPersistenceFailure,
            defaults_changed=plotter.setNewRecordAnalysis,
        )
        self.initializeSelection()
        setup_frames.setupTsFrame(self.ui)
        self.insar_map = InsarMap(self.iface)
        self.settings = QSettings()
        self._clearPersistedYAxisModes()
        self.time_series_y_axis_mode = "from_data"
        self.time_series_manual_y_lower = None
        self.time_series_manual_y_upper = None
        self.residual_manual_y_lower = None
        self.residual_manual_y_upper = None
        self.residual_y_axis_mode = self.time_series_y_axis_mode
        self.choose_point_click_handler.plot_ts.manual_y_lower = self.time_series_manual_y_lower
        self.choose_point_click_handler.plot_ts.manual_y_upper = self.time_series_manual_y_upper
        self.choose_point_click_handler.plot_ts.residual_y_axis_mode = self.residual_y_axis_mode
        self.choose_point_click_handler.plot_ts.residual_manual_y_lower = self.residual_manual_y_lower
        self.choose_point_click_handler.plot_ts.residual_manual_y_upper = self.residual_manual_y_upper
        self.time_series_style_popup = TimeSeriesStylePopup(self.ui)
        self.fit_popup = FitPopup(self.ui)
        self.manual_x_axis_popup = ManualXAxisPopup(self.ui)
        self._manual_x_axis_session = None
        self.manual_y_axis_popup = ManualYAxisPopup(self.ui)
        self.export_settings_popup = ExportSettingsPopup(self.ui)
        self.appearance_popup = AppearancePopup(self.ui)
        self.replica_popup = ReplicaPopup(self.ui)
        self.map_indicator_settings_popup = MapIndicatorSettingsPopup(self.ui)
        self._installSplitButtonPopupHoverReconciliation()
        self._manual_y_axis_session = None
        self.time_series_style_controller = TimeSeriesStyleController()
        self.fit_style_controller = FitStyleController()
        self.ensemble_style_controller = EnsembleStyleController()
        self.residual_style_controller = ResidualStyleController()
        self.last_save_path = self._initialExportDirectory()
        self.last_save_ts_name = "ts_plot.png"
        self.last_export_ts_name = "ts_data.csv"
        self.last_plot_export_format = self.settings.value(
            'insar_explorer/plot_export_format', 'png', type=str
        )
        self.last_ts_export_format = self.settings.value(
            'insar_explorer/ts_export_format', 'csv', type=str
        )
        self._symbology_dirty = False
        self._range_source = RangeSource.CUSTOM
        self._range_source_raw_values = None
        self._range_programmatic_update = False
        self._std_calculation_mode = StdCalculationMode.FAST
        self._pending_default_range_layer_id = None
        self._map_tool_signal_connected = False
        self.initializeUiParams()
        self.connectUiSignals()
        self._syncSelectionControlsToActiveMapTool()

        self.iface.currentLayerChanged.connect(self.onLayerChanged)
        self.onLayerChanged()

    def _installSplitButtonPopupHoverReconciliation(self):
        """Reconcile split-button hover whenever an associated popup closes."""
        toolbar = self.ui.time_series_toolbar
        mappings = (
            (self.fit_popup, toolbar.fit_button),
            (self.replica_popup, toolbar.replica_button),
            (self.export_settings_popup, toolbar.plot_export_button),
        )
        self._split_button_popup_hover_reconcilers = []
        for popup, split_button in mappings:
            reconciler = SplitButtonPopupHoverReconciler(split_button, popup)
            popup.installEventFilter(reconciler)
            self._split_button_popup_hover_reconcilers.append(reconciler)

    def initializeUiParams(self):
        """Initialize code-created controls; migrated style controls live in the popup."""
        return

    def _saveUserPreferences(self, save_operation, success_message):
        """Persist one preference scope without invalidating runtime state."""
        try:
            save_operation()
        except PreferencesPersistenceError as exc:
            self.msg_signal.emit(str(exc), "error", 5000)
            return False
        self.msg_signal.emit(success_message, "done", 3000)
        return True

    def _reportAnalysisDefaultsPersistenceFailure(self, scope, error):
        """Report only sticky-default failure and log the underlying exception."""
        is_fit_scope = scope == "fit analysis defaults"
        warning = (
            "Fit updated, but its default could not be saved."
            if is_fit_scope
            else f"{scope.capitalize()} could not be saved."
        )
        if is_fit_scope and self._last_fit_statistics_message:
            warning = f"{self._last_fit_statistics_message}. {warning}"
        self.msg_signal.emit(warning, "error", 6000)
        if self._plugin_diagnostic is not None:
            self._plugin_diagnostic(
                f"Unable to persist {scope}.", error, notify=False
            )

    def _persistCurrentFitAnalysisDefaults(self):
        """Persist normalized fit state after an explicit user action only."""
        state = self.time_series_fit_state
        return self._analysis_defaults.update_fit(
            enabled=state.fit_enabled,
            model=state.selected_fit_model,
            seasonal=state.seasonal_enabled,
            show_residuals=bool(state.fit_enabled and state.residual_enabled),
        )

    def _persistCurrentReplicaAnalysisDefaults(self):
        """Persist normalized Replica state after an explicit user action only."""
        return self._analysis_defaults.update_replica(
            enabled=self.time_series_replica_enabled,
            pair_count=self.time_series_replica_pair_count,
            interval_mm=self.time_series_replica_interval_mm,
        )

    def initializeSelection(self):
        if self.selection_type == "point":
            self.initializeClickTool()
        elif self.selection_type == "polygon":
            self.initializePolygonDrawingTool()
        elif self.selection_type == "reference polygon":
            self.initializePolygonDrawingTool(reference=True)

    def resetTimeSeriesTransientStateForLayer(self):
        """Clear active-layer interaction state while retaining committed series."""
        self.time_series_map_overlays.clear_committed()
        self.pending_time_series_map_overlays.clear()
        self.clear_all_pending_drawing_feedback()
        self.choose_point_click_handler.resetLayerTransientState()
        self.clearTimeSeriesClipboard()

    def resetTimeSeriesWorkspaceForDataset(self):
        """Compatibility alias for active-layer transient cleanup."""
        self.resetTimeSeriesTransientStateForLayer()

    def clearTimeSeriesWorkspace(self):
        """Explicitly clear transient state and every committed time series."""
        self.time_series_map_overlays.clear_all()
        self.pending_time_series_map_overlays.clear()
        self.clear_all_pending_drawing_feedback()
        self.choose_point_click_handler.clearTimeSeriesWorkspace()
        self.clearTimeSeriesClipboard()

    def onLayerChanged(self, layer=None):
        """Reset active-layer state while retaining the committed workspace."""
        if layer is None:
            layer = self.iface.activeLayer()

        self._setLiveSymbologyEnabled(False)
        self._syncPointMarkerControls(layer)
        layer_id = self._layerIdentity(layer)
        pending_layer_id = self._pending_default_range_layer_id
        if pending_layer_id is not None and pending_layer_id != layer_id:
            # Invalidate queued work for a previous layer/context.  Keep a same-
            # layer pending token so duplicate signals coalesce to one callback.
            self._pending_default_range_layer_id = None
            self._setDefaultRangeInitializationPending(False)

        self._setCustomRangeSource()
        self._setRangeSymmetryChecked(False)
        self._setSymbologyDirty(False)
        self.resetTimeSeriesTransientStateForLayer()
        self.committedTimeSeriesSelectionChanged(
            self.ui.time_series_point_panel.selected_committed_ids()
        )
        if layer:
            self._restoreTimeSeriesFitState()
            self._restoreTimeSeriesYAxisMode()
            self._restoreTimeSeriesReplicaState()
            self.insar_map.reset()

            layer_type = layer.type()
            is_local_raster = (hasattr(layer, "dataProvider") and getattr(layer.dataProvider(), "name", lambda: "")()
                               in ["gdal"])  # "ogr"

            self.setVectorFields(initialize_default_range=True)
            if layer_type == RASTER_LAYER and is_local_raster:
                self._scheduleDefaultRangeInitialization(layer)

            if layer_type == VECTOR_LAYER:
                self.ui.pb_choose_polygon.setEnabled(True)
                self.ui.pb_set_reference_polygon.setEnabled(True)
            elif layer_type == RASTER_LAYER:
                self._deactivatePolygonSelectionToolsForRaster()
                self.ui.settings_panel.setEnabled(False)
                self.ui.pb_choose_polygon.setEnabled(False)
                self.ui.pb_set_reference_polygon.setEnabled(False)

            if layer_type == RASTER_LAYER and not is_local_raster:
                self.ui.settings_panel.setEnabled(False)
                self.ui.pb_choose_point.setChecked(False)
                message = "Unsupported layer selected. Please choose a layer compatible with InSAR Explorer."
            else:
                self.ui.settings_panel.setEnabled(True)
                message = ""
            self.msg_signal.emit(message, "i", 0)

    def _deactivatePolygonSelectionToolsForRaster(self):
        """Deactivate polygon selection tools that cannot operate on raster layers."""
        canvas = self.iface.mapCanvas()
        if self._isActiveMapTool(canvas.mapTool(), self.drawing_tool):
            self.deactivatePolygonDrawingTool(reference=False)
        if self._isActiveMapTool(canvas.mapTool(), self.drawing_tool_reference):
            self.deactivatePolygonDrawingTool(reference=True)
        self._syncSelectionControlsToActiveMapTool()

    def _syncPointMarkerControls(self, layer=None):
        """Project active-layer geometry onto point-only marker controls."""
        is_point_vector = False
        if layer is not None:
            try:
                is_point_vector = (
                    layer.type() == VECTOR_LAYER
                    and layer.geometryType() == POINT_GEOMETRY
                )
            except (AttributeError, RuntimeError):
                is_point_vector = False
        self.ui.map_settings_panel.symbology_settings_popup.set_point_marker_available(
            is_point_vector
        )

    @staticmethod
    def _findSelectableFieldIndex(field_combo, field_name):
        """Return the real selectable combo row for an exact field name."""
        if not field_name:
            return -1
        for index in range(field_combo.count()):
            if field_combo.itemText(index) != field_name:
                continue
            model_index = field_combo.model().index(index, 0)
            flags = model_index.flags()
            if flags & ITEM_IS_ENABLED and flags & ITEM_IS_SELECTABLE:
                return index
            return -1
        return -1

    def setVectorFields(self, initialize_default_range=False):
        """Populate vector fields and optionally initialize a fresh range state."""
        layer = self.iface.activeLayer()
        if not layer:
            return

        status, message = vector_layer_utils.checkVectorLayer(layer)
        field_combo = self.ui.cb_select_field
        was_blocked = field_combo.blockSignals(True)
        try:
            field_combo.clear()
            if status is False:
                field_combo.setEnabled(False)
                self.ui.sb_symbol_size.setEnabled(False)
                self._setSymbologyDirty(False)
                return

            field_combo.setEnabled(True)
            self.ui.sb_symbol_size.setEnabled(True)

            field_list, field_types = vector_layer_utils.getVectorFields(layer)
            velocity_field, message = vector_layer_utils.getVectorVelocityFieldName(layer)

            for field, field_type in zip(field_list, field_types):
                field_combo.addItem(field)
                if field_type not in [QVariant.Double, QVariant.Int, QVariant.LongLong]:
                    index = field_combo.count() - 1
                    field_combo.model().item(index).setEnabled(False)

            velocity_index = self._findSelectableFieldIndex(
                field_combo, velocity_field
            )
            if velocity_index >= 0:
                field_combo.setCurrentIndex(velocity_index)
        finally:
            field_combo.blockSignals(was_blocked)

        if hasattr(self.ui, "map_settings_panel"):
            self.ui.map_settings_panel.sync_field_selection_state()

        self.insar_map.selected_field_name = field_combo.currentText()
        self.choose_point_click_handler.selected_field_name = self.insar_map.selected_field_name

        if initialize_default_range:
            self._scheduleDefaultRangeInitialization(layer)
        else:
            self._setSymbologyDirty(False)

    @staticmethod
    def _layerIdentity(layer):
        """Return a stable identity token for a layer/context object."""
        if layer is None:
            return None
        layer_id = getattr(layer, "id", None)
        if callable(layer_id):
            return layer_id()
        return id(layer)

    def _setDefaultRangeInitializationPending(self, pending):
        """Reflect deferred range initialization without exposing stale values."""
        enabled = not bool(pending)
        for name in (
            "sb_symbol_lower_range",
            "sb_symbol_upper_range",
            "pb_symbol_range_settings",
        ):
            control = getattr(self.ui, name, None)
            if control is not None:
                control.setEnabled(enabled)

    def _scheduleDefaultRangeInitialization(self, layer):
        """Queue fresh default range/symbology work for one active layer."""
        layer_id = self._layerIdentity(layer)
        if layer_id is None:
            return False
        if self._pending_default_range_layer_id == layer_id:
            return False

        self._pending_default_range_layer_id = layer_id
        self._setDefaultRangeInitializationPending(True)
        QTimer.singleShot(
            0,
            lambda layer_id=layer_id: (
                self._runDeferredDefaultRangeInitialization(layer_id)
            ),
        )
        return True

    def _runDeferredDefaultRangeInitialization(self, layer_id):
        """Run queued fresh default initialization only for the current layer."""
        if self._pending_default_range_layer_id != layer_id:
            return False

        current_layer = self.iface.activeLayer()
        if self._layerIdentity(current_layer) != layer_id:
            self._pending_default_range_layer_id = None
            self._setDefaultRangeInitializationPending(False)
            return False

        self._pending_default_range_layer_id = None
        try:
            return self._initializeDefaultRangeState()
        finally:
            self._setDefaultRangeInitializationPending(False)

    def _setLiveSymbologyEnabled(self, enabled):
        """Project Live update state without triggering symbology application."""
        checkbox = self.ui.cb_symbology_live
        was_blocked = checkbox.blockSignals(True)
        try:
            checkbox.setChecked(bool(enabled))
        finally:
            checkbox.blockSignals(was_blocked)

    def _setRangeSymmetryChecked(self, checked):
        """Project range symmetry state without triggering range-change behavior."""
        checkbox = self.ui.cb_symbol_range_symmetric
        was_blocked = checkbox.blockSignals(True)
        try:
            checkbox.setChecked(bool(checked))
        finally:
            checkbox.blockSignals(was_blocked)

    def _initializeDefaultRangeState(self):
        """Initialize a fresh active-field range from saved/factory policy defaults."""
        displayed_range = (
            self.ui.sb_symbol_lower_range.value(),
            self.ui.sb_symbol_upper_range.value(),
        )
        settings = self.map_range_defaults.load_defaults()
        if self._projectMapRangePolicy(settings, publish_edit=False):
            self._setSymbologyDirty(True)
            return True

        factory = self.map_range_defaults.factory_defaults()
        if settings != factory and self._projectMapRangePolicy(
            factory, publish_edit=False
        ):
            self._setSymbologyDirty(True)
            return True

        self._setCustomRangeSource()
        self._setRangeSymmetryChecked(False)
        self._setStdCalculationMode(StdCalculationMode.FAST)
        self._setDisplayedRange(*displayed_range)
        self._setSymbologyDirty(False)
        return False

    def selectVectorFieldChanged(self, index=None):
        """Update the active field while preserving the selected range strategy."""
        field_combo = self.ui.cb_select_field
        if index is None:
            index = field_combo.currentIndex()
        if index < 0:
            return
        model_index = field_combo.model().index(index, 0)
        flags = model_index.flags()
        if not (flags & ITEM_IS_ENABLED and flags & ITEM_IS_SELECTABLE):
            return

        source = self._range_source
        displayed_range = (
            self.ui.sb_symbol_lower_range.value(),
            self.ui.sb_symbol_upper_range.value(),
        )

        self.insar_map.selected_field_name = self.ui.cb_select_field.currentText()
        self.choose_point_click_handler.selected_field_name = self.insar_map.selected_field_name
        self.insar_map.reset()

        if self.ui.cb_symbol_value_offset_sync_with_ref.isChecked():
            self._syncReferenceValueFromSelection()

        if source is RangeSource.CUSTOM:
            self._range_source_raw_values = None
            self.applyLiveSymbology()
            return

        raw_values, error = self._computeRangeSourceValues(source)
        if error:
            self._setCustomRangeSource()
            self._setDisplayedRange(*displayed_range)
            self.msg_signal.emit(error, 'i', 0)
            self.applyLiveSymbology()
            return

        self._projectComputedRangeSource(source, raw_values)
        self.applyLiveSymbology()

    def initializeClickTool(self, reference=False):
        """Create the role-specific point map tool on first use."""
        attribute = "reference_click_tool" if reference else "click_tool"
        tool = getattr(self, attribute)
        if tool is None:
            tool = QgsMapToolEmitPoint(self.iface.mapCanvas())
            tool.canvasClicked.connect(
                lambda point, *args, ref=reference: self.onMapClicked(
                    point=point, reference=ref
                )
            )
            setattr(self, attribute, tool)
        return tool

    def onMapClicked(self, point, reference=False):
        self.msg_signal.emit("", "i", 0)
        self.choose_point_click_handler.choosePointClicked(
            point=point,
            layer=None,
            ref=reference,
            start_callback=self.removePolygonDrawingTool(reference),
        )

        if reference:
            self._syncStandaloneReferenceOverlay()
            self.syncOffsetWithReference()

    def removeClickTool(self, reference=False):
        """Remove one role-specific point tool without affecting the other role."""
        attribute = "reference_click_tool" if reference else "click_tool"
        tool = getattr(self, attribute)
        if tool is None:
            return
        self.iface.mapCanvas().unsetMapTool(tool)
        setattr(self, attribute, None)

    def initializePolygonDrawingTool(self, reference=False):
        if not reference:
            if not self.drawing_tool:
                self.drawing_tool = (
                    PolygonDrawingTool(self.iface.mapCanvas(), callback=self.polygonDrawnCallback,
                                       start_callback=self.choose_point_click_handler.clearFeatureHighlight,
                                       settings_provider=lambda: self.map_indicator_settings.active))
            # FIXME: when push button is reactivated, current polygon is removed
            self.iface.mapCanvas().setMapTool(self.drawing_tool)
        else:
            if not self.drawing_tool_reference:
                self.drawing_tool_reference = (
                    PolygonDrawingTool(self.iface.mapCanvas(), callback=self.polygonDrawnCallback,
                                       start_callback=self.choose_point_click_handler.clearReferenceFeatureHighlight,
                                       role="reference", settings_provider=lambda: self.map_indicator_settings.active))
            self.iface.mapCanvas().setMapTool(self.drawing_tool_reference)

    def deactivatePolygonDrawingTool(self, reference=False):
        if not reference and self.drawing_tool:
            self.iface.mapCanvas().unsetMapTool(self.drawing_tool)
        elif reference and self.drawing_tool_reference:
            self.iface.mapCanvas().unsetMapTool(self.drawing_tool_reference)

    def removePolygonDrawingTool(self, reference=False):
        self.deactivatePolygonDrawingTool(reference=reference)
        if not reference and self.drawing_tool:
            self.drawing_tool.clear()
            self.drawing_tool = None
        elif reference and self.drawing_tool_reference:
            self.drawing_tool_reference.clear()
            self.drawing_tool_reference = None

    def clear_target_drawing_feedback(self) -> None:
        """Clear temporary target-polygon feedback without clearing target state."""
        if self.drawing_tool is not None:
            self.drawing_tool.clear_feedback()

    def clear_reference_drawing_feedback(self) -> None:
        """Clear temporary reference-polygon feedback without clearing reference state."""
        if self.drawing_tool_reference is not None:
            self.drawing_tool_reference.clear_feedback()

    def clear_all_pending_drawing_feedback(self) -> None:
        """Clear all temporary polygon-tool feedback safely and idempotently."""
        self.clear_target_drawing_feedback()
        self.clear_reference_drawing_feedback()

    def polygonDrawnCallback(self, polygon):
        reference = self.ui.pb_set_reference_polygon.isChecked()
        self.choose_point_click_handler.choosePolygonDrawn(polygon=polygon, ref=reference)
        if reference:
            self._syncStandaloneReferenceOverlay()
        self.syncOffsetWithReference()

    def _syncStandaloneReferenceOverlay(self) -> None:
        """Project an accepted Reference while no Target/pending record exists."""
        if self.choose_point_click_handler.plot_ts.pending_record() is not None:
            return
        reference = self.choose_point_click_handler.reference_session.current()
        if reference is None:
            self.pending_time_series_map_overlays.clear()
            return
        self.pending_time_series_map_overlays.project_reference(reference.selection)

    def _setReferenceValue(self, value):
        """Project one Reference value without relying on valueChanged feedback."""
        try:
            value = float(value)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(value):
            return False

        spin_box = self.ui.sb_symbol_value_offset
        was_blocked = spin_box.blockSignals(True)
        try:
            spin_box.setValue(value)
        finally:
            spin_box.blockSignals(was_blocked)
        self.insar_map.offset_value = float(spin_box.value())
        return True

    def _syncReferenceValueFromSelection(self):
        """Recompute linked Reference from the active field/reference selection."""
        field_name = self.ui.cb_select_field.currentText()
        value = self.choose_point_click_handler.referenceValueForField(field_name)
        if value is None:
            reference_session = getattr(
                self.choose_point_click_handler, "reference_session", None
            )
            if reference_session is not None and reference_session.current() is None:
                return self._setReferenceValue(0.0)
            return False
        return self._setReferenceValue(value)

    def syncOffsetWithReference(self):
        """Refresh linked Reference using the normal Live/Apply policy."""
        if not self.ui.cb_symbol_value_offset_sync_with_ref.isChecked():
            return False
        if not self._syncReferenceValueFromSelection():
            return False
        self.applyLiveSymbology()
        return True

    def connectUiSignals(self):
        self.ui.visibilityChanged.connect(self.handleUiClose)
        # self.ui.pb_add_layers.clicked.connect(self.addSelectedLayers)
        # self.ui.pb_remove_layers.clicked.connect(self.removeSelectedLayers)
        self.connectTimeseriesSignals()
        self.connectMapSignals()

        self.connectAboutSignals()
        self.msg_signal.connect(self.setMessageBar)

    def setMessageBar(self, message, v, t):

        width = self.ui.lb_msg_bar.width()
        font_metrics = self.ui.lb_msg_bar.fontMetrics()
        avg_char_width = max(1, font_metrics.horizontalAdvance(str(message)) // max(1, len(str(message))))
        buffer = 50
        num_chars = max(50, (width - buffer) // avg_char_width)

        info = ""
        tip = "💡 "
        warning, error, done = [f'<span style="font-size:10px">{s}</span>&nbsp;' for s in ["🟡️", "🟠", "🟢"]]

        if message == "":
            v = ''

        if v == 'w':
            message = warning + str(message)
        elif v == 'e':
            message = error + str(message)
        elif v == 'i':
            message = info + str(message)
        elif v == 't':
            message = tip + str(message)
        elif v == 'done':
            message = done + str(message)
        else:
            message = str(message)

        self.ui.lb_msg_bar.setText(message[:num_chars])

        if t > 0:
            # reset timer
            if not hasattr(self, '_msg_timer'):
                self._msg_timer = QTimer(self.ui)
                self._msg_timer.setSingleShot(True)
                self._msg_timer.timeout.connect(lambda: self.setMessageBar("", "", 0))
            self._msg_timer.stop()
            self._msg_timer.start(t)

    def connectAboutSignals(self):
        self.ui.label_about.setOpenExternalLinks(False)
        self.ui.label_about.linkActivated.connect(self.aboutLabelClicked)

    def aboutLabelClicked(self):
        from .ui_windows.message_box import MessageBox
        text = insar_explorer_about
        MessageBox(text)

    def connectTimeseriesSignals(self):
        panel = self.ui.time_series_point_panel
        panel.addPendingRequested.connect(self.addPendingTimeSeries)
        panel.discardPendingRequested.connect(self.discardPendingTimeSeries)
        panel.pendingLabelEdited.connect(self.updatePendingTimeSeriesLabel)
        panel.committedVisibilityEdited.connect(self.setCommittedTimeSeriesVisibility)
        panel.committedVisibilityAllRequested.connect(self.setAllCommittedTimeSeriesVisibility)
        panel.toggleSelectedCommittedVisibilityRequested.connect(
            self.toggleSelectedCommittedTimeSeriesVisibility
        )
        panel.committedLabelEdited.connect(self.updateCommittedTimeSeriesLabel)
        panel.committedSelectionChanged.connect(self.committedTimeSeriesSelectionChanged)
        panel.removeSelectedCommittedRequested.connect(
            self.removeSelectedCommittedTimeSeries
        )
        panel.exportSelectedCommittedRequested.connect(
            self.exportSelectedCommittedTimeSeries
        )
        panel.copyCommittedSettingsRequested.connect(
            self.copyCommittedTimeSeriesSettings
        )
        panel.pasteCommittedRequested.connect(self.pasteCommittedTimeSeriesSettings)
        panel.assignDistinctColorsRequested.connect(
            self.assignDistinctColorsToCommitted
        )
        panel.selectCommittedSourceLayerRequested.connect(
            self.selectCommittedTimeSeriesSourceLayer
        )
        panel.zoomCommittedTargetRequested.connect(
            self.zoomCommittedTimeSeriesTarget
        )
        panel.zoomCommittedReferenceRequested.connect(
            self.zoomCommittedTimeSeriesReference
        )
        panel.committedActionStateRefreshRequested.connect(
            self._refreshCommittedNavigationActionState
        )
        panel.indicatorSettingsRequested.connect(self.showMapIndicatorSettingsPopup)
        self.ui.pb_choose_point.clicked.connect(self.activatePointSelection)
        self.ui.pb_set_reference.clicked.connect(self.activateReferencePointSelection)
        self.ui.pb_reset_reference.clicked.connect(self.resetReferencePoint)
        self.ui.pb_choose_polygon.clicked.connect(self.activatePolygonSelection)
        self.ui.pb_set_reference_polygon.clicked.connect(self.activateReferencePolygonSelection)
        self.ui.cb_symbol_value_offset_sync_with_ref.clicked.connect(self.syncOffsetWithReferenceClicked)
        # TS fit handler
        self.ui.time_series_toolbar.fitEnabledChanged.connect(self.setTimeSeriesFitEnabled)
        self.ui.time_series_toolbar.fitModelChanged.connect(self.setTimeSeriesFitModel)
        self.ui.time_series_toolbar.fitSettingsRequested.connect(self.showFitPopup)
        self.ui.time_series_toolbar.seasonalEnabledChanged.connect(self.setTimeSeriesSeasonalEnabled)
        self.ui.time_series_toolbar.residualEnabledChanged.connect(self.setTimeSeriesResidualEnabled)
        self.ui.time_series_toolbar.xAxisModeChanged.connect(self.setTimeSeriesXAxisMode)
        self.ui.time_series_toolbar.manualXAxisEditRequested.connect(self.showManualXAxisPopup)
        self.manual_x_axis_popup.applyRequested.connect(self.applyManualXAxisRange)
        self.manual_x_axis_popup.cancelRequested.connect(self.cancelManualXAxisRange)
        self.manual_x_axis_popup.currentViewRequested.connect(self.captureCurrentManualXAxisView)
        self.manual_x_axis_popup.previewRequested.connect(self.previewManualXAxisRange)
        self.ui.time_series_toolbar.yAxisModeChanged.connect(self.setTimeSeriesYAxisMode)
        self.ui.time_series_toolbar.manualYAxisEditRequested.connect(self.showManualYAxisPopup)
        self.manual_y_axis_popup.previewChanged.connect(self.previewManualYAxisRange)
        self.manual_y_axis_popup.applyRequested.connect(self.applyManualYAxisRange)
        self.manual_y_axis_popup.cancelRequested.connect(self.cancelManualYAxisRange)
        self.manual_y_axis_popup.currentViewRequested.connect(self.captureCurrentManualYAxisView)
        self.ui.time_series_toolbar.replicaEnabledChanged.connect(
            self.setTimeSeriesReplicaEnabled
        )
        self.ui.time_series_toolbar.replicaSettingsRequested.connect(self.showReplicaPopup)
        self.ui.time_series_toolbar.plotStyleRequested.connect(self.showTimeSeriesStylePopup)
        fit_popup = self.fit_popup
        toolbar = self.ui.time_series_toolbar
        fit_popup.modelChanged.connect(toolbar.selectFitModel)
        fit_popup.seasonalEnabledChanged.connect(toolbar.seasonalEnabledChanged.emit)
        fit_popup.residualEnabledChanged.connect(toolbar.residualEnabledChanged.emit)
        fit_popup.fitLineTypeChanged.connect(
            lambda value: self._applySelectedFitStyle("line_type", value)
        )
        fit_popup.fitLineColorChanged.connect(
            lambda value: self._applySelectedFitStyle("line_color", value)
        )
        fit_popup.fitLineWidthChanged.connect(
            lambda value: self._applySelectedFitStyle("line_width", value)
        )
        fit_popup.fitOpacityChanged.connect(
            lambda value: self._applySelectedFitStyle("line_opacity", percent_to_alpha(value))
        )
        fit_popup.residualMarkerTypeChanged.connect(
            lambda value: self._applySelectedResidualStyle("marker_type", value)
        )
        fit_popup.residualMarkerColorChanged.connect(
            lambda value: self._applySelectedResidualStyle("marker_color", value)
        )
        fit_popup.residualMarkerSizeChanged.connect(
            lambda value: self._applySelectedResidualStyle("marker_size", value)
        )
        fit_popup.residualMarkerOpacityChanged.connect(
            lambda value: self._applySelectedResidualStyle("marker_opacity", percent_to_alpha(value))
        )
        fit_popup.residualLineTypeChanged.connect(
            lambda value: self._applySelectedResidualStyle("line_type", value)
        )
        fit_popup.residualLineColorChanged.connect(
            lambda value: self._applySelectedResidualStyle("line_color", value)
        )
        fit_popup.residualLineWidthChanged.connect(
            lambda value: self._applySelectedResidualStyle("line_width", value)
        )
        fit_popup.residualLineOpacityChanged.connect(
            lambda value: self._applySelectedResidualStyle("line_opacity", percent_to_alpha(value))
        )
        fit_popup.randomizeResidualColorRequested.connect(self.randomizeSelectedResidualColor)
        fit_popup.applySavedFitDefaultRequested.connect(self.restoreFitStyleDefaults)
        fit_popup.applyFactoryFitDefaultRequested.connect(self.applyFactoryFitStyleDefaults)
        fit_popup.saveCurrentFitAsDefaultRequested.connect(self.setCurrentFitStyleAsDefault)
        fit_popup.applySavedResidualDefaultRequested.connect(self.restoreResidualStyleDefaults)
        fit_popup.applyFactoryResidualDefaultRequested.connect(self.applyFactoryResidualStyleDefaults)
        fit_popup.saveCurrentResidualAsDefaultRequested.connect(self.setCurrentResidualStyleAsDefault)
        popup = self.time_series_style_popup
        popup.markerTypeChanged.connect(
            lambda value: self._applySelectedSeriesStyle("marker_type", value)
        )
        popup.markerColorChanged.connect(
            lambda value: self._applySelectedSeriesStyle("marker_color", value)
        )
        popup.markerSizeChanged.connect(
            lambda value: self._applySelectedSeriesStyle("marker_size", value)
        )
        popup.markerOpacityChanged.connect(
            lambda value: self._applySelectedSeriesStyle("marker_opacity", percent_to_alpha(value))
        )
        popup.lineTypeChanged.connect(lambda value: self._applySelectedSeriesStyle("line_type", value))
        popup.lineColorChanged.connect(lambda value: self._applySelectedSeriesStyle("line_color", value))
        popup.lineWidthChanged.connect(lambda value: self._applySelectedSeriesStyle("line_width", value))
        popup.lineOpacityChanged.connect(
            lambda value: self._applySelectedSeriesStyle("line_opacity", percent_to_alpha(value))
        )
        popup.randomizeColorRequested.connect(self.randomizeSelectedTimeSeriesColor)
        popup.applySavedSeriesDefaultRequested.connect(self.restoreSeriesStyleDefaults)
        popup.applyFactorySeriesDefaultRequested.connect(self.applyFactorySeriesStyleDefaults)
        popup.saveCurrentSeriesAsDefaultRequested.connect(self.setCurrentSeriesStyleAsDefault)
        popup.ensembleMemberColorChanged.connect(
            lambda value: self._applySelectedEnsembleStyle("member_color", value)
        )
        popup.ensembleMemberWidthChanged.connect(
            lambda value: self._applySelectedEnsembleStyle("member_width", value)
        )
        popup.ensembleMemberOpacityChanged.connect(
            lambda value: self._applySelectedEnsembleStyle("member_opacity", percent_to_alpha(value))
        )
        popup.ensembleFillColorChanged.connect(
            lambda value: self._applySelectedEnsembleStyle("fill_color", value)
        )
        popup.ensembleFillOpacityChanged.connect(
            lambda value: self._applySelectedEnsembleStyle("fill_opacity", percent_to_alpha(value))
        )
        popup.applySavedEnsembleDefaultRequested.connect(self.restoreEnsembleStyleDefaults)
        popup.applyFactoryEnsembleDefaultRequested.connect(self.applyFactoryEnsembleStyleDefaults)
        popup.saveCurrentEnsembleAsDefaultRequested.connect(self.setCurrentEnsembleStyleAsDefault)
        self._restoreTimeSeriesFitState()
        # Plot setting
        self._restoreTimeSeriesXAxisMode()
        self._restoreTimeSeriesYAxisMode()
        self._restoreTimeSeriesReplicaState()
        # TS save
        self.ui.time_series_toolbar.exportSettingsRequested.connect(self.showExportSettingsPopup)
        self.ui.time_series_toolbar.appearanceRequested.connect(self.showAppearancePopup)
        self.ui.time_series_toolbar.plotExportRequested.connect(self.saveTsPlot)

        self.export_settings_popup.settingsChanged.connect(self.updateExportSettings)
        self.export_settings_popup.applySavedDefaultRequested.connect(self.restoreExportDefaults)
        self.export_settings_popup.applyFactoryDefaultRequested.connect(self.applyFactoryExportDefaults)
        self.export_settings_popup.saveCurrentAsDefaultRequested.connect(self.setCurrentExportAsDefault)
        self.appearance_popup.settingsChanged.connect(self.updateAppearanceSettings)
        self.appearance_popup.applySavedDefaultRequested.connect(self.restoreAppearanceDefaults)
        self.appearance_popup.applyFactoryDefaultRequested.connect(self.applyFactoryAppearanceDefaults)
        self.appearance_popup.saveCurrentAsDefaultRequested.connect(self.setCurrentAppearanceAsDefault)
        self.replica_popup.settingsChanged.connect(self.updateReplicaCoreSettings)
        self.replica_popup.applySavedDefaultRequested.connect(self.restoreReplicaDefaults)
        self.replica_popup.applyFactoryDefaultRequested.connect(self.applyFactoryReplicaDefaults)
        self.replica_popup.saveCurrentAsDefaultRequested.connect(self.setCurrentReplicaAsDefault)
        indicator_popup = self.map_indicator_settings_popup
        indicator_popup.settingsChanged.connect(self.updateMapIndicatorSettings)
        indicator_popup.applySavedDefaultRequested.connect(
            self.restoreMapIndicatorDefaults
        )
        indicator_popup.applyFactoryDefaultRequested.connect(
            self.applyFactoryMapIndicatorDefaults
        )
        indicator_popup.saveCurrentAsDefaultRequested.connect(
            self.setCurrentMapIndicatorsAsDefault
        )

    def connectMapSignals(self):
        if not hasattr(self, "_range_source"):
            self._range_source = RangeSource.CUSTOM
        if not hasattr(self, "_range_source_raw_values"):
            self._range_source_raw_values = None
        if not hasattr(self, "_range_programmatic_update"):
            self._range_programmatic_update = False
        if not hasattr(self, "_std_calculation_mode"):
            self._std_calculation_mode = StdCalculationMode.FAST
        self._setStdCalculationMode(self._std_calculation_mode)
        self.ui.cb_select_field.currentIndexChanged.connect(self.selectVectorFieldChanged)
        self.ui.pb_symbology.clicked.connect(self.applySymbologyClicked)
        self.ui.sb_symbol_lower_range.valueChanged.connect(self.setSymbologyLowerRange)
        self.ui.sb_symbol_upper_range.valueChanged.connect(self.setSymbologyUpperRange)
        self.ui.cmb_symbol_range_source.currentIndexChanged.connect(
            self.symbologyRangeSourceChanged
        )
        self.ui.cmb_std_calculation_mode.currentIndexChanged.connect(
            self.stdCalculationModeChanged
        )
        self.ui.cb_symbol_range_symmetric.toggled.connect(
            self.symbologyRangeSymmetryChanged
        )
        range_popup = self.ui.map_settings_panel.range_settings_popup
        range_popup.applySavedDefaultRequested.connect(
            self.restoreMapRangeDefaults
        )
        range_popup.applyFactoryDefaultRequested.connect(
            self.applyFactoryMapRangeDefaults
        )
        range_popup.saveCurrentAsDefaultRequested.connect(
            self.setCurrentMapRangeAsDefault
        )
        self.ui.sb_symbol_value_offset.valueChanged.connect(self.setSymbologyOffset)
        self.ui.sb_symbol_classes.valueChanged.connect(self.applyLiveSymbology)
        self.ui.cb_symbol_continuous_colormap.toggled.connect(
            self.continuousColormapChanged
        )
        self.ui.sb_symbol_size.valueChanged.connect(self.applyLiveSymbology)
        self.ui.cmb_symbol_marker_shape.currentIndexChanged.connect(
            self.applyLiveSymbology
        )
        self.ui.pb_symbol_outline_color.colorChanged.connect(
            self.applyLiveSymbology
        )
        self.ui.sb_symbol_outline_width.valueChanged.connect(
            self.applyLiveSymbology
        )
        self.ui.sb_symbol_opacity.valueChanged.connect(self.applyLiveSymbology)
        symbology_popup = self.ui.map_settings_panel.symbology_settings_popup
        symbology_popup.applySavedDefaultRequested.connect(
            self.restoreMapSymbologyDefaults
        )
        symbology_popup.applyFactoryDefaultRequested.connect(
            self.applyFactoryMapSymbologyDefaults
        )
        symbology_popup.saveCurrentAsDefaultRequested.connect(
            self.setCurrentMapSymbologyAsDefault
        )
        self.ui.cb_symbology_live.toggled.connect(self.activateLiveSymbology)
        self.ui.cmb_colormap.currentIndexChanged.connect(self.applyLiveSymbology)
        self.ui.pb_colormap_reverse.toggled.connect(self.colormapReverseClicked)
        self._connectMapToolSync()
        self._setSymbologyDirty(False)

    def _connectMapToolSync(self):
        """Connect once to the canvas map-tool lifecycle."""
        if self._map_tool_signal_connected:
            return
        self.iface.mapCanvas().mapToolSet.connect(self._onMapToolChanged)
        self._map_tool_signal_connected = True

    def disconnectMapToolSync(self):
        """Disconnect the long-lived canvas map-tool signal during teardown."""
        if not self._map_tool_signal_connected:
            return
        try:
            self.iface.mapCanvas().mapToolSet.disconnect(self._onMapToolChanged)
        except (TypeError, RuntimeError):
            pass
        self._map_tool_signal_connected = False

    def _syncSelectionControlsToActiveMapTool(self):
        """Project the current canvas tool without changing QGIS interaction state."""
        self._onMapToolChanged(self.iface.mapCanvas().mapTool())

    @staticmethod
    def _isActiveMapTool(new_tool, tool):
        """Return whether an initialized plugin tool is the active canvas tool."""
        return tool is not None and new_tool is tool

    def _onMapToolChanged(self, new_tool, old_tool=None):
        """Project the actual active QGIS map tool into selection-button state."""
        del old_tool
        if new_tool is None:
            button_states = (
                (self.ui.pb_choose_point, False),
                (self.ui.pb_choose_polygon, False),
                (self.ui.pb_set_reference, False),
                (self.ui.pb_set_reference_polygon, False),
            )
        else:
            button_states = (
                (
                    self.ui.pb_choose_point,
                    self._isActiveMapTool(new_tool, self.click_tool),
                ),
                (
                    self.ui.pb_choose_polygon,
                    self._isActiveMapTool(new_tool, self.drawing_tool),
                ),
                (
                    self.ui.pb_set_reference,
                    self._isActiveMapTool(new_tool, self.reference_click_tool),
                ),
                (
                    self.ui.pb_set_reference_polygon,
                    self._isActiveMapTool(new_tool, self.drawing_tool_reference),
                ),
            )
        blockers = [QSignalBlocker(button) for button, _ in button_states]
        try:
            for button, checked in button_states:
                button.setChecked(checked)
        finally:
            del blockers

    def _setRangeSource(self, source):
        """Set semantic source and project it into the popup without feedback."""
        if not isinstance(source, RangeSource):
            raise ValueError("Unsupported Map Settings range source: {!r}".format(source))
        self._range_source = source
        self._syncStdCalculationControlEnabled()
        combo = getattr(self.ui, "cmb_symbol_range_source", None)
        if combo is None:
            return
        index = combo.findData(source.value)
        if index < 0 or index == combo.currentIndex():
            return
        combo.blockSignals(True)
        try:
            combo.setCurrentIndex(index)
        finally:
            combo.blockSignals(False)

    def _syncStdCalculationControlEnabled(self):
        """Enable calculation policy only when a Std-derived source is active."""
        combo = getattr(self.ui, "cmb_std_calculation_mode", None)
        if combo is not None:
            combo.setEnabled(self._range_source in STD_RANGE_SOURCES)

    def _setStdCalculationMode(self, mode):
        """Set calculation mode and project it into the popup without feedback."""
        if not isinstance(mode, StdCalculationMode):
            raise ValueError("Unsupported Std calculation mode: {!r}".format(mode))
        self._std_calculation_mode = mode
        combo = getattr(self.ui, "cmb_std_calculation_mode", None)
        if combo is not None:
            index = combo.findData(mode.value)
            if index >= 0 and index != combo.currentIndex():
                blocked = combo.blockSignals(True)
                try:
                    combo.setCurrentIndex(index)
                finally:
                    combo.blockSignals(blocked)
        self._syncStdCalculationControlEnabled()

    def stdCalculationModeChanged(self, index):
        """Recompute an active Std source when its calculation policy changes."""
        value = self.ui.cmb_std_calculation_mode.itemData(index)
        try:
            mode = StdCalculationMode(value)
        except (TypeError, ValueError):
            return
        if mode is self._std_calculation_mode:
            return
        self._std_calculation_mode = mode
        if self._range_source in STD_RANGE_SOURCES:
            self.setSymbologyRangeSource(self._range_source)

    def _setCustomRangeSource(self):
        """Mark the displayed range as user-owned and discard computed-source state."""
        self._range_source_raw_values = None
        self._setRangeSource(RangeSource.CUSTOM)

    def _setDisplayedRange(self, minimum, maximum):
        """Project a controller-owned range without triggering manual-edit semantics."""
        self._range_programmatic_update = True
        lower = self.ui.sb_symbol_lower_range
        upper = self.ui.sb_symbol_upper_range
        lower.blockSignals(True)
        upper.blockSignals(True)
        try:
            lower.setValue(float(minimum))
            upper.setValue(float(maximum))
        finally:
            lower.blockSignals(False)
            upper.blockSignals(False)
            self._range_programmatic_update = False

    def _symmetricRange(self, minimum, maximum):
        """Return the largest-absolute range symmetric around zero."""
        limit = max(abs(float(minimum)), abs(float(maximum)))
        return -limit, limit

    def setSymbologyUpperRange(self):
        if not self._range_programmatic_update:
            self._setCustomRangeSource()
        if self.ui.cb_symbol_range_symmetric.isChecked():
            limit = abs(self.ui.sb_symbol_upper_range.value())
            self._setDisplayedRange(-limit, limit)
        self.applyLiveSymbology()

    def setSymbologyLowerRange(self):
        if not self._range_programmatic_update:
            self._setCustomRangeSource()
        if self.ui.cb_symbol_range_symmetric.isChecked():
            limit = abs(self.ui.sb_symbol_lower_range.value())
            self._setDisplayedRange(-limit, limit)
        self.applyLiveSymbology()

    def symbologyRangeSourceChanged(self, index):
        """Apply the source selected in the range settings popup."""
        value = self.ui.cmb_symbol_range_source.itemData(index)
        try:
            source = RangeSource(value)
        except (TypeError, ValueError):
            return
        self.setSymbologyRangeSource(source)

    def symbologyRangeSymmetryChanged(self, status):
        if self._range_source is RangeSource.CUSTOM or self._range_source_raw_values is None:
            minimum = self.ui.sb_symbol_lower_range.value()
            maximum = self.ui.sb_symbol_upper_range.value()
            if status:
                minimum, maximum = self._symmetricRange(minimum, maximum)
                self._setDisplayedRange(minimum, maximum)
        else:
            minimum, maximum = self._range_source_raw_values
            if status:
                minimum, maximum = self._symmetricRange(minimum, maximum)
            self._setDisplayedRange(minimum, maximum)

        if status:
            self.msg_signal.emit("Range symmetry enabled.", 't', 0)
        else:
            self.msg_signal.emit("Range symmetry disabled.", 'i', 0)
        self.applyLiveSymbology()

    def continuousColormapChanged(self, status):
        """Apply one semantic discrete/continuous colormap mode change."""
        self.insar_map.continuous_colormap = bool(status)
        self.applyLiveSymbology()

    def setSymbologyOffset(self):
        self.insar_map.offset_value = self.ui.sb_symbol_value_offset.value()
        self.applyLiveSymbology()

    def _computeRangeSourceValues(self, source):
        """Return raw values for one computed range source without changing UI state."""
        error = self.insar_map.setSymbologyRangeFromData(
            n_std=source.standard_deviations,
            std_calculation_mode=(
                self._std_calculation_mode if source in STD_RANGE_SOURCES else None
            ),
        )
        if error:
            return None, error
        return (float(self.insar_map.min_value), float(self.insar_map.max_value)), ""

    def _projectComputedRangeSource(self, source, raw_values):
        """Store and display a successfully computed range source."""
        raw_minimum, raw_maximum = raw_values
        self._range_source_raw_values = (raw_minimum, raw_maximum)
        minimum, maximum = raw_minimum, raw_maximum
        if self.ui.cb_symbol_range_symmetric.isChecked():
            minimum, maximum = self._symmetricRange(minimum, maximum)
        self._setDisplayedRange(minimum, maximum)
        self._setRangeSource(source)

    def setSymbologyRangeSource(self, source):
        """Compute and project one explicit range source using existing map statistics."""
        if not isinstance(source, RangeSource):
            raise ValueError("Unsupported Map Settings range source: {!r}".format(source))
        if source is RangeSource.CUSTOM:
            self._setCustomRangeSource()
            return

        previous_source = self._range_source
        previous_raw_values = self._range_source_raw_values
        raw_values, error = self._computeRangeSourceValues(source)
        if error:
            self._range_source_raw_values = previous_raw_values
            self._setRangeSource(previous_source)
            self.msg_signal.emit(error, 'i', 0)
            return

        self._projectComputedRangeSource(source, raw_values)

        messages = {
            RangeSource.DATA_EXTENT: "Symbology range set from data extent.",
            RangeSource.STD_1: "Symbology range set to mean±1σ.",
            RangeSource.STD_2: "Symbology range set to mean±2σ.",
            RangeSource.STD_3: "Symbology range set to mean±3σ.",
        }
        self.msg_signal.emit(messages[source], 'i', 0)
        self.applyLiveSymbology()

    def _currentMapRangePolicyDefaults(self):
        """Capture the dataset-independent policy owned by the Range popup."""
        return normalize_range_policy_defaults(RangePolicyDefaults(
            range_source=self._range_source,
            calculation=self._std_calculation_mode,
            symmetric_around_zero=bool(
                self.ui.cb_symbol_range_symmetric.isChecked()
            ),
        ))

    def _projectMapRangePolicy(self, settings, publish_edit=True):
        """Recalculate one normalized range policy against the active dataset."""
        settings = normalize_range_policy_defaults(settings)
        previous_mode = self._std_calculation_mode
        previous_symmetric = self.ui.cb_symbol_range_symmetric.isChecked()
        self._setStdCalculationMode(settings.calculation)
        raw_values, error = self._computeRangeSourceValues(settings.range_source)
        if error:
            self._setStdCalculationMode(previous_mode)
            self._setRangeSymmetryChecked(previous_symmetric)
            self.msg_signal.emit(error, 'i', 0)
            return False

        self._setRangeSymmetryChecked(settings.symmetric_around_zero)
        self._projectComputedRangeSource(settings.range_source, raw_values)
        if publish_edit:
            self.applyLiveSymbology()
        return True

    def restoreMapRangeDefaults(self):
        """Apply the user's saved reusable Range policy as one normal edit."""
        self._projectMapRangePolicy(self.map_range_defaults.load_defaults())

    def applyFactoryMapRangeDefaults(self):
        """Apply factory Range policy values without changing saved defaults."""
        self._projectMapRangePolicy(self.map_range_defaults.factory_defaults())

    def setCurrentMapRangeAsDefault(self):
        """Persist current reusable Range policy values as the user default."""
        if self._range_source is RangeSource.CUSTOM:
            self.msg_signal.emit(
                "Custom numeric ranges cannot be saved as a default. "
                "Choose a calculated range source first.",
                "i",
                5000,
            )
            return

        self.map_range_defaults.save_defaults(self._currentMapRangePolicyDefaults())
        self.msg_signal.emit("Map range policy default saved.", "done", 5000)

    def _currentMapSymbologySettings(self):
        """Capture the settings owned by the Symbology settings popup."""
        return normalize_map_symbology_settings(MapSymbologySettings(
            continuous_colormap=bool(
                self.ui.cb_symbol_continuous_colormap.isChecked()
            ),
            classes=int(self.ui.sb_symbol_classes.value()),
            marker_shape=str(self.ui.cmb_symbol_marker_shape.currentData()),
            marker_size=float(self.ui.sb_symbol_size.value()),
            outline_color=str(self.ui.pb_symbol_outline_color.color()),
            outline_width_mm=float(self.ui.sb_symbol_outline_width.value()),
            opacity_percent=int(self.ui.sb_symbol_opacity.value()),
        ))

    def _applyMapSymbologySettingsBundle(self, settings):
        """Project one normalized popup settings bundle and publish one edit."""
        settings = normalize_map_symbology_settings(settings)
        controls = (
            self.ui.cb_symbol_continuous_colormap,
            self.ui.sb_symbol_classes,
            self.ui.cmb_symbol_marker_shape,
            self.ui.sb_symbol_size,
            self.ui.pb_symbol_outline_color,
            self.ui.sb_symbol_outline_width,
            self.ui.sb_symbol_opacity,
        )
        blockers = [QSignalBlocker(control) for control in controls]
        try:
            self.ui.cb_symbol_continuous_colormap.setChecked(
                settings.continuous_colormap
            )
            self.ui.sb_symbol_classes.setValue(settings.classes)
            shape_index = self.ui.cmb_symbol_marker_shape.findData(
                settings.marker_shape
            )
            if shape_index >= 0:
                self.ui.cmb_symbol_marker_shape.setCurrentIndex(shape_index)
            self.ui.sb_symbol_size.setValue(settings.marker_size)
            self.ui.pb_symbol_outline_color.setColor(settings.outline_color)
            self.ui.sb_symbol_outline_width.setValue(settings.outline_width_mm)
            self.ui.sb_symbol_opacity.setValue(settings.opacity_percent)
        finally:
            del blockers
        self.ui.map_settings_panel.symbology_settings_popup.set_continuous_colormap(
            settings.continuous_colormap
        )
        self.applyLiveSymbology()

    def restoreMapSymbologyDefaults(self):
        """Apply the user's saved Map Symbology default as one normal edit."""
        self._applyMapSymbologySettingsBundle(
            self.map_symbology_defaults.load_defaults()
        )

    def applyFactoryMapSymbologyDefaults(self):
        """Apply factory Map Symbology values without changing saved defaults."""
        self._applyMapSymbologySettingsBundle(
            self.map_symbology_defaults.factory_defaults()
        )

    def setCurrentMapSymbologyAsDefault(self):
        """Persist current popup-owned Map Symbology values as the user default."""
        self.map_symbology_defaults.save_defaults(
            self._currentMapSymbologySettings()
        )
        self.msg_signal.emit("Map symbology default saved.", "done", 5000)

    def _setSymbologyDirty(self, dirty):
        """Project unapplied Map Settings state onto the manual Apply action."""
        self._symbology_dirty = bool(dirty)
        self.ui.pb_symbology.setEnabled(self._symbology_dirty)

    def _applySymbologyAndClearPending(self):
        """Apply current Map Settings and update pending state from the result."""
        applied = self.applySymbology()
        self._setSymbologyDirty(not applied)
        return applied

    def applyLiveSymbology(self):
        if self.ui.cb_symbology_live.isChecked():
            self._applySymbologyAndClearPending()
        else:
            self._setSymbologyDirty(True)

    def activateLiveSymbology(self, status):
        if status:
            self._applySymbologyAndClearPending()
            self.msg_signal.emit("Live symbology enabled: changes will apply immediately.", 'done', 0)
        else:
            self._setSymbologyDirty(False)
            self.msg_signal.emit("Live symbology disabled.", 'i', 0)

    def applySymbologyNow(self):
        QTimer.singleShot(0, self._applySymbologyAndClearPending)

    def applySymbology(self):
        self.insar_map.selected_field_name = self.ui.cb_select_field.currentText()
        self.insar_map.min_value = float(self.ui.sb_symbol_lower_range.value())
        self.insar_map.max_value = float(self.ui.sb_symbol_upper_range.value())
        self.insar_map.num_classes = int(self.ui.sb_symbol_classes.value())
        self.insar_map.continuous_colormap = bool(
            self.ui.cb_symbol_continuous_colormap.isChecked()
        )
        self.insar_map.alpha = float(self.ui.sb_symbol_opacity.value()) / 100
        self.insar_map.symbol_size = float(self.ui.sb_symbol_size.value())
        self.insar_map.marker_shape = str(
            self.ui.cmb_symbol_marker_shape.currentData()
        )
        self.insar_map.stroke_color = str(
            self.ui.pb_symbol_outline_color.color()
        )
        self.insar_map.stroke_width = float(
            self.ui.sb_symbol_outline_width.value()
        )
        self.insar_map.color_ramp_name = str(self.ui.cmb_colormap.currentData())
        message = self.insar_map.setSymbology()
        if message != "":
            self.msg_signal.emit(message, "i", 0)
        else:
            self.msg_signal.emit("", "", 0)
        return message == ""

    def applySymbologyClicked(self, status):
        if self._applySymbologyAndClearPending():
            self.msg_signal.emit("Symbology applied.", "done", 5000)

    def colormapReverseClicked(self, status):
        if status:
            self.msg_signal.emit("Colormap reversed.", "i", 0)
        else:
            self.msg_signal.emit("Colormap normal.", "i", 0)
        self.flipComboBoxIcons(self.ui.cmb_colormap)
        self.insar_map.color_ramp_reverse_flag = status
        self.applyLiveSymbology()

    def flipComboBoxIcons(self, combo_box: QComboBox):
        for index in range(combo_box.count()):
            icon = combo_box.itemIcon(index)
            if not icon.isNull():
                pixmap = icon.pixmap(icon.availableSizes()[0])
                transform = QTransform().scale(-1, 1)  # fip horizontally
                flipped_pixmap = pixmap.transformed(transform)
                combo_box.setItemIcon(index, QIcon(flipped_pixmap))

    @staticmethod
    def _formatFitRmse(value):
        """Format RMSE without rounding a small non-zero value to zero."""
        value = float(value)
        if value == 0.0:
            return "0.00"
        if abs(value) >= 0.01:
            return f"{value:.2f}"
        return f"{value:.2g}"

    def _handleTimeSeriesFitSuccess(self, model_id, statistics, *, seasonal=False):
        """Report transient quality metrics for one fresh successful fit."""
        label = {
            "poly-1": "Linear",
            "poly-2": "Quadratic",
            "poly-3": "Cubic",
            "exp": "Exponential",
            "log": "Logarithmic",
        }.get(model_id, "Model")
        r_squared = (
            "n/a" if statistics.r_squared is None else f"{statistics.r_squared:.3f}"
        )
        seasonal_suffix = " + seasonal" if seasonal else ""
        message = (
            f"R² {r_squared} · "
            f"RMSE {self._formatFitRmse(statistics.rmse)} mm — "
            f"{label}{seasonal_suffix} fit"
        )
        self._last_fit_statistics_message = message
        self.msg_signal.emit(message, "i", 6000)

    def _handleTimeSeriesFitFailure(self, error, *, seasonal=False):
        """Show a non-modal fitting failure message without retaining stale statistics."""
        self._last_fit_statistics_message = None
        label = {
            "exp": "Exponential",
            "log": "Logarithmic",
        }.get(error.model_id, "Model")
        self.msg_signal.emit(
            f"{label} fit failed for the current series.", "e", 6000
        )

    def _restoreTimeSeriesFitState(self):
        """Restore session fit state after UI, plotter, or layer lifecycle changes."""
        state = self.time_series_fit_state
        state.setSelectedModel(state.selected_fit_model)
        self._applyTimeSeriesFitState(refresh=False)

    def resetTimeSeriesFitState(self):
        """Reset fit activity while retaining a valid selected model for this session."""
        self.time_series_fit_state.setFitEnabled(False)
        self.time_series_fit_state.residual_enabled = False
        self._applyTimeSeriesFitState(refresh=False)

    def _syncTimeSeriesFitControls(self):
        """Synchronize the code-created toolbar from shared fit state."""
        state = self.time_series_fit_state
        toolbar = self.ui.time_series_toolbar
        toolbar.setFitEnabled(state.fit_enabled)
        toolbar.setSelectedFitModel(state.selected_fit_model)
        toolbar.setSeasonalEnabled(state.seasonal_enabled)
        toolbar.setResidualEnabled(state.residual_enabled)
        if hasattr(self, "fit_popup"):
            self.fit_popup.setSettings(
                state.selected_fit_model,
                state.seasonal_enabled,
                state.residual_enabled,
            )
            self._refreshFitPopupAvailability()

    def _syncActiveAnalysisControls(self, record):
        """Project active-record analysis into controller controls without rerendering."""
        if record is None:
            return
        fit = record.analysis.fit
        state = self.time_series_fit_state
        state.fit_enabled = fit.enabled
        if fit.model is not None:
            state.setSelectedModel(fit.model)
        state.seasonal_enabled = fit.seasonal
        state.residual_enabled = fit.show_residuals
        replica = record.analysis.replica
        self._replica_enabled_view = replica.enabled
        self._replica_interval_view = replica.interval_mm
        self._replica_pair_count_view = replica.pair_count
        self._syncTimeSeriesFitControls()
        self._syncTimeSeriesReplicaControls()

    def _applyTimeSeriesFitState(
        self, refresh=True, *, report_statistics: bool = False,
    ):
        """Apply fit state and optionally report one explicit fit recalculation."""
        state = self.time_series_fit_state
        plotter = self.choose_point_click_handler.plot_ts
        plotter.fit_models = [state.selected_fit_model] if state.fit_enabled else []
        plotter.fit_seasonal_flag = state.seasonal_enabled
        plotter.plot_residuals_flag = state.residual_enabled and state.fit_enabled
        fit_config = FitConfiguration(
            enabled=state.fit_enabled,
            model=state.selected_fit_model if state.fit_enabled else None,
            seasonal=state.seasonal_enabled,
            show_residuals=state.residual_enabled and state.fit_enabled,
        )
        self._syncTimeSeriesFitControls()
        if refresh and plotter.editable_time_series_record() is not None:
            with plotter.axisViewUpdateGuard():
                plotter.updateActiveAnalysis(
                    fit=fit_config,
                    report_statistics=report_statistics,
                )
        if hasattr(self, "time_series_style_popup"):
            self._refreshTimeSeriesStylePopup()

    def setTimeSeriesFitEnabled(self, enabled):
        """Commit Fit intent and rebuild any dependent residual layout once."""
        state = self.time_series_fit_state
        state.setFitEnabled(enabled)
        plotter = self.choose_point_click_handler.plot_ts
        self._last_fit_statistics_message = None
        with plotter.axisViewUpdateGuard():
            self._applyTimeSeriesFitState(
                refresh=True,
                report_statistics=bool(enabled),
            )
            plotter.initializeAxes()
        current = plotter.editable_time_series_record()
        if current is not None:
            self._syncActiveAnalysisControls(current)
        self._persistCurrentFitAnalysisDefaults()
        if not enabled:
            self.msg_signal.emit("No fit model selected.", "i", 0)

    def setTimeSeriesFitModel(self, model):
        """Select a model and refresh only when fitting is active."""
        self.time_series_fit_state.setSelectedModel(model)
        fit_enabled = self.time_series_fit_state.fit_enabled
        if fit_enabled:
            self._last_fit_statistics_message = None
        self._applyTimeSeriesFitState(
            refresh=fit_enabled,
            report_statistics=fit_enabled,
        )
        self._persistCurrentFitAnalysisDefaults()

    def setTimeSeriesSeasonalEnabled(self, enabled):
        """Set seasonal fitting and activate fitting when seasonal is enabled."""
        self.time_series_fit_state.setSeasonalEnabled(enabled)
        fit_enabled = self.time_series_fit_state.fit_enabled
        if fit_enabled:
            self._last_fit_statistics_message = None
        self._applyTimeSeriesFitState(
            report_statistics=fit_enabled,
        )
        self._persistCurrentFitAnalysisDefaults()

    def setTimeSeriesResidualEnabled(self, enabled):
        """Commit residual intent once, then rebuild the matching axes layout."""
        self.time_series_fit_state.setResidualEnabled(enabled)
        state = self.time_series_fit_state
        plotter = self.choose_point_click_handler.plot_ts
        fit_config = FitConfiguration(
            enabled=state.fit_enabled,
            model=state.selected_fit_model if state.fit_enabled else None,
            seasonal=state.seasonal_enabled,
            show_residuals=bool(state.fit_enabled and state.residual_enabled),
        )
        with plotter.axisViewUpdateGuard():
            if not plotter.updateActiveAnalysis(
                fit=fit_config, report_statistics=False
            ):
                self._applyTimeSeriesFitState(refresh=False)
            plotter.initializeAxes()
        # The rerender callback projects the committed record back into both UI
        # surfaces. Repeat the guarded projection for plotters without a callback.
        current = plotter.editable_time_series_record()
        if current is not None:
            self._syncActiveAnalysisControls(current)
        self._persistCurrentFitAnalysisDefaults()
        self.msg_signal.emit(
            "Residual plot enabled using the selected fit model."
            if enabled else "Residual plot disabled.", "i", 0
        )

    def _fitStyleAvailable(self):
        """Return Fit Style editability from Fit activation alone."""
        return bool(self.time_series_fit_state.fit_enabled)

    def _residualStyleAvailable(self):
        """Return Residual Style editability from Fit and residual feature state."""
        state = self.time_series_fit_state
        return bool(state.fit_enabled and state.residual_enabled)

    def _refreshFitStyleAvailability(self):
        """Synchronize Fit Style contents without rendering or emitting edits."""
        if hasattr(self, "fit_popup"):
            self.fit_popup.setFitStyleAvailable(self._fitStyleAvailable())

    def _refreshResidualStyleAvailability(self):
        """Synchronize Residual Style contents without rendering or emitting edits."""
        if hasattr(self, "fit_popup"):
            self.fit_popup.setResidualStyleAvailable(
                self._residualStyleAvailable()
            )

    def _refreshFitPopupAvailability(self):
        """Synchronize both Fit popup style domains from feature state."""
        self._refreshFitStyleAvailability()
        self._refreshResidualStyleAvailability()

    def selectedTimeSeriesSnapshots(self):
        """Return all explicit style-edit targets for current and future selection UIs."""
        return self.choose_point_click_handler.plot_ts.selectedTimeSeriesSnapshots()

    def timeSeriesStyleAvailability(self, snapshots=None):
        """Return centralized style-layer availability for the current selection."""
        snapshots = self.selectedTimeSeriesSnapshots() if snapshots is None else snapshots
        state = self.time_series_fit_state
        return TimeSeriesStyleAvailability.fromSelection(
            snapshots, fit_enabled=state.fit_enabled, residual_enabled=state.residual_enabled
        )

    def selectedSeriesStyles(self):
        """Return styles for all currently selected time-series snapshots."""
        return self.time_series_style_controller.selectedSeriesStyles(
            self.selectedTimeSeriesSnapshots()
        )

    def _selectedTimeSeriesSnapshots(self):
        """Return explicit current style-edit targets from the plotter selection API."""
        return self.selectedTimeSeriesSnapshots()

    def _applySelectedSeriesStyle(self, property_name, value):
        """Apply one style property to selected series and redraw exactly once."""
        snapshots = self._selectedTimeSeriesSnapshots()
        if not snapshots:
            return
        changed = self.time_series_style_controller.applyProperty(snapshots, property_name, value)
        self.choose_point_click_handler.plot_ts.rerenderTimeSeriesSnapshots(changed)

    def _currentFitStyle(self):
        """Return the authoritative runtime Fit appearance."""
        return self.time_series_settings.fit_current

    def _currentResidualStyle(self):
        """Return the authoritative runtime Residual appearance."""
        return self.time_series_settings.residual_current

    def _updateCurrentFitStyle(self, property_name, value):
        """Update one authoritative Fit property without touching saved defaults."""
        values = self._currentFitStyle().asParams()
        values[self.fit_style_controller.STYLE_KEYS[property_name]] = value
        style = FitStyleSettings.fromParams({"model fit": values})
        self.time_series_settings.replace_domain("fit_current", style)
        return style

    def _updateCurrentResidualStyle(self, property_name, value):
        """Update one authoritative Residual property without touching saved defaults."""
        values = self._currentResidualStyle().asParams()
        values[self.residual_style_controller.STYLE_KEYS[property_name]] = value
        style = ResidualStyleSettings.fromParams({"residual plot": values})
        self.time_series_settings.replace_domain("residual_current", style)
        return style

    def _applySelectedFitStyle(self, property_name, value):
        """Store one Fit property and rerender selected renderable targets once."""
        self._updateCurrentFitStyle(property_name, value)
        snapshots = self._selectedTimeSeriesSnapshots()
        if snapshots:
            changed = self.fit_style_controller.applyProperty(
                snapshots, property_name, value
            )
            if self.timeSeriesStyleAvailability(snapshots).fit_available:
                self.choose_point_click_handler.plot_ts.rerenderTimeSeriesSnapshots(
                    changed
                )
        self._refreshTimeSeriesStylePopup()

    def _applySelectedEnsembleStyle(self, property_name, value):
        """Apply one Ensemble property to applicable selected snapshots and redraw once."""
        snapshots = self._selectedTimeSeriesSnapshots()
        changed = self.ensemble_style_controller.applyProperty(snapshots, property_name, value)
        if not changed:
            return
        plotter = self.choose_point_click_handler.plot_ts
        y_axis_mode = self.time_series_y_axis_mode
        plotter.rerenderTimeSeriesSnapshots(changed)
        self.time_series_y_axis_mode = y_axis_mode
        self._refreshTimeSeriesStylePopup()

    def _applySelectedResidualStyle(self, property_name, value):
        """Store one Residual property and rerender selected visible targets once."""
        self._updateCurrentResidualStyle(property_name, value)
        snapshots = self._selectedTimeSeriesSnapshots()
        if snapshots:
            changed = self.residual_style_controller.applyProperty(
                snapshots, property_name, value
            )
            if self.timeSeriesStyleAvailability(snapshots).residual_available:
                self.choose_point_click_handler.plot_ts.rerenderTimeSeriesSnapshots(changed)
        self._refreshTimeSeriesStylePopup()

    def randomizeSelectedResidualColor(self):
        """Store one random residual color and apply it to selected targets."""
        from random import randint
        color = "#{:02x}{:02x}{:02x}".format(
            randint(0, 255), randint(0, 255), randint(0, 255)
        )
        values = self._currentResidualStyle().asParams()
        values.update({"marker color": color, "line color": color})
        current = ResidualStyleSettings.fromParams({"residual plot": values})
        self.time_series_settings.replace_domain("residual_current", current)
        snapshots = self._selectedTimeSeriesSnapshots()
        if snapshots:
            changed = self.residual_style_controller.applyValues(
                snapshots, current.asParams()
            )
            if self.timeSeriesStyleAvailability(snapshots).residual_available:
                self.choose_point_click_handler.plot_ts.rerenderTimeSeriesSnapshots(changed)
        self._refreshTimeSeriesStylePopup()

    def restoreEnsembleStyleDefaults(self):
        """Apply the persisted ensemble defaults to the selected ensemble series."""
        snapshots = self.ensemble_style_controller.applicableSnapshots(
            self._selectedTimeSeriesSnapshots()
        )
        if not snapshots:
            return
        defaults = self.choose_point_click_handler.plot_ts.user_preferences.load().ensemble_defaults
        changed = self.ensemble_style_controller.applyValues(
            snapshots, defaults.asParams()
        )
        self.choose_point_click_handler.plot_ts.rerenderTimeSeriesSnapshots(changed)
        self._refreshTimeSeriesStylePopup()

    def applyFactoryEnsembleStyleDefaults(self):
        """Apply canonical Ensemble style without changing saved defaults."""
        snapshots = self.ensemble_style_controller.applicableSnapshots(self._selectedTimeSeriesSnapshots())
        if snapshots:
            changed = self.ensemble_style_controller.applyValues(snapshots, EnsembleStyleSettings().asParams())
            self.choose_point_click_handler.plot_ts.rerenderTimeSeriesSnapshots(changed)
            self._refreshTimeSeriesStylePopup()

    def setCurrentEnsembleStyleAsDefault(self):
        """Persist selected Ensemble appearance for future ensemble snapshots only."""
        snapshots = self.ensemble_style_controller.applicableSnapshots(
            self._selectedTimeSeriesSnapshots()
        )
        if not snapshots:
            return
        ensemble_style = self.ensemble_style_controller.ensembleStyle(snapshots[0])
        plotter = self.choose_point_click_handler.plot_ts
        plotter.settings_model.replace_domain("ensemble_defaults", ensemble_style)
        self._saveUserPreferences(
            lambda: plotter.user_preferences.save_ensemble_defaults(ensemble_style),
            "Current ensemble style saved as default.",
        )

    def _applyCurrentResidualStyle(self, style):
        """Replace current Residual style and update selected render targets."""
        self.time_series_settings.replace_domain("residual_current", style)
        snapshots = self._selectedTimeSeriesSnapshots()
        if snapshots:
            changed = self.residual_style_controller.applyValues(
                snapshots, style.asParams()
            )
            if self.timeSeriesStyleAvailability(snapshots).residual_available:
                self.choose_point_click_handler.plot_ts.rerenderTimeSeriesSnapshots(changed)
        self._refreshTimeSeriesStylePopup()

    def restoreResidualStyleDefaults(self):
        """Apply saved Residual defaults to current and selected styles."""
        defaults = self.choose_point_click_handler.plot_ts.user_preferences.load().residual_defaults
        self._applyCurrentResidualStyle(defaults)

    def applyFactoryResidualStyleDefaults(self):
        """Apply canonical Residual style without changing saved defaults."""
        self._applyCurrentResidualStyle(ResidualStyleSettings())

    def setCurrentResidualStyleAsDefault(self):
        """Persist the authoritative current Residual appearance."""
        residual_style = self._currentResidualStyle()
        plotter = self.choose_point_click_handler.plot_ts
        plotter.settings_model.replace_domain("residual_defaults", residual_style)
        self._saveUserPreferences(
            lambda: plotter.user_preferences.save_residual_defaults(residual_style),
            "Current residual style saved as default.",
        )

    def randomizeSelectedTimeSeriesColor(self):
        """Randomize only selected series colors while preserving future defaults."""
        snapshots = self._selectedTimeSeriesSnapshots()
        if not snapshots:
            return
        changed = self.time_series_style_controller.randomizeColor(snapshots)
        self.choose_point_click_handler.plot_ts.rerenderTimeSeriesSnapshots(changed)
        self.time_series_style_popup.setStyle(changed[0].style)

    def restoreSeriesStyleDefaults(self):
        """Apply the persisted primary-series defaults to selected series."""
        snapshots = self._selectedTimeSeriesSnapshots()
        if not snapshots:
            return
        defaults = self.choose_point_click_handler.plot_ts.user_preferences.load().series_defaults
        changed = self.time_series_style_controller.applyStyleValues(
            snapshots, defaults.as_params()
        )
        self.choose_point_click_handler.plot_ts.rerenderTimeSeriesSnapshots(changed)
        self._refreshTimeSeriesStylePopup()

    def applyFactorySeriesStyleDefaults(self):
        """Apply canonical Series style without changing saved defaults."""
        snapshots = self._selectedTimeSeriesSnapshots()
        if snapshots:
            changed = self.time_series_style_controller.applyStyleValues(snapshots, SeriesStyleSettings().as_params())
            self.choose_point_click_handler.plot_ts.rerenderTimeSeriesSnapshots(changed)
            self._refreshTimeSeriesStylePopup()

    def setCurrentSeriesStyleAsDefault(self):
        """Persist the selected series style as the default for newly-created series."""
        snapshots = self._selectedTimeSeriesSnapshots()
        if not snapshots:
            return
        style = snapshots[0].style
        plotter = self.choose_point_click_handler.plot_ts
        series_defaults = SeriesStyleSettings.from_params(style.params)
        plotter.settings_model.replace_domain("series_defaults", series_defaults)
        self._saveUserPreferences(
            lambda: plotter.user_preferences.save_series_defaults(series_defaults),
            "Current plot style set as default for new time series.",
        )

    def _applyCurrentFitStyle(self, style):
        """Replace current Fit style and update selected render targets."""
        self.time_series_settings.replace_domain("fit_current", style)
        snapshots = self._selectedTimeSeriesSnapshots()
        if snapshots:
            changed = self.fit_style_controller.applyValues(
                snapshots, style.asParams()
            )
            if self.timeSeriesStyleAvailability(snapshots).fit_available:
                self.choose_point_click_handler.plot_ts.rerenderTimeSeriesSnapshots(changed)
        self._refreshTimeSeriesStylePopup()

    def restoreFitStyleDefaults(self):
        """Apply saved Fit defaults to current and selected styles."""
        defaults = self.choose_point_click_handler.plot_ts.user_preferences.load().fit_defaults
        self._applyCurrentFitStyle(defaults)

    def applyFactoryFitStyleDefaults(self):
        """Apply canonical Fit style without changing saved defaults."""
        self._applyCurrentFitStyle(FitStyleSettings())

    def setCurrentFitStyleAsDefault(self):
        """Persist the authoritative current Fit appearance."""
        fit_style = self._currentFitStyle()
        plotter = self.choose_point_click_handler.plot_ts
        plotter.settings_model.replace_domain("fit_defaults", fit_style)
        self._saveUserPreferences(
            lambda: plotter.user_preferences.save_fit_defaults(fit_style),
            "Current fit style saved as default.",
        )

    def _refreshFitStyleTab(self):
        """Refresh Fit controls from selection or authoritative current style."""
        snapshots = self.selectedTimeSeriesSnapshots()
        style = (self.fit_style_controller.fitStyle(snapshots[0])
                 if snapshots else self._currentFitStyle())
        self.fit_popup.setFitStyle(style)

    def _refreshTimeSeriesStylePopup(self):
        """Refresh popup controls from actual selected snapshot styles without edits."""
        snapshots = self.selectedTimeSeriesSnapshots()
        popup = self.time_series_style_popup
        availability = self.timeSeriesStyleAvailability(snapshots)
        popup.setLayerAvailability(availability)
        self._refreshFitPopupAvailability()
        if snapshots:
            styles = self.time_series_style_controller.selectedSeriesStyles(snapshots)
            popup.setStyle(styles[0])
            self.fit_popup.setFitStyle(
                self.fit_style_controller.fitStyle(snapshots[0])
            )
            self.fit_popup.setResidualStyle(
                self.residual_style_controller.residualStyle(snapshots[0])
            )
            ensemble_snapshots = self.ensemble_style_controller.applicableSnapshots(snapshots)
            if ensemble_snapshots:
                popup.setEnsembleStyle(self.ensemble_style_controller.ensembleStyle(ensemble_snapshots[0]))
            popup.setMixedProperties(
                self.time_series_style_controller.mixedProperties(snapshots)
            )
        else:
            self.fit_popup.setFitStyle(self._currentFitStyle())
            self.fit_popup.setResidualStyle(self._currentResidualStyle())
            popup.setMixedProperties(set())

    def syncAppearancePopup(self):
        """Refresh the Appearance popup from the authoritative runtime model."""
        self.appearance_popup.setSettings(
            self.choose_point_click_handler.plot_ts.settings_model.appearance
        )

    def updateAppearanceSettings(
        self, time_series_title, residual_title, time_series_x_label,
        time_series_y_label, residual_x_label, residual_y_label, date_format,
        font_size, grid_mode, plot_background, canvas_background,
    ):
        """Persist one complete appearance replacement after an immediate edit."""
        plotter = self.choose_point_click_handler.plot_ts
        current = plotter.settings_model.appearance
        settings = replace(
            current,
            time_series_title=str(time_series_title),
            residual_title=str(residual_title),
            time_series_x_label=str(time_series_x_label),
            time_series_y_label=str(time_series_y_label),
            residual_x_label=str(residual_x_label),
            residual_y_label=str(residual_y_label),
            date_format=str(date_format),
            font_size=float(font_size),
            grid_mode=AppearanceSettings.normalize_grid_mode(grid_mode),
            plot_background=str(plot_background),
            canvas_background=str(canvas_background),
        )
        plotter.settings_model.replace_domain("appearance", settings)
        plotter.refreshCompatibilityViews()
        self.syncAppearancePopup()

    def restoreAppearanceDefaults(self):
        """Restore Appearance controls from the currently persisted defaults."""
        plotter = self.choose_point_click_handler.plot_ts
        defaults = plotter.user_preferences.load().appearance
        plotter.settings_model.replace_domain("appearance", defaults)
        plotter.refreshCompatibilityViews()
        self.syncAppearancePopup()

    def setCurrentAppearanceAsDefault(self):
        """Persist an Appearance snapshot without changing current controls."""
        settings = self.choose_point_click_handler.plot_ts.settings_model.appearance
        self._saveUserPreferences(
            lambda: self.choose_point_click_handler.plot_ts.user_preferences.save_appearance(settings),
            "Current appearance saved as default.",
        )

    def applyFactoryAppearanceDefaults(self):
        """Apply canonical built-in Appearance values without changing saved defaults."""
        plotter = self.choose_point_click_handler.plot_ts
        plotter.settings_model.replace_domain("appearance", AppearanceSettings())
        plotter.refreshCompatibilityViews()
        self.syncAppearancePopup()

    def showAppearancePopup(self):
        """Open the anchored Appearance editor initialized from runtime state."""
        self.syncAppearancePopup()
        toolbar = self.ui.time_series_toolbar
        action_widget = toolbar.widgetForAction(toolbar.appearance_action)
        anchor = action_widget or toolbar
        self.appearance_popup.adjustSize()
        anchor_top_left = anchor.mapToGlobal(QPoint(0, 0))
        anchor_rect = QRect(anchor_top_left, anchor.size())
        geometry = available_screen_geometry(anchor_rect.center(), anchor)
        self.appearance_popup.move(screen_aware_popup_position(
            anchor_rect, self.appearance_popup.sizeHint(), geometry
        ))
        self.appearance_popup.show()
        self.appearance_popup.raise_()

    def syncExportSettingsPopup(self):
        """Refresh the export popup from the authoritative runtime model."""
        self.export_settings_popup.setSettings(
            self.choose_point_click_handler.plot_ts.settings_model.export
        )

    def updateExportSettings(self, dpi, aspect_ratio, include_attribution):
        """Normalize, commit, and persist one complete export settings value."""
        plotter = self.choose_point_click_handler.plot_ts
        settings = ExportSettings.normalized(dpi, aspect_ratio, include_attribution)
        plotter.settings_model.replace_domain("export", settings)
        plotter.parms = build_legacy_plot_params(plotter.settings_model, plotter.parms)
        self.syncExportSettingsPopup()

    def restoreExportDefaults(self):
        """Restore Save Figure controls from the currently persisted defaults."""
        plotter = self.choose_point_click_handler.plot_ts
        defaults = plotter.user_preferences.load().export
        plotter.settings_model.replace_domain("export", defaults)
        plotter.parms = build_legacy_plot_params(plotter.settings_model, plotter.parms)
        self.syncExportSettingsPopup()

    def setCurrentExportAsDefault(self):
        """Persist an Export snapshot without changing current controls."""
        settings = self.choose_point_click_handler.plot_ts.settings_model.export
        self._saveUserPreferences(
            lambda: self.choose_point_click_handler.plot_ts.user_preferences.save_export(settings),
            "Current export settings saved as default.",
        )

    def applyFactoryExportDefaults(self):
        """Apply canonical built-in Export values without changing saved defaults."""
        plotter = self.choose_point_click_handler.plot_ts
        plotter.settings_model.replace_domain("export", ExportSettings())
        plotter.parms = build_legacy_plot_params(plotter.settings_model, plotter.parms)
        self.syncExportSettingsPopup()

    def showExportSettingsPopup(self):
        """Open export defaults anchored to the Export Settings action."""
        self.syncExportSettingsPopup()
        toolbar = self.ui.time_series_toolbar
        anchor = toolbar.plot_export_button.secondary_button
        self.export_settings_popup.adjustSize()
        anchor_top_left = anchor.mapToGlobal(QPoint(0, 0))
        anchor_rect = QRect(anchor_top_left, anchor.size())
        geometry = available_screen_geometry(anchor_rect.center(), anchor)
        self.export_settings_popup.move(screen_aware_popup_position(
            anchor_rect, self.export_settings_popup.sizeHint(), geometry
        ))
        self.export_settings_popup.show()
        self.export_settings_popup.raise_()

    def showFitPopup(self):
        """Open the synchronized Fit popup below the split-button arrow."""
        self._syncTimeSeriesFitControls()
        self._refreshTimeSeriesStylePopup()
        anchor = self.ui.time_series_toolbar.fit_button.secondary_button
        self.fit_popup.adjustSize()
        anchor_top_left = anchor.mapToGlobal(QPoint(0, 0))
        anchor_rect = QRect(anchor_top_left, anchor.size())
        geometry = available_screen_geometry(anchor_rect.center(), anchor)
        self.fit_popup.move(screen_aware_popup_position(
            anchor_rect, self.fit_popup.sizeHint(), geometry
        ))
        self.fit_popup.show()
        self.fit_popup.raise_()

    def showTimeSeriesStylePopup(self):
        """Open the style popup anchored below the Plot style toolbar action."""
        self._refreshTimeSeriesStylePopup()
        toolbar = self.ui.time_series_toolbar
        action_widget = toolbar.widgetForAction(toolbar.plot_style_action)
        anchor = action_widget or toolbar
        self.time_series_style_popup.adjustSize()
        anchor_top_left = anchor.mapToGlobal(QPoint(0, 0))
        anchor_rect = QRect(anchor_top_left, anchor.size())
        available_geometry = available_screen_geometry(anchor_rect.center(), anchor)
        point = screen_aware_popup_position(
            anchor_rect,
            self.time_series_style_popup.sizeHint(),
            available_geometry,
        )
        self.time_series_style_popup.move(point)
        self.time_series_style_popup.show()
        self.time_series_style_popup.raise_()

    def _syncPendingTimeSeriesPanel(self, record):
        """Project pending panel and complete pending map geometry from the record."""
        panel = self.ui.time_series_point_panel
        if record is None:
            panel.clear_pending()
            self.pending_time_series_map_overlays.clear()
            self.choose_point_click_handler.clearFeatureHighlight()
            self.choose_point_click_handler.clearReferenceFeatureHighlight()
            self.clear_all_pending_drawing_feedback()
            self.time_series_map_overlays.set_pending_active(False)
            self.committedTimeSeriesSelectionChanged(panel.selected_committed_ids())
            return

        panel.show_pending(record)
        # Stable pending presentation is authoritative from the complete record
        # snapshot, not from whichever point/polygon tool ran most recently.
        self.pending_time_series_map_overlays.project_record(record)
        self.choose_point_click_handler.clearFeatureHighlight()
        self.choose_point_click_handler.clearReferenceFeatureHighlight()
        self.clear_all_pending_drawing_feedback()
        self.time_series_map_overlays.set_pending_active(True)
        self.ui.time_series_toolbar.setSeriesControlsEnabled(True)
        self._refreshTimeSeriesPlotActionState()

    def addPendingTimeSeries(self):
        """Atomically commit pending ownership and create committed-list metadata."""
        plotter = self.choose_point_click_handler.plot_ts
        pending = plotter.pending_record()
        if pending is None:
            return
        try:
            self.time_series_list_state.add(pending.id)
            try:
                committed = plotter.commit_pending()
            except Exception:
                self.time_series_list_state.remove(pending.id)
                raise
            panel = self.ui.time_series_point_panel
            panel.refresh_committed_model()
            panel.select_committed_record(committed.id)
        except Exception as error:
            if self._plugin_diagnostic is not None:
                self._plugin_diagnostic("pending_add", error)
            else:
                self.msg_signal.emit(str(error), "c", 0)

    def _syncCommittedTimeSeriesList(self, records):
        """Refresh list projection and clear session metadata on full store reset."""
        panel = self.ui.time_series_point_panel
        if not records:
            self.time_series_map_overlays.clear_committed()
            if self.time_series_list_state.entries():
                self.time_series_list_state.clear()
        if panel.committed_model is not None:
            panel.refresh_committed_model()
        self._refreshTimeSeriesPlotActionState()
        self._refreshCommittedNavigationActionState()

    def _clipboard_available_categories(self):
        """Return all paste categories when one coherent clipboard exists."""
        if self.time_series_clipboard is None:
            return ()
        return (
            CopyPasteCategory.STYLE,
            CopyPasteCategory.FIT,
            CopyPasteCategory.REPLICA,
            CopyPasteCategory.ALL_PRESENTATION,
        )

    def _refreshTimeSeriesClipboardProjection(self):
        """Project controller-owned clipboard availability into the list menu."""
        self.ui.time_series_point_panel.set_clipboard_categories(
            self._clipboard_available_categories()
        )

    def clearTimeSeriesClipboard(self):
        """Clear the dataset-scoped, non-persistent settings clipboard."""
        self.time_series_clipboard = None
        self._refreshTimeSeriesClipboardProjection()

    def _resolveTimeSeriesSourceLayer(self, record):
        """Resolve a committed record's exact source layer by stored QGIS layer ID."""
        source = None if record is None else record.source
        if source is None or not source.layer_id:
            return None
        return QgsProject.instance().mapLayer(source.layer_id)

    def _selectedCommittedTimeSeriesRecord(self):
        """Return the one unambiguous selected committed record, or ``None``."""
        selected = self.ui.time_series_point_panel.selected_committed_ids()
        if len(selected) != 1:
            return None
        return self.choose_point_click_handler.plot_ts.committed_record(selected[0])

    def _refreshCommittedSourceLayerActionState(self):
        """Enable source navigation only for one selected record with a live source."""
        panel = self.ui.time_series_point_panel
        record = self._selectedCommittedTimeSeriesRecord()
        source_layer = self._resolveTimeSeriesSourceLayer(record)
        panel.set_select_source_layer_enabled(source_layer is not None)
        return source_layer

    def _refreshCommittedMapNavigationActionState(self):
        """Project record-owned target/reference navigation availability."""
        panel = self.ui.time_series_point_panel
        record = self._selectedCommittedTimeSeriesRecord()
        target_location = None
        reference_location = None
        if record is not None:
            target_location = resolve_selection_navigation_location(record.target)
            reference_location = resolve_selection_navigation_location(record.reference)
        panel.set_map_navigation_enabled(
            target_enabled=target_location is not None,
            reference_enabled=reference_location is not None,
        )
        return target_location, reference_location

    def _refreshCommittedNavigationActionState(self):
        """Refresh all single-record committed map-navigation command states."""
        source_layer = self._refreshCommittedSourceLayerActionState()
        self._refreshCommittedMapNavigationActionState()
        return source_layer

    def selectCommittedTimeSeriesSourceLayer(self):
        """Select the exact originating QGIS layer for one committed time series."""
        panel = self.ui.time_series_point_panel
        record = self._selectedCommittedTimeSeriesRecord()
        source_layer = self._resolveTimeSeriesSourceLayer(record)
        if source_layer is None:
            panel.set_select_source_layer_enabled(False)
            return False
        self.iface.setActiveLayer(source_layer)
        return True

    def _reportCommittedNavigationFailure(
        self, record, role, stage, error, source_crs=None, destination_crs=None
    ):
        """Log a quiet committed map-navigation failure with useful context."""
        if self._plugin_diagnostic is None:
            return
        source_authid = (
            source_crs.authid() if source_crs is not None and source_crs.isValid() else "invalid"
        )
        destination_authid = (
            destination_crs.authid()
            if destination_crs is not None and destination_crs.isValid()
            else "invalid"
        )
        diagnostic_stage = (
            "committed_map_navigation:{}:{}:record={}:source_crs={}:destination_crs={}"
            .format(role, stage, getattr(record, "id", "unknown"), source_authid, destination_authid)
        )
        self._plugin_diagnostic(diagnostic_stage, error)

    def _showProjectCrsRequiredWarning(self, role):
        """Warn when explicit committed navigation needs an assigned project CRS."""
        QMessageBox.warning(
            self.ui,
            "Project CRS required",
            f"A project CRS must be set before InSAR Explorer can zoom to this {role}.",
            MESSAGE_BUTTON_OK,
        )

    def _navigateCommittedTimeSeriesSelection(self, role):
        """Recenter on one record-owned target/reference without changing active layer."""
        record = self._selectedCommittedTimeSeriesRecord()
        if record is None:
            self._refreshCommittedMapNavigationActionState()
            return False
        selection = record.target if role == "target" else record.reference
        try:
            location = resolve_selection_navigation_location(selection)
        except Exception as error:
            self._reportCommittedNavigationFailure(record, role, "geometry", error)
            return False
        if location is None:
            self._refreshCommittedMapNavigationActionState()
            return False

        canvas = self.iface.mapCanvas()
        project = QgsProject.instance()
        destination_crs = None
        try:
            destination_crs, established_project_crs = ensure_canvas_navigation_crs(
                canvas, project, location.source_crs
            )
        except Exception as error:
            self._reportCommittedNavigationFailure(
                record, role, "destination_crs", error, source_crs=location.source_crs
            )
            return False

        if destination_crs is None:
            if not location.canvas_compatible_without_crs:
                self._showProjectCrsRequiredWarning(role)
                return False
            destination_point = location.point
        else:
            try:
                destination_point = transform_navigation_point(
                    location, destination_crs, project
                )
            except Exception as error:
                self._reportCommittedNavigationFailure(
                    record, role, "transform", error,
                    source_crs=location.source_crs, destination_crs=destination_crs,
                )
                return False

        try:
            recenter_canvas_preserving_scale(
                canvas, destination_point, preserve_scale=not established_project_crs
            )
        except Exception as error:
            self._reportCommittedNavigationFailure(
                record, role, "recenter", error,
                source_crs=location.source_crs, destination_crs=destination_crs,
            )
            return False
        return True

    def zoomCommittedTimeSeriesTarget(self):
        """Center the QGIS map on the selected committed record's target."""
        return self._navigateCommittedTimeSeriesSelection("target")

    def zoomCommittedTimeSeriesReference(self):
        """Center the QGIS map on the selected committed record's reference."""
        return self._navigateCommittedTimeSeriesSelection("reference")

    def copyCommittedTimeSeriesSettings(self):
        """Atomically capture Style, Fit, and Replica from one committed source."""
        panel = self.ui.time_series_point_panel
        selected = panel.selected_committed_ids()
        if len(selected) != 1:
            return
        record = self.choose_point_click_handler.plot_ts.committed_record(
            selected[0]
        )
        if record is None:
            self._reportCopyPasteFailure(
                "copy", KeyError("selected committed time series no longer exists")
            )
            return
        try:
            clipboard = TimeSeriesSettingsClipboard(
                source_record_id=record.id,
                style=capture_style(record),
                fit=capture_fit(record),
                replica=capture_replica(record),
            )
        except Exception as error:
            self._reportCopyPasteFailure("copy", error)
            return
        self.time_series_clipboard = clipboard
        self._refreshTimeSeriesClipboardProjection()
        self.setMessageBar("Copied style, Fit and Replica", "done", 3000)

    def pasteCommittedTimeSeriesSettings(self, category):
        """Atomically paste one typed category to selected committed destinations."""
        try:
            category = CopyPasteCategory(category)
        except ValueError:
            return
        clipboard = self.time_series_clipboard
        if clipboard is None or not clipboard.has(category):
            return
        panel = self.ui.time_series_point_panel
        selection_snapshot = panel.capture_committed_selection()
        requested = selection_snapshot.selected_record_ids
        if not requested:
            return
        # Preserve model order and remove duplicate UUIDs before preflight.
        requested_set = set(requested)
        record_ids = tuple(
            entry.record_id for entry in self.time_series_list_state.entries()
            if entry.record_id in requested_set
        )
        plotter = self.choose_point_click_handler.plot_ts
        try:
            originals = tuple(
                plotter.committed_record(record_id) for record_id in record_ids
            )
            if any(record is None for record in originals):
                raise KeyError("one or more selected committed time series no longer exist")
            replacements = []
            for record in originals:
                updated = record
                if category in (CopyPasteCategory.STYLE, CopyPasteCategory.ALL_PRESENTATION):
                    updated = apply_style_snapshot(updated, clipboard.style)
                if category in (CopyPasteCategory.FIT, CopyPasteCategory.ALL_PRESENTATION):
                    updated = apply_fit_snapshot(updated, clipboard.fit)
                if category in (CopyPasteCategory.REPLICA, CopyPasteCategory.ALL_PRESENTATION):
                    updated = apply_replica_snapshot(updated, clipboard.replica)
                replacements.append(updated)
            plotter.rerender_records(replacements, notify=True, draw=True)
        except Exception as error:
            self._reportCopyPasteFailure("paste", error)
            panel.restore_committed_selection(
                selection_snapshot.selected_record_ids,
                current_record_id=selection_snapshot.current_record_id,
                vertical_scroll=selection_snapshot.vertical_scroll,
                horizontal_scroll=selection_snapshot.horizontal_scroll,
            )
            self.committedTimeSeriesSelectionChanged(
                panel.selected_committed_ids()
            )
            return

        panel.restore_committed_selection(
            selection_snapshot.selected_record_ids,
            current_record_id=selection_snapshot.current_record_id,
            vertical_scroll=selection_snapshot.vertical_scroll,
            horizontal_scroll=selection_snapshot.horizontal_scroll,
        )
        self.committedTimeSeriesSelectionChanged(panel.selected_committed_ids())
        labels = {
            CopyPasteCategory.STYLE: "style",
            CopyPasteCategory.FIT: "Fit",
            CopyPasteCategory.REPLICA: "Replica",
            CopyPasteCategory.ALL_PRESENTATION: "style, Fit and Replica",
        }
        count = len(record_ids)
        self.setMessageBar(
            "Pasted {} to {} time series".format(labels[category], count),
            "done", 3000,
        )

    def assignDistinctColorsToCommitted(self):
        """Assign deterministic qualitative colors to selected committed records."""
        panel = self.ui.time_series_point_panel
        snapshot = panel.capture_committed_selection()
        selected = snapshot.selected_record_ids
        if len(selected) < 2:
            return ()

        selected_set = set(selected)
        record_ids = tuple(
            entry.record_id for entry in self.time_series_list_state.entries()
            if entry.record_id in selected_set
        )
        if len(record_ids) != len(selected):
            self._reportDistinctColorFailure(
                RuntimeError("one or more selected committed time series no longer exist")
            )
            panel.restore_committed_selection(
                snapshot.selected_record_ids,
                current_record_id=snapshot.current_record_id,
                vertical_scroll=snapshot.vertical_scroll,
                horizontal_scroll=snapshot.horizontal_scroll,
            )
            return ()

        plotter = self.choose_point_click_handler.plot_ts
        try:
            originals = tuple(
                plotter.committed_record(record_id) for record_id in record_ids
            )
            if any(record is None for record in originals):
                raise KeyError(
                    "one or more selected committed time series no longer exist"
                )
            replacements = []
            for index, record in enumerate(originals):
                color = DISTINCT_TIME_SERIES_COLORS[
                    index % len(DISTINCT_TIME_SERIES_COLORS)
                ]
                replacements.append(with_primary_series_color(record, color))
            plotter.rerender_records(replacements, notify=True, draw=True)
        except Exception as error:
            self._reportDistinctColorFailure(error)
            panel.restore_committed_selection(
                snapshot.selected_record_ids,
                current_record_id=snapshot.current_record_id,
                vertical_scroll=snapshot.vertical_scroll,
                horizontal_scroll=snapshot.horizontal_scroll,
            )
            self.committedTimeSeriesSelectionChanged(
                panel.selected_committed_ids()
            )
            return ()

        panel.restore_committed_selection(
            snapshot.selected_record_ids,
            current_record_id=snapshot.current_record_id,
            vertical_scroll=snapshot.vertical_scroll,
            horizontal_scroll=snapshot.horizontal_scroll,
        )
        panel.committed_view.setFocus()
        self.committedTimeSeriesSelectionChanged(panel.selected_committed_ids())
        self.setMessageBar(
            "Assigned distinct colors to {} time series".format(len(record_ids)),
            "done", 3000,
        )
        return record_ids

    def _reportDistinctColorFailure(self, error):
        """Report one batch-color diagnostic without exposing record UUIDs."""
        if self._plugin_diagnostic is not None:
            self._plugin_diagnostic("committed_assign_distinct_colors", error)
        else:
            self.msg_signal.emit(
                "Unable to assign distinct time-series colors: {}".format(error),
                "c", 0,
            )

    def _reportCopyPasteFailure(self, operation, error):
        """Report one diagnostic without exposing record UUIDs to normal feedback."""
        if self._plugin_diagnostic is not None:
            self._plugin_diagnostic("committed_{}".format(operation), error)
        else:
            self.msg_signal.emit(
                "Unable to {} time-series settings: {}".format(operation, error), "c", 0
            )

    def removeSelectedCommittedTimeSeries(self):
        """Remove the selected committed UUIDs through the shared batch command."""
        panel = self.ui.time_series_point_panel
        record_ids = panel.selected_committed_ids()
        if not record_ids:
            return
        self._removeCommittedTimeSeries(
            record_ids,
            removed_rows=panel.selected_committed_rows(),
        )

    def _removeCommittedTimeSeries(self, record_ids, *, removed_rows=()):
        """Synchronize store, renderer, list metadata, selection, and toolbar once."""
        panel = self.ui.time_series_point_panel
        plotter = self.choose_point_click_handler.plot_ts
        requested = tuple(record_ids)
        if not requested:
            return ()
        smallest_row = min(removed_rows) if removed_rows else 0
        try:
            result = plotter.remove_records(requested, notify=False)
            removed_ids = result.removed_record_ids
        except Exception as error:
            if self._plugin_diagnostic is not None:
                self._plugin_diagnostic("committed_remove", error)
            else:
                self.msg_signal.emit(str(error), "c", 0)
            panel.refresh_committed_model()
            return ()
        if not removed_ids:
            panel.refresh_committed_model()
            return ()

        for record_id in removed_ids:
            self.time_series_map_overlays.hide_record(record_id)
            self.time_series_list_state.remove(record_id)

        plotter.notify_committed_changed()
        remaining_entries = self.time_series_list_state.entries()
        surviving_requested = tuple(
            record_id for record_id in requested
            if record_id not in set(removed_ids)
            and self.time_series_list_state.entry(record_id) is not None
        )
        if surviving_requested:
            repaired_selection = surviving_requested
        elif remaining_entries:
            repaired_row = min(smallest_row, len(remaining_entries) - 1)
            repaired_selection = (remaining_entries[repaired_row].record_id,)
        else:
            repaired_selection = ()
        panel.restore_committed_selection(repaired_selection)
        panel.refresh_removal_actions()
        if remaining_entries:
            panel.committed_view.setFocus()
        self.committedTimeSeriesSelectionChanged(panel.selected_committed_ids())

        if result.graphics_errors:
            error = result.graphics_errors[0]
            if self._plugin_diagnostic is not None:
                self._plugin_diagnostic("committed_remove_graphics", error)
            else:
                self.msg_signal.emit(str(error), "c", 0)
        count = len(removed_ids)
        message = "Removed {} time series".format(count)
        self.setMessageBar(message, "done", 3000)
        return removed_ids

    def setCommittedTimeSeriesVisibility(self, record_id, visible):
        """Update explicit list visibility and renderer ownership by UUID."""
        plotter = self.choose_point_click_handler.plot_ts
        previous = self.time_series_list_state.entry(record_id)
        if previous is None or previous.visible == bool(visible):
            return
        self.time_series_list_state.set_visible(record_id, visible)
        try:
            plotter.set_committed_visibility(record_id, visible)
        except Exception:
            self.time_series_list_state.set_visible(record_id, previous.visible)
            raise
        panel = self.ui.time_series_point_panel
        panel.refresh_committed_model()
        self._refreshTimeSeriesPlotActionState()

    def setCommittedTimeSeriesVisibilityBatch(self, record_ids, visible):
        """Set committed visibility for UUIDs as one renderer/list transaction."""
        record_ids = tuple(record_ids)
        if not record_ids:
            return False
        entries = tuple(self.time_series_list_state.entry(record_id) for record_id in record_ids)
        if any(entry is None for entry in entries):
            error = RuntimeError("stale committed UUID in visibility batch")
            if self._plugin_diagnostic is not None:
                self._plugin_diagnostic("committed_visibility_batch", error)
            else:
                self.msg_signal.emit(str(error), "c", 0)
            return False
        target = bool(visible)
        changed_ids = tuple(
            record_id for record_id, entry in zip(record_ids, entries)
            if entry.visible != target
        )
        if not changed_ids:
            return True
        plotter = self.choose_point_click_handler.plot_ts
        try:
            result = plotter.set_committed_visibility_batch(changed_ids, target)
        except Exception as error:
            if self._plugin_diagnostic is not None:
                self._plugin_diagnostic("committed_visibility_batch", error)
            else:
                self.msg_signal.emit(str(error), "c", 0)
            return False
        for record_id in result.changed_record_ids:
            self.time_series_list_state.set_visible(record_id, target)
        self.ui.time_series_point_panel.refresh_committed_model()
        if result.graphics_errors:
            error = result.graphics_errors[0]
            if self._plugin_diagnostic is not None:
                self._plugin_diagnostic("committed_visibility_graphics", error)
            else:
                self.msg_signal.emit(str(error), "c", 0)
        if result.refresh_errors:
            error = result.refresh_errors[0]
            if self._plugin_diagnostic is not None:
                self._plugin_diagnostic("committed_visibility_refresh", error)
            else:
                self.msg_signal.emit(str(error), "c", 0)
        self._refreshTimeSeriesPlotActionState()
        return True

    def toggleSelectedCommittedTimeSeriesVisibility(self):
        """Apply one predictable visibility state to selected committed UUIDs."""
        panel = self.ui.time_series_point_panel
        snapshot = panel.capture_committed_selection()
        record_ids = snapshot.selected_record_ids
        if not record_ids:
            return False
        entries = tuple(self.time_series_list_state.entry(record_id) for record_id in record_ids)
        if any(entry is None for entry in entries):
            return self.setCommittedTimeSeriesVisibilityBatch(record_ids, True)
        target = not all(entry.visible for entry in entries)
        changed = self.setCommittedTimeSeriesVisibilityBatch(record_ids, target)
        if changed:
            panel.restore_committed_selection(
                snapshot.selected_record_ids,
                current_record_id=snapshot.current_record_id,
                vertical_scroll=snapshot.vertical_scroll,
                horizontal_scroll=snapshot.horizontal_scroll,
            )
            panel.committed_view.setFocus()
        return changed

    def setAllCommittedTimeSeriesVisibility(self, visible):
        """Apply deterministic show/hide-all through one batch command."""
        self.setCommittedTimeSeriesVisibilityBatch(
            tuple(entry.record_id for entry in self.time_series_list_state.entries()),
            visible,
        )

    def updateCommittedTimeSeriesLabel(self, record_id, label):
        """Immutably update one committed optional label without changing visibility."""
        plotter = self.choose_point_click_handler.plot_ts
        record = plotter.committed_record(record_id)
        if record is None:
            return
        updated = replace(
            record,
            presentation=replace(record.presentation, label=str(label).strip()),
        )
        plotter.replace_series_records((updated,))
        self.ui.time_series_point_panel.refresh_committed_model()

    def _refreshCommittedTimeSeriesMapOverlays(self, record_ids):
        """Project committed map overlays from list selection only."""
        plotter = self.choose_point_click_handler.plot_ts
        self.time_series_map_overlays.update_selection(
            record_ids, plotter.committed_record
        )

    def committedTimeSeriesSelectionChanged(self, record_ids):
        """Project selected UUIDs and enable only record-owned toolbar controls."""
        self._refreshCommittedNavigationActionState()
        plotter = self.choose_point_click_handler.plot_ts
        self._refreshCommittedTimeSeriesMapOverlays(record_ids)
        toolbar = self.ui.time_series_toolbar
        if plotter.pending_record() is not None:
            toolbar.setSeriesControlsEnabled(True)
            self._refreshTimeSeriesPlotActionState()
            return
        if len(record_ids) == 1:
            plotter.setActiveSeries(record_ids[0])
            toolbar.setSeriesControlsEnabled(True)
            self._syncActiveAnalysisControls(plotter.current_series())
            self._refreshTimeSeriesPlotActionState()
            return
        plotter._series_store.set_active(None)
        plotter._set_current_series(None)
        toolbar.setSeriesControlsEnabled(False)
        self._refreshTimeSeriesPlotActionState()
        if len(record_ids) > 1:
            self.msg_signal.emit("Multiple time series selected", "i", 0)

    def _refreshTimeSeriesPlotActionState(self):
        """Project renderer-owned plot availability into plot-level toolbar actions."""
        plotter = self.choose_point_click_handler.plot_ts
        has_plot = plotter.has_exportable_plot()
        toolbar = self.ui.time_series_toolbar
        toolbar.appearance_action.setEnabled(has_plot)
        toolbar.plot_export_button.setPrimaryEnabled(has_plot)
        toolbar.setRangeControlsEnabled(plotter.hasPlottedTimeSeriesData())

    def discardPendingTimeSeries(self):
        """Discard only the pending preview and preserve the active reference."""
        self.choose_point_click_handler.plot_ts.discard_pending()

    def updatePendingTimeSeriesLabel(self, label):
        """Apply a normalized label to the pending record only."""
        self.choose_point_click_handler.plot_ts.update_pending_label(label)

    def _syncAxisToolbarControls(self):
        """Refresh both axis selectors from authoritative runtime state without drawing."""
        self._syncTimeSeriesXAxisControls()
        self._syncTimeSeriesYAxisControls(self.time_series_settings.y_axis.policy)

    def _axisViewportChanged(self, axis_name):
        """Mark an interactively changed ViewBox as Custom without redrawing."""
        if axis_name == "x":
            state = self.time_series_settings.x_axis
            if not state.custom_view:
                self.time_series_settings.replace_domain(
                    "x_axis", replace(state, custom_view=True)
                )
            self._syncTimeSeriesXAxisControls()
            return

        state = self.time_series_settings.y_axis
        if axis_name == "series_y":
            updated = replace(state, series_custom_view=True)
        elif axis_name == "residual_y":
            if not self.choose_point_click_handler.plot_ts.plot_residuals_flag:
                self._syncTimeSeriesYAxisControls(state.policy)
                return
            updated = replace(state, residual_custom_view=True)
        else:
            return
        if updated != state:
            self.time_series_settings.replace_domain("y_axis", updated)
        self._syncTimeSeriesYAxisControls(updated.policy)

    def _handlePlotAutoRequest(self):
        """Reset the coordinated plot workspace to canonical From Data ranges."""
        plotter = self.choose_point_click_handler.plot_ts
        if plotter.ax is None:
            self._syncAxisToolbarControls()
            return

        with plotter.axisViewUpdateGuard():
            x_state = self.time_series_settings.x_axis
            self.time_series_settings.replace_domain(
                "x_axis", replace(
                    x_state,
                    start_policy="from_data",
                    end_policy="from_data",
                    custom_view=False,
                )
            )
            y_state = self.time_series_settings.y_axis
            updated_y = y_state.select_all_from_data()
            if updated_y != y_state:
                self.time_series_settings.replace_domain("y_axis", updated_y)

            plotter.resetSharedXAxisFromData()
            plotter.setYlims(ax=plotter.ax)
            if plotter.ax_residuals is not None:
                plotter.setYlims(ax=plotter.ax_residuals)
            self._syncTimeSeriesXAxisControls()
            self._syncTimeSeriesYAxisControls(updated_y.policy)
            plotter._draw()

    def _restoreTimeSeriesXAxisMode(self):
        """Reset the session-only X-axis state and synchronize the toolbar."""
        current = self.time_series_settings.x_axis
        self.time_series_settings.replace_domain(
            "x_axis", replace(
                current, start_policy="from_data", end_policy="from_data", custom_view=False,
            )
        )
        self._syncTimeSeriesXAxisControls()

    def _syncTimeSeriesXAxisControls(self):
        """Synchronize the toolbar from authoritative X-axis runtime state."""
        state = self.time_series_settings.x_axis
        self.ui.time_series_toolbar.setSelectedXAxisMode(
            state.policy, state.manual_start, state.manual_end, state.custom_view
        )

    def _applyXAxisLimitsToExistingPlot(self):
        """Apply runtime X limits to existing graphics and redraw exactly once."""
        plotter = self.choose_point_click_handler.plot_ts
        if plotter.ax is None:
            return False
        plotter.setXlims(ax=plotter.ax)
        plotter._draw()
        return True

    def _applyTimeSeriesXAxisMode(self, mode, refresh=True):
        """Apply Auto or restore the last committed manual-editor configuration."""
        state = self.time_series_settings.x_axis
        if mode not in {"from_data", "manual"}:
            mode = "from_data"
        if mode == "from_data":
            updated = replace(
                state, start_policy="from_data", end_policy="from_data", custom_view=False
            )
        else:
            if (
                state.manual_editor_start_policy == "from_data"
                and state.manual_editor_end_policy == "from_data"
            ):
                self._syncTimeSeriesXAxisControls()
                if refresh:
                    self.showManualXAxisPopup()
                return False
            updated = replace(
                state,
                start_policy=state.manual_editor_start_policy,
                end_policy=state.manual_editor_end_policy,
                custom_view=False,
            )
            plotter = self.choose_point_click_handler.plot_ts
            if plotter.resolveXAxisRange(updated) is None:
                self._syncTimeSeriesXAxisControls()
                if refresh:
                    self.showManualXAxisPopup()
                return False
        self.time_series_settings.replace_domain("x_axis", updated)
        self._syncTimeSeriesXAxisControls()
        if refresh:
            self._applyXAxisLimitsToExistingPlot()
        return True

    def setTimeSeriesXAxisMode(self, mode):
        """Apply a toolbar-selected X-axis policy immediately."""
        if not self._applyTimeSeriesXAxisMode(mode):
            return
        message = "X range set to Data range." if mode == "from_data" else "Stored manual time range applied."
        self.msg_signal.emit(message, "i", 0)

    def showManualXAxisPopup(self):
        """Open the transactional session-local time-range editor."""
        plotter = self.choose_point_click_handler.plot_ts
        if plotter.availableDateRange() is None:
            return
        state = self.time_series_settings.x_axis
        viewport = plotter.captureViewport()
        self._manual_x_axis_session = {"x_axis": state, "viewport": viewport}
        data_start, data_end = plotter.resolveXAxisRange(XAxisSettings())
        self.manual_x_axis_popup.openForBounds(
            state.manual_start, state.manual_end, data_start, data_end,
            state.manual_editor_start_policy, state.manual_editor_end_policy,
        )
        self.manual_x_axis_popup.adjustSize()
        button = self.ui.time_series_toolbar.x_axis_button
        top_left = button.mapToGlobal(QPoint(0, 0))
        anchor_rect = QRect(top_left, button.size())
        geometry = available_screen_geometry(top_left, self.manual_x_axis_popup)
        self.manual_x_axis_popup.move(
            screen_aware_popup_position(anchor_rect, self.manual_x_axis_popup.sizeHint(), geometry)
        )
        self.manual_x_axis_popup.show()
        self.manual_x_axis_popup.raise_()
        self.manual_x_axis_popup.activateWindow()

    def _draftXAxisState(self, start_policy, end_policy, manual_start, manual_end):
        """Build and validate one per-bound X-axis draft against current data."""
        if start_policy not in {"from_data", "manual"} or end_policy not in {"from_data", "manual"}:
            return None, None
        state = replace(
            self.time_series_settings.x_axis,
            start_policy=start_policy, end_policy=end_policy,
            manual_start=manual_start, manual_end=manual_end, custom_view=False,
        )
        plotter = self.choose_point_click_handler.plot_ts
        if plotter.availableDateRange() is None:
            return state, None
        return state, plotter.resolveXAxisRange(state)

    def previewManualXAxisRange(
        self, start_policy, end_policy, manual_start, manual_end,
    ):
        """Preview one valid per-bound draft without committing runtime state."""
        if self._manual_x_axis_session is None:
            return
        state, effective = self._draftXAxisState(
            start_policy, end_policy, manual_start, manual_end
        )
        plotter = self.choose_point_click_handler.plot_ts
        if state is None or effective is None or plotter.ax is None:
            return
        plotter.applyXAxisViewport(*effective, draw=True)
        self._manual_x_axis_session["preview_range"] = effective

    def applyManualXAxisRange(
        self, start_policy, end_policy, manual_start, manual_end,
    ):
        """Commit independent X-bound policies while retaining manual drafts."""
        if self._manual_x_axis_session is None:
            return
        state, effective = self._draftXAxisState(
            start_policy, end_policy, manual_start, manual_end
        )
        if state is None or effective is None:
            return
        state = replace(
            state,
            manual_editor_start_policy=start_policy,
            manual_editor_end_policy=end_policy,
        )
        self.time_series_settings.replace_domain("x_axis", state)
        self._manual_x_axis_session = None
        self._syncTimeSeriesXAxisControls()
        self._applyXAxisLimitsToExistingPlot()

    def captureCurrentManualXAxisView(self):
        """Commit the complete visible viewport without snapping or changing it."""
        if self._manual_x_axis_session is None:
            return
        plotter = self.choose_point_click_handler.plot_ts
        start, end = plotter.currentVisibleDateRange()
        state = self.time_series_settings.x_axis
        self.time_series_settings.replace_domain(
            "x_axis", replace(
                state, start_policy="manual", end_policy="manual",
                manual_editor_start_policy="manual", manual_editor_end_policy="manual",
                manual_start=start, manual_end=end, custom_view=False
            )
        )
        self._manual_x_axis_session = None
        self.manual_x_axis_popup.closeAfterCommit()
        self._syncTimeSeriesXAxisControls()
        plotter._draw()

    def cancelManualXAxisRange(self):
        """Restore original committed state and the exact pre-preview viewport."""
        session = self._manual_x_axis_session
        if session is None:
            return
        self._manual_x_axis_session = None
        plotter = self.choose_point_click_handler.plot_ts
        self.time_series_settings.replace_domain("x_axis", session["x_axis"])
        self._syncTimeSeriesXAxisControls()
        if session.get("preview_range") is not None:
            plotter.restoreViewport(session["viewport"])
            plotter._draw()

    def _clearPersistedYAxisModes(self):
        """Remove obsolete persisted Y-axis state; all policy state is session-local."""
        self.settings.remove("insar_explorer/time_series_y_axis_mode")
        self.settings.remove("insar_explorer/residual_y_axis_mode")
        for axis_name in ("time_series", "residual"):
            for bound_name in ("lower", "upper"):
                self.settings.remove(
                    f"insar_explorer/{axis_name}_manual_y_{bound_name}"
                )

    def _restoreTimeSeriesYAxisMode(self):
        """Restore axis-local effective Y displays after plotter lifecycle changes."""
        plotter = self.choose_point_click_handler.plot_ts
        plotter.manual_y_lower = self.time_series_manual_y_lower
        plotter.manual_y_upper = self.time_series_manual_y_upper
        plotter.residual_manual_y_lower = self.residual_manual_y_lower
        plotter.residual_manual_y_upper = self.residual_manual_y_upper
        self._syncTimeSeriesYAxisControls(self.time_series_settings.y_axis.policy)

    def _syncTimeSeriesYAxisControls(self, mode):
        """Synchronize the toolbar from policy and aggregate visible custom state."""
        state = self.time_series_settings.y_axis
        residual_visible = bool(
            self.choose_point_click_handler.plot_ts.plot_residuals_flag
        )
        if state.policy == "symmetric":
            presentation_mode = state.policy
        else:
            presentation_mode = state.policy_for_effective_display(residual_visible)
        self.ui.time_series_toolbar.setSelectedYAxisMode(
            presentation_mode,
            self.time_series_manual_y_lower,
            self.time_series_manual_y_upper,
            self.residual_manual_y_lower,
            self.residual_manual_y_upper,
            residual_visible,
            state.has_custom_view(residual_visible),
        )

    def _applyTimeSeriesYAxisMode(self, mode, refresh=True):
        """Apply an aggregate Y mode while preserving axis-local saved ranges."""
        if mode not in {"from_data", "symmetric", "manual"}:
            mode = "from_data"
        plotter = self.choose_point_click_handler.plot_ts
        residual_available = plotter.ax_residuals is not None
        current_axis = self.time_series_settings.y_axis
        if mode == "manual":
            updated_axis = current_axis.select_manual_for_visible_axes(
                residual_available
            )
        elif mode == "from_data":
            updated_axis = current_axis.select_from_data_for_visible_axes(
                residual_available
            )
        else:
            updated_axis = replace(
                current_axis, policy=mode,
                series_custom_view=False, residual_custom_view=False,
            )
        self.time_series_settings.replace_domain("y_axis", updated_axis)
        plotter.manual_y_lower = self.time_series_manual_y_lower
        plotter.manual_y_upper = self.time_series_manual_y_upper
        plotter.residual_manual_y_lower = self.residual_manual_y_lower
        plotter.residual_manual_y_upper = self.residual_manual_y_upper
        self._syncTimeSeriesYAxisControls(updated_axis.policy)
        if refresh and plotter.ax is not None:
            with plotter.axisViewUpdateGuard():
                plotter.setYlims(ax=plotter.ax, parms=plotter.parms["time series plot"])
                if plotter.ax_residuals is not None:
                    plotter.setYlims(ax=plotter.ax_residuals, parms=plotter.parms["residual plot"])
            plotter._draw()

    def _hasValidConfiguredManualYAxis(self):
        """Return whether relevant stored Y bounds are configured and resolvable."""
        plotter = self.choose_point_click_handler.plot_ts
        if plotter.ax is None:
            return False
        state = self.time_series_settings.y_axis
        residual_available = plotter.ax_residuals is not None
        if not state.has_configured_manual(residual_available):
            return False
        if plotter.resolveManualYAxisRange(
            ax=plotter.ax, manual=state.series_manual
        ) is None:
            return False
        if residual_available and plotter.resolveManualYAxisRange(
            ax=plotter.ax_residuals, manual=state.residual_manual
        ) is None:
            return False
        return True

    def setTimeSeriesYAxisMode(self, mode):
        """Apply a toolbar-selected shared Y-axis policy immediately."""
        if mode == "manual":
            plotter = self.choose_point_click_handler.plot_ts
            if plotter.ax is None:
                self._syncTimeSeriesYAxisControls(
                    self.time_series_settings.y_axis.policy
                )
                return
            if not self._hasValidConfiguredManualYAxis():
                self._syncTimeSeriesYAxisControls(
                    self.time_series_settings.y_axis.policy
                )
                self.showManualYAxisPopup()
                return
        self._applyTimeSeriesYAxisMode(mode)
        messages = {
            "from_data": "Y range set to Data range.",
            "symmetric": "Y range set to Symmetric.",
            "manual": "Stored manual Y-axis ranges applied.",
        }
        self.msg_signal.emit(messages[self.time_series_y_axis_mode], "i", 0)

    def showManualYAxisPopup(self):
        """Open the editor and capture both policies and viewports transactionally."""
        plotter = self.choose_point_click_handler.plot_ts
        if plotter.ax is None:
            self._syncTimeSeriesYAxisControls(self.time_series_settings.y_axis.policy)
            return
        if self._manual_y_axis_session is not None:
            self.manual_y_axis_popup.show()
            self.manual_y_axis_popup.raise_()
            self.manual_y_axis_popup.activateWindow()
            return
        series_data = plotter.dataYAxisRange(plotter.ax)
        if series_data is None:
            self._syncTimeSeriesYAxisControls(self.time_series_settings.y_axis.policy)
            return
        residual_available = plotter.ax_residuals is not None
        residual_data = (
            plotter.dataYAxisRange(plotter.ax_residuals) if residual_available else None
        )
        if residual_available and residual_data is None:
            self._syncTimeSeriesYAxisControls(self.time_series_settings.y_axis.policy)
            return
        viewport = plotter.captureViewport()
        self._manual_y_axis_session = {
            "y_axis": self.time_series_settings.y_axis,
            "viewport": viewport,
        }
        popup = self.manual_y_axis_popup
        popup.openForBounds(
            self.time_series_settings.y_axis.series_manual,
            self.time_series_settings.y_axis.residual_manual,
            series_data, residual_data or (0.0, 1.0), residual_available,
        )
        popup.adjustSize()
        button = self.ui.time_series_toolbar.y_axis_button
        top_left = button.mapToGlobal(QPoint(0, 0))
        anchor = QRect(top_left, button.size())
        geometry = available_screen_geometry(top_left, popup)
        popup.move(screen_aware_popup_position(anchor, popup.sizeHint(), geometry))
        popup.show()
        popup.raise_()
        popup.activateWindow()

    def captureCurrentManualYAxisView(self, axis_name):
        """Commit one visible Y viewport as Manual without touching its sibling."""
        if self._manual_y_axis_session is None:
            return
        plotter = self.choose_point_click_handler.plot_ts
        axis = plotter.ax if axis_name == "series" else plotter.ax_residuals
        if axis is None:
            return
        lower, upper = (float(value) for value in axis.viewRange()[1])
        residual_available = plotter.ax_residuals is not None
        updated = self.time_series_settings.y_axis.commit_current_view(
            axis_name, lower, upper, residual_available
        )
        self.time_series_settings.replace_domain("y_axis", updated)
        self._manual_y_axis_session = None
        self.manual_y_axis_popup.closeAfterCommit()
        self._syncTimeSeriesYAxisControls(updated.policy)
        self.msg_signal.emit("Current Y-axis view saved as Manual.", "i", 0)

    def previewManualYAxisRange(self, axis_name, lower, upper):
        """Preview the complete draft through the same paths used by Apply."""
        if self._manual_y_axis_session is None:
            return
        popup = self.manual_y_axis_popup
        series_lower, series_upper = popup.bounds("series")
        residual_lower, residual_upper = popup.bounds("residual")
        series_retained = popup.retainedBounds("series")
        residual_retained = popup.retainedBounds("residual")
        plotter = self.choose_point_click_handler.plot_ts
        plotter.setManualYRanges(
            AxisManualRange(
                series_lower, series_upper, *series_retained
            ),
            AxisManualRange(
                residual_lower, residual_upper, *residual_retained
            ),
            plotter.ax_residuals is not None,
        )

    def applyManualYAxisRange(
        self, series_lower, series_upper, residual_lower, residual_upper,
        series_retained_lower, series_retained_upper,
        residual_retained_lower, residual_retained_upper,
        series_changed, residual_changed,
    ):
        """Commit editor memory and activate Manual or truthful From Data mode."""
        state = self.time_series_settings.y_axis
        state = replace(
            state,
            series_manual=AxisManualRange(
                series_lower, series_upper,
                series_retained_lower, series_retained_upper,
            ),
        )
        if residual_changed:
            state = replace(
                state,
                residual_manual=AxisManualRange(
                    residual_lower, residual_upper,
                    residual_retained_lower, residual_retained_upper,
                ),
            )
        residual_available = self.choose_point_click_handler.plot_ts.ax_residuals is not None
        state = replace(
            state,
            series_display_mode=(
                "manual" if series_lower is not None or series_upper is not None
                else "from_data"
            ),
        )
        if residual_available:
            state = replace(
                state, residual_display_mode=(
                    "manual" if residual_lower is not None or residual_upper is not None
                    else "from_data"
                ),
            )
        resulting_policy = state.policy_for_effective_display(residual_available)
        self.time_series_settings.replace_domain(
            "y_axis", replace(state, policy=resulting_policy)
        )
        self._manual_y_axis_session = None
        self._applyTimeSeriesYAxisMode(resulting_policy, refresh=True)
        message = (
            "Y range set to Data range." if resulting_policy == "from_data"
            else "Stored manual Y-axis ranges applied."
        )
        self.msg_signal.emit(message, "i", 0)

    def cancelManualYAxisRange(self):
        """Restore both original policies and all captured X/Y view ranges."""
        session = self._manual_y_axis_session
        if session is None:
            return
        self._manual_y_axis_session = None
        plotter = self.choose_point_click_handler.plot_ts
        self.time_series_settings.replace_domain("y_axis", session["y_axis"])
        plotter.restoreViewport(session["viewport"])
        self._syncTimeSeriesYAxisControls(session["y_axis"].policy)
        plotter._draw()

    def _loadReplicaInterval(self):
        """Load and validate the persisted replica half-wavelength interval."""
        value = self.settings.value(
            "insar_explorer/replica_interval_mm", 27.8, type=float
        )
        return value if value > 0 else 27.8

    @staticmethod
    def _validateReplicaPairCount(value):
        """Validate a Replica pair count without accepting coercible values."""
        if isinstance(value, bool) or not isinstance(value, int):
            return 1
        return max(1, min(10, value))

    def _loadReplicaPairCount(self):
        """Load the symmetric Replica pair count from the canonical JSON config."""
        return self.choose_point_click_handler.plot_ts.settings_model.replica.pair_count

    def _applicableReplicaTargets(self):
        """Return current plotted targets eligible for Replica rerendering."""
        selected = self._selectedTimeSeriesSnapshots()
        if not selected:
            return []
        plot = self.choose_point_click_handler.plot_ts
        return list(getattr(plot, "series_history", ()) or ())

    def _replicaStyleAvailable(self):
        """Return Replica Style availability from the active compatibility view."""
        return bool(self.time_series_replica_enabled)

    def _refreshReplicaPopupAvailability(self):
        """Synchronize Replica Style availability from feature activation."""
        if hasattr(self, "replica_popup"):
            self.replica_popup.setReplicaStyleAvailable(
                self._replicaStyleAvailable()
            )

    def _activeReplicaSettingsSnapshot(self):
        """Combine active record calculation and visual state for popup projection."""
        plot = self.choose_point_click_handler.plot_ts
        current = plot.current_series()
        visual = (current.presentation.replica
                  if current is not None else self.time_series_settings.replica)
        return ReplicaSettings(
            enabled=self.time_series_replica_enabled,
            interval_mm=self.time_series_replica_interval_mm,
            pair_count=self.time_series_replica_pair_count,
            color_1=visual.color_1, color_2=visual.color_2,
            opacity=visual.opacity, marker=visual.marker, marker_size=visual.marker_size,
        )

    def syncReplicaPopup(self):
        """Refresh Replica controls from active record state without write-back."""
        if hasattr(self, "replica_popup"):
            self.replica_popup.setSettings(self._activeReplicaSettingsSnapshot())
            self._refreshReplicaPopupAvailability()

    def showReplicaPopup(self):
        """Open the Replica popup without changing activation state."""
        self.syncReplicaPopup()
        self.replica_popup.adjustSize()
        toolbar = self.ui.time_series_toolbar
        anchor = toolbar.replica_button

        if anchor is not None:
            local_rect = anchor.rect()
            anchor_rect = QRect(
                anchor.mapToGlobal(local_rect.topLeft()),
                local_rect.size(),
            )
            fallback_widget = anchor
        else:
            local_rect = toolbar.rect()
            anchor_rect = QRect(
                toolbar.mapToGlobal(local_rect.topLeft()),
                local_rect.size(),
            )
            fallback_widget = toolbar

        geometry = available_screen_geometry(
            anchor_rect.center(),
            fallback_widget,
        )
        self.replica_popup.move(
            screen_aware_popup_position(
                anchor_rect,
                self.replica_popup.sizeHint(),
                geometry,
            )
        )
        self.replica_popup.show()
        self.replica_popup.raise_()

    def _applyReplicaSettingsSnapshot(self, settings, *, rerender):
        """Apply active-record Replica state without changing creation defaults."""
        applied = settings
        defaults = self.time_series_settings.replica
        presentation = replace(
            defaults, color_1=applied.color_1, color_2=applied.color_2,
            opacity=applied.opacity, marker=applied.marker,
            marker_size=applied.marker_size,
        )
        self.time_series_settings.replace_domain("replica", presentation)
        self.time_series_replica_enabled = applied.enabled
        self.time_series_replica_interval_mm = applied.interval_mm
        self.time_series_replica_pair_count = applied.pair_count

        plot = self.choose_point_click_handler.plot_ts
        replica_config = ReplicaConfiguration(
            enabled=applied.enabled, interval_mm=applied.interval_mm,
            pair_count=applied.pair_count,
        )
        replica_style = ReplicaStyleSettings(
            color_1=applied.color_1, color_2=applied.color_2,
            opacity=applied.opacity, marker=applied.marker,
            marker_size=applied.marker_size,
        )
        if plot.updateActiveReplicaState(
            configuration=replica_config, presentation=replica_style
        ):
            rerender = False
        self._syncTimeSeriesReplicaControls()
        if rerender and self._applicableReplicaTargets():
            self._refreshReplicaGraphicsAndYAxis()
        return applied

    def updateReplicaCoreSettings(
        self, interval_mm, pair_count, color_1, color_2, opacity, marker, marker_size
    ):
        """Apply the complete consolidated Replica runtime state once."""
        previous = self.time_series_settings.replica
        replica = type(previous)(
            enabled=self.time_series_replica_enabled, interval_mm=interval_mm, pair_count=pair_count,
            color_1=color_1, color_2=color_2, opacity=opacity,
            marker=marker, marker_size=marker_size,
        )
        self._applyReplicaSettingsSnapshot(replica, rerender=True)
        self._persistCurrentReplicaAnalysisDefaults()

    def _applyReplicaDefaults(self, settings):
        """Intentionally replace future-record defaults and apply them to the active record."""
        applied = replace(settings, enabled=self.time_series_replica_enabled)
        self.time_series_settings.replace_domain("replica", settings)
        self._applyReplicaSettingsSnapshot(applied, rerender=True)
        self._persistCurrentReplicaAnalysisDefaults()

    def restoreReplicaDefaults(self):
        """Apply persisted Replica defaults when an applicable target exists."""
        if not self._replicaStyleAvailable():
            self.syncReplicaPopup()
            return
        defaults = self.choose_point_click_handler.plot_ts.user_preferences.load().replica_defaults
        self._applyReplicaDefaults(defaults)

    def setCurrentReplicaAsDefault(self):
        """Persist the current Replica controls only for an applicable target."""
        if not self._replicaStyleAvailable():
            self.syncReplicaPopup()
            return
        presentation = self.time_series_settings.replica
        current = replace(
            presentation, enabled=self.time_series_replica_enabled,
            interval_mm=self.time_series_replica_interval_mm,
            pair_count=self.time_series_replica_pair_count,
        )
        self.time_series_settings.replace_domain("replica", current)
        if self._saveUserPreferences(
            lambda: self.choose_point_click_handler.plot_ts.user_preferences.save_replica_defaults(current),
            "Current replica settings saved as default.",
        ):
            self.settings.setValue("insar_explorer/replica_interval_mm", current.interval_mm)

    def applyFactoryReplicaDefaults(self):
        """Apply canonical Replica values when an applicable target exists."""
        if not self._replicaStyleAvailable():
            self.syncReplicaPopup()
            return
        self._applyReplicaDefaults(ReplicaSettings())

    def _reloadReplicaPairCountFromConfig(self):
        """Reload the canonical Replica pair count and synchronize its toolbar view."""
        reloaded = self.choose_point_click_handler.plot_ts.user_preferences.load()
        self.choose_point_click_handler.plot_ts.settings_model.replace_domain(
            "replica", replace(reloaded.replica_defaults,
                               enabled=self.time_series_replica_enabled,
                               interval_mm=self.time_series_replica_interval_mm)
        )
        self.time_series_replica_pair_count = self.time_series_settings.replica.pair_count
        self._syncTimeSeriesReplicaControls()

    def _restoreTimeSeriesReplicaState(self):
        """Restore controls from typed analysis defaults without persistence writes."""
        defaults = self.time_series_settings.replica_analysis_defaults
        self._replica_enabled_view = defaults.enabled
        self._replica_interval_view = defaults.interval_mm
        self._replica_pair_count_view = defaults.pair_count
        self._applyTimeSeriesReplicaState(refresh=False)

    def _syncTimeSeriesReplicaControls(self):
        """Synchronize toolbar and temporary Settings controls without recursion."""
        toolbar = self.ui.time_series_toolbar
        toolbar.setReplicaPresentation(
            self.time_series_replica_enabled,
            self.time_series_replica_interval_mm,
            self.time_series_replica_pair_count,
        )
        self.syncReplicaPopup()

    def _shouldReapplyAutomaticYAxisAfterReplicaChange(self):
        """Return whether Replica extent changes should reapply the main Y policy."""
        y_axis = self.time_series_settings.y_axis
        return (
            not y_axis.series_custom_view
            and (
                y_axis.policy == "symmetric"
                or y_axis.series_display_mode == "from_data"
            )
        )

    def _refreshReplicaGraphicsAndYAxis(self):
        """Refresh Replica graphics and the effective main Y range with one draw."""
        plot = self.choose_point_click_handler.plot_ts
        targets = self._applicableReplicaTargets()
        if plot.ax is None or not targets:
            return

        plot.rerenderTimeSeriesSnapshots(targets, draw=False)
        if self._shouldReapplyAutomaticYAxisAfterReplicaChange():
            with plot.axisViewUpdateGuard():
                plot.setYlims(ax=plot.ax, parms=plot.parms["time series plot"])
        self._syncTimeSeriesYAxisControls(self.time_series_settings.y_axis.policy)
        plot._draw()

    def _applyTimeSeriesReplicaState(self, refresh=True):
        """Apply Replica state and optionally refresh graphics and Y range once."""
        replica = replace(
            self.time_series_settings.replica,
            enabled=self.time_series_replica_enabled,
            interval_mm=self.time_series_replica_interval_mm,
            pair_count=self.time_series_replica_pair_count,
        )
        self._applyReplicaSettingsSnapshot(replica, rerender=refresh)

    def setTimeSeriesReplicaEnabled(self, enabled):
        """Enable or disable replicas while preserving the selected interval."""
        self.time_series_replica_enabled = bool(enabled)
        self._applyTimeSeriesReplicaState()
        self._persistCurrentReplicaAnalysisDefaults()
        if enabled:
            message = (
                "Replica enabled: time series will be replicated every "
                f"±{self.time_series_replica_interval_mm:.1f} mm."
            )
        else:
            message = "Replica disabled."
        self.msg_signal.emit(message, "i", 0)

    def setTimeSeriesReplicaInterval(self, interval_mm):
        """Store a positive replica interval and redraw only when Replica is active."""
        interval_mm = float(interval_mm)
        if interval_mm <= 0:
            return
        self.time_series_replica_interval_mm = interval_mm
        self._applyTimeSeriesReplicaState(refresh=self.time_series_replica_enabled)
        self._persistCurrentReplicaAnalysisDefaults()
        self.msg_signal.emit(
            f"Replica interval set to ±{interval_mm:.1f} mm.", "i", 0
        )

    def _applyReplicaPairCount(self, pair_count):
        """Apply a validated pair count to the active compatibility view only."""
        self.time_series_replica_pair_count = pair_count

    def setTimeSeriesReplicaPairCount(self, pair_count):
        """Persist, apply, and redraw a toolbar Replica pair-count change once."""
        pair_count = self._validateReplicaPairCount(pair_count)
        self._applyReplicaPairCount(pair_count)

        presentation = self.time_series_settings.replica
        applied = replace(
            presentation, enabled=self.time_series_replica_enabled,
            interval_mm=self.time_series_replica_interval_mm,
            pair_count=self.time_series_replica_pair_count,
        )
        self._applyReplicaSettingsSnapshot(
            applied, rerender=self.time_series_replica_enabled,
        )
        self._persistCurrentReplicaAnalysisDefaults()

        self.msg_signal.emit(
            f"Replica pairs set to {self.time_series_replica_pair_count}.", "i", 0
        )

    def syncMapIndicatorSettingsPopup(self):
        """Project active global settings into the popup without side effects."""
        self.map_indicator_settings_popup.setSettings(
            self.map_indicator_settings.active
        )

    def updateMapIndicatorSettings(self, settings):
        """Normalize and apply one complete active map-indicator value."""
        normalized = type(settings)(
            QColor(settings.target_color),
            QColor(settings.reference_color),
            QColor(settings.point_outer_color),
            bool(settings.show_point_outer_ring),
            int(settings.point_size),
            int(settings.opacity_percent),
        )
        self.applyMapIndicatorSettings(normalized)
        self.syncMapIndicatorSettingsPopup()

    def restoreMapIndicatorDefaults(self):
        """Apply the persisted user defaults immediately."""
        self.applyMapIndicatorSettings(self.map_indicator_settings.load_defaults())
        self.syncMapIndicatorSettingsPopup()

    def setCurrentMapIndicatorsAsDefault(self):
        """Persist the current active settings as the user default."""
        self.map_indicator_settings.save_defaults(
            self.map_indicator_settings.active
        )

    def applyFactoryMapIndicatorDefaults(self):
        """Apply factory settings without overwriting saved defaults."""
        self.applyMapIndicatorSettings(
            self.map_indicator_settings.factory_defaults()
        )
        self.syncMapIndicatorSettingsPopup()

    def showMapIndicatorSettingsPopup(self):
        """Open the synchronized indicator-settings popup beside its button."""
        self.syncMapIndicatorSettingsPopup()
        popup = self.map_indicator_settings_popup
        popup.adjustSize()
        button = self.ui.time_series_point_panel.indicator_settings_button
        top_left = button.mapToGlobal(QPoint(0, 0))
        anchor = QRect(top_left, button.size())
        geometry = available_screen_geometry(top_left, popup)
        popup.move(
            screen_aware_popup_position(anchor, popup.sizeHint(), geometry)
        )
        popup.show()
        popup.raise_()

    def applyMapIndicatorSettings(self, settings):
        """Apply global presentation and refresh owned overlays."""
        self.map_indicator_settings.apply(settings, notify=False)
        if self.drawing_tool is not None:
            self.drawing_tool.refresh_style()
        if self.drawing_tool_reference is not None:
            self.drawing_tool_reference.refresh_style()
        self.pending_time_series_map_overlays.refresh_style()
        self.time_series_map_overlays.refresh_style()
        active = self.map_indicator_settings.active
        for highlight, role in (
            (self.choose_point_click_handler.highlight, "target"),
            (self.choose_point_click_handler.reference_highlight, "reference"),
        ):
            if highlight is not None:
                from .time_series.map_indicator_style import semantic_indicator_color
                color = semantic_indicator_color(
                    role, active,
                    alpha=round(255 * active.opacity_percent / 100.0),
                )
                highlight.setColor(color)
        self.iface.mapCanvas().refresh()
        # Publish only after every owned presentation consumer is restyled.
        self.map_indicator_settings.settingsChanged.emit(
            self.map_indicator_settings.active
        )

    def clearTimeSeriesMapOverlays(self):
        """Release all stable pending and committed map indicators."""
        self.pending_time_series_map_overlays.clear()
        self.time_series_map_overlays.clear_all()

    def handleUiClose(self, visible):
        if not visible:
            self.clearTimeSeriesMapOverlays()
            self.choose_point_click_handler.clearFeatureHighlight()
            self.choose_point_click_handler.clearReferenceFeatureHighlight()
            self.removeClickTool(reference=False)
            self.removeClickTool(reference=True)
            self.removePolygonDrawingTool(reference=False)
            self.removePolygonDrawingTool(reference=True)
            self.ui.pb_choose_point.setChecked(False)
            self.ui.pb_set_reference.setChecked(False)
            self.ui.pb_choose_polygon.setChecked(False)

    def activatePointSelection(self, status):
        self.ui.pb_set_reference.setChecked(False)
        self.ui.pb_choose_polygon.setChecked(False)
        self.ui.pb_set_reference_polygon.setChecked(False)
        if status:
            tool = self.initializeClickTool(reference=False)
            self.iface.mapCanvas().setMapTool(tool)
            self._syncStandaloneReferenceOverlay()
            self.msg_signal.emit("Click any point on the map to view its time series.", "t", 0)
        else:
            self.removeClickTool(reference=False)

    def activateReferencePointSelection(self, status):
        self.ui.pb_choose_point.setChecked(False)
        self.ui.pb_choose_polygon.setChecked(False)
        self.ui.pb_set_reference_polygon.setChecked(False)
        if status:
            tool = self.initializeClickTool(reference=True)
            self.iface.mapCanvas().setMapTool(tool)
            self.msg_signal.emit("Click any point on the map to set it as reference.", "t", 0)
        else:
            self.ui.pb_set_reference.setChecked(False)
            self.removeClickTool(reference=True)

    def activatePolygonSelection(self, status):
        self.ui.pb_choose_point.setChecked(False)
        self.ui.pb_set_reference.setChecked(False)
        self.ui.pb_set_reference_polygon.setChecked(False)
        if status:
            self.initializePolygonDrawingTool()
            self._syncStandaloneReferenceOverlay()
            self.msg_signal.emit("Click to add polygon vertices; double-click or right-click to finish and plot time "
                                 "series.", "t", 0)
        else:
            self.deactivatePolygonDrawingTool(reference=False)

    def activateReferencePolygonSelection(self, status):
        self.ui.pb_choose_point.setChecked(False)
        self.ui.pb_set_reference.setChecked(False)
        self.ui.pb_choose_polygon.setChecked(False)
        if status:
            self.initializePolygonDrawingTool(reference=True)
            self.msg_signal.emit("Click to add polygon vertices; double-click or right-click to finish.", "t", 0)
        else:
            self.deactivatePolygonDrawingTool(reference=True)

    def resetReferencePoint(self):
        self.choose_point_click_handler.resetReferencePoint()
        self._syncStandaloneReferenceOverlay()
        self.activateReferencePointSelection(status=False)

        if self.ui.cb_symbol_value_offset_sync_with_ref.isChecked():
            self._setReferenceValue(0.0)
            self.applyLiveSymbology()

        self.removePolygonDrawingTool(reference=True)  # remove reference polygon
        self.deactivatePolygonDrawingTool(reference=False)  # deactivate polygon
        self.msg_signal.emit("Reference point has been reset.", "done", 5000)

    def syncOffsetWithReferenceClicked(self, status):
        if status:
            self.syncOffsetWithReference()
            self.msg_signal.emit("Reference linked to the selected reference location.", "done", 0)
        else:
            self.msg_signal.emit("Reference unlinked; the current value is now editable.", "i", 0)

    def addSelectedLayers(self):
        """
        add selected layers to the list widget
        """
        selected_layers = self.iface.layerTreeView().selectedLayers()
        existing_layers = [self.ui.lw_layers.item(i).text() for i in range(self.ui.lw_layers.count())]

        for layer in selected_layers:
            layer_name = layer.name()
            if layer_name not in existing_layers:
                print(layer_name)
                self.ui.lw_layers.addItem(layer_name)

    def removeSelectedLayers(self):
        """
        remove layers from the list widget
        """
        selected_layers = self.ui.lw_layers.selectedItems()
        for layer in selected_layers:
            self.ui.lw_layers.takeItem(self.ui.lw_layers.row(layer))

    def _initialExportDirectory(self):
        """Return the initial directory used by plot and data export dialogs."""
        saved_path = self.settings.value('insar_explorer/export_directory', '', type=str)
        if saved_path and os.path.isdir(saved_path):
            return saved_path

        home_path = QStandardPaths.writableLocation(QStandardPaths.HomeLocation)
        if home_path and os.path.isdir(home_path):
            return home_path

        return os.path.expanduser('~')

    def _suggestedExportPath(self, filename):
        """Return a full export path in a usable directory."""
        export_dir = self.last_save_path
        if not export_dir or not os.path.isdir(export_dir):
            export_dir = self._initialExportDirectory()
            self.last_save_path = export_dir
        return os.path.join(export_dir, filename)

    def _rememberExportPath(self, file_path):
        """Remember the last directory used by plot and data export dialogs."""
        export_dir = os.path.dirname(file_path)
        if not export_dir:
            return
        self.last_save_path = export_dir
        self.settings.setValue('insar_explorer/export_directory', export_dir)

    @staticmethod
    def _extensionFromFilter(selected_filter):
        """Return the first file extension advertised by a QFileDialog filter."""
        if not selected_filter:
            return ""

        start = selected_filter.find('*.')
        if start == -1:
            return ""

        start += 1
        end = selected_filter.find(')', start)
        if end == -1:
            end = len(selected_filter)

        extension = selected_filter[start:end].split()[0].strip(';')
        return extension.lower()

    @staticmethod
    def _withExtension(filename, extension):
        """Return filename with extension applied to its suffix."""
        if not extension:
            return filename
        if not extension.startswith('.'):
            extension = f'.{extension}'

        base, _ = os.path.splitext(filename)
        return base + extension

    def _rememberExportFormat(self, settings_key, file_path):
        """Remember the extension used by an export dialog."""
        _, extension = os.path.splitext(file_path)
        if not extension:
            return
        self.settings.setValue(settings_key, extension.lstrip('.').lower())

    def saveTsPlot(self):
        self.msg_signal.emit("", "", 0)

        plotter = self.choose_point_click_handler.plot_ts
        if not plotter.has_exportable_plot():
            self.msg_signal.emit('No time-series plot to export.', 'w', 0)
            return

        plot_extension = self.last_plot_export_format.lower().lstrip('.')
        suggested_name = self._withExtension(self.last_save_ts_name, plot_extension)
        suggested_path = self._suggestedExportPath(suggested_name)
        _, ext = os.path.splitext(suggested_path)

        ext_to_filter = {
            '.png': "PNG (*.png)",
            '.svg': "SVG (*.svg)",
            '.jpg': "JPG (*.jpg)",
        }
        filters = ";;".join(ext_to_filter.values())
        default = ext_to_filter.get(ext.lower(), "PNG (*.png)")

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self.ui,
            "Save plot as image",
            suggested_path,
            filters,
            default,
        )

        if not file_path:
            return

        base, ext = os.path.splitext(file_path)
        selected_extension = self._extensionFromFilter(selected_filter)
        if ext == '' and selected_extension:
            file_path = base + selected_extension
        elif ext == '':
            file_path = base + '.png'

        result = plotter.savePlotAsImage(file_path)
        if not result.success:
            self.msg_signal.emit(result.error or "Plot export failed.", 'e', 0)
            return

        exported_filename = result.filename
        self._rememberExportPath(exported_filename)
        self._rememberExportFormat(
            'insar_explorer/plot_export_format', exported_filename
        )
        self.last_plot_export_format = (
            os.path.splitext(exported_filename)[1].lstrip('.').lower()
        )
        self.last_save_ts_name = os.path.basename(exported_filename)
        self.msg_signal.emit(
            f"Plot exported to {exported_filename}", 'done', 0
        )

    @staticmethod
    def _sanitizeTimeSeriesExportLabel(label):
        """Return a conservative cross-platform filename component."""
        invalid = set('<>:"/\\|?*')
        sanitized = "".join(
            "_" if character in invalid or ord(character) < 32 else character
            for character in str(label or "")
        ).strip()
        sanitized = sanitized.rstrip(". ")
        if not sanitized:
            return "time_series"
        reserved = {"CON", "PRN", "AUX", "NUL"}
        reserved.update(f"COM{index}" for index in range(1, 10))
        reserved.update(f"LPT{index}" for index in range(1, 10))
        if sanitized.upper() in reserved:
            sanitized += "_"
        return sanitized

    def _timeSeriesBatchTargets(self, directory, records, extension):
        """Return deterministic numbered target paths for records in model order."""
        extension = str(extension or "csv").lower().lstrip(".") or "csv"
        return tuple(
            os.path.join(
                directory,
                f"{index:03d}_{self._sanitizeTimeSeriesExportLabel(record.presentation.label)}.{extension}",
            )
            for index, record in enumerate(records, 1)
        )

    def _timeSeriesBatchCollisionChoice(self, collisions):
        """Ask once how to handle preflighted batch filename collisions."""
        dialog = QMessageBox(self.ui)
        dialog.setWindowTitle("Export selected time series")
        dialog.setIcon(MESSAGE_ICON_WARNING)
        count = len(collisions)
        noun = "file already exists" if count == 1 else "files already exist"
        dialog.setText(f"{count} generated {noun} in the selected folder.")
        dialog.setInformativeText(
            "Replace only those generated files, choose another folder, or cancel the export."
        )
        replace_button = dialog.addButton("Replace existing", MESSAGE_ROLE_DESTRUCTIVE)
        another_button = dialog.addButton("Choose another folder", MESSAGE_ROLE_ACTION)
        cancel_button = dialog.addButton("Cancel", MESSAGE_ROLE_REJECT)
        dialog.setDefaultButton(cancel_button)
        exec_dialog(dialog)
        clicked = dialog.clickedButton()
        if clicked is replace_button:
            return "replace"
        if clicked is another_button:
            return "another"
        return "cancel"

    @staticmethod
    def _recordHasExportableTimeSeriesData(record):
        """Return whether one committed record has non-empty exportable data."""
        data = getattr(record, "data", None)
        dates = getattr(data, "dates", None)
        plot_values = getattr(data, "plot_values", None)
        if dates is None or plot_values is None:
            return False
        try:
            sample_count = len(dates)
            return sample_count > 0 and sample_count == len(plot_values)
        except TypeError:
            return False

    def _exportCommittedTimeSeriesRecord(self, file_path, record):
        """Serialize one committed record through the established export helper."""
        self.choose_point_click_handler.plot_ts.exportAscii(file_path, record=record)

    def _exportMultipleCommittedTimeSeries(self, records):
        """Export committed records to separate deterministic files in one folder."""
        if any(not self._recordHasExportableTimeSeriesData(record) for record in records):
            self.msg_signal.emit(
                "One or more selected time series have no exportable data.", "w", 0
            )
            return False

        extension = self.last_ts_export_format.lower().lstrip(".") or "csv"
        directory = self.last_save_path
        if not directory or not os.path.isdir(directory):
            directory = self._initialExportDirectory()

        while True:
            directory = QFileDialog.getExistingDirectory(
                self.ui,
                "Export selected time series",
                directory,
            )
            if not directory:
                return False

            targets = self._timeSeriesBatchTargets(directory, records, extension)
            collisions = tuple(path for path in targets if os.path.lexists(path))
            if not collisions:
                break

            choice = self._timeSeriesBatchCollisionChoice(collisions)
            if choice == "cancel":
                return False
            if choice == "another":
                continue
            break

        written = []
        for record, file_path in zip(records, targets):
            try:
                self._exportCommittedTimeSeriesRecord(file_path, record)
            except (OSError, IOError, ValueError) as error:
                self.msg_signal.emit(
                    f"Time-series export failed for {file_path}: {error}. "
                    f"Exported {len(written)} of {len(targets)} files.",
                    "e",
                    0,
                )
                return False
            written.append(file_path)

        self._rememberExportPath(targets[0])
        self.msg_signal.emit(
            f"Exported {len(targets)} time series to {directory}", "done", 3000
        )
        return True

    def exportSelectedCommittedTimeSeries(self):
        """Export selected committed time series using single or batch flow."""
        self.msg_signal.emit("", "", 0)

        selected_ids = self.ui.time_series_point_panel.selected_committed_ids()
        if not selected_ids:
            return

        plotter = self.choose_point_click_handler.plot_ts
        records = tuple(plotter.committed_record(record_id) for record_id in selected_ids)
        if any(record is None for record in records):
            self.ui.time_series_point_panel.refresh_removal_actions()
            return

        if len(records) > 1:
            self._exportMultipleCommittedTimeSeries(records)
            return

        record = records[0]
        if not self._recordHasExportableTimeSeriesData(record):
            self.msg_signal.emit('No time series to export.', 'w', 0)
            return

        ts_extension = self.last_ts_export_format.lower().lstrip('.')
        suggested_name = self._withExtension(self.last_export_ts_name, ts_extension)
        suggested_path = self._suggestedExportPath(suggested_name)
        _, ext = os.path.splitext(suggested_path)

        ext_to_filter = {
            '.csv': "CSV files (*.csv)",
            '.txt': "Text files (*.txt)",
        }
        filters = ";;".join(ext_to_filter.values())
        default = ext_to_filter.get(ext.lower(), "CSV files (*.csv)")

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self.ui,
            "Export time series data",
            suggested_path,
            filters,
            default,
        )

        if not file_path:
            return

        base, ext = os.path.splitext(file_path)
        selected_extension = self._extensionFromFilter(selected_filter)
        if ext == '' and selected_extension:
            file_path = base + selected_extension
        elif ext == '':
            file_path = base + '.csv'

        try:
            self._exportCommittedTimeSeriesRecord(file_path, record)
        except (OSError, IOError, ValueError) as error:
            self.msg_signal.emit(
                f"Time-series export failed for {file_path}: {error}", 'e', 0
            )
            return

        self._rememberExportPath(file_path)
        self._rememberExportFormat('insar_explorer/ts_export_format', file_path)
        self.last_ts_export_format = os.path.splitext(file_path)[1].lstrip('.').lower()
        self.last_export_ts_name = os.path.basename(file_path)

        self.msg_signal.emit(f'Time series exported: {file_path}', 'done', 3000)

