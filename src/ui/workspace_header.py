"""Shared presentation for compact top-level workspace panel headers."""

from qgis.PyQt import QtWidgets

from ..qt_compat import ALIGN_LEFT, ALIGN_VCENTER


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
