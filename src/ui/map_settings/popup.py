"""Compact popup for Map Settings range source and symmetry controls."""

from qgis.PyQt import QtWidgets

from ...qt_compat import POPUP_WINDOW_FLAG
from .range_state import RangeSource


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
        layout.addLayout(form)

        self.cb_symbol_range_symmetric = QtWidgets.QCheckBox(
            "Symmetric around zero", self
        )
        self.cb_symbol_range_symmetric.setObjectName("cb_symbol_range_symmetric")
        self.cb_symbol_range_symmetric.setToolTip(
            "Use the largest absolute bound on both sides of zero"
        )
        self.cb_symbol_range_symmetric.setAccessibleName("Symmetric around zero")
        self.cb_symbol_range_symmetric.setChecked(True)
        layout.addWidget(self.cb_symbol_range_symmetric)

        self.setMaximumWidth(280)
