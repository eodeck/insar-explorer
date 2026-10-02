"""Compact editor for plot-wide time-series legend settings."""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QGroupBox,
    QSpinBox, QVBoxLayout, QWidget,
)

from ...qt_compat import POPUP_WINDOW_FLAG
from .defaults_menu import createDefaultsMenu


class LegendPopup(QWidget):
    """Edit plot-wide legend settings with immediate runtime updates."""

    settingsChanged = pyqtSignal(str, bool, float, float)
    applySavedGeneralDefaultRequested = pyqtSignal()
    saveCurrentGeneralAsDefaultRequested = pyqtSignal()
    applyFactoryGeneralDefaultRequested = pyqtSignal()

    LOCATIONS = (
        ("Top right", "top_right"),
        ("Top left", "top_left"),
        ("Bottom right", "bottom_right"),
        ("Bottom left", "bottom_left"),
        ("Right", "right"),
        ("Left", "left"),
    )

    def __init__(self, parent=None):
        super().__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("legendPopup")
        self.setWindowTitle("Plot legend")

        layout = QVBoxLayout(self)
        self._buildSettings(layout)

        self.sync_font_size_checkbox.setChecked(True)
        self.font_size_spin.setValue(9.0)
        self.background_opacity_spin.setValue(80)
        self._syncFontSizeEnabled(True)

        self.location_combo.currentIndexChanged.connect(self._emit_settings)
        self.sync_font_size_checkbox.toggled.connect(self._syncFontSizeEnabled)
        self.sync_font_size_checkbox.toggled.connect(self._emit_settings)
        self.font_size_spin.valueChanged.connect(self._emit_settings)
        self.background_opacity_spin.valueChanged.connect(self._emit_settings)

    def _buildSettings(self, layout):
        """Add the compact plot-wide layout, text, and defaults controls."""
        legend_group = QGroupBox("Layout", self)
        legend_form = QFormLayout(legend_group)
        self.location_combo = QComboBox(legend_group)
        self.location_combo.setObjectName("combo_legend_location")
        for text, value in self.LOCATIONS:
            self.location_combo.addItem(text, value)
        self.location_combo.setAccessibleName("Legend location")
        self.location_combo.setToolTip("Choose where legends are placed in each plot.")
        self.location_combo.setMaximumWidth(140)
        self.background_opacity_spin = QSpinBox(legend_group)
        self.background_opacity_spin.setObjectName("spin_legend_background_opacity")
        self.background_opacity_spin.setRange(0, 100)
        self.background_opacity_spin.setSuffix("%")
        self.background_opacity_spin.setMaximumWidth(80)
        self.background_opacity_spin.setSingleStep(5)
        legend_form.addRow("Location", self.location_combo)
        legend_form.addRow("Background opacity", self.background_opacity_spin)
        layout.addWidget(legend_group)

        text_group = QGroupBox("Text", self)
        text_form = QFormLayout(text_group)
        self.sync_font_size_checkbox = QCheckBox("Match plot text size", text_group)
        self.sync_font_size_checkbox.setObjectName("check_legend_sync_font_size")
        self.font_size_spin = QDoubleSpinBox(text_group)
        self.font_size_spin.setObjectName("spin_legend_font_size")
        self.font_size_spin.setRange(1.0, 200.0)
        self.font_size_spin.setDecimals(1)
        self.font_size_spin.setSingleStep(1.0)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setMaximumWidth(80)
        text_form.addRow(self.sync_font_size_checkbox)
        text_form.addRow("Text size", self.font_size_spin)
        layout.addWidget(text_group)
        layout.addStretch(1)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.general_defaults_button = createDefaultsMenu(
            self, self.applySavedGeneralDefaultRequested.emit,
            self.saveCurrentGeneralAsDefaultRequested.emit,
            self.applyFactoryGeneralDefaultRequested.emit,
            "button_legend_general_defaults",
        )
        actions.addWidget(self.general_defaults_button)
        layout.addLayout(actions)

    def _syncFontSizeEnabled(self, checked):
        self.font_size_spin.setEnabled(not checked)

    def settings(self):
        """Return the plot-wide LegendSettings fields managed by this popup."""
        return (
            str(self.location_combo.currentData() or "top_right"),
            self.sync_font_size_checkbox.isChecked(),
            float(self.font_size_spin.value()),
            float(self.background_opacity_spin.value()) / 100.0,
        )

    def setSettings(self, settings):
        """Refresh all controls without emitting runtime updates."""
        widgets = (
            self.location_combo, self.sync_font_size_checkbox, self.font_size_spin,
            self.background_opacity_spin,
        )
        previous = [widget.blockSignals(True) for widget in widgets]
        try:
            self.location_combo.setCurrentIndex(max(0, self.location_combo.findData(settings.location)))
            self.sync_font_size_checkbox.setChecked(settings.sync_font_size)
            self.font_size_spin.setValue(float(settings.font_size))
            self.background_opacity_spin.setValue(int(round(settings.background_opacity * 100)))
            self._syncFontSizeEnabled(settings.sync_font_size)
        finally:
            for widget, blocked in zip(widgets, previous):
                widget.blockSignals(blocked)

    def _emit_settings(self, *_args):
        self.settingsChanged.emit(*self.settings())
