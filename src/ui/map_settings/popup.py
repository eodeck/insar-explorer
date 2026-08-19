"""Compact popups for secondary Map Settings controls."""

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal

from ...qt_compat import POPUP_WINDOW_FLAG, TOOLTIP_ROLE
from ..popups.defaults_menu import createDefaultsMenu
from ..popups.time_series_style_popup import CompactColorButton
from ..spacing import SPACE_MD, SPACE_LG
from .marker_state import (
    DEFAULT_MARKER_SHAPE, DEFAULT_OUTLINE_COLOR, DEFAULT_OUTLINE_WIDTH_MM,
    MARKER_SHAPES,
)
from .range_state import RangeSource, StdCalculationMode


class RangeSettingsPopup(QtWidgets.QWidget):
    """Present range derivation and symmetry as independent UI state."""

    applySavedDefaultRequested = pyqtSignal()
    saveCurrentAsDefaultRequested = pyqtSignal()
    applyFactoryDefaultRequested = pyqtSignal()

    def __init__(self, parent=None):
        """Create the compact range settings popup."""
        super(RangeSettingsPopup, self).__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("map_range_settings_popup")
        self.setWindowTitle("Range settings")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        layout.setSpacing(SPACE_MD)

        form = QtWidgets.QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(SPACE_LG)
        form.setVerticalSpacing(SPACE_MD)

        self.cmb_symbol_range_source = QtWidgets.QComboBox(self)
        self.cmb_symbol_range_source.setObjectName("cmb_symbol_range_source")
        self.cmb_symbol_range_source.setToolTip("Choose how the range is derived")
        self.cmb_symbol_range_source.setAccessibleName("Range source")
        for source in RangeSource:
            self.cmb_symbol_range_source.addItem(source.display_name, source.value)
        form.addRow("Range source", self.cmb_symbol_range_source)

        self.cmb_std_calculation_mode = QtWidgets.QComboBox(self)
        self.cmb_std_calculation_mode.setObjectName("cmb_std_calculation_mode")
        self.cmb_std_calculation_mode.setAccessibleName("Std calculation")
        for mode in StdCalculationMode:
            self.cmb_std_calculation_mode.addItem(mode.display_name, mode.value)
        self.cmb_std_calculation_mode.setCurrentIndex(
            self.cmb_std_calculation_mode.findData(StdCalculationMode.FAST.value)
        )
        self.cmb_std_calculation_mode.setEnabled(False)
        self._update_std_calculation_tooltip()
        self.cmb_std_calculation_mode.currentIndexChanged.connect(
            self._update_std_calculation_tooltip
        )
        form.addRow("Calculation", self.cmb_std_calculation_mode)
        layout.addLayout(form)

        self.cb_symbol_range_symmetric = QtWidgets.QCheckBox(
            "Symmetric around zero", self
        )
        self.cb_symbol_range_symmetric.setObjectName("cb_symbol_range_symmetric")
        self.cb_symbol_range_symmetric.setToolTip(
            "Use the largest absolute bound on both sides of zero"
        )
        self.cb_symbol_range_symmetric.setAccessibleName("Symmetric around zero")
        self.cb_symbol_range_symmetric.setChecked(False)
        layout.addWidget(self.cb_symbol_range_symmetric)

        actions = QtWidgets.QHBoxLayout()
        actions.addStretch(1)
        self.defaults_button = createDefaultsMenu(
            self,
            self.applySavedDefaultRequested.emit,
            self.saveCurrentAsDefaultRequested.emit,
            self.applyFactoryDefaultRequested.emit,
            "button_map_range_defaults",
        )
        actions.addWidget(self.defaults_button)
        layout.addLayout(actions)

        self.setMaximumWidth(280)

    def _update_std_calculation_tooltip(self, index=None):
        """Describe the currently selected standard-deviation calculation mode."""
        if index is None:
            index = self.cmb_std_calculation_mode.currentIndex()
        value = self.cmb_std_calculation_mode.itemData(index)
        try:
            mode = StdCalculationMode(value)
        except (TypeError, ValueError):
            return
        self.cmb_std_calculation_mode.setToolTip(mode.tooltip)


