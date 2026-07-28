"""Compact popup for consolidated Replica controls."""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from ...qt_compat import POPUP_WINDOW_FLAG
from ...time_series.replica_schema import (
    REPLICA_INTERVAL_PRESETS,
    replica_interval_for_preset,
    replica_preset_id_for_interval,
)
from ...time_series.style_schema import MARKER_OPTIONS
from .time_series_style_popup import CompactColorButton
from .defaults_menu import createDefaultsMenu


class ReplicaPopup(QWidget):
    """Edit global Replica settings and appearance without Apply/Cancel controls."""

    settingsChanged = pyqtSignal(float, int, str, str, float, str, float)
    applySavedDefaultRequested = pyqtSignal()
    saveCurrentAsDefaultRequested = pyqtSignal()
    applyFactoryDefaultRequested = pyqtSignal()
    CUSTOM_PRESET_ID = "custom"

    def __init__(self, parent=None):
        """Build the compact immediate-update popup with Settings and Style tabs."""
        super().__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("replicaPopup")
        self.setWindowTitle("Replica")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("replicaTabs")
        layout.addWidget(self.tabs)

        self.settings_tab = QWidget(self.tabs)
        self.settings_tab.setObjectName("replicaSettingsTab")
        self.style_tab = QWidget(self.tabs)
        self.style_tab.setObjectName("replicaStyleTab")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.style_tab, "Style")
        self.tabs.setCurrentIndex(0)

        self._buildSettingsTab()
        self._buildStyleTab()
        self._connectSignals()
        self._setTabOrder()
        self.setReplicaStyleAvailable(False)

    def _buildSettingsTab(self):
        """Create Replica generation controls in the Settings domain."""
        tab_layout = QVBoxLayout(self.settings_tab)
        tab_layout.setContentsMargins(6, 6, 6, 6)
        tab_layout.setSpacing(6)

        settings_group = QGroupBox("Settings", self.settings_tab)
        settings_form = QFormLayout(settings_group)
        self.preset_combo = QComboBox(settings_group)
        self.preset_combo.setEditable(False)
        self.preset_combo.setToolTip("Select a common radar half-wavelength interval.")
        settings_control_width = 140
        for preset_id, label, _interval in REPLICA_INTERVAL_PRESETS:
            self.preset_combo.addItem(label, preset_id)
        self.preset_combo.addItem("Custom", self.CUSTOM_PRESET_ID)

        self.interval_spin = QDoubleSpinBox(settings_group)
        self.interval_spin.setRange(0.1, 10000.0)
        self.interval_spin.setDecimals(1)
        self.interval_spin.setSuffix(" mm")
        self.preset_combo.setFixedWidth(settings_control_width)
        self.interval_spin.setFixedWidth(settings_control_width)

        self.pair_count_spin = QSpinBox(settings_group)
        self.pair_count_spin.setRange(1, 10)
        self.pair_count_spin.setFixedWidth(settings_control_width)
        settings_form.addRow("Preset", self.preset_combo)
        settings_form.addRow("Interval", self.interval_spin)
        settings_form.addRow("Pairs", self.pair_count_spin)
        tab_layout.addWidget(settings_group)
        tab_layout.addStretch(1)

    def _buildStyleTab(self):
        """Create Replica appearance controls and defaults in the Style domain."""
        tab_layout = QVBoxLayout(self.style_tab)
        tab_layout.setContentsMargins(6, 6, 6, 6)
        tab_layout.setSpacing(6)

        self.style_content = QWidget(self.style_tab)
        self.style_content.setObjectName("replicaStyleContent")
        content_layout = QVBoxLayout(self.style_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)
        tab_layout.addWidget(self.style_content)

        appearance_group = QGroupBox("Appearance", self.style_content)
        appearance_form = QFormLayout(appearance_group)
        self.color_1_button = CompactColorButton(
            "●", "First color used by the alternating Replica pattern.", appearance_group
        )
        self.color_2_button = CompactColorButton(
            "●", "Second color used by the alternating Replica pattern.", appearance_group
        )
        self.opacity_spin = QSpinBox(appearance_group)
        self.opacity_spin.setRange(0, 100)
        self.opacity_spin.setSingleStep(5)
        self.opacity_spin.setSuffix(" %")
        appearance_control_width = 110
        self.opacity_spin.setFixedWidth(appearance_control_width)
        self.marker_combo = QComboBox(appearance_group)
        self.marker_combo.setToolTip("Replica marker")
        for marker in MARKER_OPTIONS:
            self.marker_combo.addItem(marker, marker)
        self.marker_combo.setFixedWidth(appearance_control_width)
        self.marker_size_spin = QDoubleSpinBox(appearance_group)
        self.marker_size_spin.setRange(0.0, 100.0)
        self.marker_size_spin.setSingleStep(0.5)
        self.marker_size_spin.setDecimals(1)
        self.marker_size_spin.setFixedWidth(appearance_control_width)
        self.color_1_button.setAccessibleName("Replica Color 1")
        self.color_2_button.setAccessibleName("Replica Color 2")

        colors_widget = QWidget(appearance_group)
        colors_layout = QGridLayout(colors_widget)
        colors_layout.setContentsMargins(0, 0, 0, 0)
        colors_layout.setHorizontalSpacing(6)
        colors_layout.setVerticalSpacing(0)
        colors_layout.addWidget(QLabel("Color 1", colors_widget), 0, 0)
        colors_layout.addWidget(self.color_1_button, 0, 1)
        colors_layout.setColumnMinimumWidth(2, 8)
        colors_layout.addWidget(QLabel("Color 2", colors_widget), 0, 3)
        colors_layout.addWidget(self.color_2_button, 0, 4)
        colors_layout.setColumnStretch(5, 1)
        appearance_form.addRow(colors_widget)
        appearance_form.addRow("Opacity", self.opacity_spin)
        appearance_form.addRow("Marker", self.marker_combo)
        appearance_form.addRow("Marker size", self.marker_size_spin)
        content_layout.addWidget(appearance_group)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.defaults_button = createDefaultsMenu(
            self.style_content, self.applySavedDefaultRequested.emit,
            self.saveCurrentAsDefaultRequested.emit,
            self.applyFactoryDefaultRequested.emit,
            "button_replica_defaults",
        )
        actions.addWidget(self.defaults_button)
        content_layout.addLayout(actions)
        content_layout.addStretch(1)
        tab_layout.addStretch(1)

    def _connectSignals(self):
        """Connect each existing immediate-update signal exactly once."""
        self.preset_combo.currentIndexChanged.connect(self._presetChanged)
        self.interval_spin.valueChanged.connect(self._intervalChanged)
        self.pair_count_spin.valueChanged.connect(self._emitSettings)
        self.color_1_button.colorChanged.connect(self._emitSettings)
        self.color_2_button.colorChanged.connect(self._emitSettings)
        self.opacity_spin.valueChanged.connect(self._emitSettings)
        self.marker_combo.currentIndexChanged.connect(self._emitSettings)
        self.marker_size_spin.valueChanged.connect(self._emitSettings)

    def _setTabOrder(self):
        """Preserve logical keyboard navigation within and across both domains."""
        QWidget.setTabOrder(self.preset_combo, self.interval_spin)
        QWidget.setTabOrder(self.interval_spin, self.pair_count_spin)
        QWidget.setTabOrder(self.pair_count_spin, self.color_1_button)
        QWidget.setTabOrder(self.color_1_button, self.color_2_button)
        QWidget.setTabOrder(self.color_2_button, self.opacity_spin)
        QWidget.setTabOrder(self.opacity_spin, self.marker_combo)
        QWidget.setTabOrder(self.marker_combo, self.marker_size_spin)
        QWidget.setTabOrder(self.marker_size_spin, self.defaults_button)

    def setReplicaStyleAvailable(self, available):
        """Enable or disable Style contents while keeping the tab discoverable."""
        self.style_content.setEnabled(bool(available))

    def _setPresetForInterval(self, interval_mm):
        """Synchronize the preset view from the authoritative numeric interval."""
        preset_id = replica_preset_id_for_interval(interval_mm) or self.CUSTOM_PRESET_ID
        previous = self.preset_combo.blockSignals(True)
        try:
            index = self.preset_combo.findData(preset_id)
            self.preset_combo.setCurrentIndex(max(0, index))
        finally:
            self.preset_combo.blockSignals(previous)

    def _presetChanged(self, _index):
        """Apply a named preset to Interval and emit one consolidated update."""
        interval = replica_interval_for_preset(self.preset_combo.currentData())
        if interval is None:
            return
        previous = self.interval_spin.blockSignals(True)
        try:
            self.interval_spin.setValue(interval)
        finally:
            self.interval_spin.blockSignals(previous)
        self._emitSettings()

    def _intervalChanged(self, interval_mm):
        """Derive the preset selection from a manually edited interval."""
        self._setPresetForInterval(interval_mm)
        self._emitSettings()

    def _emitSettings(self, *_args):
        """Emit normalized UI values, converting percent opacity at the boundary."""
        self.settingsChanged.emit(
            self.interval_spin.value(), self.pair_count_spin.value(),
            self.color_1_button.color(),
            self.color_2_button.color(), self.opacity_spin.value() / 100.0,
            self.marker_combo.currentData(), self.marker_size_spin.value(),
        )

    def setSettings(self, settings):
        """Refresh controls from runtime state without emitting writes."""
        controls = (
            self.preset_combo, self.interval_spin,
            self.pair_count_spin, self.color_1_button, self.color_2_button,
            self.opacity_spin, self.marker_combo, self.marker_size_spin,
        )
        previous = [control.blockSignals(True) for control in controls]
        try:
            self.interval_spin.setValue(settings.interval_mm)
            preset_id = replica_preset_id_for_interval(settings.interval_mm) or self.CUSTOM_PRESET_ID
            self.preset_combo.setCurrentIndex(max(0, self.preset_combo.findData(preset_id)))
            self.pair_count_spin.setValue(settings.pair_count)
            self.color_1_button.setColor(settings.color_1)
            self.color_2_button.setColor(settings.color_2)
            self.opacity_spin.setValue(round(settings.opacity * 100))
            index = self.marker_combo.findData(settings.marker)
            self.marker_combo.setCurrentIndex(max(0, index))
            self.marker_size_spin.setValue(settings.marker_size)
        finally:
            for control, blocked in zip(controls, previous):
                control.blockSignals(blocked)
