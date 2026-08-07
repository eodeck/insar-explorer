"""Code-defined Map Settings panel preserving the legacy dock-widget interface."""

from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import QSize

from ...qt_compat import (
    SIZE_POLICY_EXPANDING,
    SIZE_POLICY_FIXED,
    SIZE_POLICY_PREFERRED,
    SPIN_BOX_NO_BUTTONS,
    configure_compact_command_button,
)


class MapSettingsPanel(QtWidgets.QWidget):
    """Own the map-value, symbology, and apply controls."""

    MINIMUM_WIDTH = 180
    PREFERRED_WIDTH = 200
    MAXIMUM_WIDTH = 280
    CONTENT_MAXIMUM_WIDTH = 280
    BUTTON_SIZE = 24
    ICON_SIZE = 20
    HOVER_STYLE = "QPushButton:hover {\n    border: 1px solid #bbb;\n}\n"
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
            self.cb_symbol_range_sync,
            self.sb_symbol_value_offset,
            self.cb_symbol_value_offset_sync_with_ref,
            self.pb_range_from_data,
            self.cmb_colormap,
            self.pb_colormap_reverse,
            self.sb_symbol_classes,
            self.sb_symbol_size,
            self.sb_symbol_opacity,
            self.pb_symbology_live,
            self.pb_symbology,
        )

    def _create_controls(self):
        self.cb_select_field = QtWidgets.QComboBox(self)
        self.cb_select_field.setObjectName("cb_select_field")

        self.sb_symbol_lower_range = QtWidgets.QDoubleSpinBox(self)
        self.sb_symbol_lower_range.setObjectName("sb_symbol_lower_range")
        self.cb_symbol_range_sync = QtWidgets.QPushButton(self)
        self.cb_symbol_range_sync.setObjectName("cb_symbol_range_sync")
        self.sb_symbol_upper_range = QtWidgets.QDoubleSpinBox(self)
        self.sb_symbol_upper_range.setObjectName("sb_symbol_upper_range")

        self.sb_symbol_value_offset = QtWidgets.QDoubleSpinBox(self)
        self.sb_symbol_value_offset.setObjectName("sb_symbol_value_offset")
        self.cb_symbol_value_offset_sync_with_ref = QtWidgets.QPushButton(self)
        self.cb_symbol_value_offset_sync_with_ref.setObjectName(
            "cb_symbol_value_offset_sync_with_ref"
        )
        self.pb_range_from_data = QtWidgets.QPushButton(self)
        self.pb_range_from_data.setObjectName("pb_range_from_data")

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

        self.pb_symbology_live = QtWidgets.QPushButton(self)
        self.pb_symbology_live.setObjectName("pb_symbology_live")
        self.pb_symbology = QtWidgets.QPushButton(self)
        self.pb_symbology.setObjectName("pb_symbology")

    def _configure_controls(self):
        self.cb_select_field.setToolTip("Select field")
        self.cb_select_field.setEditable(True)
        self.cb_select_field.setAcceptDrops(False)

        self._configure_double_spin_box(
            self.sb_symbol_lower_range,
            tooltip="Min symbology value",
            decimals=1,
            minimum=-1_000_000_000.0,
            maximum=1_000_000_000.0,
            value=-10.0,
        )
        self._configure_toggle_button(
            self.cb_symbol_range_sync,
            icon=":/icons/icons/synched.svg",
            tooltip="Synchronize range",
            checked=True,
        )
        self._configure_double_spin_box(
            self.sb_symbol_upper_range,
            tooltip="Max symbology value",
            decimals=1,
            minimum=-1_000_000_000.0,
            maximum=1_000_000_000.0,
            value=10.0,
        )
        self._configure_double_spin_box(
            self.sb_symbol_value_offset,
            tooltip="Offset the values",
            decimals=2,
            minimum=-1_000_000_000.0,
            maximum=1_000_000_000.0,
            value=0.0,
        )
        self._configure_toggle_button(
            self.cb_symbol_value_offset_sync_with_ref,
            icon=":/icons/icons/sync_map_with_reference.svg",
            tooltip="Synchronize map offset with selected reference point",
            checked=False,
        )
        self._configure_flat_button(
            self.pb_range_from_data,
            icon=":/icons/icons/data_range.svg",
            tooltip="Min/Max from data",
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
        self._configure_toggle_button(
            self.pb_symbology_live,
            icon=":/icons/icons/apply_symbology_on-the-fly.svg",
            tooltip="Apply symbology automatically",
            checked=False,
        )
        self._configure_command_button(
            self.pb_symbology,
            icon=":/icons/icons/apply_symbology.svg",
            tooltip="Apply symbology",
        )

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
        content_layout.addWidget(self._build_apply_group())
        content_layout.addStretch(1)

    def _build_value_group(self):
        group = self._group_box("Value", "map_value_group")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.cb_select_field)

        range_layout = QtWidgets.QHBoxLayout()
        range_layout.setSpacing(5)
        range_layout.addWidget(self.sb_symbol_lower_range)
        range_layout.addWidget(self.cb_symbol_range_sync)
        range_layout.addWidget(self.sb_symbol_upper_range)
        layout.addLayout(range_layout)

        offset_layout = QtWidgets.QHBoxLayout()
        offset_layout.setSpacing(1)
        offset_layout.addWidget(QtWidgets.QLabel("Ref. shift:", group))
        offset_layout.addWidget(self.sb_symbol_value_offset)
        offset_layout.addWidget(self.cb_symbol_value_offset_sync_with_ref)
        offset_layout.addStretch(1)
        layout.addLayout(offset_layout)

        range_from_data_layout = QtWidgets.QHBoxLayout()
        range_from_data_layout.setSpacing(1)
        range_from_data_layout.addWidget(self.pb_range_from_data)
        range_from_data_layout.addStretch(1)
        layout.addLayout(range_from_data_layout)
        return group

    def _build_symbology_group(self):
        group = self._group_box("Symbology", "map_symbology_group")
        layout = QtWidgets.QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        colormap_layout = QtWidgets.QHBoxLayout()
        colormap_layout.setSpacing(5)
        colormap_layout.addWidget(self.cmb_colormap)
        colormap_layout.addWidget(self.pb_colormap_reverse)
        layout.addLayout(colormap_layout)
        layout.addLayout(self._labeled_control_row("Classes:", self.sb_symbol_classes))
        layout.addLayout(self._labeled_control_row("Size:", self.sb_symbol_size))
        layout.addLayout(self._labeled_control_row("Opacity:", self.sb_symbol_opacity))
        return group

    def _build_apply_group(self):
        group = self._group_box("Apply", "map_apply_group")
        layout = QtWidgets.QHBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        layout.addStretch(1)
        layout.addWidget(self.pb_symbology_live)
        layout.addWidget(self.pb_symbology)
        return group

    @staticmethod
    def _group_box(title, object_name):
        group = QtWidgets.QGroupBox(title)
        group.setObjectName(object_name)
        group.setFlat(True)
        group.setMinimumWidth(150)
        group.setSizePolicy(SIZE_POLICY_FIXED, SIZE_POLICY_PREFERRED)
        return group

    @staticmethod
    def _labeled_control_row(label_text, control):
        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(1)
        layout.addWidget(QtWidgets.QLabel(label_text, control.parent()))
        layout.addWidget(control)
        return layout

    @staticmethod
    def _configure_double_spin_box(
        spin_box, *, tooltip, decimals, minimum, maximum, value, single_step=None
    ):
        spin_box.setToolTip(tooltip)
        spin_box.setButtonSymbols(SPIN_BOX_NO_BUTTONS)
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
        spin_box.setButtonSymbols(SPIN_BOX_NO_BUTTONS)
        spin_box.setMinimum(minimum)
        spin_box.setMaximum(maximum)
        spin_box.setSingleStep(single_step)
        spin_box.setValue(value)
        spin_box.setSizePolicy(SIZE_POLICY_PREFERRED, SIZE_POLICY_FIXED)

    def _configure_toggle_button(self, button, *, icon, tooltip, checked):
        self._configure_flat_button(button, icon=icon, tooltip=tooltip)
        button.setCheckable(True)
        button.setChecked(checked)

    def _configure_flat_button(self, button, *, icon, tooltip):
        self._configure_button_base(button, icon=icon, tooltip=tooltip)
        button.setFlat(True)
        button.setStyleSheet(self.HOVER_STYLE)

    def _configure_command_button(self, button, *, icon, tooltip):
        button.setText("")
        button.setIcon(QtGui.QIcon(icon))
        button.setToolTip(tooltip)
        configure_compact_command_button(
            button, size=self.BUTTON_SIZE, icon_size=self.ICON_SIZE
        )
        button.setMinimumSize(0, 0)

    def _configure_button_base(self, button, *, icon, tooltip):
        button.setText("")
        button.setIcon(QtGui.QIcon(icon))
        button.setToolTip(tooltip)
        button.setMaximumSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        button.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        button.setSizePolicy(SIZE_POLICY_FIXED, SIZE_POLICY_FIXED)
