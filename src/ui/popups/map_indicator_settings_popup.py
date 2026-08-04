"""Compact popup editor for global map-indicator presentation settings."""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QFormLayout, QHBoxLayout, QSpinBox, QVBoxLayout, QWidget

from ...qt_compat import POPUP_WINDOW_FLAG
from ...time_series.map_indicator_settings import MapIndicatorSettings
from .defaults_menu import createDefaultsMenu
from .time_series_style_popup import CompactColorButton


class MapIndicatorSettingsPopup(QWidget):
    """Edit global map-indicator settings using the standard compact popup."""

    settingsChanged = pyqtSignal(object)
    applySavedDefaultRequested = pyqtSignal()
    saveCurrentAsDefaultRequested = pyqtSignal()
    applyFactoryDefaultRequested = pyqtSignal()

    def __init__(self, parent=None):
        """Create four immediate-commit controls and the shared Defaults menu."""
        super().__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("mapIndicatorSettingsPopup")
        self.setWindowTitle("Map indicators")
        self._loading = False

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.target_color = CompactColorButton(
            "●", "Target indicator color", self,
            accessible_name="Target indicator color",
        )
        self.reference_color = CompactColorButton(
            "●", "Reference indicator color", self,
            accessible_name="Reference indicator color",
        )
        self.point_outer_color = CompactColorButton(
            "○", "Point outer-ring color", self,
            accessible_name="Point outer-ring color",
        )
        self.opacity = QSpinBox(self)
        self.opacity.setObjectName("spin_map_indicator_opacity")
        self.opacity.setAccessibleName("Indicator opacity")
        self.opacity.setRange(0, 100)
        self.opacity.setSuffix(" %")
        self.opacity.setMaximumWidth(110)

        form.addRow("Target color", self.target_color)
        form.addRow("Reference color", self.reference_color)
        form.addRow("Point outer-ring color", self.point_outer_color)
        form.addRow("Opacity", self.opacity)
        layout.addLayout(form)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.defaults_button = createDefaultsMenu(
            self,
            self.applySavedDefaultRequested.emit,
            self.saveCurrentAsDefaultRequested.emit,
            self.applyFactoryDefaultRequested.emit,
            "button_map_indicator_defaults",
        )
        actions.addWidget(self.defaults_button)
        layout.addLayout(actions)
        self.setMaximumWidth(320)

        self.target_color.colorChanged.connect(self._emitSettings)
        self.reference_color.colorChanged.connect(self._emitSettings)
        self.point_outer_color.colorChanged.connect(self._emitSettings)
        self.opacity.valueChanged.connect(self._emitSettings)

    def setSettings(self, settings):
        """Project one immutable settings snapshot without emitting changes."""
        self._loading = True
        try:
            self.target_color.setColor(settings.target_color)
            self.reference_color.setColor(settings.reference_color)
            self.point_outer_color.setColor(settings.point_outer_color)
            self.opacity.setValue(int(settings.opacity_percent))
        finally:
            self._loading = False

    def settings(self):
        """Return the complete immutable value represented by the controls."""
        return MapIndicatorSettings(
            QColor(self.target_color.color()),
            QColor(self.reference_color.color()),
            QColor(self.point_outer_color.color()),
            int(self.opacity.value()),
        )

    def _emitSettings(self, unused=None):
        """Publish one complete value for each committed control change."""
        if not self._loading:
            self.settingsChanged.emit(self.settings())
