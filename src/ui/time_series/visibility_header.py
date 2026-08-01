"""Tri-state visibility header for committed time-series records."""

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import QRect, pyqtSignal

from ...qt_compat import CHECKED, PARTIALLY_CHECKED, UNCHECKED


class TimeSeriesVisibilityHeader(QtWidgets.QHeaderView):
    """Paint and toggle a tri-state checkbox in the visibility header cell."""

    toggleAllRequested = pyqtSignal(bool)

    def __init__(self, orientation, parent=None):
        super(TimeSeriesVisibilityHeader, self).__init__(orientation, parent)
        self._check_state = UNCHECKED
        self._has_records = False
        self.sectionClicked.connect(self._section_clicked)

    def set_visibility_state(self, state, has_records):
        """Project aggregate visibility without generating user intent."""
        self._check_state = state
        self._has_records = bool(has_records)
        self.viewport().update()

    def paintSection(self, painter, rect, logical_index):
        super(TimeSeriesVisibilityHeader, self).paintSection(painter, rect, logical_index)
        if logical_index != 0:
            return
        option = QtWidgets.QStyleOptionButton()
        sub_element = getattr(getattr(QtWidgets.QStyle, "SubElement", QtWidgets.QStyle), "SE_CheckBoxIndicator")
        indicator = self.style().subElementRect(sub_element, option, self)
        option.rect = QRect(
            rect.center().x() - indicator.width() // 2,
            rect.center().y() - indicator.height() // 2,
            indicator.width(), indicator.height(),
        )
        state_owner = getattr(QtWidgets.QStyle, "StateFlag", QtWidgets.QStyle)
        option.state = state_owner.State_Enabled if self._has_records else state_owner.State_None
        if self._check_state == CHECKED:
            option.state |= state_owner.State_On
        elif self._check_state == PARTIALLY_CHECKED:
            option.state |= state_owner.State_NoChange
        else:
            option.state |= state_owner.State_Off
        control = getattr(getattr(QtWidgets.QStyle, "ControlElement", QtWidgets.QStyle), "CE_CheckBox")
        self.style().drawControl(control, option, painter, self)

    def _section_clicked(self, logical_index):
        if logical_index != 0 or not self._has_records:
            return
        self.toggleAllRequested.emit(self._check_state == UNCHECKED)
