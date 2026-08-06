"""Committed time-series table view interaction policy."""

from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import QEvent, QTimer, pyqtSignal

from ...qt_compat import (
    QAction, CLEAR_AND_SELECT, CURRENT_SELECTION, CUSTOM_CONTEXT_MENU,
    CHECK_STATE_ROLE, CHECKED, UNCHECKED, LEFT_MOUSE_BUTTON,
    EDITING_STATE, EVENT_KEY_PRESS, KEY_BACKSPACE, KEY_DELETE, KEY_ENTER,
    KEY_ESCAPE, KEY_F2, KEY_RETURN, KEY_SPACE, NO_UPDATE_CURRENT,
    SELECT_ROWS_SELECTION, WIDGET_SHORTCUT,
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
    toggleSelectedVisibilityRequested = pyqtSignal()

    def __init__(self, parent=None):
        """Create an intent-only view with a shared removal context action."""
        super(CommittedTimeSeriesView, self).__init__(parent)
        self._selection_active = True
        self._applying_selection_palette = False
        self._rename_record_id = None
        self._rename_editor = None
        self._restore_focus_after_rename = False
        self.rename_action = QAction("Rename", self)
        self.rename_action.setObjectName("action_rename_selected_time_series")
        self.rename_action.setShortcut(QtGui.QKeySequence(KEY_F2))
        self.rename_action.setShortcutContext(WIDGET_SHORTCUT)
        self.rename_action.setToolTip("Rename the selected time series")
        self.rename_action.setStatusTip("Rename the selected time series")
        set_accessible_name = getattr(self.rename_action, "setAccessibleName", None)
        if callable(set_accessible_name):
            set_accessible_name("Rename selected time series")
        self.rename_action.setEnabled(False)
        self.rename_action.triggered.connect(self.begin_rename_selected_record)
        self.addAction(self.rename_action)
        self.remove_action = QAction(
            QtGui.QIcon(":/icons/icons/item_remove.svg"), "Remove", self
        )
        self.remove_action.setObjectName("action_remove_selected_time_series")
        self.remove_action.setToolTip("Remove selected time series")
        self.remove_action.setEnabled(False)
        self.remove_action.triggered.connect(self._request_selected_removal)
        from ...time_series.copy_paste import CopyPasteCategory
        self.copy_settings_action = QAction("Copy Style, Fit and Replica", self)
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

    def _selected_record_ids(self):
        """Return selected committed UUIDs through the model identity API."""
        model = self.model()
        selection_model = self.selectionModel()
        if model is None or selection_model is None:
            return ()
        return tuple(
            record_id for record_id in (
                model.record_id_at(index.row())
                for index in selection_model.selectedRows()
            ) if record_id is not None
        )

    def _update_rename_action_enabled(self, *unused):
        """Enable Rename only for exactly one selected committed UUID."""
        self.rename_action.setEnabled(
            self.state() != EDITING_STATE and len(self._selected_record_ids()) == 1
        )

    def setModel(self, model):
        """Bind selection-driven Rename enablement to each installed model."""
        old_selection_model = self.selectionModel()
        if old_selection_model is not None:
            try:
                old_selection_model.selectionChanged.disconnect(
                    self._update_rename_action_enabled
                )
            except (TypeError, RuntimeError):
                pass
        super(CommittedTimeSeriesView, self).setModel(model)
        selection_model = self.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(
                self._update_rename_action_enabled
            )
        self._update_rename_action_enabled()

    def begin_rename_selected_record(self):
        """Start inline label editing for the single selected committed record."""
        if self.state() == EDITING_STATE:
            return False
        selected_ids = self._selected_record_ids()
        model = self.model()
        selection_model = self.selectionModel()
        if len(selected_ids) != 1 or model is None or selection_model is None:
            self._update_rename_action_enabled()
            return False
        record_id = selected_ids[0]
        row = model.row_for_id(record_id)
        if row is None:
            self._update_rename_action_enabled()
            return False
        index = model.index(row, CommittedTimeSeriesColumn.LABEL)
        if not index.isValid():
            return False
        self._rename_record_id = record_id
        self._restore_focus_after_rename = False
        selection_model.setCurrentIndex(index, NO_UPDATE_CURRENT)
        self.edit(index)
        if self.state() != EDITING_STATE:
            self._rename_record_id = None
            self._update_rename_action_enabled()
            return False
        QTimer.singleShot(0, self._select_active_editor_text)
        self._update_rename_action_enabled()
        return True

    def _select_active_editor_text(self):
        """Select label text and observe keyboard-driven editor completion."""
        editor = self.findChild(QtWidgets.QLineEdit)
        if editor is not None and editor.isVisible():
            self._rename_editor = editor
            editor.installEventFilter(self)
            editor.selectAll()

    def eventFilter(self, watched, event):
        """Remember whether Enter or Escape is closing the active rename editor."""
        if watched is self._rename_editor and event.type() == EVENT_KEY_PRESS:
            if event.key() in (KEY_RETURN, KEY_ENTER, KEY_ESCAPE):
                self._restore_focus_after_rename = True
        return super(CommittedTimeSeriesView, self).eventFilter(watched, event)

    def _restore_current_record(self, record_id):
        """Restore one committed UUID as current without changing selection."""
        model = self.model()
        selection_model = self.selectionModel()
        if model is None or selection_model is None:
            return
        row = model.row_for_id(record_id)
        if row is None:
            return
        index = model.index(row, CommittedTimeSeriesColumn.LABEL)
        if index.isValid():
            selection_model.setCurrentIndex(index, NO_UPDATE_CURRENT)

    def closeEditor(self, editor, hint):
        """Close rename editing and restore predictable list navigation state."""
        record_id = self._rename_record_id
        restore_focus = self._restore_focus_after_rename
        if editor is self._rename_editor:
            editor.removeEventFilter(self)
        self._rename_editor = None
        super(CommittedTimeSeriesView, self).closeEditor(editor, hint)
        if record_id is not None:
            self._restore_current_record(record_id)
        self._rename_record_id = None
        self._restore_focus_after_rename = False
        if restore_focus:
            self.setFocus()
        self._update_rename_action_enabled()

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
        self._update_rename_action_enabled()

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
        menu.addAction(self.rename_action)
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
        """Handle local committed-row keyboard commands outside active editors."""
        if (
            event.key() == KEY_SPACE
            and self.state() != EDITING_STATE
            and self._has_selected_rows()
        ):
            self.toggleSelectedVisibilityRequested.emit()
            event.accept()
            return
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
