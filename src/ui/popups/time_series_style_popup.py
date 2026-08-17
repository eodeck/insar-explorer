"""Compact popup editor for time-series series and fit-line styles."""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor, QIcon

from ...ui_windows.color_picker import ColorPicker
from ...time_series.ensemble_style import (
    ENSEMBLE_MEMBER_WIDTH_RANGE,
)
from ...time_series.style_schema import (
    LINE_STYLE_OPTIONS,
    LINE_WIDTH_RANGE,
    MARKER_OPTIONS,
    MARKER_SIZE_RANGE,
    NUMERIC_DECIMALS,
    NUMERIC_STEP,
    OPACITY_PERCENT_MIN, OPACITY_PERCENT_MAX, OPACITY_PERCENT_STEP,
    alpha_to_percent,
)
from .defaults_menu import createDefaultsMenu
from ...qt_compat import (
    POPUP_WINDOW_FLAG,
    SIZE_POLICY_FIXED,
    SIZE_POLICY_MAXIMUM,
    SIZE_POLICY_PREFERRED,
    configure_compact_command_button,
)

from qgis.PyQt.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QSpinBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class CompactColorButton(QPushButton):
    """Square color-preview button matching the former Settings control."""

    colorChanged = pyqtSignal(str)

    def __init__(self, glyph, tooltip, parent=None, accessible_name=None):
        """Create a fixed-size color preview with optional semantic metadata."""
        super().__init__(glyph, parent)
        self._color = "#000000"
        self.setToolTip(tooltip)
        self.setAccessibleName(accessible_name or tooltip)
        self.setFixedSize(24, 24)
        self.setSizePolicy(SIZE_POLICY_FIXED, SIZE_POLICY_FIXED)
        self.clicked.connect(self._pickColor)
        self._updatePreview()

    def setColor(self, color, emit=False):
        """Update the preview immediately and optionally emit the selected color."""
        parsed = QColor(color)
        if not parsed.isValid():
            parsed = QColor("#000000")
        self._color = parsed.name()
        self.setAccessibleDescription("{}: {}".format(self.accessibleName(), self._color))
        self._updatePreview()
        if emit:
            self.colorChanged.emit(self._color)

    def color(self):
        """Return the current normalized color name."""
        return self._color

    def _updatePreview(self):
        self.setStyleSheet(
            "QPushButton { color: %s; } QPushButton:hover { border: 1px solid #bbb; }"
            % self._color
        )

    def _pickColor(self):
        picker = ColorPicker(self._color, use_native_flag=False, parent=self)
        selected = picker.pickColor()
        if selected != self._color:
            self.setColor(selected, emit=True)


