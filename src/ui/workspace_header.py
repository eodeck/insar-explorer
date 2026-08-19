"""Shared presentation for compact top-level workspace panel headers."""

from qgis.PyQt import QtWidgets

from ..qt_compat import (
    ALIGN_LEFT,
    ALIGN_VCENTER,
    SIZE_POLICY_EXPANDING,
    SIZE_POLICY_FIXED,
    configure_compact_command_button,
)
from .spacing import SPACE_XS


WORKSPACE_COLLAPSE_BUTTON_SIZE = 20
WORKSPACE_COLLAPSE_ICON_SIZE = 12


def create_workspace_panel_header(parent, text, object_name):
    """Return a compact, theme-native header for a main workspace region."""
    label = QtWidgets.QLabel(text, parent)
    label.setObjectName(object_name)
    label.setAccessibleName("{} panel".format(text))
    label.setAlignment(ALIGN_LEFT | ALIGN_VCENTER)
    label.setContentsMargins(0, 0, 0, 0)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    return label


def create_collapsible_workspace_panel_header(
    parent, text, object_name, *, button_on_left
):
    """Return a compact header widget, title label, and chevron button."""
    header = QtWidgets.QWidget(parent)
    header.setObjectName("{}_container".format(object_name))
    header.setSizePolicy(SIZE_POLICY_EXPANDING, SIZE_POLICY_FIXED)

    layout = QtWidgets.QHBoxLayout(header)
    layout.setContentsMargins(SPACE_XS, 0, SPACE_XS, 0)
    layout.setSpacing(SPACE_XS)

    title = create_workspace_panel_header(header, text, object_name)
    button = QtWidgets.QToolButton(header)
    button.setObjectName("{}_collapse_button".format(object_name))
    configure_compact_command_button(
        button,
        size=WORKSPACE_COLLAPSE_BUTTON_SIZE,
        icon_size=WORKSPACE_COLLAPSE_ICON_SIZE,
    )

    if button_on_left:
        layout.addWidget(button)
        layout.addWidget(title)
        layout.addStretch(1)
    else:
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(button)

    return header, title, button


def set_collapsible_workspace_panel_header_collapsed(header, collapsed):
    """Use compact rail margins only while a workspace panel is collapsed."""
    layout = header.layout()
    top_margin = SPACE_XS if collapsed else 0
    layout.setContentsMargins(SPACE_XS, top_margin, SPACE_XS, 0)
