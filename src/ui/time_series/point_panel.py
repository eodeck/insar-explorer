"""Dedicated time-series point panel for selection controls and future records."""

from dataclasses import dataclass
from typing import Optional, Tuple
from uuid import UUID

from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import QEvent, QSize, pyqtSignal

from ...qt_compat import (
    ALIGN_LEFT,
    ALIGN_VCENTER,
    SIZE_POLICY_EXPANDING,
    SIZE_POLICY_FIXED,
    SIZE_POLICY_PREFERRED,
    EDIT_DOUBLE_CLICKED,
    EDIT_KEY_PRESSED,
    EDIT_SELECTED_CLICKED,
    NO_EDIT_TRIGGERS,
    HEADER_FIXED,
    HEADER_STRETCH,
    NO_CONTEXT_MENU,
    NO_DRAG_DROP,
    NO_SELECTION,
    EXTENDED_SELECTION,
    SELECT_ROWS,
    SCROLL_BAR_ALWAYS_OFF,
    NO_UPDATE_CURRENT,
    SELECT_ROWS_SELECTION,
    SELECT_SELECTION,
    TOOL_BUTTON_INSTANT_POPUP,
    TOOL_BUTTON_ICON_ONLY,
    configure_compact_command_button,
)

from .committed_columns import (
    COMMITTED_SEQUENCE_COLUMN_WIDTH, COMMITTED_VISIBLE_COLUMN_WIDTH,
    CommittedTimeSeriesColumn,
)
from .committed_model import CommittedTimeSeriesModel
from .committed_view import CommittedTimeSeriesView
from .visibility_header import TimeSeriesVisibilityHeader

from .columns import (
    PENDING_ROW_HEIGHT,
    TimeSeriesColumn,
)

from .presentation import (
    TIME_SERIES_ACTION_BUTTON_SIZE,
    TIME_SERIES_ACTION_ICON_SIZE,
    TIME_SERIES_ROW_HEIGHT,
    TIME_SERIES_TYPE_COLUMN_WIDTH,
    TIME_SERIES_TYPE_ICON_SIZE,
)

from .pending_label_delegate import PendingLabelDelegate
from .pending_model import PendingTimeSeriesModel
from .type_indicator_delegate import TimeSeriesTypeIndicatorDelegate


@dataclass(frozen=True)
class CommittedSelectionSnapshot:
    """UUID-based committed selection, current row, and viewport position."""

    selected_record_ids: Tuple[UUID, ...]
    current_record_id: Optional[UUID]
    vertical_scroll: int
    horizontal_scroll: int


PENDING_ACTION_ICONS = {
    "add": ":/icons/icons/item_add.svg",
    "discard": ":/icons/icons/item_discard.svg",
}


def configure_time_series_action_button(
    button, *, icon, tooltip, accessible_name
):
    """Apply the shared compact time-series action-button presentation."""
    button.setText("")
    button.setIcon(QtGui.QIcon(icon))
    button.setToolTip(tooltip)
    button.setAccessibleName(accessible_name)
    configure_compact_command_button(
        button,
        size=TIME_SERIES_ACTION_BUTTON_SIZE,
        icon_size=TIME_SERIES_ACTION_ICON_SIZE,
    )
    return button


