"""Dedicated time-series point panel for selection controls and future records."""

from qgis.PyQt import QtGui, QtWidgets
from qgis.PyQt.QtCore import QEvent, QSize

from ...qt_compat import (
    ALIGN_LEFT,
    ALIGN_VCENTER,
    SIZE_POLICY_EXPANDING,
    SIZE_POLICY_FIXED,
    SIZE_POLICY_MAXIMUM,
    SIZE_POLICY_PREFERRED,
)


class TimeSeriesPointPanel(QtWidgets.QWidget):
    """Own the compact selection header and reserved point-list area.

    The selection controls are recreated as compatible widgets because the
    baseline ``.ui`` controls were removed when the controls moved out of the
    settings tab. Their object names, icon resources, dimensions, interaction
    flags, styling, and dock-level compatibility attributes are preserved.
    """

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

        layout.addWidget(self._separator(vertical=False, object_name="point_list_separator"))

        points_heading = QtWidgets.QLabel("Time-series points", self)
        points_heading.setObjectName("label_time_series_points_heading")
        heading_font = points_heading.font()
        heading_font.setBold(True)
        points_heading.setFont(heading_font)
        layout.addWidget(points_heading)

        self.placeholder_label = QtWidgets.QLabel(
            "Point list will be added in a later phase.", self
        )
        self.placeholder_label.setObjectName("label_time_series_points_placeholder")
        self.placeholder_label.setWordWrap(True)
        self.placeholder_label.setEnabled(True)
        self.placeholder_label.setSizePolicy(SIZE_POLICY_PREFERRED, SIZE_POLICY_MAXIMUM)
        layout.addWidget(self.placeholder_label)
        layout.addStretch(1)

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
            and hasattr(self, "placeholder_label")
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
            (self.placeholder_label, self.PLACEHOLDER_TEXT_EMPHASIS),
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
