"""Compact popups for secondary Map Settings controls."""

from qgis.PyQt import QtWidgets

from ...qt_compat import POPUP_WINDOW_FLAG
from .range_state import RangeSource, StdCalculationMode


class RangeSettingsPopup(QtWidgets.QWidget):
    """Present range derivation and symmetry as independent UI state."""

    def __init__(self, parent=None):
        """Create the compact range settings popup."""
        super(RangeSettingsPopup, self).__init__(parent, POPUP_WINDOW_FLAG)
        self.setObjectName("map_range_settings_popup")
        self.setWindowTitle("Range settings")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(6)

        form = QtWidgets.QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)

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

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(6)

        form = QtWidgets.QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(6)
        form.addRow("Classes", self.sb_symbol_classes)
        form.addRow("Marker size", self.sb_symbol_size)
        form.addRow("Opacity", self.sb_symbol_opacity)
        layout.addLayout(form)

        self._form_layout = form
        self.setMaximumWidth(280)
