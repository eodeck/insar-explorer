"""Code-defined Map Settings panel preserving the legacy dock-widget interface."""

from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import QRect, QSize

from ...qt_compat import (
    ALIGN_VCENTER,
    CASE_INSENSITIVE,
    COMBO_NO_INSERT,
    COMPLETER_POPUP_COMPLETION,
    ITEM_IS_ENABLED,
    ITEM_IS_SELECTABLE,
    MATCH_CONTAINS,
    SIZE_POLICY_EXPANDING,
    SIZE_POLICY_FIXED,
    SIZE_POLICY_PREFERRED,
    SPIN_BOX_UP_DOWN_ARROWS,
    available_screen_geometry,
    screen_aware_popup_position,
)

from ..widgets import AdaptiveDoubleSpinBox
from .popup import RangeSettingsPopup


class MapSettingsPanel(QtWidgets.QWidget):
    """Own the map-value, symbology, and apply controls."""

    MINIMUM_WIDTH = 180
    PREFERRED_WIDTH = 200
    MAXIMUM_WIDTH = 280
    CONTENT_MAXIMUM_WIDTH = 280
    BUTTON_SIZE = 24
    ICON_SIZE = 20
    HOVER_STYLE = "QPushButton:hover {\n    border: 1px solid #bbb;\n}\n"
    TOGGLE_STYLE = """
QPushButton {
    border: 1px solid transparent;
    background: transparent;
}
QPushButton:hover:enabled:!checked {
    border-color: palette(mid);
    background-color: palette(alternate-base);
}
QPushButton:checked {
    border-color: palette(highlight);
    background-color: palette(highlight);
    color: palette(highlighted-text);
}
QPushButton:checked:hover:enabled {
    border-color: palette(highlight);
    background-color: palette(highlight);
    color: palette(highlighted-text);
}
QPushButton:disabled {
    border-color: transparent;
    background: transparent;
    color: palette(mid);
}
QPushButton:checked:disabled {
    border-color: palette(midlight);
    background-color: palette(midlight);
    color: palette(mid);
}
"""
    ACTION_BUTTON_STYLE = """
QPushButton {
    padding: 1px 3px;
}
"""
    ACTION_ICON_SIZE = 14
    COLORMAPS = (
        ("Roma", ":/colormaps/icons/colormaps/roma.png"),
        ("Vik", ":/colormaps/icons/colormaps/vik.png"),
        ("Turbo_r", ":/colormaps/icons/colormaps/turbo_r.png"),
        ("Gray", ":/colormaps/icons/colormaps/gray.png"),
    )

    def __init__(self, parent=None):
        """Create the panel with the same defaults as the Designer UI."""
        super(MapSettingsPanel, self).__init__(parent)
        self.setObjectName("map_settings_panel")
        self.setMinimumWidth(self.MINIMUM_WIDTH)
        self.setMaximumWidth(self.MAXIMUM_WIDTH)
        self.setSizePolicy(SIZE_POLICY_PREFERRED, SIZE_POLICY_EXPANDING)

        self._last_valid_field_index = -1
        self._create_controls()
        self._configure_controls()
        self._build_layout()

    def sizeHint(self):
        """Prefer the legacy settings-region width while remaining bounded."""
        hint = super(MapSettingsPanel, self).sizeHint()
        hint.setWidth(self.PREFERRED_WIDTH)
        return hint

    @property
    def compatibility_widgets(self):
        """Return public controls historically exposed by the dock widget."""
        return (
            self.cb_select_field,
            self.sb_symbol_lower_range,
            self.sb_symbol_upper_range,
            self.pb_symbol_range_settings,
            self.cmb_symbol_range_source,
            self.cb_symbol_range_symmetric,
            self.sb_symbol_value_offset,
            self.cb_symbol_value_offset_sync_with_ref,
            self.cmb_colormap,
            self.pb_colormap_reverse,
            self.sb_symbol_classes,
            self.sb_symbol_size,
            self.sb_symbol_opacity,
            self.cb_symbology_live,
            self.pb_symbology,
        )

    def _create_controls(self):
        self.cb_select_field = QtWidgets.QComboBox(self)
        self.cb_select_field.setObjectName("cb_select_field")

        self.sb_symbol_lower_range = AdaptiveDoubleSpinBox(self)
        self.sb_symbol_lower_range.setObjectName("sb_symbol_lower_range")
        self.sb_symbol_upper_range = AdaptiveDoubleSpinBox(self)
        self.sb_symbol_upper_range.setObjectName("sb_symbol_upper_range")
        self.pb_symbol_range_settings = QtWidgets.QPushButton(self)
        self.pb_symbol_range_settings.setObjectName("pb_symbol_range_settings")
        self.range_settings_popup = RangeSettingsPopup(self)
        self.cmb_symbol_range_source = (
            self.range_settings_popup.cmb_symbol_range_source
        )
        self.cb_symbol_range_symmetric = (
            self.range_settings_popup.cb_symbol_range_symmetric
        )

        self.sb_symbol_value_offset = AdaptiveDoubleSpinBox(self)
        self.sb_symbol_value_offset.setObjectName("sb_symbol_value_offset")
        self.cb_symbol_value_offset_sync_with_ref = QtWidgets.QPushButton(self)
        self.cb_symbol_value_offset_sync_with_ref.setObjectName(
            "cb_symbol_value_offset_sync_with_ref"
        )
        self.cmb_colormap = QtWidgets.QComboBox(self)
        self.cmb_colormap.setObjectName("cmb_colormap")
        self.pb_colormap_reverse = QtWidgets.QPushButton(self)
        self.pb_colormap_reverse.setObjectName("pb_colormap_reverse")
        self.sb_symbol_classes = QtWidgets.QSpinBox(self)
        self.sb_symbol_classes.setObjectName("sb_symbol_classes")
        self.sb_symbol_size = QtWidgets.QDoubleSpinBox(self)
        self.sb_symbol_size.setObjectName("sb_symbol_size")
        self.sb_symbol_opacity = QtWidgets.QSpinBox(self)
        self.sb_symbol_opacity.setObjectName("sb_symbol_opacity")

        self.cb_symbology_live = QtWidgets.QCheckBox(self)
        self.cb_symbology_live.setObjectName("cb_symbology_live")
        self.pb_symbology = QtWidgets.QPushButton(self)
        self.pb_symbology.setObjectName("pb_symbology")

    def _configure_controls(self):
        self.cb_select_field.setToolTip("Select a field; type to search")
        self.cb_select_field.setEditable(True)
        self.cb_select_field.setInsertPolicy(COMBO_NO_INSERT)
        self.cb_select_field.setAcceptDrops(False)
        self._configure_field_completer()

        self._configure_double_spin_box(
            self.sb_symbol_lower_range,
            tooltip="Min symbology value",
            decimals=5,
            minimum=-1_000_000_000.0,
            maximum=1_000_000_000.0,
            value=-10.0,
            single_step=0.1,
        )
        self._configure_double_spin_box(
            self.sb_symbol_upper_range,
            tooltip="Max symbology value",
            decimals=5,
            minimum=-1_000_000_000.0,
            maximum=1_000_000_000.0,
            value=10.0,
            single_step=0.1,
        )
        self._configure_double_spin_box(
            self.sb_symbol_value_offset,
            tooltip="Offset the values",
            decimals=5,
            minimum=-1_000_000_000.0,
            maximum=1_000_000_000.0,
            value=0.0,
            single_step=0.1,
        )
        self._configure_toggle_button(
            self.cb_symbol_value_offset_sync_with_ref,
            icon=":/icons/icons/sync_map_with_reference.svg",
            tooltip="Keep offset synchronized with the reference point",
            checked=False,
        )
        self.cb_symbol_value_offset_sync_with_ref.toggled.connect(
            self._set_reference_offset_sync_state
        )
        self._set_reference_offset_sync_state(
            self.cb_symbol_value_offset_sync_with_ref.isChecked()
        )
        self._configure_flat_button(
            self.pb_symbol_range_settings,
            icon=":/icons/icons/edit.svg",
            tooltip="Configure range source and symmetry",
        )
        self.pb_symbol_range_settings.clicked.connect(
            self._show_range_settings_popup
        )

        self.cmb_colormap.setToolTip("Select colormap")
        self.cmb_colormap.setEditable(False)
        self.cmb_colormap.setIconSize(QSize(72, 16))
        for name, icon in self.COLORMAPS:
            self.cmb_colormap.addItem(QtGui.QIcon(icon), name)

        self._configure_toggle_button(
            self.pb_colormap_reverse,
            icon=":/icons/icons/reverse.svg",
            tooltip="Reverse colormap",
            checked=False,
        )
        self._configure_spin_box(
            self.sb_symbol_classes,
            tooltip="Number of classes",
            minimum=1,
            value=21,
        )
        self._configure_double_spin_box(
            self.sb_symbol_size,
            tooltip="Symbol size",
            decimals=1,
            minimum=0.0,
            maximum=99.99,
            value=1.0,
            single_step=0.1,
        )
        self._configure_spin_box(
            self.sb_symbol_opacity,
            tooltip="Symbol opacity",
            minimum=0,
            maximum=100,
            value=100,
            single_step=10,
        )
        self.sb_symbol_opacity.setSuffix(" %")
        self._configure_live_update_checkbox()
        self._configure_apply_button()

    def _build_layout(self):
        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setObjectName("map_settings_scroll_area")
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumWidth(self.MAXIMUM_WIDTH)
        scroll_area.setSizePolicy(SIZE_POLICY_PREFERRED, SIZE_POLICY_PREFERRED)
        outer_layout.addWidget(scroll_area)
        self.scroll_area = scroll_area

        content = QtWidgets.QWidget(scroll_area)
        content.setObjectName("map_settings_content")
        content.setMaximumWidth(self.CONTENT_MAXIMUM_WIDTH)
        content.setSizePolicy(SIZE_POLICY_EXPANDING, SIZE_POLICY_EXPANDING)
        scroll_area.setWidget(content)
        self.content = content

        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(9, 9, 9, 9)
        content_layout.setSpacing(6)
        content_layout.addWidget(self._build_value_group())
        content_layout.addWidget(self._build_symbology_group())
        content_layout.addStretch(1)
        content_layout.addWidget(self._build_action_row())

    def _build_value_group(self):
        group = self._group_box("Value", "map_value_group")
        layout = QtWidgets.QGridLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(5)
        layout.setVerticalSpacing(4)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(2, 1)
        self._value_layout = layout

        self._field_label = QtWidgets.QLabel("Field", group)
        self._field_label.setObjectName("map_field_label")
        layout.addWidget(self._field_label, 0, 0, 1, 3)
        layout.addWidget(self.cb_select_field, 1, 0, 1, 3)

        self._range_label = QtWidgets.QLabel("Range", group)
        self._range_label.setObjectName("map_range_label")
        layout.addWidget(self._range_label, 2, 0, 1, 3)
        range_layout = QtWidgets.QHBoxLayout()
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(3)
        range_layout.addWidget(self.sb_symbol_lower_range, 1)
        self._range_separator_label = QtWidgets.QLabel("–", group)
        self._range_separator_label.setObjectName("map_range_separator_label")
        self._range_separator_label.setAlignment(ALIGN_VCENTER)
        range_layout.addWidget(self._range_separator_label)
        range_layout.addWidget(self.sb_symbol_upper_range, 1)
        range_layout.addWidget(self.pb_symbol_range_settings)
        self._range_layout = range_layout
        layout.addLayout(range_layout, 3, 0, 1, 3)

        reference_layout = QtWidgets.QGridLayout()
        reference_layout.setContentsMargins(0, 0, 0, 0)
        reference_layout.setHorizontalSpacing(5)
        reference_layout.setColumnStretch(0, 1)
        self._reference_offset_layout = reference_layout

        self._reference_offset_label = QtWidgets.QLabel("Reference offset", group)
        self._reference_offset_label.setObjectName("map_reference_offset_label")
        layout.addWidget(self._reference_offset_label, 4, 0, 1, 3)
        reference_layout.addWidget(self.sb_symbol_value_offset, 0, 0)
        reference_layout.addWidget(
            self.cb_symbol_value_offset_sync_with_ref, 0, 1
        )
        layout.addLayout(reference_layout, 5, 0, 1, 3)
        return group

    def _build_symbology_group(self):
        group = self._group_box("Symbology", "map_symbology_group")
        layout = QtWidgets.QGridLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(5)
        layout.setVerticalSpacing(4)
        layout.setColumnStretch(1, 1)
        self._symbology_layout = layout

        self._colormap_label = QtWidgets.QLabel("Colormap", group)
        self._colormap_label.setObjectName("map_colormap_label")
        self._classes_label = QtWidgets.QLabel("Classes", group)
        self._classes_label.setObjectName("map_classes_label")
        self._size_label = QtWidgets.QLabel("Size", group)
        self._size_label.setObjectName("map_size_label")
        self._opacity_label = QtWidgets.QLabel("Opacity", group)
        self._opacity_label.setObjectName("map_opacity_label")

        layout.addWidget(self._colormap_label, 0, 0, 1, 3)
        layout.addWidget(self.cmb_colormap, 1, 0, 1, 2)
        layout.addWidget(self.pb_colormap_reverse, 1, 2)
        layout.addWidget(self._classes_label, 2, 0)
        layout.addWidget(self.sb_symbol_classes, 2, 1, 1, 2)
        layout.addWidget(self._size_label, 3, 0)
        layout.addWidget(self.sb_symbol_size, 3, 1, 1, 2)
        layout.addWidget(self._opacity_label, 4, 0)
        layout.addWidget(self.sb_symbol_opacity, 4, 1, 1, 2)
        return group

    def _build_action_row(self):
        row = QtWidgets.QWidget(self.content)
        row.setObjectName("map_settings_action_row")
        row.setSizePolicy(SIZE_POLICY_EXPANDING, SIZE_POLICY_PREFERRED)

        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.cb_symbology_live)
        layout.addStretch(1)
        layout.addWidget(self.pb_symbology)

        self._action_row = row
        self._action_layout = layout
        return row

    @staticmethod
    def _group_box(title, object_name):
        group = QtWidgets.QGroupBox(title)
        group.setObjectName(object_name)
        group.setFlat(True)
        group.setMinimumWidth(150)
        group.setSizePolicy(SIZE_POLICY_EXPANDING, SIZE_POLICY_PREFERRED)
        return group

    def _configure_field_completer(self):
        """Configure native shared-model completion for the Field selector."""
        completer = QtWidgets.QCompleter(
            self.cb_select_field.model(),
            self.cb_select_field,
        )
        completer.setCaseSensitivity(CASE_INSENSITIVE)
        completer.setFilterMode(MATCH_CONTAINS)
        completer.setCompletionMode(COMPLETER_POPUP_COMPLETION)
        self.cb_select_field.setCompleter(completer)
        self._field_completer = completer

        self.cb_select_field.currentIndexChanged.connect(
            self._remember_valid_field_index
        )
        self.cb_select_field.lineEdit().editingFinished.connect(
            self._commit_or_restore_field_text
        )

    def _field_index_is_selectable(self, index):
        """Return whether a combo row is an enabled, selectable field item."""
        if index < 0 or index >= self.cb_select_field.count():
            return False
        model_index = self.cb_select_field.model().index(index, 0)
        flags = model_index.flags()
        return bool(flags & ITEM_IS_ENABLED) and bool(flags & ITEM_IS_SELECTABLE)

    def _remember_valid_field_index(self, index):
        """Remember only committed selectable field rows."""
        if self._field_index_is_selectable(index):
            self._last_valid_field_index = index

    def sync_field_selection_state(self):
        """Capture the current canonical field after blocked model population."""
        index = self.cb_select_field.currentIndex()
        if self._field_index_is_selectable(index):
            self._last_valid_field_index = index
            self.cb_select_field.lineEdit().setText(
                self.cb_select_field.itemText(index)
            )
        else:
            self._last_valid_field_index = -1

    def _find_selectable_field_index(self, text):
        """Resolve exact field text to its canonical selectable combo row."""
        needle = str(text).casefold()
        for index in range(self.cb_select_field.count()):
            if self.cb_select_field.itemText(index).casefold() != needle:
                continue
            if self._field_index_is_selectable(index):
                return index
        return -1

    def _commit_or_restore_field_text(self):
        """Commit an exact valid field name or restore the last valid field."""
        line_edit = self.cb_select_field.lineEdit()
        index = self._find_selectable_field_index(line_edit.text())
        if index >= 0:
            self.cb_select_field.setCurrentIndex(index)
            line_edit.setText(self.cb_select_field.itemText(index))
            self._last_valid_field_index = index
            return

        fallback = self._last_valid_field_index
        if not self._field_index_is_selectable(fallback):
            current = self.cb_select_field.currentIndex()
            fallback = current if self._field_index_is_selectable(current) else -1
        if fallback >= 0:
            self.cb_select_field.setCurrentIndex(fallback)
            line_edit.setText(self.cb_select_field.itemText(fallback))
        else:
            line_edit.clear()

    @staticmethod
    def _configure_double_spin_box(
        spin_box, *, tooltip, decimals, minimum, maximum, value, single_step=None
    ):
        spin_box.setToolTip(tooltip)
        spin_box.setButtonSymbols(SPIN_BOX_UP_DOWN_ARROWS)
        spin_box.setDecimals(decimals)
        spin_box.setMinimum(minimum)
        spin_box.setMaximum(maximum)
        if single_step is not None:
            spin_box.setSingleStep(single_step)
        spin_box.setValue(value)
        spin_box.setSizePolicy(SIZE_POLICY_PREFERRED, SIZE_POLICY_FIXED)

    @staticmethod
    def _configure_spin_box(
        spin_box, *, tooltip, minimum, value, maximum=99, single_step=1
    ):
        spin_box.setToolTip(tooltip)
        spin_box.setButtonSymbols(SPIN_BOX_UP_DOWN_ARROWS)
        spin_box.setMinimum(minimum)
        spin_box.setMaximum(maximum)
        spin_box.setSingleStep(single_step)
        spin_box.setValue(value)
        spin_box.setSizePolicy(SIZE_POLICY_PREFERRED, SIZE_POLICY_FIXED)

    def _configure_toggle_button(self, button, *, icon, tooltip, checked):
        self._configure_button_base(button, icon=icon, tooltip=tooltip)
        button.setFlat(True)
        button.setCheckable(True)
        button.setChecked(checked)
        button.setStyleSheet(self.TOGGLE_STYLE)

    def _configure_flat_button(self, button, *, icon, tooltip):
        self._configure_button_base(button, icon=icon, tooltip=tooltip)
        button.setFlat(True)
        button.setStyleSheet(self.HOVER_STYLE)

    def _show_range_settings_popup(self, checked=False):
        """Open the compact range settings popup next to its anchor button."""
        popup = self.range_settings_popup
        popup.adjustSize()
        top_left = self.pb_symbol_range_settings.mapToGlobal(
            self.pb_symbol_range_settings.rect().topLeft()
        )
        anchor = QRect(top_left, self.pb_symbol_range_settings.size())
        geometry = available_screen_geometry(top_left, self)
        popup.move(screen_aware_popup_position(anchor, popup.sizeHint(), geometry))
        popup.show()
        popup.raise_()

    def _set_reference_offset_sync_state(self, synchronized):
        """Reflect reference synchronization in offset editability."""
        self.sb_symbol_value_offset.setEnabled(not synchronized)

    def _configure_live_update_checkbox(self):
        checkbox = self.cb_symbology_live
        checkbox.setText("Live update")
        checkbox.setToolTip("Apply changes automatically")
        checkbox.setAccessibleName("Live update")
        checkbox.setChecked(False)
        checkbox.setSizePolicy(SIZE_POLICY_FIXED, SIZE_POLICY_FIXED)

    def _configure_apply_button(self):
        button = self.pb_symbology
        button.setText("Apply")
        button.setIcon(QtGui.QIcon(":/icons/icons/apply_symbology.svg"))
        button.setToolTip("Apply symbology")
        button.setAccessibleName("Apply symbology")
        button.setCheckable(False)
        button.setEnabled(False)
        button.setFlat(False)
        button.setIconSize(QSize(self.ACTION_ICON_SIZE, self.ACTION_ICON_SIZE))
        button.setFixedHeight(self.BUTTON_SIZE)
        button.setSizePolicy(SIZE_POLICY_FIXED, SIZE_POLICY_FIXED)
        button.setStyleSheet(self.ACTION_BUTTON_STYLE)

    def _configure_button_base(self, button, *, icon, tooltip):
        button.setText("")
        button.setIcon(QtGui.QIcon(icon))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setMaximumSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        button.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        button.setSizePolicy(SIZE_POLICY_FIXED, SIZE_POLICY_FIXED)
