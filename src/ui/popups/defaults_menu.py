"""Shared compact Defaults menu for settings popups."""

from ..icon_theme import icon as themed_icon

from qgis.PyQt.QtWidgets import QMenu, QToolButton

from ...qt_compat import configure_compact_command_button


def createDefaultsMenu(parent, apply_saved, save_current, apply_factory, object_name):
    """Create the standard icon-only Defaults menu in canonical order."""
    button = QToolButton(parent)
    button.setObjectName(object_name)
    button.setText("")
    button.setIcon(themed_icon("bookmark"))
    configure_compact_command_button(button)
    popup_mode = getattr(QToolButton, "ToolButtonPopupMode", QToolButton)
    button.setPopupMode(popup_mode.InstantPopup)
    button.setToolTip("Defaults")
    button.setAccessibleName("Defaults")
    button.setAccessibleDescription("Open saved and factory default actions.")

    menu = QMenu(button)
    default_action = menu.addAction(
        themed_icon("bookmark_star"), "Default"
    )
    default_action.setToolTip("Apply the saved default.")
    default_action.triggered.connect(apply_saved)

    factory_action = menu.addAction(
        themed_icon("bookmark_reset"), "Factory default"
    )
    factory_action.setToolTip("Apply the original plugin defaults.")
    factory_action.triggered.connect(apply_factory)

    menu.addSeparator()

    set_default_action = menu.addAction(
        themed_icon("bookmark_set"), "Set as default"
    )
    set_default_action.setToolTip("Save the current values as the default.")
    set_default_action.triggered.connect(save_current)

    button.setMenu(menu)
    return button
