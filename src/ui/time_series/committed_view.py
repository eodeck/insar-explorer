"""Committed time-series table view interaction policy."""

from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import QEvent, pyqtSignal

from ...qt_compat import (
    QAction, CLEAR_AND_SELECT, CURRENT_SELECTION, CUSTOM_CONTEXT_MENU,
    CHECK_STATE_ROLE, CHECKED, UNCHECKED, LEFT_MOUSE_BUTTON,
    EDITING_STATE, KEY_BACKSPACE, KEY_DELETE, SELECT_ROWS_SELECTION,
    PALETTE_ACTIVE, PALETTE_HIGHLIGHT, PALETTE_HIGHLIGHTED_TEXT,
    PALETTE_INACTIVE,
)
from .committed_columns import CommittedTimeSeriesColumn
from .action_icons import (
    FIT_ACTION_ICON, REPLICA_ACTION_ICON, STYLE_ACTION_ICON,
)


class CommittedTimeSeriesView(QtWidgets.QTableView):
    """Own committed-list interaction presentation and emit typed intent only."""

    removeSelectedRequested = pyqtSignal()
    copySettingsRequested = pyqtSignal()
    pasteRequested = pyqtSignal(object)

    def __init__(self, parent=None):
        """Create an intent-only view with a shared removal context action."""
        super(CommittedTimeSeriesView, self).__init__(parent)
        self._selection_active = True
        self._applying_selection_palette = False
        self.remove_action = QAction(
            QtGui.QIcon(":/icons/icons/item_remove.svg"), "Remove", self
        )
        self.remove_action.setObjectName("action_remove_selected_time_series")
        self.remove_action.setToolTip("Remove selected time series")
        self.remove_action.setEnabled(False)
        self.remove_action.triggered.connect(self._request_selected_removal)
        from ...time_series.copy_paste import CopyPasteCategory
        self.copy_settings_action = QAction("Copy style, Fit and Replica", self)
        self.copy_settings_action.setObjectName("action_copy_time_series_settings")
        self.copy_settings_action.setToolTip(
            "Copy style, Fit and Replica from the selected time series"
        )
        self.copy_settings_action.triggered.connect(
            self.copySettingsRequested.emit
        )
        self.paste_actions = {}
        self._paste_menus = []
        labels = (
            (CopyPasteCategory.STYLE, "Style", STYLE_ACTION_ICON),
            (CopyPasteCategory.FIT, "Fit", FIT_ACTION_ICON),
            (CopyPasteCategory.REPLICA, "Replica", REPLICA_ACTION_ICON),
            (CopyPasteCategory.ALL_PRESENTATION, "Style, Fit and Replica", None),
        )
        for category, label, icon_path in labels:
            paste_action = (
                QAction(QtGui.QIcon(icon_path), label, self)
                if icon_path else QAction(label, self)
            )
            paste_action.setObjectName("action_paste_time_series_" + category.value)
            paste_action.triggered.connect(
                lambda checked=False, value=category: self.pasteRequested.emit(value)
            )
            self.paste_actions[category] = paste_action
        self.paste_menu = self._create_paste_menu(self)
        self.setContextMenuPolicy(CUSTOM_CONTEXT_MENU)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _create_paste_menu(self, parent):
        """Create a Paste container that reuses the shared leaf actions."""
        menu = QtWidgets.QMenu("Paste", parent)
        for action in self.paste_actions.values():
            menu.addAction(action)
        self._paste_menus.append(menu)
        return menu

    def create_copy_paste_menu(self, parent=None):
        """Return a menu using the existing Copy and Paste action registry."""
        menu = QtWidgets.QMenu(parent or self)
        menu.addAction(self.copy_settings_action)
        menu.addMenu(self._create_paste_menu(menu))
        return menu

    def set_selection_active(self, active):
        """Render selected rows as active or inactive without changing selection."""
        active = bool(active)
        self._selection_active = active
        native_palette = QtWidgets.QApplication.palette(self)
        palette = QtGui.QPalette(native_palette)
        if not active:
            palette.setColor(
                PALETTE_ACTIVE,
                PALETTE_HIGHLIGHT,
                native_palette.color(PALETTE_INACTIVE, PALETTE_HIGHLIGHT),
            )
            palette.setColor(
                PALETTE_ACTIVE,
                PALETTE_HIGHLIGHTED_TEXT,
                native_palette.color(
                    PALETTE_INACTIVE, PALETTE_HIGHLIGHTED_TEXT
                ),
            )
        self._applying_selection_palette = True
        try:
            self.setPalette(palette)
        finally:
            self._applying_selection_palette = False
        self.viewport().update()

    def selection_is_active(self):
        """Return the current selection-presentation mode for tests."""
        return self._selection_active

    def changeEvent(self, event):
        """Reapply palette-derived selection styling after theme changes."""
        super(CommittedTimeSeriesView, self).changeEvent(event)
        if getattr(self, "_applying_selection_palette", False):
            return
        event_type_enum = getattr(QEvent, "Type", QEvent)
        palette_events = tuple(
            getattr(event_type_enum, name)
            for name in ("PaletteChange", "ApplicationPaletteChange", "StyleChange")
        )
        if event.type() in palette_events:
            self.set_selection_active(self._selection_active)

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

    def set_copy_paste_enabled(self, *, copy_enabled, paste_categories=()):
        """Project controller-owned clipboard/selection availability onto actions."""
        available = set(paste_categories)
        self.copy_settings_action.setEnabled(bool(copy_enabled))
        for paste_menu in self._paste_menus:
            paste_menu.setEnabled(bool(available))
        for category, action in self.paste_actions.items():
            action.setEnabled(category in available)

    def _show_context_menu(self, position):
        """Prepare the pointed row, then expose committed-record commands."""
        self._prepare_context_selection(self.indexAt(position))
        self._update_remove_action_enabled()
        menu = QtWidgets.QMenu(self)
        menu.addAction(self.copy_settings_action)
        menu.addMenu(self.paste_menu)
        menu.addSeparator()
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
