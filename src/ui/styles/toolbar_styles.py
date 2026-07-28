"""Reusable styling helpers for code-created toolbars."""

from qgis.PyQt.QtCore import QSize


COMMAND_TOOLBAR_STYLESHEET = """
QToolBar {
    background: transparent;
    margin: 0;
    padding: 0;
    border: none;
    spacing: 1px;
}
QToolButton[controlRole="toggle"]:hover:enabled {
    border: 1px solid palette(mid);
}
QToolButton[controlRole="command"]:hover:enabled {
    background-color: palette(alternate-base);
    border: 2px solid palette(mid);
    border-radius: 3px;
}
QToolButton[controlRole="command"]:pressed:enabled {
    background-color: palette(mid);
    border: 2px solid palette(dark);
    border-radius: 3px;
}
QToolButton[controlRole="selector"] {
    margin: 0;
    padding: 1px 1px;
}
"""


def apply_command_toolbar_style(toolbar):
    """Apply the shared style for code-created command toolbars."""
    toolbar.setStyleSheet(COMMAND_TOOLBAR_STYLESHEET)


def set_toolbar_control_role(widget, role):
    """Assign and configure a visual role for a code-created toolbar control."""
    if role not in {"toggle", "command", "selector"}:
        raise ValueError(f"Unsupported toolbar control role: {role}")

    widget.setProperty("controlRole", role)
    widget.setIconSize(QSize(18, 18))

    if role == "selector":
        widget.setAutoRaise(True)
        widget.setFixedHeight(22)
        widget.setMinimumWidth(22)
    else:
        widget.setAutoRaise(role == "toggle")
        widget.setFixedSize(22, 22)

    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
