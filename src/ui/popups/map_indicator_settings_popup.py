"""Compact popup editor for global map-indicator presentation settings."""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...qt_compat import POPUP_WINDOW_FLAG
from ...time_series.map_indicator_settings import (
    MapIndicatorSettings,
    POINT_SIZE_MAX,
    POINT_SIZE_MIN,
)
from .defaults_menu import createDefaultsMenu
from .time_series_style_popup import CompactColorButton


class MapIndicatorSettingsPopup(QWidget):
    """Edit global map-indicator settings using the standard compact popup."""

    settingsChanged = pyqtSignal(object)
    applySavedDefaultRequested = pyqtSignal()
    saveCurrentAsDefaultRequested = pyqtSignal()
    applyFactoryDefaultRequested = pyqtSignal()

    def __init__(self, parent=None):
        """Create immediate-commit controls and the shared Defaults menu."""
        super().__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("mapIndicatorSettingsPopup")
        self.setWindowTitle("Map indicators")
        self._loading = False

        layout = QVBoxLayout(self)
        self.map_markers_group = QGroupBox("Map markers", self)
        self.map_markers_group.setObjectName("group_map_indicators_markers")
        form = QFormLayout(self.map_markers_group)
        self.target_color = CompactColorButton(
            "●", "Target indicator color", self.map_markers_group,
            accessible_name="Target indicator color",
        )
        self.reference_color = CompactColorButton(
            "■", "Reference indicator color", self.map_markers_group,
            accessible_name="Reference indicator color",
        )
        self.point_size = QSpinBox(self.map_markers_group)
        self.point_size.setObjectName("spin_map_indicator_point_size")
        self.point_size.setAccessibleName("Marker size")
        self.point_size.setToolTip(
            "Base size of current Target/Reference markers; record markers remain "
            "slightly smaller and current-selection boxes scale with this value"
        )
        self.point_size.setRange(POINT_SIZE_MIN, POINT_SIZE_MAX)
        self.point_size.setSingleStep(1)
        self.point_size.setSuffix(" px")
        self.point_size.setMaximumWidth(110)

        self.opacity = QSpinBox(self.map_markers_group)
        self.opacity.setObjectName("spin_map_indicator_opacity")
        self.opacity.setAccessibleName("Indicator opacity")
        self.opacity.setRange(0, 100)
        self.opacity.setSingleStep(5)
        self.opacity.setSuffix(" %")
        self.opacity.setMaximumWidth(110)

        form.addRow("Target color", self.target_color)
        form.addRow("Reference color", self.reference_color)
        form.addRow("Marker size", self.point_size)
        form.addRow("Opacity", self.opacity)
        layout.addWidget(self.map_markers_group)

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
        self.point_size.valueChanged.connect(self._emitSettings)
        self.opacity.valueChanged.connect(self._emitSettings)

    def setSettings(self, settings):
        """Project one immutable settings snapshot without emitting changes."""
        self._loading = True
        try:
            self.target_color.setColor(settings.target_color)
            self.reference_color.setColor(settings.reference_color)
            self.point_size.setValue(int(settings.point_size))
            self.opacity.setValue(int(settings.opacity_percent))
        finally:
            self._loading = False

    def settings(self):
        """Return the complete immutable value represented by the controls."""
        return MapIndicatorSettings(
            QColor(self.target_color.color()),
            QColor(self.reference_color.color()),
            int(self.point_size.value()),
            int(self.opacity.value()),
        )

    def _emitSettings(self, unused=None):
        """Publish one complete value for each committed control change."""
        if not self._loading:
            self.settingsChanged.emit(self.settings())
