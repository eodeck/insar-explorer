"""Toolbar actions for the time-series plot panel."""

from qgis.PyQt.QtCore import QSize, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QInputDialog,
    QMenu,
    QToolBar,
    QToolButton,
    QWidget,
)

from ...qt_compat import (
    QAction,
    QActionGroup,
    SIZE_POLICY_EXPANDING,
    SIZE_POLICY_PREFERRED,
    TOOL_BUTTON_INSTANT_POPUP,
)
from ..styles import (
    apply_command_toolbar_style,
    set_toolbar_control_role,
)
from ..widgets import SplitToolButton


class TimeSeriesToolbar(QToolBar):
    """Code-defined toolbar exposing semantic time-series action signals."""

    appearanceRequested = pyqtSignal()
    exportSettingsRequested = pyqtSignal()
    plotExportRequested = pyqtSignal()
    dataExportRequested = pyqtSignal()
    fitEnabledChanged = pyqtSignal(bool)
    fitSettingsRequested = pyqtSignal()
    fitModelChanged = pyqtSignal(str)
    seasonalEnabledChanged = pyqtSignal(bool)
    residualEnabledChanged = pyqtSignal(bool)
    xAxisModeChanged = pyqtSignal(str)
    manualXAxisEditRequested = pyqtSignal()
    yAxisModeChanged = pyqtSignal(str)
    manualYAxisEditRequested = pyqtSignal()
    replicaEnabledChanged = pyqtSignal(bool)
    replicaSettingsRequested = pyqtSignal()
    plotStyleRequested = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize the toolbar and its actions."""
        super().__init__(parent)
        self.setObjectName("timeSeriesToolbar")
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QSize(18, 18))
        self.setContentsMargins(0, 0, 0, 0)
        apply_command_toolbar_style(self)

        self._fit_models = {
            "poly-1": ("Linear", ":/icons/icons/fit_poly1.svg"),
            "poly-2": ("Quadratic", ":/icons/icons/fit_poly2.svg"),
            "poly-3": ("Cubic", ":/icons/icons/fit_poly3.svg"),
            "exp": ("Exponential", ":/icons/icons/fit_exponential.svg"),
            "log": ("Logarithmic", ":/icons/icons/fit_log.svg"),
        }
        self._selected_fit_model = "poly-1"
        self._seasonal_enabled = False
        self._residual_enabled = False
        self.fit_button = SplitToolButton(
            icon=QIcon(self._fit_models[self._selected_fit_model][1]),
            primary_checkable=True,
            parent=self,
            object_name="tool_ts_fit",
            arrow_side=SplitToolButton.Right,
        )
        self.fit_button.setIconSize(self.iconSize())
        self.fit_button.setPrimaryAccessibleName("Fit time series")
        self.fit_button.setPrimaryAccessibleDescription(
            "Enable or disable fitting using the selected model."
        )
        self.fit_button.setSecondaryToolTip("Fit settings")
        self.fit_button.setSecondaryAccessibleName("Fit settings")
        self.fit_button.setSecondaryAccessibleDescription(
            "Choose the fitting model and configure fit appearance."
        )
        self._updateFitMetadata()

        self.x_axis_button = QToolButton(self)
        self.x_axis_button.setObjectName("tool_ts_x_axis")
        set_toolbar_control_role(self.x_axis_button, "selector")
        self.x_axis_button.setPopupMode(TOOL_BUTTON_INSTANT_POPUP)
        self.x_axis_menu = QMenu(self.x_axis_button)
        self.x_axis_menu.setObjectName("menu_ts_x_axis")
        self.x_axis_group = QActionGroup(self.x_axis_menu)
        self.x_axis_group.setExclusive(True)
        self.x_axis_actions = {}
        for mode, text, tooltip, icon_path, object_name in (
            (
                "from_data",
                "From data",
                "X-axis: From data\n\nUses the full available time range.",
                ":/icons/icons/x_axis_from_data.svg",
                "action_ts_x_from_data",
            ),
            (
                "manual",
                "Manual",
                "Manual time range\n\nNot configured",
                ":/icons/icons/x_axis_manual.svg",
                "action_ts_x_manual",
            ),
        ):
            action = QAction(QIcon(icon_path), text, self.x_axis_group)
            action.setObjectName(object_name)
            action.setCheckable(True)
            action.setData(mode)
            action.setToolTip(tooltip)
            self.x_axis_group.addAction(action)
            self.x_axis_menu.addAction(action)
            self.x_axis_actions[mode] = action
        self.x_axis_actions["from_data"].setChecked(True)
        self.x_axis_menu.addSeparator()
        self.edit_manual_x_axis_action = QAction("Edit range…", self.x_axis_menu)
        self.edit_manual_x_axis_action.setObjectName("action_ts_x_edit_manual")
        self.edit_manual_x_axis_action.setToolTip("Edit stored manual time range")
        self.x_axis_menu.addAction(self.edit_manual_x_axis_action)
        self.x_axis_button.setMenu(self.x_axis_menu)
        self.x_axis_button.setCheckable(False)
        self._updateXAxisSelector(self.x_axis_actions["from_data"])

        self.y_axis_button = QToolButton(self)
        self.y_axis_button.setObjectName("tool_ts_y_axis")
        set_toolbar_control_role(self.y_axis_button, "selector")
        self.y_axis_button.setPopupMode(TOOL_BUTTON_INSTANT_POPUP)
        self.y_axis_menu = QMenu(self.y_axis_button)
        self.y_axis_menu.setObjectName("menu_ts_y_axis")
        self.y_axis_group = QActionGroup(self.y_axis_menu)
        self.y_axis_group.setExclusive(True)
        self.y_axis_actions = {}
        for mode, text, tooltip, icon_path, object_name in (
            (
                "from_data",
                "From data",
                "Y-axis from data",
                ":/icons/icons/y_axis_from_data.svg",
                "action_ts_y_from_data",
            ),
            (
                "symmetric",
                "Symmetric",
                "Symmetric Y-axis",
                ":/icons/icons/y_axis_symmetric.svg",
                "action_ts_y_symmetric",
            ),
            (
                "adaptive",
                "Adaptive",
                "Adaptive Y-axis",
                ":/icons/icons/y_axis_adaptive.svg",
                "action_ts_y_adaptive",
            ),
            (
                "manual",
                "Manual",
                "Apply stored manual Y-axis ranges",
                ":/icons/icons/y_axis_manual.svg",
                "action_ts_y_manual",
            ),
        ):
            action = QAction(QIcon(icon_path), text, self.y_axis_group)
            action.setObjectName(object_name)
            action.setCheckable(True)
            action.setData(mode)
            action.setToolTip(tooltip)
            self.y_axis_group.addAction(action)
            self.y_axis_menu.addAction(action)
            self.y_axis_actions[mode] = action
        self.y_axis_actions["from_data"].setChecked(True)
        self.y_axis_menu.addSeparator()
        self.edit_manual_y_axis_action = QAction("Edit Manual ranges…", self.y_axis_menu)
        self.edit_manual_y_axis_action.setObjectName("action_ts_y_edit_manual")
        self.edit_manual_y_axis_action.setToolTip("Edit stored manual Y-axis ranges")
        self.y_axis_menu.addAction(self.edit_manual_y_axis_action)
        self.y_axis_button.setMenu(self.y_axis_menu)
        self.y_axis_button.setCheckable(False)
        self._updateYAxisSelector(self.y_axis_actions["from_data"])

        self.replica_button = SplitToolButton(
            icon=QIcon(":/icons/icons/replica.svg"),
            primary_checkable=True,
            parent=self,
            object_name="tool_ts_replica",
            arrow_side=SplitToolButton.Right,
        )
        self.replica_button.setIconSize(self.iconSize())
        self.replica_button.setPrimaryAccessibleName("Replica")
        self.replica_button.setPrimaryAccessibleDescription(
            "Toggle Replica. Use the arrow for settings."
        )
        self.replica_button.setSecondaryToolTip("Replica settings")
        self.replica_button.setSecondaryAccessibleName("Replica settings")
        self.replica_button.setSecondaryAccessibleDescription(
            "Open Replica settings."
        )
        self.plot_style_action = self._createAction(
            ":/icons/icons/plot_settings.svg",
            "Plot style",
            "Edit the style of the current time series",
            "action_ts_plot_style",
        )
        self.appearance_action = self._createAction(
            ":/icons/icons/setting.svg",
            "Appearance",
            "Appearance",
            "action_ts_appearance",
        )
        self.plot_export_button = SplitToolButton(
            icon=QIcon(":/icons/icons/screenshot.svg"),
            primary_checkable=False,
            parent=self,
            object_name="tool_ts_plot_export",
            arrow_side=SplitToolButton.Left,
            visual_role=SplitToolButton.Command,
        )
        self.plot_export_button.setIconSize(self.iconSize())
        self.plot_export_button.setPrimaryToolTip("Export plot")
        self.plot_export_button.setPrimaryStatusTip(
            "Export the current time-series plot"
        )
        self.plot_export_button.setPrimaryAccessibleName("Export plot")
        self.plot_export_button.setPrimaryAccessibleDescription(
            "Export the current time-series plot using the current export settings."
        )
        self.plot_export_button.setSecondaryToolTip("Export settings")
        self.plot_export_button.setSecondaryAccessibleName("Export settings")
        self.plot_export_button.setSecondaryAccessibleDescription(
            "Open plot export settings."
        )
        self.plot_export_button.setStatusTip(
            "Export plot; use the arrow for export settings."
        )
        self.data_export_action = self._createAction(
            ":/icons/icons/export.svg",
            "Export data",
            "Export the current time-series data",
            "action_ts_export_data",
        )

        self.addAction(self.plot_style_action)
        self.addSeparator()
        self.addWidget(self.x_axis_button)
        self.addWidget(self.y_axis_button)
        self.addSeparator()
        self.addWidget(self.fit_button)
        self.addWidget(self.replica_button)

        self._spacer_widget = QWidget(self)
        self._spacer_widget.setObjectName("timeSeriesToolbarSpacer")
        self._spacer_widget.setSizePolicy(
            SIZE_POLICY_EXPANDING,
            SIZE_POLICY_PREFERRED,
        )
        self.addWidget(self._spacer_widget)

        self.addAction(self.appearance_action)
        self.addSeparator()
        self.addWidget(self.plot_export_button)
        self.addAction(self.data_export_action)

        for action in (
            self.appearance_action,
            self.data_export_action,
            self.plot_style_action,
        ):
            self._setActionControlRole(action, "command")

        self.plot_style_action.triggered.connect(self.plotStyleRequested.emit)
        self.appearance_action.triggered.connect(self.appearanceRequested.emit)
        self.plot_export_button.primaryTriggered.connect(
            self.plotExportRequested.emit
        )
        self.plot_export_button.secondaryTriggered.connect(
            self.exportSettingsRequested.emit
        )
        self.data_export_action.triggered.connect(self.dataExportRequested.emit)
        self.fit_button.primaryToggled.connect(self.fitEnabledChanged.emit)
        self.fit_button.secondaryTriggered.connect(self.fitSettingsRequested.emit)
        self.x_axis_group.triggered.connect(self._xAxisActionTriggered)
        self.edit_manual_x_axis_action.triggered.connect(self.manualXAxisEditRequested.emit)
        self.y_axis_group.triggered.connect(self._yAxisActionTriggered)
        self.edit_manual_y_axis_action.triggered.connect(self.manualYAxisEditRequested.emit)
        self.replica_button.primaryToggled.connect(self.replicaEnabledChanged.emit)
        self.replica_button.secondaryTriggered.connect(self.replicaSettingsRequested.emit)

    def setFitEnabled(self, enabled):
        """Update the Fit primary state without emitting a user-change signal."""
        self.fit_button.setChecked(bool(enabled))
        self._updateFitMetadata()

    def setSelectedFitModel(self, model):
        """Update the selected model icon without emitting a user-change signal."""
        if model not in self._fit_models:
            raise KeyError(f"Unknown fit model: {model}")
        self._selected_fit_model = model
        self.fit_button.setPrimaryIcon(QIcon(self._fit_models[model][1]))
        self._updateFitMetadata()

    def selectFitModel(self, model):
        """Apply a user-selected model immediately, then emit one semantic change."""
        self.setSelectedFitModel(model)
        self.fitModelChanged.emit(model)

    def setSeasonalEnabled(self, enabled):
        """Update Seasonal metadata without emitting a user-change signal."""
        self._seasonal_enabled = bool(enabled)
        self._updateFitMetadata()

    def setResidualEnabled(self, enabled):
        """Update Residual metadata without emitting a user-change signal."""
        self._residual_enabled = bool(enabled)
        self._updateFitMetadata()

    def _updateFitMetadata(self):
        """Describe the selected model and current Fit configuration."""
        label = self._fit_models[self._selected_fit_model][0]
        detail = label + (" + seasonal" if self._seasonal_enabled else "")
        if self._residual_enabled:
            detail += "; residual shown"
        state = "enabled" if self.fit_button.isChecked() else "disabled"
        tooltip = f"Fit: {detail} — {state}"
        self.fit_button.setPrimaryToolTip(tooltip)
        self.fit_button.setPrimaryStatusTip(tooltip)
        self.fit_button.setStatusTip(tooltip)

    def setSelectedXAxisMode(self, mode, start=None, end=None, custom_view=False):
        """Update the selected X-axis mode without emitting a user-change signal."""
        self.refreshXAxisPresentation(mode, start, end, custom_view=custom_view)

    def refreshXAxisPresentation(self, mode, start=None, end=None, custom_view=False):
        """Refresh all temporary X-axis toolbar compatibility views.

        TODO(phase-appearance-toolbar): remove this compatibility presentation
        helper when toolbar controls bind directly to the runtime settings model.
        """
        mode = mode if mode in self.x_axis_actions else "from_data"
        action = self.x_axis_actions[mode]
        manual_action = self.x_axis_actions["manual"]
        manual_action.setText("Manual")
        if start is None or end is None:
            manual_tooltip = "Manual time range\n\nNot configured"
        else:
            manual_tooltip = f"Manual time range\n\n{start:%Y-%m-%d}\n→\n{end:%Y-%m-%d}"
        manual_action.setToolTip(manual_tooltip)

        previous = self.x_axis_group.blockSignals(True)
        action.setChecked(True)
        self.x_axis_group.blockSignals(previous)
        self._updateXAxisSelector(action, custom_view=custom_view)

    def setManualXAxisSummary(self, start, end):
        """Refresh Manual metadata while preserving the selected policy."""
        selected = self.x_axis_group.checkedAction()
        mode = selected.data() if selected is not None else "from_data"
        self.refreshXAxisPresentation(mode, start, end)

    def _xAxisActionTriggered(self, action):
        """Emit the requested policy; the controller owns presentation refresh."""
        self.xAxisModeChanged.emit(action.data())

    def _updateXAxisSelector(self, action, *, custom_view=False):
        """Render X-axis presentation from the base policy and transient viewport state."""
        if custom_view:
            tooltip = f"Custom X view\nBase policy: {action.text()}"
            self.x_axis_button.setIcon(QIcon(":/icons/icons/x_axis_custom.svg"))
        else:
            tooltip = action.toolTip()
            self.x_axis_button.setIcon(action.icon())
        self.x_axis_button.setText(action.text())
        self.x_axis_button.setToolTip(tooltip)
        self.x_axis_button.setStatusTip(tooltip)
        self.x_axis_button.setWhatsThis(tooltip)
        self.x_axis_button.setAccessibleName(f"Selected X-axis mode: {action.text()}")

    def setSelectedYAxisMode(self, mode, lower=None, upper=None, residual_lower=None, residual_upper=None, residual_active=True, custom_view=False):
        """Update the selected Y-axis mode without emitting a user-change signal."""
        self.refreshYAxisPresentation(
            mode, lower, upper, residual_lower, residual_upper, residual_active,
            custom_view,
        )

    def refreshYAxisPresentation(self, mode, lower=None, upper=None, residual_lower=None, residual_upper=None, residual_active=True, custom_view=False):
        """Refresh checked policy and aggregate visible viewport presentation."""
        action = self.y_axis_actions[mode]
        if mode == "manual":
            self.setManualYAxisSummary(lower, upper, residual_lower, residual_upper, residual_active)
        previous = self.y_axis_group.blockSignals(True)
        action.setChecked(True)
        self.y_axis_group.blockSignals(previous)
        self._updateYAxisSelector(action, custom_view=custom_view)

    def setManualYAxisSummary(self, lower, upper, residual_lower=None, residual_upper=None, residual_active=True):
        """Update Manual action text and metadata with its configured bounds."""
        def display(value):
            if value is None:
                return "Auto"
            return f"{value:g}"

        action = self.y_axis_actions["manual"]
        action.setText("Manual")
        residual_summary = (
            f"{display(residual_lower)} to {display(residual_upper)}"
            if residual_active
            else "Inactive"
        )
        action.setToolTip(
            f"Time series: {display(lower)} to {display(upper)}\n"
            f"Residuals: {residual_summary}"
        )

    def _yAxisActionTriggered(self, action):
        """Emit the requested policy; the controller owns presentation refresh."""
        self.yAxisModeChanged.emit(action.data())

    def _updateYAxisSelector(self, action, *, custom_view=False):
        """Render the aggregate visible Y-axis presentation for the selected policy."""
        if custom_view:
            self.y_axis_button.setIcon(QIcon(":/icons/icons/y_axis_custom.svg"))
            tooltip = f"Custom Y view\nBase policy: {action.text()}"
        else:
            self.y_axis_button.setIcon(action.icon())
            tooltip = action.toolTip()
        self.y_axis_button.setText(action.text())
        self.y_axis_button.setToolTip(tooltip)
        self.y_axis_button.setStatusTip(tooltip)
        self.y_axis_button.setWhatsThis(tooltip)
        self.y_axis_button.setAccessibleName(f"Selected Y-axis mode: {action.text()}")

    def setReplicaPresentation(self, enabled, interval_mm, pair_count):
        """Refresh the Replica split button without changing runtime state."""
        enabled = bool(enabled)
        toggle_tooltip = "Disable Replica" if enabled else "Enable Replica"
        description = (
            f"Replica enabled; interval {float(interval_mm):.1f} mm; "
            f"{int(pair_count)} pair(s)."
            if enabled else "Replica disabled."
        )

        self.replica_button.setChecked(enabled)
        self.replica_button.setPrimaryToolTip(toggle_tooltip)
        self.replica_button.setPrimaryStatusTip(description)
        self.replica_button.setPrimaryAccessibleDescription(
            "Toggle Replica. Use the arrow for settings. " + description
        )
        self.replica_button.setStatusTip(description)

    def _setActionControlRole(self, action, role):
        """Assign a semantic role to the tool button generated for an action."""
        button = self.widgetForAction(action)
        if isinstance(button, QToolButton):
            set_toolbar_control_role(button, role)

    def _createAction(self, icon_path, text, tooltip, object_name):
        """Create a non-checkable command action with stable metadata."""
        action = QAction(QIcon(icon_path), text, self)
        action.setObjectName(object_name)
        action.setToolTip(tooltip)
        action.setCheckable(False)
        return action

    def _createToggleAction(self, icon_path, text, tooltip, object_name):
        """Create a checkable toolbar action for an independent state toggle."""
        action = QAction(QIcon(icon_path), text, self)
        action.setObjectName(object_name)
        action.setToolTip(tooltip)
        action.setCheckable(True)
        return action
