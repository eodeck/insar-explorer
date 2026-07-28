"""Compact tabbed editor for time-series Fit settings and styles."""

from qgis.PyQt.QtCore import QSize, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout,
    QGroupBox, QHBoxLayout, QPushButton, QRadioButton, QSpinBox, QTabWidget,
    QToolButton,
    QVBoxLayout, QWidget,
)

from ...qt_compat import (
    POPUP_WINDOW_FLAG, SIZE_POLICY_MAXIMUM, SIZE_POLICY_PREFERRED,
    configure_compact_command_button,
)
from ...time_series.style_schema import (
    FIT_LINE_STYLE_OPTIONS, FIT_LINE_WIDTH_DECIMALS, FIT_LINE_WIDTH_RANGE,
    FIT_LINE_WIDTH_STEP, NUMERIC_DECIMALS, NUMERIC_STEP,
    OPACITY_PERCENT_MAX, OPACITY_PERCENT_MIN, OPACITY_PERCENT_STEP,
    RESIDUAL_LINE_STYLE_OPTIONS, RESIDUAL_LINE_WIDTH_RANGE,
    RESIDUAL_MARKER_OPTIONS, RESIDUAL_MARKER_SIZE_RANGE, alpha_to_percent,
)
from .time_series_style_popup import CompactColorButton
from .defaults_menu import createDefaultsMenu


FIT_MODELS = (
    ("poly-1", "Linear", ":/icons/icons/fit_poly1.svg", "choice_ts_fit_poly_1"),
    ("poly-2", "Quadratic", ":/icons/icons/fit_poly2.svg", "choice_ts_fit_poly_2"),
    ("poly-3", "Cubic", ":/icons/icons/fit_poly3.svg", "choice_ts_fit_poly_3"),
    ("exp", "Exponential", ":/icons/icons/fit_exponential.svg", "choice_ts_fit_exp"),
    ("log", "Logarithmic", ":/icons/icons/fit_log.svg", "choice_ts_fit_log"),
)