class TimeSeriesPointPanel(QtWidgets.QWidget):
    """Own selection controls, pending preview controls, and future list space."""

    addPendingRequested = pyqtSignal()
    discardPendingRequested = pyqtSignal()
    pendingLabelEdited = pyqtSignal(str)
    committedVisibilityEdited = pyqtSignal(object, bool)
    toggleSelectedCommittedVisibilityRequested = pyqtSignal()
    committedLabelEdited = pyqtSignal(object, str)
    committedSelectionChanged = pyqtSignal(tuple)
    committedVisibilityAllRequested = pyqtSignal(bool)
    removeSelectedCommittedRequested = pyqtSignal()
    copyCommittedSettingsRequested = pyqtSignal()
    pasteCommittedRequested = pyqtSignal(object)
    assignDistinctColorsRequested = pyqtSignal()
    indicatorSettingsRequested = pyqtSignal()

    ICON_SIZE = 18
    BUTTON_SIZE = 26
    MINIMUM_WIDTH = 190
    PREFERRED_WIDTH = 215
    MAXIMUM_WIDTH = 240
    HOVER_STYLE = "QPushButton:hover {\n    border: 1px solid #bbb;\n}\n"
    SUBGROUP_TEXT_EMPHASIS = 0.76
    PLACEHOLDER_TEXT_EMPHASIS = 0.62
    _BUTTON_METADATA = (
        ("pb_choose_point", ":/icons/icons/select_point.svg", True, True,
         "Select a time-series point on the map", "Select time-series point"),
        ("pb_choose_polygon", ":/icons/icons/polygon_selection.png", True, True,
         "Select time-series points within a polygon", "Select time-series polygon"),
        ("pb_set_reference", ":/icons/icons/select_select_reference.svg", True, True,
         "Select a reference point on the map", "Select reference point"),
        ("pb_set_reference_polygon", ":/icons/icons/polygon_reference_selection.png", True, True,
         "Select reference points within a polygon", "Select reference polygon"),
        ("pb_reset_reference", ":/icons/icons/select_reset_reference.svg", False, False,
         "Reset the active reference selection", "Reset reference"),
    )

    def __init__(self, parent=None):
        """Create the panel and baseline-compatible selection controls."""
        super(TimeSeriesPointPanel, self).__init__(parent)
        self.setObjectName("time_series_point_panel")
        self.setMinimumWidth(self.MINIMUM_WIDTH)
        self.setMaximumWidth(self.MAXIMUM_WIDTH)
        self.setSizePolicy(SIZE_POLICY_PREFERRED, SIZE_POLICY_EXPANDING)

        self._buttons = self._create_buttons()
        self._configure_buttons()
        self._build_layout()
        self._configure_tab_order()
        self._refresh_secondary_text_palettes()

    @property
    def selection_buttons(self):
        """Return selection buttons in keyboard-navigation order."""
        return tuple(self._buttons[name] for name, *_ in self._BUTTON_METADATA)

    def sizeHint(self):
        """Prefer a compact panel while allowing the plot to dominate."""
        hint = super(TimeSeriesPointPanel, self).sizeHint()
        hint.setWidth(self.PREFERRED_WIDTH)
        return hint

    def _create_buttons(self):
        buttons = {}
        for name, icon_path, checkable, flat, _, _ in self._BUTTON_METADATA:
            button = QtWidgets.QPushButton(self)
            button.setObjectName(name)
            button.setIcon(QtGui.QIcon(icon_path))
            button.setCheckable(checkable)
            button.setFlat(flat)
            buttons[name] = button
        return buttons

    def _configure_buttons(self):
        for name, _, _, flat, tooltip, accessible_name in self._BUTTON_METADATA:
            button = self._buttons[name]
            button.setText("")
            button.setToolTip(tooltip)
            button.setAccessibleName(accessible_name)
            button.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
            button.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
            button.setSizePolicy(SIZE_POLICY_FIXED, SIZE_POLICY_FIXED)
            if flat:
                button.setStyleSheet(self.HOVER_STYLE)

    def _build_layout(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 8)
        layout.setSpacing(5)

        header_grid = QtWidgets.QGridLayout()
        header_grid.setObjectName("time_series_selection_header_layout")
        header_grid.setContentsMargins(0, 0, 0, 0)
        header_grid.setHorizontalSpacing(3)
        header_grid.setVerticalSpacing(2)

        self.target_label = self._secondary_label("Target", "label_target")
        self.reference_label = self._secondary_label("Reference", "label_reference")
        header_grid.addWidget(self.target_label, 0, 0, 1, 2, ALIGN_LEFT | ALIGN_VCENTER)
        header_grid.addWidget(self.reference_label, 0, 3, 1, 3, ALIGN_LEFT | ALIGN_VCENTER)

        header_grid.addWidget(self._buttons["pb_choose_point"], 1, 0)
        header_grid.addWidget(self._buttons["pb_choose_polygon"], 1, 1)
        header_grid.addWidget(
            self._separator(vertical=True, object_name="selection_group_separator"),
            1,
            2,
        )
        header_grid.addWidget(self._buttons["pb_set_reference"], 1, 3)
        header_grid.addWidget(self._buttons["pb_set_reference_polygon"], 1, 4)
        header_grid.addWidget(self._buttons["pb_reset_reference"], 1, 5)
        header_grid.setColumnStretch(6, 1)
        layout.addLayout(header_grid)

        self.selection_pending_separator = self._separator(
            vertical=False, object_name="selection_pending_separator"
        )
        layout.addWidget(self.selection_pending_separator)

        self.pending_model = PendingTimeSeriesModel(self)
        self.pending_model.labelEdited.connect(self.pendingLabelEdited.emit)
        self.pending_view = QtWidgets.QTableView(self)
        self.pending_view.setObjectName("pending_time_series_view")
        self.pending_view.setAccessibleDescription("Current pending time series")
        self.pending_view.setModel(self.pending_model)
        self.pending_view.setIconSize(
            QSize(TIME_SERIES_TYPE_ICON_SIZE, TIME_SERIES_TYPE_ICON_SIZE)
        )
        pending_font = self.pending_view.font()
        if pending_font.pointSizeF() > 0:
            pending_font.setPointSizeF(max(pending_font.pointSizeF() - 1.0, 8.0))
            self.pending_view.setFont(pending_font)
        self.pending_view.setSelectionMode(NO_SELECTION)
        self.pending_view.setMouseTracking(True)
        self.pending_view.viewport().setMouseTracking(True)
        self.pending_view.setEditTriggers(
            EDIT_DOUBLE_CLICKED | EDIT_SELECTED_CLICKED | EDIT_KEY_PRESSED
        )
        self.pending_view.setSortingEnabled(False)
        self.pending_view.setDragDropMode(NO_DRAG_DROP)
        self.pending_view.setDragEnabled(False)
        self.pending_view.setAcceptDrops(False)
        self.pending_view.setContextMenuPolicy(NO_CONTEXT_MENU)
        self.pending_view.setHorizontalScrollBarPolicy(SCROLL_BAR_ALWAYS_OFF)
        self.pending_view.setVerticalScrollBarPolicy(SCROLL_BAR_ALWAYS_OFF)
        self.pending_view.setShowGrid(False)
        self.pending_view.setStyleSheet(
            "QTableView#pending_time_series_view {"
            " border: none;"
            " border-bottom: 1px solid palette(mid);"
            " background: transparent;"
            "}"
            "QTableView#pending_time_series_view::item {"
            " border: none;"
            "}"
        )
        self.pending_view.verticalHeader().hide()
        self.pending_view.horizontalHeader().hide()
        self.pending_view.verticalHeader().setDefaultSectionSize(PENDING_ROW_HEIGHT)
        header = self.pending_view.horizontalHeader()
        header.setSectionResizeMode(TimeSeriesColumn.LABEL, HEADER_STRETCH)
        header.setSectionResizeMode(TimeSeriesColumn.TARGET, HEADER_FIXED)
        header.setSectionResizeMode(TimeSeriesColumn.REFERENCE, HEADER_FIXED)
        self.pending_view.setColumnWidth(
            TimeSeriesColumn.TARGET, TIME_SERIES_TYPE_COLUMN_WIDTH
        )
        self.pending_view.setColumnWidth(
            TimeSeriesColumn.REFERENCE, TIME_SERIES_TYPE_COLUMN_WIDTH
        )
        self.pending_label_delegate = PendingLabelDelegate(self.pending_view)
        self.pending_view.setItemDelegateForColumn(
            TimeSeriesColumn.LABEL, self.pending_label_delegate
        )
        self.pending_type_indicator_delegate = TimeSeriesTypeIndicatorDelegate(
            self.pending_view
        )
        self.pending_view.setItemDelegateForColumn(
            TimeSeriesColumn.TARGET, self.pending_type_indicator_delegate
        )
        self.pending_view.setItemDelegateForColumn(
            TimeSeriesColumn.REFERENCE, self.pending_type_indicator_delegate
        )
        self.pending_view.setFixedHeight(PENDING_ROW_HEIGHT + 1)
        self.pending_view.setSizePolicy(SIZE_POLICY_EXPANDING, SIZE_POLICY_FIXED)

        pending_actions = QtWidgets.QHBoxLayout()
        pending_actions.setObjectName("pending_time_series_actions_layout")
        pending_actions.setContentsMargins(0, 0, 0, 0)
        pending_actions.setSpacing(3)
        pending_actions.addWidget(self.pending_view, 1)

        self.pending_add_button = self._pending_action_button(
            "pb_add_pending",
            PENDING_ACTION_ICONS["add"],
            "Add the pending time series",
            "Add pending time series",
        )
        self.pending_add_button.clicked.connect(self.addPendingRequested)
        pending_actions.addWidget(self.pending_add_button, 0, ALIGN_VCENTER)

        self.pending_discard_button = self._pending_action_button(
            "pb_discard_pending",
            PENDING_ACTION_ICONS["discard"],
            "Discard the pending time series",
            "Discard pending time series",
        )
        self.pending_discard_button.clicked.connect(self.discardPendingRequested)
        pending_actions.addWidget(self.pending_discard_button, 0, ALIGN_VCENTER)
        layout.addLayout(pending_actions)
        self.clear_pending()

        self.committed_model = None
        self.committed_view = CommittedTimeSeriesView(self)
        self.committed_view.setObjectName("committed_time_series_view")
        self.committed_view.setAccessibleDescription(
            "Committed selection is retained while a pending time series is active"
        )
        self.committed_view.setSelectionBehavior(SELECT_ROWS)
        self.committed_view.setSelectionMode(EXTENDED_SELECTION)
        self.committed_view.setEditTriggers(NO_EDIT_TRIGGERS)
        self.committed_view.setSortingEnabled(False)
        self.committed_view.setDragDropMode(NO_DRAG_DROP)
        self.committed_view.setDragEnabled(False)
        self.committed_view.setAcceptDrops(False)
        self.committed_view.setShowGrid(False)
        self.committed_view.verticalHeader().hide()
        self.committed_view.verticalHeader().setDefaultSectionSize(TIME_SERIES_ROW_HEIGHT)
        self.committed_view.setIconSize(
            QSize(TIME_SERIES_TYPE_ICON_SIZE, TIME_SERIES_TYPE_ICON_SIZE)
        )
        self.committed_header = TimeSeriesVisibilityHeader(
            self.committed_view.horizontalHeader().orientation(), self.committed_view
        )
        self.committed_view.setHorizontalHeader(self.committed_header)
        self.committed_header.toggleAllRequested.connect(
            self.committedVisibilityAllRequested.emit
        )
        self.committed_label_delegate = PendingLabelDelegate(self.committed_view)
        self.committed_type_indicator_delegate = TimeSeriesTypeIndicatorDelegate(
            self.committed_view
        )
        self.committed_view.setSizePolicy(SIZE_POLICY_EXPANDING, SIZE_POLICY_EXPANDING)
        layout.addWidget(self.committed_view, 1)

        removal_actions = QtWidgets.QHBoxLayout()
        removal_actions.setObjectName("committed_time_series_actions_layout")
        removal_actions.setContentsMargins(0, 0, 0, 0)
        removal_actions.setSpacing(3)
        self.copy_paste_button = QtWidgets.QToolButton(self)
        self.copy_paste_button.setObjectName("tb_copy_paste_time_series")
        configure_time_series_action_button(
            self.copy_paste_button,
            icon=":/icons/icons/clipboard.svg",
            tooltip="Copy or paste time-series settings",
            accessible_name="Copy and paste time-series settings",
        )
        self.copy_paste_button.setToolButtonStyle(TOOL_BUTTON_ICON_ONLY)
        self.copy_paste_button.setPopupMode(TOOL_BUTTON_INSTANT_POPUP)
        self.copy_paste_button.setMenu(
            self.committed_view.create_copy_paste_menu(self.copy_paste_button)
        )
        removal_actions.addWidget(self.copy_paste_button, 0, ALIGN_VCENTER)
        self.remove_selected_button = self._pending_action_button(
            "pb_remove_selected_time_series",
            ":/icons/icons/item_remove.svg",
            "Remove selected time series",
            "Remove selected time series",
        )
        self.remove_selected_button.clicked.connect(
            self.committed_view.remove_action.trigger
        )
        self.committed_view.remove_action.changed.connect(
            self._sync_remove_button_enabled
        )
        removal_actions.addWidget(
            self.remove_selected_button, 0, ALIGN_VCENTER
        )
        removal_actions.addStretch(1)
        self.indicator_settings_button = QtWidgets.QToolButton(self)
        self.indicator_settings_button.setObjectName(
            "tb_time_series_indicator_settings"
        )
        configure_time_series_action_button(
            self.indicator_settings_button,
            icon=":/icons/icons/setting.svg",
            tooltip="Configure target and reference map indicators",
            accessible_name="Target and reference indicator settings",
        )
        self.indicator_settings_button.setToolButtonStyle(TOOL_BUTTON_ICON_ONLY)
        self.indicator_settings_button.clicked.connect(self.indicatorSettingsRequested.emit)
        removal_actions.addWidget(self.indicator_settings_button, 0, ALIGN_VCENTER)
        layout.addLayout(removal_actions)
        self.committed_view.removeSelectedRequested.connect(
            self.removeSelectedCommittedRequested.emit
        )
        self.committed_view.copySettingsRequested.connect(
            self.copyCommittedSettingsRequested.emit
        )
        self.committed_view.pasteRequested.connect(self.pasteCommittedRequested.emit)
        self.committed_view.assignDistinctColorsRequested.connect(
            self.assignDistinctColorsRequested.emit
        )
        self.committed_view.toggleSelectedVisibilityRequested.connect(
            self.toggleSelectedCommittedVisibilityRequested.emit
        )
        self._clipboard_categories = ()
        self.refresh_removal_actions()

    def configure_committed_list(self, list_state, record_provider):
        """Bind the committed projection to authoritative state providers."""
        if self.committed_model is not None:
            return self.committed_model
        self.committed_model = CommittedTimeSeriesModel(
            list_state, record_provider, self.committed_view
        )
        self.committed_view.setModel(self.committed_model)
        self.committed_model.visibilityEdited.connect(
            self.committedVisibilityEdited.emit
        )
        self.committed_model.labelEdited.connect(self.committedLabelEdited.emit)
        selection_model = self.committed_view.selectionModel()
        selection_model.selectionChanged.connect(self._emit_committed_selection)
        header = self.committed_view.horizontalHeader()
        header.setSectionResizeMode(CommittedTimeSeriesColumn.VISIBLE, HEADER_FIXED)
        header.setSectionResizeMode(CommittedTimeSeriesColumn.SEQUENCE, HEADER_FIXED)
        header.setSectionResizeMode(CommittedTimeSeriesColumn.LABEL, HEADER_STRETCH)
        header.setSectionResizeMode(CommittedTimeSeriesColumn.TARGET, HEADER_FIXED)
        header.setSectionResizeMode(CommittedTimeSeriesColumn.REFERENCE, HEADER_FIXED)
        self.committed_view.setColumnWidth(
            CommittedTimeSeriesColumn.VISIBLE, COMMITTED_VISIBLE_COLUMN_WIDTH
        )
        self.committed_view.setColumnWidth(
            CommittedTimeSeriesColumn.SEQUENCE, COMMITTED_SEQUENCE_COLUMN_WIDTH
        )
        for column in (
            CommittedTimeSeriesColumn.TARGET,
            CommittedTimeSeriesColumn.REFERENCE,
        ):
            self.committed_view.setColumnWidth(column, TIME_SERIES_TYPE_COLUMN_WIDTH)
            self.committed_view.setItemDelegateForColumn(
                column, self.committed_type_indicator_delegate
            )
        self.committed_view.setItemDelegateForColumn(
            CommittedTimeSeriesColumn.LABEL, self.committed_label_delegate
        )
        self.refresh_committed_visibility_header()
        self.refresh_removal_actions()
        return self.committed_model

    def selected_committed_ids(self):
        """Return selected committed UUIDs without using row identity."""
        if self.committed_model is None or self.committed_view.selectionModel() is None:
            return ()
        rows = self.committed_view.selectionModel().selectedRows()
        return tuple(
            record_id for record_id in (
                self.committed_model.record_id_at(index.row()) for index in rows
            ) if record_id is not None
        )

    def select_committed_record(self, record_id):
        """Select one committed row by UUID."""
        if self.committed_model is None:
            return False
        row = self.committed_model.row_for_id(record_id)
        if row is None:
            return False
        self.committed_view.clearSelection()
        self.committed_view.selectRow(row)
        self.committed_view.scrollTo(self.committed_model.index(row, 0))
        return True

    def refresh_committed_visibility_header(self):
        """Project checked, unchecked, or partial aggregate visibility."""
        from ...qt_compat import CHECKED, PARTIALLY_CHECKED, UNCHECKED
        total, visible_count = (0, 0) if self.committed_model is None else self.committed_model.visibility_summary()
        if total == 0 or visible_count == 0:
            state = UNCHECKED
        elif visible_count == total:
            state = CHECKED
        else:
            state = PARTIALLY_CHECKED
        self.committed_header.set_visibility_state(state, bool(total))

    def refresh_committed_model(self):
        """Refresh the projection while preserving selected UUIDs."""
        if self.committed_model is None:
            return
        selected = self.selected_committed_ids()
        self.committed_model.refresh()
        self.restore_committed_selection(selected)
        self.refresh_committed_visibility_header()
        self.refresh_removal_actions()

    def capture_committed_selection(self):
        """Capture UUID selection/current state and viewport position atomically."""
        current_id = None
        current_index = self.committed_view.currentIndex()
        if current_index.isValid() and self.committed_model is not None:
            current_id = self.committed_model.record_id_at(current_index.row())
        return CommittedSelectionSnapshot(
            selected_record_ids=self.selected_committed_ids(),
            current_record_id=current_id,
            vertical_scroll=self.committed_view.verticalScrollBar().value(),
            horizontal_scroll=self.committed_view.horizontalScrollBar().value(),
        )

    def restore_committed_selection(
        self, record_ids, current_record_id=None, vertical_scroll=None,
        horizontal_scroll=None,
    ):
        """Restore UUID selection/current/scroll without changing selection via current."""
        if self.committed_model is None or self.committed_view.selectionModel() is None:
            return
        selection_model = self.committed_view.selectionModel()
        selection_model.clearSelection()
        for record_id in record_ids:
            row = self.committed_model.row_for_id(record_id)
            if row is not None:
                index = self.committed_model.index(row, 0)
                selection_model.select(
                    index, SELECT_SELECTION | SELECT_ROWS_SELECTION
                )
        if current_record_id is not None:
            current_row = self.committed_model.row_for_id(current_record_id)
            if current_row is not None:
                selection_model.setCurrentIndex(
                    self.committed_model.index(current_row, 0), NO_UPDATE_CURRENT
                )
        if vertical_scroll is not None:
            self.committed_view.verticalScrollBar().setValue(vertical_scroll)
        if horizontal_scroll is not None:
            self.committed_view.horizontalScrollBar().setValue(horizontal_scroll)

    def selected_committed_rows(self):
        """Return selected model row numbers in ascending order."""
        if self.committed_view.selectionModel() is None:
            return ()
        return tuple(sorted(index.row() for index in self.committed_view.selectionModel().selectedRows()))

    def set_clipboard_categories(self, categories):
        """Project session clipboard availability without owning clipboard state."""
        self._clipboard_categories = tuple(categories)
        self.refresh_removal_actions()

    def _sync_remove_button_enabled(self):
        """Mirror the shared Remove action state onto the bottom button."""
        self.remove_selected_button.setEnabled(
            self.committed_view.remove_action.isEnabled()
        )

    def refresh_removal_actions(self):
        """Enable committed-list commands from selection and clipboard projection."""
        selected_ids = self.selected_committed_ids()
        selected = bool(selected_ids)
        committed_count = (
            0 if self.committed_model is None else self.committed_model.rowCount()
        )
        self.copy_paste_button.setEnabled(committed_count > 0)
        self.committed_view.refresh_action_enabled_states()
        self.remove_selected_button.setEnabled(
            self.committed_view.remove_action.isEnabled()
        )
        self.committed_view.set_copy_paste_enabled(
            copy_enabled=len(selected_ids) == 1,
            paste_categories=self._clipboard_categories if selected else (),
        )

    def _emit_committed_selection(self, *_):
        self.refresh_removal_actions()
        self.committedSelectionChanged.emit(self.selected_committed_ids())

    def _pending_action_button(self, object_name, icon_path, tooltip, accessible_name):
        """Create a compact icon-only pending lifecycle action."""
        button = QtWidgets.QPushButton(self)
        button.setObjectName(object_name)
        configure_time_series_action_button(
            button,
            icon=icon_path,
            tooltip=tooltip,
            accessible_name=accessible_name,
        )
        button.setAutoDefault(False)
        button.setDefault(False)
        return button

    def show_pending(self, record):
        """Project pending ownership without mutating committed selection."""
        self.pending_model.set_record(record)
        self.pending_model.set_toolbar_target_active(True)
        self.committed_view.set_selection_active(False)
        self.pending_add_button.setEnabled(True)
        self.pending_discard_button.setEnabled(True)

    def clear_pending(self):
        """Clear pending presentation and restore committed selection styling."""
        self.pending_model.set_toolbar_target_active(False)
        self.pending_model.clear()
        if hasattr(self, "committed_view"):
            self.committed_view.set_selection_active(True)
        self.pending_add_button.setEnabled(False)
        self.pending_discard_button.setEnabled(False)

    def _configure_tab_order(self):
        buttons = self.selection_buttons
        for current, following in zip(buttons, buttons[1:]):
            QtWidgets.QWidget.setTabOrder(current, following)

    def _secondary_label(self, text, object_name):
        label = QtWidgets.QLabel(text, self)
        label.setObjectName(object_name)
        label.setAlignment(ALIGN_LEFT | ALIGN_VCENTER)
        label.setEnabled(True)
        return label

    def changeEvent(self, event):
        """Refresh locally derived secondary colours after theme changes."""
        super(TimeSeriesPointPanel, self).changeEvent(event)
        event_type = event.type()
        if (
            event_type in self._palette_refresh_event_types()
            and hasattr(self, "target_label")
        ):
            self._refresh_secondary_text_palettes()

    @classmethod
    def _palette_refresh_event_types(cls):
        event_enum = getattr(QEvent, "Type", QEvent)
        names = ("PaletteChange", "ApplicationPaletteChange", "StyleChange")
        return tuple(getattr(event_enum, name) for name in names)

    @staticmethod
    def _palette_enum(enum_name, value_name):
        enum_owner = getattr(QtGui.QPalette, enum_name, None)
        if enum_owner is not None and hasattr(enum_owner, value_name):
            return getattr(enum_owner, value_name)
        return getattr(QtGui.QPalette, value_name)

    @staticmethod
    def _blend_colour(foreground, background, emphasis):
        """Blend active text toward its background while retaining its hue."""
        inverse = 1.0 - emphasis
        return QtGui.QColor(
            round(foreground.red() * emphasis + background.red() * inverse),
            round(foreground.green() * emphasis + background.green() * inverse),
            round(foreground.blue() * emphasis + background.blue() * inverse),
            foreground.alpha(),
        )

    def _refresh_secondary_text_palettes(self):
        """Derive enabled secondary text from the panel's effective palette."""
        active = self._palette_enum("ColorGroup", "Active")
        inactive = self._palette_enum("ColorGroup", "Inactive")
        window_text = self._palette_enum("ColorRole", "WindowText")
        window = self._palette_enum("ColorRole", "Window")

        source_palette = self.palette()
        for label, emphasis in (
            (self.target_label, self.SUBGROUP_TEXT_EMPHASIS),
            (self.reference_label, self.SUBGROUP_TEXT_EMPHASIS),
        ):
            palette = QtGui.QPalette(source_palette)
            for group in (active, inactive):
                text_colour = source_palette.color(group, window_text)
                background_colour = source_palette.color(group, window)
                palette.setColor(
                    group,
                    window_text,
                    self._blend_colour(text_colour, background_colour, emphasis),
                )
            label.setForegroundRole(window_text)
            label.setPalette(palette)
            label.setEnabled(True)

    def _separator(self, vertical, object_name):
        separator = QtWidgets.QFrame(self)
        separator.setObjectName(object_name)
        shape_enum = getattr(QtWidgets.QFrame, "Shape", QtWidgets.QFrame)
        shadow_enum = getattr(QtWidgets.QFrame, "Shadow", QtWidgets.QFrame)
        separator.setFrameShape(shape_enum.VLine if vertical else shape_enum.HLine)
        separator.setFrameShadow(shadow_enum.Sunken)
        separator.setFocusPolicy(self._no_focus_policy())
        if vertical:
            separator.setFixedHeight(24)
            separator.setSizePolicy(SIZE_POLICY_FIXED, SIZE_POLICY_FIXED)
        return separator

    @staticmethod
    def _no_focus_policy():
        from qgis.PyQt.QtCore import Qt

        focus_enum = getattr(Qt, "FocusPolicy", Qt)
        return focus_enum.NoFocus
