"""Committed time-series table view interaction policy."""

from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import pyqtSignal

from ...qt_compat import (
    QAction, CLEAR_AND_SELECT, CURRENT_SELECTION, CUSTOM_CONTEXT_MENU,
    CHECK_STATE_ROLE, CHECKED, UNCHECKED, LEFT_MOUSE_BUTTON,
    EDITING_STATE, KEY_BACKSPACE, KEY_DELETE, SELECT_ROWS_SELECTION,
)
from .committed_columns import CommittedTimeSeriesColumn


class CommittedTimeSeriesView(QtWidgets.QTableView):
    """Keep visibility interaction separate and emit removal intent only."""

    removeSelectedRequested = pyqtSignal()

    def __init__(self, parent=None):
        """Create an intent-only view with a shared removal context action."""
        super(CommittedTimeSeriesView, self).__init__(parent)
        self.remove_action = QAction(
            QtGui.QIcon(":/icons/icons/item_remove.svg"), "Remove", self
        )
        self.remove_action.setObjectName("action_remove_selected_time_series")
        self.remove_action.setToolTip("Remove selected time series")
        self.remove_action.setEnabled(False)
        self.remove_action.triggered.connect(self._request_selected_removal)
        self.setContextMenuPolicy(CUSTOM_CONTEXT_MENU)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _has_selected_rows(self):
        selection_model = self.selectionModel()
        return selection_model is not None and selection_model.hasSelection()

    def _request_selected_removal(self):
        """Emit removal intent only when committed rows are selected."""
        if self.state() != EDITING_STATE and self._has_selected_rows():
            self.removeSelectedRequested.emit()

    def _prepare_context_selection(self, index):
        """Select an unselected right-clicked row and preserve existing groups."""
        if not index.isValid():
            return
        selection_model = self.selectionModel()
        if selection_model is None:
            return
        selected_rows = {selected.row() for selected in selection_model.selectedRows()}
        if index.row() not in selected_rows:
            row_index = self.model().index(index.row(), 0)
            flags = CLEAR_AND_SELECT | SELECT_ROWS_SELECTION | CURRENT_SELECTION
            selection_model.select(row_index, flags)
            selection_model.setCurrentIndex(row_index, CURRENT_SELECTION)
        self.setFocus()

    def _update_remove_action_enabled(self):
        """Project selection availability onto the context-menu action."""
        self.remove_action.setEnabled(self._has_selected_rows())

    def _show_context_menu(self, position):
        """Prepare the pointed row, then expose the shared Remove intent."""
        self._prepare_context_selection(self.indexAt(position))
        self._update_remove_action_enabled()
        menu = QtWidgets.QMenu(self)
        menu.addAction(self.remove_action)
        global_position = self.viewport().mapToGlobal(position)
        if hasattr(menu, "exec"):
            menu.exec(global_position)
        else:
            menu.exec_(global_position)

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

    def keyPressEvent(self, event):
        """Request row removal while preserving inline label editing keys."""
        if (
            event.key() in (KEY_DELETE, KEY_BACKSPACE)
            and self.state() != EDITING_STATE
            and self.selectionModel() is not None
            and self.selectionModel().hasSelection()
        ):
            self._request_selected_removal()
            event.accept()
            return
        super(CommittedTimeSeriesView, self).keyPressEvent(event)
