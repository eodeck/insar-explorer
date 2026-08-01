"""Committed time-series table view interaction policy."""

from qgis.PyQt import QtWidgets

from ...qt_compat import CHECK_STATE_ROLE, CHECKED, UNCHECKED, LEFT_MOUSE_BUTTON
from .committed_columns import CommittedTimeSeriesColumn


class CommittedTimeSeriesView(QtWidgets.QTableView):
    """Keep visibility checkbox interaction independent from row selection."""

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        if (
            event.button() == LEFT_MOUSE_BUTTON
            and index.isValid()
            and index.column() == CommittedTimeSeriesColumn.VISIBLE
        ):
            current = index.data(CHECK_STATE_ROLE)
            self.model().setData(
                index,
                CHECKED if current != CHECKED else UNCHECKED,
                CHECK_STATE_ROLE,
            )
            event.accept()
            return
        super(CommittedTimeSeriesView, self).mousePressEvent(event)
