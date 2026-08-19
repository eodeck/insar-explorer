"""Shared palette-based styles for checkable active-mode buttons."""


ACTIVE_MODE_PUSH_BUTTON_STYLESHEET = """
QPushButton {
    border: 1px solid transparent;
    background: transparent;
}
QPushButton:hover:enabled:!checked {
    border-color: palette(mid);
    background-color: palette(alternate-base);
}
QPushButton:checked,
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


def apply_active_mode_push_button_style(button):
    """Apply the shared checked-state presentation to an active-mode button."""
    button.setStyleSheet(ACTIVE_MODE_PUSH_BUTTON_STYLESHEET)