class FitPopup(QWidget):
    """Edit Fit configuration and the existing Fit-specific style domains."""

    modelChanged = pyqtSignal(str)
    seasonalEnabledChanged = pyqtSignal(bool)
    residualEnabledChanged = pyqtSignal(bool)
    fitLineTypeChanged = pyqtSignal(str)
    fitLineColorChanged = pyqtSignal(str)
    fitLineWidthChanged = pyqtSignal(float)
    fitOpacityChanged = pyqtSignal(int)
    residualMarkerTypeChanged = pyqtSignal(str)
    residualMarkerColorChanged = pyqtSignal(str)
    residualMarkerSizeChanged = pyqtSignal(float)
    residualMarkerOpacityChanged = pyqtSignal(int)
    residualLineTypeChanged = pyqtSignal(str)
    residualLineColorChanged = pyqtSignal(str)
    residualLineWidthChanged = pyqtSignal(float)
    residualLineOpacityChanged = pyqtSignal(int)
    applySavedFitDefaultRequested = pyqtSignal()
    saveCurrentFitAsDefaultRequested = pyqtSignal()
    applyFactoryFitDefaultRequested = pyqtSignal()
    randomizeResidualColorRequested = pyqtSignal()
    applySavedResidualDefaultRequested = pyqtSignal()
    saveCurrentResidualAsDefaultRequested = pyqtSignal()
    applyFactoryResidualDefaultRequested = pyqtSignal()

    def __init__(self, parent=None):
        """Create the three focused tabs without mutating runtime state."""
        super().__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("popup_ts_fit")
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("tabs_ts_fit")
        layout.addWidget(self.tabs)

        self._createSettingsTab()
        self._createFitStyleTab()
        self._createResidualStyleTab()
        self.setFitStyleAvailable(False)
        self.setResidualStyleAvailable(False)
        self.setMaximumWidth(430)

    def _createSettingsTab(self):
        """Build compact model choices and the two Fit option checkboxes."""
        tab = QWidget(self.tabs)
        tab.setObjectName("tab_ts_fit_settings")
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        models = QGroupBox("Model", tab)
        models_layout = QGridLayout(models)
        models_layout.setContentsMargins(8, 6, 8, 6)
        models_layout.setHorizontalSpacing(12)
        models_layout.setVerticalSpacing(2)
        self.model_grid = models_layout
        self.model_group = QButtonGroup(models)
        self.model_group.setExclusive(True)
        self.model_buttons = {}
        for index, (model_id, label, icon_path, object_name) in enumerate(FIT_MODELS):
            button = QRadioButton(label, models)
            button.setObjectName(object_name)
            button.setIcon(QIcon(icon_path))
            button.setIconSize(QSize(18, 18))
            button.setCheckable(True)
            button.setAccessibleName(f"{label} fit")
            button.setProperty("modelId", model_id)
            button.setMinimumHeight(24)
            self.model_group.addButton(button)
            self.model_buttons[model_id] = button
            models_layout.addWidget(button, index // 2, index % 2)
            button.clicked.connect(
                lambda checked, mid=model_id: self._emitModel(mid, checked)
            )
        self.seasonal_checkbox = QCheckBox("Seasonal component", models)
        self.seasonal_checkbox.setObjectName("check_ts_fit_seasonal")
        self.seasonal_checkbox.setIcon(
            QIcon(":/icons/icons/fit__add_seasonal.svg")
        )
        self.seasonal_checkbox.setIconSize(QSize(18, 18))
        self.seasonal_checkbox.setAccessibleName("Seasonal component")
        self.seasonal_checkbox.setAccessibleDescription(
            "Add a seasonal component to the selected fitting model."
        )
        models_layout.addWidget(self.seasonal_checkbox, 3, 0, 1, 2)
        layout.addWidget(models)

        options = QGroupBox("Options", tab)
        options_layout = QVBoxLayout(options)
        options_layout.setContentsMargins(8, 6, 8, 6)
        options_layout.setSpacing(4)
        self.residual_checkbox = QCheckBox("Show residual plot", options)
        self.residual_checkbox.setObjectName("check_ts_fit_residual")
        self.residual_checkbox.setIcon(
            QIcon(":/icons/icons/residual.svg")
        )
        options_layout.addWidget(self.residual_checkbox)
        layout.addWidget(options)
        layout.addStretch(1)

        ordered_controls = [
            self.model_buttons[model_id] for model_id, *_ in FIT_MODELS
        ] + [self.seasonal_checkbox, self.residual_checkbox]
        for current, following in zip(ordered_controls, ordered_controls[1:]):
            QWidget.setTabOrder(current, following)

        self.seasonal_checkbox.toggled.connect(
            lambda value: None if self._loading
            else self.seasonalEnabledChanged.emit(bool(value))
        )
        self.residual_checkbox.toggled.connect(
            lambda value: None if self._loading
            else self.residualEnabledChanged.emit(bool(value))
        )
        self.tabs.addTab(tab, "Settings")

    def _createFitStyleTab(self):
        """Build the compact fitted-model style editor."""
        tab = QWidget(self.tabs)
        tab.setObjectName("tab_ts_fit_fit_style")
        self.fit_style_tab = tab
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.fit_style_content = QWidget(tab)
        content_layout = QVBoxLayout(self.fit_style_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)
        layout.addWidget(self.fit_style_content)

        self.fit_group = QGroupBox("Fit line", self.fit_style_content)
        self.fit_group.setSizePolicy(SIZE_POLICY_MAXIMUM, SIZE_POLICY_PREFERRED)
        form = QFormLayout(self.fit_group)
        form.setContentsMargins(8, 6, 8, 6)
        form.setSpacing(4)
        self.fit_line_type = QComboBox(self.fit_group)
        self.fit_line_type.addItems(list(FIT_LINE_STYLE_OPTIONS))
        self.fit_line_width = QDoubleSpinBox(self.fit_group)
        self.fit_line_width.setRange(*FIT_LINE_WIDTH_RANGE)
        self.fit_line_width.setDecimals(FIT_LINE_WIDTH_DECIMALS)
        self.fit_line_width.setSingleStep(FIT_LINE_WIDTH_STEP)
        self.fit_line_color = CompactColorButton(
            "━", "Select fit line color", self.fit_group
        )
        self.fit_line_opacity = self._opacity(self.fit_group)
        form.addRow("Type", self.fit_line_type)
        form.addRow("Width", self.fit_line_width)
        form.addRow("Color", self.fit_line_color)
        form.addRow("Opacity", self.fit_line_opacity)
        content_layout.addWidget(self.fit_group, 0)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        self.fit_default_button = createDefaultsMenu(
            self.fit_style_content, self.applySavedFitDefaultRequested.emit,
            self.saveCurrentFitAsDefaultRequested.emit,
            self.applyFactoryFitDefaultRequested.emit,
            "button_fit_defaults",
        )
        action_layout.addStretch(1)
        action_layout.addWidget(self.fit_default_button)
        content_layout.addLayout(action_layout)
        content_layout.addStretch(1)

        self.fit_line_type.currentTextChanged.connect(
            lambda value: None if self._loading
            else self.fitLineTypeChanged.emit(value)
        )
        self.fit_line_width.valueChanged.connect(
            lambda value: None if self._loading
            else self.fitLineWidthChanged.emit(float(value))
        )
        self.fit_line_opacity.valueChanged.connect(
            lambda value: None if self._loading
            else self.fitOpacityChanged.emit(int(value))
        )
        self.fit_line_color.colorChanged.connect(self.fitLineColorChanged.emit)
        self._setCompactEditorWidths(
            self.fit_line_type, self.fit_line_width, self.fit_line_opacity
        )
        self.tabs.addTab(tab, "Fit style")

    def _createResidualStyleTab(self):
        """Build side-by-side compact residual marker and line editors."""
        tab = QWidget(self.tabs)
        tab.setObjectName("tab_ts_fit_residual_style")
        self.residual_style_tab = tab
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.residual_style_content = QWidget(tab)
        content_layout = QVBoxLayout(self.residual_style_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)
        layout.addWidget(self.residual_style_content)

        groups = QHBoxLayout()
        groups.setContentsMargins(0, 0, 0, 0)
        groups.setSpacing(8)

        self.residual_marker_group = QGroupBox("Marker", self.residual_style_content)
        self.residual_marker_group.setSizePolicy(
            SIZE_POLICY_MAXIMUM, SIZE_POLICY_PREFERRED
        )
        marker_form = QFormLayout(self.residual_marker_group)
        marker_form.setContentsMargins(8, 6, 8, 6)
        marker_form.setSpacing(4)
        self.residual_marker_type = QComboBox(self.residual_marker_group)
        self.residual_marker_type.addItems(list(RESIDUAL_MARKER_OPTIONS))
        self.residual_marker_size = QDoubleSpinBox(self.residual_marker_group)
        self.residual_marker_size.setRange(*RESIDUAL_MARKER_SIZE_RANGE)
        self.residual_marker_size.setDecimals(NUMERIC_DECIMALS)
        self.residual_marker_size.setSingleStep(NUMERIC_STEP)
        self.residual_marker_color = CompactColorButton(
            "●", "Select residual marker color", self.residual_marker_group
        )
        self.residual_marker_opacity = self._opacity(self.residual_marker_group)
        marker_form.addRow("Type", self.residual_marker_type)
        marker_form.addRow("Size", self.residual_marker_size)
        marker_form.addRow("Color", self.residual_marker_color)
        marker_form.addRow("Opacity", self.residual_marker_opacity)

        self.residual_line_group = QGroupBox("Line", self.residual_style_content)
        self.residual_line_group.setSizePolicy(
            SIZE_POLICY_MAXIMUM, SIZE_POLICY_PREFERRED
        )
        line_form = QFormLayout(self.residual_line_group)
        line_form.setContentsMargins(8, 6, 8, 6)
        line_form.setSpacing(4)
        self.residual_line_type = QComboBox(self.residual_line_group)
        self.residual_line_type.addItems(list(RESIDUAL_LINE_STYLE_OPTIONS))
        self.residual_line_width = QDoubleSpinBox(self.residual_line_group)
        self.residual_line_width.setRange(*RESIDUAL_LINE_WIDTH_RANGE)
        self.residual_line_width.setDecimals(NUMERIC_DECIMALS)
        self.residual_line_width.setSingleStep(NUMERIC_STEP)
        self.residual_line_color = CompactColorButton(
            "━", "Select residual line color", self.residual_line_group
        )
        self.residual_line_opacity = self._opacity(self.residual_line_group)
        line_form.addRow("Type", self.residual_line_type)
        line_form.addRow("Width", self.residual_line_width)
        line_form.addRow("Color", self.residual_line_color)
        line_form.addRow("Opacity", self.residual_line_opacity)
        groups.addWidget(self.residual_marker_group)
        groups.addWidget(self.residual_line_group)
        groups.addStretch(1)
        content_layout.addLayout(groups)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        self.residual_randomize_button = QToolButton(self.residual_style_content)
        self.residual_randomize_button.setIcon(
            QIcon(":/icons/icons/plot_random_color.svg")
        )
        configure_compact_command_button(self.residual_randomize_button)
        self.residual_randomize_button.setToolTip("Randomize residual colors")
        self.residual_randomize_button.setAccessibleName(
            "Randomize residual colors"
        )
        self.residual_randomize_button.setAccessibleDescription(
            "Assign new colors to the residual series."
        )
        self.residual_default_button = createDefaultsMenu(
            self.residual_style_content, self.applySavedResidualDefaultRequested.emit,
            self.saveCurrentResidualAsDefaultRequested.emit,
            self.applyFactoryResidualDefaultRequested.emit,
            "button_residual_defaults",
        )
        actions.addWidget(self.residual_randomize_button)
        actions.addStretch(1)
        actions.addWidget(self.residual_default_button)
        content_layout.addLayout(actions)
        content_layout.addStretch(1)

        self.residual_marker_type.currentTextChanged.connect(
            lambda value: None if self._loading
            else self.residualMarkerTypeChanged.emit(value)
        )
        self.residual_marker_size.valueChanged.connect(
            lambda value: None if self._loading
            else self.residualMarkerSizeChanged.emit(float(value))
        )
        self.residual_marker_opacity.valueChanged.connect(
            lambda value: None if self._loading
            else self.residualMarkerOpacityChanged.emit(int(value))
        )
        self.residual_marker_color.colorChanged.connect(
            self.residualMarkerColorChanged.emit
        )
        self.residual_line_type.currentTextChanged.connect(
            lambda value: None if self._loading
            else self.residualLineTypeChanged.emit(value)
        )
        self.residual_line_width.valueChanged.connect(
            lambda value: None if self._loading
            else self.residualLineWidthChanged.emit(float(value))
        )
        self.residual_line_opacity.valueChanged.connect(
            lambda value: None if self._loading
            else self.residualLineOpacityChanged.emit(int(value))
        )
        self.residual_line_color.colorChanged.connect(
            self.residualLineColorChanged.emit
        )
        self.residual_randomize_button.clicked.connect(
            self.randomizeResidualColorRequested.emit
        )
        self._setCompactEditorWidths(
            self.residual_marker_type, self.residual_marker_size,
            self.residual_marker_opacity, self.residual_line_type,
            self.residual_line_width, self.residual_line_opacity,
        )
        self.tabs.addTab(tab, "Residual style")


    def setFitStyleAvailable(self, available):
        """Toggle Fit appearance contents while keeping its tab selectable."""
        self.fit_style_content.setEnabled(bool(available))

    def setResidualStyleAvailable(self, available):
        """Toggle Residual appearance contents while keeping its tab selectable."""
        self.residual_style_content.setEnabled(bool(available))

    @staticmethod
    def _setCompactEditorWidths(*editors):
        """Keep property editors at the established compact popup width."""
        for editor in editors:
            editor.setMaximumWidth(110)

    @staticmethod
    def _opacity(parent):
        """Create a compact percentage editor using the existing style range."""
        editor = QSpinBox(parent)
        editor.setRange(OPACITY_PERCENT_MIN, OPACITY_PERCENT_MAX)
        editor.setSingleStep(OPACITY_PERCENT_STEP)
        editor.setSuffix("%")
        return editor

    def _emitModel(self, model_id, checked):
        """Emit one semantic model change for a checked user selection."""
        if checked and not self._loading:
            self.modelChanged.emit(model_id)

    def setSettings(self, model, seasonal, residual):
        """Synchronize configuration without emitting user-facing changes."""
        if model not in self.model_buttons:
            raise KeyError(f"Unknown fit model: {model}")
        self._loading = True
        try:
            self.model_buttons[model].setChecked(True)
            self.seasonal_checkbox.setChecked(bool(seasonal))
            self.residual_checkbox.setChecked(bool(residual))
        finally:
            self._loading = False

    def setFitStyle(self, style):
        """Synchronize the fitted-model style without emitting writes."""
        self._loading = True
        try:
            self.fit_line_type.setCurrentText(style.line_style)
            self.fit_line_color.setColor(style.line_color)
            self.fit_line_width.setValue(float(style.line_width))
            self.fit_line_opacity.setValue(alpha_to_percent(style.line_alpha))
        finally:
            self._loading = False

    def setResidualStyle(self, style):
        """Synchronize the residual style without emitting writes."""
        self._loading = True
        try:
            self.residual_marker_type.setCurrentText(style.marker)
            self.residual_marker_color.setColor(style.marker_color)
            self.residual_marker_size.setValue(float(style.marker_size))
            self.residual_marker_opacity.setValue(alpha_to_percent(style.marker_alpha))
            self.residual_line_type.setCurrentText(style.line_style)
            self.residual_line_color.setColor(style.line_color)
            self.residual_line_width.setValue(float(style.line_width))
            self.residual_line_opacity.setValue(alpha_to_percent(style.line_alpha))
        finally:
            self._loading = False
