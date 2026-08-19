"""Code-defined Map Settings panel preserving the legacy dock-widget interface."""

from qgis.PyQt import QtGui, QtWidgets

from ... import color_maps
from qgis.PyQt.QtCore import QRect, QSize

from ...qt_compat import (
    ALIGN_TOP,
    ALIGN_VCENTER,
    LEFT_ARROW,
    RIGHT_ARROW,
    CASE_INSENSITIVE,
    FRAME_SHAPE_NO_FRAME,
    COMBO_NO_INSERT,
    COMPLETER_POPUP_COMPLETION,
    ITEM_IS_ENABLED,
    ITEM_IS_SELECTABLE,
    MATCH_CONTAINS,
    SIZE_POLICY_EXPANDING,
    SIZE_POLICY_FIXED,
    SIZE_POLICY_IGNORED,
    SIZE_POLICY_PREFERRED,
    SPIN_BOX_UP_DOWN_ARROWS,
    SCROLL_BAR_ALWAYS_OFF,
    configure_compact_command_button,
    available_screen_geometry,
    screen_aware_popup_position,
)

from ..widgets import AdaptiveDoubleSpinBox
from ..workspace_header import (
    create_collapsible_workspace_panel_header,
    set_collapsible_workspace_panel_header_collapsed,
)
from ..spacing import SPACE_XS, SPACE_SM, SPACE_MD, SPACE_LG
from .popup import RangeSettingsPopup, SymbologySettingsPopup