class SymbologySettingsPopup(QtWidgets.QWidget):
    """Present secondary symbology controls in a compact popup."""

    applySavedDefaultRequested = pyqtSignal()
    saveCurrentAsDefaultRequested = pyqtSignal()
    applyFactoryDefaultRequested = pyqtSignal()

    def __init__(
        self,
        classes_spin_box,
        marker_size_spin_box,
        opacity_spin_box,
        parent=None,
    ):
        """Create the popup around the existing symbology controls."""
        super(SymbologySettingsPopup, self).__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("map_symbology_settings_popup")
        self.setWindowTitle("Symbology settings")

        self.sb_symbol_classes = classes_spin_box
        self.sb_symbol_size = marker_size_spin_box
        self.sb_symbol_opacity = opacity_spin_box

        self.cb_symbol_continuous_colormap = QtWidgets.QCheckBox(
            "Continuous colormap", self
        )
        self.cb_symbol_continuous_colormap.setObjectName(
            "cb_symbol_continuous_colormap"
        )
        self.cb_symbol_continuous_colormap.setToolTip(
            "Use a continuously interpolated colormap"
        )
        self.cb_symbol_continuous_colormap.setAccessibleName(
            "Continuous colormap"
        )
        self.cb_symbol_continuous_colormap.setChecked(True)
        self.cb_symbol_continuous_colormap.toggled.connect(
            self._sync_continuous_colormap_controls
        )

        self.cmb_symbol_marker_shape = QtWidgets.QComboBox(self)
        self.cmb_symbol_marker_shape.setObjectName("cmb_symbol_marker_shape")
        self.cmb_symbol_marker_shape.setEditable(False)
        self.cmb_symbol_marker_shape.setToolTip("Point marker type")
        self.cmb_symbol_marker_shape.setAccessibleName("Marker type")
        for token, value, accessible_label in MARKER_SHAPES:
            index = self.cmb_symbol_marker_shape.count()
            self.cmb_symbol_marker_shape.addItem(token, value)
            description = "{} — {}".format(token, accessible_label)
            self.cmb_symbol_marker_shape.setItemData(index, description, TOOLTIP_ROLE)
            item = self.cmb_symbol_marker_shape.model().item(index)
            if item is not None:
                if hasattr(item, "setAccessibleText"):
                    item.setAccessibleText(accessible_label)
                if hasattr(item, "setAccessibleDescription"):
                    item.setAccessibleDescription(description)
        self.cmb_symbol_marker_shape.setCurrentIndex(
            self.cmb_symbol_marker_shape.findData(DEFAULT_MARKER_SHAPE)
        )

        self.pb_symbol_outline_color = CompactColorButton(
            "●", "Select marker outline color", self,
            accessible_name="Marker outline color",
        )
        self.pb_symbol_outline_color.setObjectName("pb_symbol_outline_color")
        self.pb_symbol_outline_color.setColor(DEFAULT_OUTLINE_COLOR)

        self.sb_symbol_outline_width = QtWidgets.QDoubleSpinBox(self)
        self.sb_symbol_outline_width.setObjectName("sb_symbol_outline_width")
        self.sb_symbol_outline_width.setRange(0.0, 2.0)
        self.sb_symbol_outline_width.setDecimals(2)
        self.sb_symbol_outline_width.setSingleStep(0.05)
        self.sb_symbol_outline_width.setValue(DEFAULT_OUTLINE_WIDTH_MM)
        self.sb_symbol_outline_width.setSuffix(" mm")
        self.sb_symbol_outline_width.setToolTip(
            "Marker outline width; 0.00 mm removes the outline"
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        layout.setSpacing(SPACE_MD)

        groups = QtWidgets.QHBoxLayout()
        groups.setContentsMargins(0, 0, 0, 0)
        groups.setSpacing(SPACE_LG)

        self.color_group = QtWidgets.QGroupBox("Color", self)
        self.color_group.setObjectName("map_symbology_color_group")
        color_layout = QtWidgets.QVBoxLayout(self.color_group)
        color_layout.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        color_layout.setSpacing(SPACE_MD)
        color_layout.addWidget(self.cb_symbol_continuous_colormap)
        color_form = QtWidgets.QFormLayout()
        color_form.setContentsMargins(0, 0, 0, 0)
        color_form.setHorizontalSpacing(SPACE_LG)
        color_form.setVerticalSpacing(SPACE_MD)
        color_form.addRow("Classes", self.sb_symbol_classes)
        color_form.addRow("Opacity", self.sb_symbol_opacity)
        color_layout.addLayout(color_form)
        groups.addWidget(self.color_group)

        self.marker_group = QtWidgets.QGroupBox("Marker", self)
        self.marker_group.setObjectName("map_symbology_marker_group")
        marker_form = QtWidgets.QFormLayout(self.marker_group)
        marker_form.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        marker_form.setHorizontalSpacing(SPACE_LG)
        marker_form.setVerticalSpacing(SPACE_MD)
        marker_form.addRow("Type", self.cmb_symbol_marker_shape)
        marker_form.addRow("Size", self.sb_symbol_size)
        marker_form.addRow("Outline", self.pb_symbol_outline_color)
        marker_form.addRow("Width", self.sb_symbol_outline_width)
        groups.addWidget(self.marker_group)
        layout.addLayout(groups)

        actions = QtWidgets.QHBoxLayout()
        actions.addStretch(1)
        self.defaults_button = createDefaultsMenu(
            self,
            self.applySavedDefaultRequested.emit,
            self.saveCurrentAsDefaultRequested.emit,
            self.applyFactoryDefaultRequested.emit,
            "button_map_symbology_defaults",
        )
        actions.addWidget(self.defaults_button)
        layout.addLayout(actions)

        # Compatibility alias retained for callers/tests introduced with the first
        # marker-controls implementation; the QGroupBox is the single real owner.
        self.marker_section = self.marker_group
        self._form_layout = color_form
        self._sync_continuous_colormap_controls(
            self.cb_symbol_continuous_colormap.isChecked()
        )
        self.setMaximumWidth(360)

    def set_point_marker_available(self, available):
        """Show point-only marker controls only for a point-vector layer."""
        self.marker_group.setVisible(bool(available))
        self.adjustSize()

    def set_continuous_colormap(self, continuous):
        """Set continuous mode programmatically and synchronize dependent UI."""
        continuous = bool(continuous)
        blocked = self.cb_symbol_continuous_colormap.blockSignals(True)
        try:
            self.cb_symbol_continuous_colormap.setChecked(continuous)
        finally:
            self.cb_symbol_continuous_colormap.blockSignals(blocked)
        self._sync_continuous_colormap_controls(continuous)

    def _sync_continuous_colormap_controls(self, continuous):
        """Keep class-count editability consistent with renderer mode."""
        self.sb_symbol_classes.setEnabled(not bool(continuous))
