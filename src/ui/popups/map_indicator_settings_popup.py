"""Compact popup editor for global map-indicator presentation settings."""

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import (
    QCheckBox,
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
            "■", "Target indicator color", self.map_markers_group,
            accessible_name="Target indicator color",
        )
        self.reference_color = CompactColorButton(
            "●", "Reference indicator color", self.map_markers_group,
            accessible_name="Reference indicator color",
        )
        self.point_size = QSpinBox(self.map_markers_group)
        self.point_size.setObjectName("spin_map_indicator_point_size")
        self.point_size.setAccessibleName("Point indicator size")
        self.point_size.setToolTip(
            "Base size of pending point indicators; committed indicators remain "
            "slightly smaller"
        )
        self.point_size.setRange(POINT_SIZE_MIN, POINT_SIZE_MAX)
        self.point_size.setSingleStep(1)
        self.point_size.setSuffix(" px")
        self.point_size.setMaximumWidth(110)

        self.show_point_outer_ring = QCheckBox(self.map_markers_group)
        self.show_point_outer_ring.setObjectName("check_map_indicator_outer_ring")
        self.show_point_outer_ring.setAccessibleName("Show point outer ring")
        self.show_point_outer_ring.setToolTip(
            "Show a contrasting outer ring around point indicators"
        )
        self.point_outer_color = CompactColorButton(
            "○", "Color of the optional point outer ring", self.map_markers_group,
            accessible_name="Point outer-ring color",
        )
        outer_ring_row = QWidget(self.map_markers_group)
        outer_ring_layout = QHBoxLayout(outer_ring_row)
        outer_ring_layout.setContentsMargins(0, 0, 0, 0)
        outer_ring_layout.setSpacing(6)
        outer_ring_layout.addWidget(self.show_point_outer_ring)
        outer_ring_layout.addWidget(self.point_outer_color)
        outer_ring_layout.addStretch(1)

        self.opacity = QSpinBox(self.map_markers_group)
        self.opacity.setObjectName("spin_map_indicator_opacity")
        self.opacity.setAccessibleName("Indicator opacity")
        self.opacity.setRange(0, 100)
        self.opacity.setSuffix(" %")
        self.opacity.setMaximumWidth(110)

        form.addRow("Target color", self.target_color)
        form.addRow("Reference color", self.reference_color)
        form.addRow("Point size", self.point_size)
        form.addRow("Outer ring", outer_ring_row)
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
        self.show_point_outer_ring.toggled.connect(self._outerRingToggled)
        self.point_outer_color.colorChanged.connect(self._emitSettings)
        self.opacity.valueChanged.connect(self._emitSettings)

    def setSettings(self, settings):
        """Project one immutable settings snapshot without emitting changes."""
        self._loading = True
        try:
            self.target_color.setColor(settings.target_color)
            self.reference_color.setColor(settings.reference_color)
            self.point_size.setValue(int(settings.point_size))
            self.show_point_outer_ring.setChecked(bool(settings.show_point_outer_ring))
            self.point_outer_color.setColor(settings.point_outer_color)
            self.point_outer_color.setEnabled(bool(settings.show_point_outer_ring))
            self.opacity.setValue(int(settings.opacity_percent))
        finally:
            self._loading = False

    def settings(self):
        """Return the complete immutable value represented by the controls."""
        return MapIndicatorSettings(
            QColor(self.target_color.color()),
            QColor(self.reference_color.color()),
            QColor(self.point_outer_color.color()),
            bool(self.show_point_outer_ring.isChecked()),
            int(self.point_size.value()),
            int(self.opacity.value()),
        )

    def _outerRingToggled(self, checked):
        """Synchronize color availability and publish the complete value."""
        self.point_outer_color.setEnabled(bool(checked))
        self._emitSettings()

    def _emitSettings(self, unused=None):
        """Publish one complete value for each committed control change."""
        if not self._loading:
            self.settingsChanged.emit(self.settings())