class TimeSeriesStylePopup(QWidget):
    """Non-modal anchored editor for the currently selected time series."""

    markerTypeChanged = pyqtSignal(str)
    markerColorChanged = pyqtSignal(str)
    markerSizeChanged = pyqtSignal(float)
    markerOpacityChanged = pyqtSignal(int)
    lineTypeChanged = pyqtSignal(str)
    lineColorChanged = pyqtSignal(str)
    lineWidthChanged = pyqtSignal(float)
    lineOpacityChanged = pyqtSignal(int)
    randomizeColorRequested = pyqtSignal()
    applySavedSeriesDefaultRequested = pyqtSignal()
    saveCurrentSeriesAsDefaultRequested = pyqtSignal()
    applyFactorySeriesDefaultRequested = pyqtSignal()
    ensembleMemberColorChanged = pyqtSignal(str)
    ensembleMemberWidthChanged = pyqtSignal(float)
    ensembleMemberOpacityChanged = pyqtSignal(int)
    ensembleFillColorChanged = pyqtSignal(str)
    ensembleFillOpacityChanged = pyqtSignal(int)
    applySavedEnsembleDefaultRequested = pyqtSignal()
    saveCurrentEnsembleAsDefaultRequested = pyqtSignal()
    applyFactoryEnsembleDefaultRequested = pyqtSignal()

    def __init__(self, parent=None):
        """Create compact tabbed style controls without applying changes."""
        super().__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("timeSeriesStylePopup")
        self._loading = False

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("tabs_time_series_style")
        layout.addWidget(self.tabs)
        self._createSeriesTab()
        self._createEnsembleTab()
        self.setMaximumWidth(360)
        self.setSelectionState(False)

    def _createSeriesTab(self):
        """Build the existing Series controls without redesigning them."""
        tab = QWidget(self.tabs)
        layout = QVBoxLayout(tab)
        self.marker_group = QGroupBox("Marker", tab)
        marker_layout = QFormLayout(self.marker_group)
        self.marker_type = QComboBox(self.marker_group)
        self.marker_type.addItems(list(MARKER_OPTIONS))
        self.marker_color = CompactColorButton("●", "Select marker color", self.marker_group)
        self.marker_size = QDoubleSpinBox(self.marker_group)
        self.marker_size.setRange(*MARKER_SIZE_RANGE)
        self.marker_size.setDecimals(NUMERIC_DECIMALS)
        self.marker_size.setSingleStep(NUMERIC_STEP)
        marker_layout.addRow("Type", self.marker_type)
        marker_layout.addRow("Size", self.marker_size)
        marker_layout.addRow("Color", self.marker_color)
        self.marker_opacity = self._createOpacitySpinBox(self.marker_group)
        marker_layout.addRow("Opacity", self.marker_opacity)

        self.line_group = QGroupBox("Line", tab)
        line_layout = QFormLayout(self.line_group)
        self.line_type = QComboBox(self.line_group)
        self.line_type.addItems(list(LINE_STYLE_OPTIONS))
        self.line_color = CompactColorButton("━", "Select line color", self.line_group)
        self.line_width = QDoubleSpinBox(self.line_group)
        self.line_width.setRange(*LINE_WIDTH_RANGE)
        self.line_width.setDecimals(NUMERIC_DECIMALS)
        self.line_width.setSingleStep(NUMERIC_STEP)
        line_layout.addRow("Type", self.line_type)
        line_layout.addRow("Width", self.line_width)
        line_layout.addRow("Color", self.line_color)
        self.line_opacity = self._createOpacitySpinBox(self.line_group)
        line_layout.addRow("Opacity", self.line_opacity)

        groups_layout = QHBoxLayout()
        groups_layout.setContentsMargins(0, 0, 0, 0)
        groups_layout.addWidget(self.marker_group)
        groups_layout.addWidget(self.line_group)
        layout.addLayout(groups_layout)

        self.randomize_button = QPushButton(tab)
        self.randomize_button.setIcon(QIcon(":/icons/icons/plot_random_color.svg"))
        configure_compact_command_button(self.randomize_button)
        self.randomize_button.setToolTip("Randomize marker and line color")
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.addWidget(self.randomize_button)
        actions_layout.addStretch(1)
        self.default_button = createDefaultsMenu(
            tab, self.applySavedSeriesDefaultRequested.emit,
            self.saveCurrentSeriesAsDefaultRequested.emit,
            self.applyFactorySeriesDefaultRequested.emit,
            "button_series_defaults",
        )
        actions_layout.addWidget(self.default_button)
        layout.addLayout(actions_layout)

        self.marker_type.currentTextChanged.connect(self._emitMarkerType)
        self.marker_size.valueChanged.connect(self._emitMarkerSize)
        self.marker_opacity.valueChanged.connect(
            lambda v: None if self._loading else self.markerOpacityChanged.emit(int(v))
        )
        self.line_type.currentTextChanged.connect(self._emitLineType)
        self.line_width.valueChanged.connect(self._emitLineWidth)
        self.line_opacity.valueChanged.connect(
            lambda v: None if self._loading else self.lineOpacityChanged.emit(int(v))
        )
        self.marker_color.colorChanged.connect(self.markerColorChanged.emit)
        self.line_color.colorChanged.connect(self.lineColorChanged.emit)
        self.randomize_button.clicked.connect(self.randomizeColorRequested.emit)
        for editor in (self.marker_type,
                       self.marker_size,
                       self.marker_opacity,
                       self.line_type, self.line_width,
                       self.line_opacity
                       ):
            editor.setMaximumWidth(110)
        self.marker_group.setSizePolicy(SIZE_POLICY_MAXIMUM, SIZE_POLICY_PREFERRED)
        self.line_group.setSizePolicy(SIZE_POLICY_MAXIMUM, SIZE_POLICY_PREFERRED)
        self.tabs.addTab(tab, "Series")

    def _createEnsembleTab(self):
        """Build compact member-line and spread controls for ensemble snapshots."""
        tab = QWidget(self.tabs)
        layout = QVBoxLayout(tab)
        groups = QHBoxLayout()
        groups.setContentsMargins(0, 0, 0, 0)
        self.ensemble_member_group = QGroupBox("Member series", tab)
        member_layout = QFormLayout(self.ensemble_member_group)
        self.ensemble_member_color = CompactColorButton("━", "Select ensemble member color", self.ensemble_member_group)
        self.ensemble_member_width = QDoubleSpinBox(self.ensemble_member_group)
        self.ensemble_member_width.setRange(*ENSEMBLE_MEMBER_WIDTH_RANGE)
        self.ensemble_member_width.setDecimals(NUMERIC_DECIMALS)
        self.ensemble_member_width.setSingleStep(NUMERIC_STEP)
        self.ensemble_member_opacity = self._createOpacitySpinBox(self.ensemble_member_group)
        member_layout.addRow("Color", self.ensemble_member_color)
        member_layout.addRow("Width", self.ensemble_member_width)
        member_layout.addRow("Opacity", self.ensemble_member_opacity)

        self.ensemble_spread_group = QGroupBox("Spread", tab)
        spread_layout = QFormLayout(self.ensemble_spread_group)
        self.ensemble_fill_color = CompactColorButton("■", "Select ensemble spread color", self.ensemble_spread_group)
        self.ensemble_fill_opacity = self._createOpacitySpinBox(self.ensemble_spread_group)
        spread_layout.addRow("Fill color", self.ensemble_fill_color)
        spread_layout.addRow("Opacity", self.ensemble_fill_opacity)
        groups.addWidget(self.ensemble_member_group)
        groups.addWidget(self.ensemble_spread_group)
        layout.addLayout(groups)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.ensemble_default_button = createDefaultsMenu(
            tab, self.applySavedEnsembleDefaultRequested.emit,
            self.saveCurrentEnsembleAsDefaultRequested.emit,
            self.applyFactoryEnsembleDefaultRequested.emit,
            "button_ensemble_defaults",
        )
        actions.addWidget(self.ensemble_default_button)
        layout.addLayout(actions)
        layout.addStretch(1)

        self.ensemble_member_color.colorChanged.connect(self.ensembleMemberColorChanged.emit)
        self.ensemble_member_width.valueChanged.connect(
            lambda v: None if self._loading else self.ensembleMemberWidthChanged.emit(float(v))
        )
        self.ensemble_member_opacity.valueChanged.connect(
            lambda v: None if self._loading else self.ensembleMemberOpacityChanged.emit(int(v))
        )
        self.ensemble_fill_color.colorChanged.connect(self.ensembleFillColorChanged.emit)
        self.ensemble_fill_opacity.valueChanged.connect(
            lambda v: None if self._loading else self.ensembleFillOpacityChanged.emit(int(v))
        )
        for editor in (self.ensemble_member_width, self.ensemble_member_opacity, self.ensemble_fill_opacity):
            editor.setMaximumWidth(90)
        self.tabs.addTab(tab, "Ensemble")

    def setEnsembleStyle(self, ensemble_style):
        """Populate Ensemble controls without emitting user-action signals."""
        self._loading = True
        self.ensemble_member_color.setColor(ensemble_style.member_line_color)
        self.ensemble_member_width.setValue(float(ensemble_style.member_line_width))
        self.ensemble_member_opacity.setValue(alpha_to_percent(ensemble_style.member_line_alpha))
        self.ensemble_fill_color.setColor(ensemble_style.fill_color)
        self.ensemble_fill_opacity.setValue(alpha_to_percent(ensemble_style.fill_alpha))
        self._loading = False

    def setEnsembleAvailability(self, available, applicable_count=0):
        """Keep the Ensemble tab stable while disabling unavailable controls."""
        available = bool(available)
        for widget in (self.ensemble_member_group, self.ensemble_spread_group, self.ensemble_default_button):
            widget.setEnabled(available)

    def setLayerAvailability(self, availability):
        """Apply centralized layer availability without emitting edit signals."""
        for widget in (self.marker_group, self.line_group, self.randomize_button, self.default_button):
            widget.setEnabled(bool(availability.series_available))
        for widget in (self.ensemble_member_group, self.ensemble_spread_group,
                       self.ensemble_default_button):
            widget.setEnabled(bool(availability.ensemble_available))

    def setSelectionState(self, selected, count=0):
        """Compatibility entry point for Series selection state only."""
        selected = bool(selected)
        for widget in (self.marker_group, self.line_group, self.randomize_button, self.default_button):
            widget.setEnabled(selected)

    @staticmethod
    def _createOpacitySpinBox(parent):
        """Create a compact percentage editor shared by all style tabs."""
        editor = QSpinBox(parent)
        editor.setRange(OPACITY_PERCENT_MIN, OPACITY_PERCENT_MAX)
        editor.setSingleStep(OPACITY_PERCENT_STEP)
        editor.setSuffix("%")
        editor.setMaximumWidth(76)
        editor.setToolTip("0% hides the element; 100% is fully opaque.")
        return editor

    def setStyle(self, style):
        """Populate Series controls from a TimeSeriesStyle without emitting edits."""
        params = style.params.get("time series plot", {}) if style is not None else {}
        self._loading = True
        self.marker_type.setCurrentText(str(params.get("marker", "")))
        self.marker_size.setValue(float(params.get("marker size", 0.0)))
        self.line_type.setCurrentText(str(params.get("line style", "")))
        self.line_width.setValue(float(params.get("line width", 0.0)))
        self.marker_color.setColor(params.get("marker color", "#000000"))
        self.marker_opacity.setValue(alpha_to_percent(params.get("marker alpha", 1.0)))
        self.line_color.setColor(params.get("line color", "#000000"))
        self.line_opacity.setValue(alpha_to_percent(params.get("line alpha", 1.0)))
        self._loading = False

    def setMixedProperties(self, properties):
        """Record property names with mixed values for future multi-selection UI."""
        self.setProperty("mixedStyleProperties", tuple(sorted(properties)))

    def _emitMarkerType(self, value):
        if not self._loading:
            self.markerTypeChanged.emit(value)

    def _emitMarkerSize(self, value):
        if not self._loading:
            self.markerSizeChanged.emit(float(value))

    def _emitLineType(self, value):
        if not self._loading:
            self.lineTypeChanged.emit(value)

    def _emitLineWidth(self, value):
        if not self._loading:
            self.lineWidthChanged.emit(float(value))
