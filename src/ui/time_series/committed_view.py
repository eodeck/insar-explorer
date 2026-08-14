"""Committed time-series table view interaction policy."""

from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import QEvent, QTimer, pyqtSignal

from ...qt_compat import (
    QAction, CLEAR_AND_SELECT, CURRENT_SELECTION, CUSTOM_CONTEXT_MENU,
    CHECK_STATE_ROLE, CHECKED, UNCHECKED, LEFT_MOUSE_BUTTON,
    EDITING_STATE, EVENT_KEY_PRESS, KEY_ENTER,
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
    assignDistinctColorsRequested = pyqtSignal()
    toggleSelectedVisibilityRequested = pyqtSignal()
    exportDataRequested = pyqtSignal()
    selectSourceLayerRequested = pyqtSignal()
    zoomMapToTargetRequested = pyqtSignal()
    zoomMapToReferenceRequested = pyqtSignal()
    actionStateRefreshRequested = pyqtSignal()

    def __init__(self, parent=None):
        """Create an intent-only view with a shared removal context action."""
        super(CommittedTimeSeriesView, self).__init__(parent)
        self._selection_active = True
        self._applying_selection_palette = False
        self._rename_record_id = None
        self._rename_editor = None
        self._restore_focus_after_rename = False
        self._select_source_layer_available = False
        self._zoom_target_available = False
        self._zoom_reference_available = False
        self.rename_action = QAction(QtGui.QIcon(":/icons/icons/rename.svg"), "Rename", self)
        self.rename_action.setObjectName("action_rename_selected_time_series")
        self.rename_action.setShortcut(QtGui.QKeySequence(KEY_F2))
        self.rename_action.setShortcutContext(WIDGET_SHORTCUT)
        self.rename_action.setToolTip("Rename the selected time series (F2)")
        self.rename_action.setStatusTip("Rename the selected time series (F2)")
        set_accessible_name = getattr(self.rename_action, "setAccessibleName", None)
        if callable(set_accessible_name):
            set_accessible_name("Rename selected time series")
        self.rename_action.setEnabled(False)
        self.rename_action.triggered.connect(self.begin_rename_selected_record)
        self.addAction(self.rename_action)
        self.remove_action = QAction(
            QtGui.QIcon(":/icons/icons/delete.svg"), "Remove", self
        )
        self.remove_action.setObjectName("action_remove_selected_time_series")
        self.remove_action.setToolTip("Remove selected time series")
        self.remove_action.setStatusTip("Remove selected time series")
        set_remove_accessible_name = getattr(
            self.remove_action, "setAccessibleName", None
        )
        if callable(set_remove_accessible_name):
            set_remove_accessible_name("Remove selected time series")
        self.remove_action.setEnabled(False)
        self.remove_action.triggered.connect(self._request_selected_removal)
        self.addAction(self.remove_action)
        self.export_action = QAction(
            QtGui.QIcon(":/icons/icons/export.svg"), "Export data", self
        )
        self.export_action.setObjectName("action_export_selected_time_series")
        self.export_action.setToolTip("Export selected time-series data")
        self.export_action.setStatusTip("Export selected time-series data")
        set_export_accessible_name = getattr(
            self.export_action, "setAccessibleName", None
        )
        if callable(set_export_accessible_name):
            set_export_accessible_name("Export selected time-series data")
        self.export_action.setEnabled(False)
        self.export_action.triggered.connect(self._request_selected_export)
        self.addAction(self.export_action)
        from ...time_series.copy_paste import CopyPasteCategory
        self.copy_settings_action = QAction(
            QtGui.QIcon(":/icons/icons/copy_content.svg"), "Copy settings", self
        )
        self.copy_settings_action.setObjectName("action_copy_time_series_settings")
        self.copy_settings_action.setToolTip(
            "Copy style, fit, and replica settings"
        )
        self.copy_settings_action.setStatusTip(
            "Copy style, fit, and replica settings"
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
        self.assign_distinct_colors_action = QAction(
            QtGui.QIcon(":/icons/icons/plot_random_color.svg"),
            "Assign distinct colors",
            self
        )
        self.assign_distinct_colors_action.setObjectName(
            "action_assign_distinct_colors_time_series"
        )
        self.assign_distinct_colors_action.setToolTip(
            "Assign distinct colors to the selected time series"
        )
        self.assign_distinct_colors_action.setStatusTip(
            "Assign distinct colors to the selected time series"
        )
        set_distinct_accessible_name = getattr(
            self.assign_distinct_colors_action, "setAccessibleName", None
        )
        if callable(set_distinct_accessible_name):
            set_distinct_accessible_name(
                "Assign distinct colors to selected time series"
            )
        self.assign_distinct_colors_action.setEnabled(False)
        self.assign_distinct_colors_action.triggered.connect(
            self.assignDistinctColorsRequested.emit
        )
        self.select_source_layer_action = QAction(
            QtGui.QIcon(":/icons/icons/layers.svg"), "Select source in Layers", self)
        self.select_source_layer_action.setObjectName(
            "action_select_time_series_source_layer"
        )
        source_layer_tip = (
            "Select the layer this time series came from in the QGIS Layers panel"
        )
        self.select_source_layer_action.setToolTip(source_layer_tip)
        self.select_source_layer_action.setStatusTip(source_layer_tip)
        set_source_accessible_name = getattr(
            self.select_source_layer_action, "setAccessibleName", None
        )
        if callable(set_source_accessible_name):
            set_source_accessible_name(
                "Select source layer in QGIS Layers panel"
            )
        self.select_source_layer_action.setEnabled(False)
        self.select_source_layer_action.triggered.connect(
            self.selectSourceLayerRequested.emit
        )
        self.zoom_map_to_target_action = QAction(
            QtGui.QIcon(":/icons/icons/zoom.svg"), "Zoom map to target", self
        )
        self.zoom_map_to_target_action.setObjectName("action_zoom_map_to_time_series_target")
        target_tip = "Center the QGIS map on this time series target"
        self.zoom_map_to_target_action.setToolTip(target_tip)
        self.zoom_map_to_target_action.setStatusTip(target_tip)
        self.zoom_map_to_target_action.setEnabled(False)
        self.zoom_map_to_target_action.triggered.connect(
            self.zoomMapToTargetRequested.emit
        )
        self.zoom_map_to_reference_action = QAction(
            QtGui.QIcon(":/icons/icons/zoom.svg"), "Zoom map to reference", self
        )
        self.zoom_map_to_reference_action.setObjectName(
            "action_zoom_map_to_time_series_reference"
        )
        reference_tip = "Center the QGIS map on this time series reference"
        self.zoom_map_to_reference_action.setToolTip(reference_tip)
        self.zoom_map_to_reference_action.setStatusTip(reference_tip)
        self.zoom_map_to_reference_action.setEnabled(False)
        self.zoom_map_to_reference_action.triggered.connect(
            self.zoomMapToReferenceRequested.emit
        )
        self.setContextMenuPolicy(CUSTOM_CONTEXT_MENU)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _create_paste_menu(self, parent):
        """Create a Paste container that reuses the shared leaf actions."""
        menu = QtWidgets.QMenu("Paste settings", parent)
        menu.setIcon(QtGui.QIcon(":/icons/icons/clipboard.svg"))
        paste_tip = "Apply copied style, fit, and replica settings"
        menu.menuAction().setToolTip(paste_tip)
        menu.menuAction().setStatusTip(paste_tip)
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
        """Refresh shared action state after rename-related changes."""
        self.refresh_action_enabled_states()

    def setModel(self, model):
        """Bind selection-driven Rename enablement to each installed model."""
        old_selection_model = self.selectionModel()
        if old_selection_model is not None:
            try:
                old_selection_model.selectionChanged.disconnect(
                    self.refresh_action_enabled_states
                )
            except (TypeError, RuntimeError):
                pass
        super(CommittedTimeSeriesView, self).setModel(model)
        self._select_source_layer_available = False
        self._zoom_target_available = False
        self._zoom_reference_available = False
        selection_model = self.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(
                self.refresh_action_enabled_states
            )
        self.refresh_action_enabled_states()

    def refresh_action_enabled_states(self, *unused):
        """Refresh shared Rename and Remove actions from view state."""
        editing = self.state() == EDITING_STATE
        selected_ids = self._selected_record_ids()
        self.rename_action.setEnabled(not editing and len(selected_ids) == 1)
        self.remove_action.setEnabled(not editing and bool(selected_ids))
        self.export_action.setEnabled(not editing and bool(selected_ids))
        self.assign_distinct_colors_action.setEnabled(
            not editing and len(selected_ids) >= 2
        )
        single = not editing and len(selected_ids) == 1
        self.select_source_layer_action.setEnabled(
            single and self._select_source_layer_available
        )
        self.zoom_map_to_target_action.setEnabled(
            single and self._zoom_target_available
        )
        self.zoom_map_to_reference_action.setEnabled(
            single and self._zoom_reference_available
        )

    def set_select_source_layer_enabled(self, enabled):
        """Project controller-owned source-layer availability onto the action."""
        self._select_source_layer_available = bool(enabled)
        self.refresh_action_enabled_states()

    def set_map_navigation_enabled(self, *, target_enabled, reference_enabled):
        """Project record-owned target/reference navigation availability."""
        self._zoom_target_available = bool(target_enabled)
        self._zoom_reference_available = bool(reference_enabled)
        self.refresh_action_enabled_states()

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

    def _request_selected_export(self):
        """Emit export intent when one or more committed UUIDs are selected."""
        if self.state() != EDITING_STATE and self._selected_record_ids():
            self.exportDataRequested.emit()

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
        """Refresh shared action state before exposing row commands."""
        self.refresh_action_enabled_states()

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
        self.actionStateRefreshRequested.emit()
        menu = QtWidgets.QMenu(self)
        menu.addAction(self.copy_settings_action)
        menu.addMenu(self.paste_menu)
        menu.addAction(self.export_action)
        menu.addAction(self.assign_distinct_colors_action)
        menu.addSeparator()
        menu.addAction(self.rename_action)
        menu.addSeparator()
        menu.addAction(self.select_source_layer_action)
        menu.addAction(self.zoom_map_to_target_action)
        menu.addAction(self.zoom_map_to_reference_action)
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
        """Handle local committed-row keyboard commands outside active editors."""
        if (
            event.key() == KEY_SPACE
            and self.state() != EDITING_STATE
            and self._has_selected_rows()
        ):
            self.toggleSelectedVisibilityRequested.emit()
            event.accept()
            return
        super(CommittedTimeSeriesView, self).keyPressEvent(event)