class MapSettingsPanel(QtWidgets.QWidget):
    """Own the map-value, symbology, and apply controls."""

    MINIMUM_WIDTH = 180
    PREFERRED_WIDTH = 200
    MAXIMUM_WIDTH = 280
    CONTENT_MAXIMUM_WIDTH = 280
    BUTTON_SIZE = 24
    ICON_SIZE = 20
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
    COLORMAPS = color_maps.COLORMAPS

    def __init__(self, parent=None):
        """Create the panel with the same defaults as the Designer UI."""
        super(MapSettingsPanel, self).__init__(parent)
        self.setObjectName("map_settings_panel")
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
            self.cmb_std_calculation_mode,
            self.cb_symbol_range_symmetric,
            self.sb_symbol_value_offset,
            self.cb_symbol_value_offset_sync_with_ref,
            self.cmb_colormap,
            self.pb_colormap_reverse,
            self.cb_symbol_continuous_colormap,
            self.sb_symbol_classes,
            self.sb_symbol_size,
            self.cmb_symbol_marker_shape,
            self.pb_symbol_outline_color,
            self.sb_symbol_outline_width,
            self.sb_symbol_opacity,
            self.cb_symbology_live,
            self.pb_symbology_revert,
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
        self.cmb_std_calculation_mode = (
            self.range_settings_popup.cmb_std_calculation_mode
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
        self.pb_reference_reset = QtWidgets.QPushButton(self)
        self.pb_reference_reset.setObjectName("pb_reference_reset")
        self.cmb_colormap = QtWidgets.QComboBox(self)
        self.cmb_colormap.setObjectName("cmb_colormap")
        self.pb_colormap_reverse = QtWidgets.QPushButton(self)
        self.pb_colormap_reverse.setObjectName("pb_colormap_reverse")
        self.pb_symbology_settings = QtWidgets.QPushButton(self)
        self.pb_symbology_settings.setObjectName("pb_symbology_settings")
        self.sb_symbol_classes = QtWidgets.QSpinBox(self)
        self.sb_symbol_classes.setObjectName("sb_symbol_classes")
        self.sb_symbol_size = QtWidgets.QDoubleSpinBox(self)
        self.sb_symbol_size.setObjectName("sb_symbol_size")
        self.sb_symbol_opacity = QtWidgets.QSpinBox(self)
        self.sb_symbol_opacity.setObjectName("sb_symbol_opacity")
        self.symbology_settings_popup = SymbologySettingsPopup(
            self.sb_symbol_classes,
            self.sb_symbol_size,
            self.sb_symbol_opacity,
            self,
        )
        self.cb_symbol_continuous_colormap = (
            self.symbology_settings_popup.cb_symbol_continuous_colormap
        )
        self.cmb_symbol_marker_shape = (
            self.symbology_settings_popup.cmb_symbol_marker_shape
        )
        self.pb_symbol_outline_color = (
            self.symbology_settings_popup.pb_symbol_outline_color
        )
        self.sb_symbol_outline_width = (
            self.symbology_settings_popup.sb_symbol_outline_width
        )

        self.cb_symbology_live = QtWidgets.QCheckBox(self)
        self.cb_symbology_live.setObjectName("cb_symbology_live")
        self.pb_symbology_revert = QtWidgets.QPushButton(self)
        self.pb_symbology_revert.setObjectName("pb_symbology_revert")
        self.pb_symbology = QtWidgets.QPushButton(self)
        self.pb_symbology.setObjectName("pb_symbology")

    def _configure_controls(self):
        self.cb_select_field.setToolTip("Select a field; type to search")
        self.cb_select_field.setEditable(True)
        self.cb_select_field.setInsertPolicy(COMBO_NO_INSERT)
        self.cb_select_field.setAcceptDrops(False)
        self.cb_select_field.setMinimumWidth(0)
        self.cb_select_field.setSizePolicy(SIZE_POLICY_IGNORED, SIZE_POLICY_FIXED)
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
            tooltip="Value at the selected reference location, used to shift the colormap range.",
            decimals=5,
            minimum=-1_000_000_000.0,
            maximum=1_000_000_000.0,
            value=0.0,
            single_step=0.1,
        )
        self._configure_command_button(
            self.pb_reference_reset,
            icon=":/icons/icons/reset_offset.svg",
            tooltip="Reset Reference to zero",
        )
        self.pb_reference_reset.clicked.connect(self._reset_reference_value)
        self._configure_toggle_button(
            self.cb_symbol_value_offset_sync_with_ref,
            icon=":/icons/icons/sync_map_with_reference.svg",
            tooltip="Link Reference to the selected reference location",
            checked=False,
        )
        self.cb_symbol_value_offset_sync_with_ref.toggled.connect(
            self._sync_reference_editability
        )
        self._sync_reference_editability()
        self._configure_command_button(
            self.pb_symbol_range_settings,
            icon=":/icons/icons/edit.svg",
            tooltip="Configure range source and symmetry",
        )
        self.pb_symbol_range_settings.clicked.connect(
            self._show_range_settings_popup
        )

        self.cmb_colormap.setToolTip("Select colormap")
        self.cmb_colormap.setEditable(False)
        self.cmb_colormap.setMinimumWidth(0)
        self.cmb_colormap.setSizePolicy(SIZE_POLICY_IGNORED, SIZE_POLICY_FIXED)
        self.cmb_colormap.setIconSize(QSize(72, 16))
        for spec in self.COLORMAPS:
            self.cmb_colormap.addItem(
                QtGui.QIcon(spec.icon_path), spec.label, spec.id
            )

        self._configure_toggle_button(
            self.pb_colormap_reverse,
            icon=":/icons/icons/reverse.svg",
            tooltip="Reverse colormap",
            checked=False,
        )
        self._configure_command_button(
            self.pb_symbology_settings,
            icon=":/icons/icons/setting.svg",
            tooltip="Configure symbology",
        )
        self.pb_symbology_settings.clicked.connect(
            self._show_symbology_settings_popup
        )
        self._configure_spin_box(
            self.sb_symbol_classes,
            tooltip="Number of classes",
            minimum=1,
            value=21,
            horizontal_policy=SIZE_POLICY_EXPANDING,
        )
        self._configure_double_spin_box(
            self.sb_symbol_size,
            tooltip="Symbol size",
            decimals=1,
            minimum=0.0,
            maximum=99.99,
            value=1.0,
            single_step=0.1,
            horizontal_policy=SIZE_POLICY_EXPANDING,
        )
        self._configure_spin_box(
            self.sb_symbol_opacity,
            tooltip="Symbol opacity",
            minimum=0,
            maximum=100,
            value=100,
            single_step=10,
            horizontal_policy=SIZE_POLICY_EXPANDING,
        )
        self.sb_symbol_opacity.setSuffix(" %")
        self._configure_live_update_checkbox()
        self._configure_revert_button()
        self._configure_apply_button()

    def _build_layout(self):
        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        (
            self.panel_header_container,
            self.panel_header,
            self.collapse_button,
        ) = create_collapsible_workspace_panel_header(
            self,
            "Map settings",
            "label_map_settings_panel",
            button_on_left=True,
        )
        self.collapse_button.clicked.connect(self._toggle_collapsed)
        outer_layout.addWidget(self.panel_header_container)
        outer_layout.setAlignment(self.panel_header_container, ALIGN_TOP)

        scroll_area = QtWidgets.QScrollArea(self)
        scroll_area.setObjectName("map_settings_scroll_area")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(FRAME_SHAPE_NO_FRAME)
        scroll_area.setHorizontalScrollBarPolicy(SCROLL_BAR_ALWAYS_OFF)
        scroll_area.setMinimumWidth(self.MINIMUM_WIDTH)
        scroll_area.setMaximumWidth(self.MAXIMUM_WIDTH)
        scroll_area.setSizePolicy(SIZE_POLICY_EXPANDING, SIZE_POLICY_EXPANDING)
        outer_layout.addWidget(scroll_area)
        self.scroll_area = scroll_area

        content = QtWidgets.QWidget(scroll_area)
        content.setObjectName("map_settings_content")
        content.setMinimumWidth(0)
        content.setMaximumWidth(self.CONTENT_MAXIMUM_WIDTH)
        content.setSizePolicy(SIZE_POLICY_IGNORED, SIZE_POLICY_EXPANDING)
        scroll_area.setWidget(content)
        self.content = content

        content_layout = QtWidgets.QVBoxLayout(content)
        content_layout.setContentsMargins(SPACE_LG, SPACE_LG, SPACE_LG, SPACE_LG)
        content_layout.setSpacing(SPACE_LG)
        content_layout.addLayout(self._build_value_layout())
        content_layout.addLayout(self._build_symbology_layout())
        content_layout.addStretch(1)
        content_layout.addWidget(self._build_action_row())
        self._collapsed = False
        self.set_collapsed(False)


    def _toggle_collapsed(self):
        """Toggle shell presentation without changing Map Settings state."""
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed):
        """Project expanded/collapsed shell presentation only."""
        self._collapsed = bool(collapsed)
        self.panel_header.setVisible(not self._collapsed)
        self.scroll_area.setVisible(not self._collapsed)
        set_collapsible_workspace_panel_header_collapsed(
            self.panel_header_container, self._collapsed
        )
        if self._collapsed:
            self.collapse_button.setArrowType(RIGHT_ARROW)
            action = "Expand Map Settings"
        else:
            self.collapse_button.setArrowType(LEFT_ARROW)
            action = "Collapse Map Settings"
        self.collapse_button.setToolTip(action)
        self.collapse_button.setAccessibleName(action)
        self.collapse_button.setAccessibleDescription(action)

    def _build_value_layout(self):
        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(SPACE_MD)
        layout.setVerticalSpacing(SPACE_SM)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(2, 1)
        self._value_layout = layout

        self._field_label = QtWidgets.QLabel("Field", self.content)
        self._field_label.setObjectName("map_field_label")
        layout.addWidget(self._field_label, 0, 0, 1, 3)
        layout.addWidget(self.cb_select_field, 1, 0, 1, 3)

        self._range_label = QtWidgets.QLabel("Range", self.content)
        self._range_label.setObjectName("map_range_label")
        layout.addWidget(self._range_label, 2, 0, 1, 3)
        range_layout = QtWidgets.QHBoxLayout()
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(SPACE_XS)
        range_layout.addWidget(self.sb_symbol_lower_range, 1)
        self._range_separator_label = QtWidgets.QLabel("–", self.content)
        self._range_separator_label.setObjectName("map_range_separator_label")
        self._range_separator_label.setAlignment(ALIGN_VCENTER)
        range_layout.addWidget(self._range_separator_label)
        range_layout.addWidget(self.sb_symbol_upper_range, 1)
        range_layout.addWidget(self.pb_symbol_range_settings)
        self._range_layout = range_layout
        layout.addLayout(range_layout, 3, 0, 1, 3)

        reference_layout = QtWidgets.QGridLayout()
        reference_layout.setContentsMargins(0, 0, 0, 0)
        reference_layout.setHorizontalSpacing(SPACE_MD)
        reference_layout.setColumnStretch(0, 1)
        self._reference_offset_layout = reference_layout

        self._reference_offset_label = QtWidgets.QLabel(
            "Reference", self.content
        )
        self._reference_offset_label.setObjectName("map_reference_offset_label")
        layout.addWidget(self._reference_offset_label, 4, 0, 1, 3)
        reference_layout.addWidget(self.sb_symbol_value_offset, 0, 0)
        reference_layout.addWidget(self.pb_reference_reset, 0, 1)
        reference_layout.addWidget(
            self.cb_symbol_value_offset_sync_with_ref, 0, 2
        )
        layout.addLayout(reference_layout, 5, 0, 1, 3)
        return layout

    def _build_symbology_layout(self):
        layout = QtWidgets.QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(SPACE_MD)
        layout.setVerticalSpacing(SPACE_SM)
        layout.setColumnStretch(1, 1)
        self._symbology_layout = layout

        self._colormap_label = QtWidgets.QLabel("Colormap", self.content)
        self._colormap_label.setObjectName("map_colormap_label")

        layout.addWidget(self._colormap_label, 0, 0, 1, 4)
        layout.addWidget(self.cmb_colormap, 1, 0, 1, 2)
        layout.addWidget(self.pb_colormap_reverse, 1, 2)
        layout.addWidget(self.pb_symbology_settings, 1, 3)
        return layout

    def _build_action_row(self):
        row = QtWidgets.QWidget(self.content)
        row.setObjectName("map_settings_action_row")
        row.setSizePolicy(SIZE_POLICY_EXPANDING, SIZE_POLICY_PREFERRED)

        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_SM)
        layout.addWidget(self.cb_symbology_live)
        layout.addStretch(1)
        layout.addWidget(self.pb_symbology_revert)
        layout.addWidget(self.pb_symbology)

        self._action_row = row
        self._action_layout = layout
        return row

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
        spin_box,
        *,
        tooltip,
        decimals,
        minimum,
        maximum,
        value,
        single_step=None,
        horizontal_policy=SIZE_POLICY_IGNORED,
    ):
        spin_box.setToolTip(tooltip)
        spin_box.setButtonSymbols(SPIN_BOX_UP_DOWN_ARROWS)
        spin_box.setDecimals(decimals)
        spin_box.setMinimum(minimum)
        spin_box.setMaximum(maximum)
        if single_step is not None:
            spin_box.setSingleStep(single_step)
        spin_box.setValue(value)
        spin_box.setMinimumWidth(0)
        spin_box.setSizePolicy(horizontal_policy, SIZE_POLICY_FIXED)

    @staticmethod
    def _configure_spin_box(
        spin_box,
        *,
        tooltip,
        minimum,
        value,
        maximum=99,
        single_step=1,
        horizontal_policy=SIZE_POLICY_IGNORED,
    ):
        spin_box.setToolTip(tooltip)
        spin_box.setButtonSymbols(SPIN_BOX_UP_DOWN_ARROWS)
        spin_box.setMinimum(minimum)
        spin_box.setMaximum(maximum)
        spin_box.setSingleStep(single_step)
        spin_box.setValue(value)
        spin_box.setMinimumWidth(0)
        spin_box.setSizePolicy(horizontal_policy, SIZE_POLICY_FIXED)

    def _configure_toggle_button(self, button, *, icon, tooltip, checked):
        button.setText("")
        button.setIcon(QtGui.QIcon(icon))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.setCheckable(True)
        button.setChecked(checked)
        button.setFlat(True)
        button.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        button.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        button.setSizePolicy(SIZE_POLICY_FIXED, SIZE_POLICY_FIXED)
        button.setStyleSheet(self.TOGGLE_STYLE)

    def _configure_command_button(self, button, *, icon, tooltip):
        self._configure_button_base(button, icon=icon, tooltip=tooltip)

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

    def _show_symbology_settings_popup(self, checked=False):
        """Open secondary symbology controls next to their settings button."""
        popup = self.symbology_settings_popup
        popup.adjustSize()
        top_left = self.pb_symbology_settings.mapToGlobal(
            self.pb_symbology_settings.rect().topLeft()
        )
        anchor = QRect(top_left, self.pb_symbology_settings.size())
        geometry = available_screen_geometry(top_left, self)
        popup.move(screen_aware_popup_position(anchor, popup.sizeHint(), geometry))
        popup.show()
        popup.raise_()

    def _sync_reference_editability(self, checked=None):
        """Synchronize Reference controls with the link state."""
        linked = self.cb_symbol_value_offset_sync_with_ref.isChecked()
        self.sb_symbol_value_offset.setReadOnly(linked)
        self.pb_reference_reset.setEnabled(not linked)
        self.cb_symbol_value_offset_sync_with_ref.setToolTip(
            "Reference is linked to the selected reference location"
            if linked
            else "Link Reference to the selected reference location"
        )

    def _reset_reference_value(self, checked=False):
        """Reset an unlinked Reference through the normal valueChanged path."""
        if self.cb_symbol_value_offset_sync_with_ref.isChecked():
            return
        if self.sb_symbol_value_offset.value() == 0.0:
            return
        self.sb_symbol_value_offset.setValue(0.0)

    def set_reference_sync_checked(self, checked):
        """Set Reference linking programmatically and synchronize presentation."""
        button = self.cb_symbol_value_offset_sync_with_ref
        was_blocked = button.blockSignals(True)
        try:
            button.setChecked(bool(checked))
        finally:
            button.blockSignals(was_blocked)
        self._sync_reference_editability()

    def _configure_live_update_checkbox(self):
        checkbox = self.cb_symbology_live
        checkbox.setText("Live")
        checkbox.setToolTip("Apply changes immediately")
        checkbox.setAccessibleName("Live")
        checkbox.setAccessibleDescription("Apply changes immediately")
        checkbox.setChecked(False)
        checkbox.setSizePolicy(SIZE_POLICY_FIXED, SIZE_POLICY_FIXED)

    def _configure_revert_button(self):
        """Configure the secondary action that discards unapplied editor state."""
        button = self.pb_symbology_revert
        button.setText("")
        button.setIcon(QtGui.QIcon(":/icons/icons/revert.svg"))
        button.setToolTip("Revert unapplied map settings")
        button.setAccessibleName("Revert")
        button.setAccessibleDescription("Revert unapplied map settings")
        button.setCheckable(False)
        button.setEnabled(False)
        button.setFlat(False)
        configure_compact_command_button(
            button,
            size=self.BUTTON_SIZE,
            icon_size=self.ACTION_ICON_SIZE,
        )

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
        configure_compact_command_button(
            button,
            size=self.BUTTON_SIZE,
            icon_size=self.ICON_SIZE,
        )
