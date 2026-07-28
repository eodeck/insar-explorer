"""Shared compact Defaults menu for settings popups."""

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QMenu, QToolButton

from ...qt_compat import configure_compact_command_button


def createDefaultsMenu(parent, apply_saved, save_current, apply_factory, object_name):
    """Create the standard icon-only Defaults menu in canonical order."""
    button = QToolButton(parent)
    button.setObjectName(object_name)
    button.setText("")
    button.setIcon(QIcon(":/icons/icons/bookmark.svg"))
    configure_compact_command_button(button)
    popup_mode = getattr(QToolButton, "ToolButtonPopupMode", QToolButton)
    button.setPopupMode(popup_mode.InstantPopup)
    button.setToolTip("Defaults")
    button.setAccessibleName("Defaults")
    button.setAccessibleDescription("Open saved and factory default actions.")

    menu = QMenu(button)
    default_action = menu.addAction(
        QIcon(":/icons/icons/bookmark_star.svg"), "Default"
    )
    default_action.setToolTip("Apply the saved default.")
    default_action.triggered.connect(apply_saved)

    factory_action = menu.addAction(
        QIcon(":/icons/icons/bookmark_reset.svg"), "Factory default"
    )
    factory_action.setToolTip("Apply the original plugin defaults.")
    factory_action.triggered.connect(apply_factory)

    menu.addSeparator()

    set_default_action = menu.addAction(
        QIcon(":/icons/icons/bookmark_set.svg"), "Set as default"
    )
    set_default_action.setToolTip("Save the current values as the default.")
    set_default_action.triggered.connect(save_current)

    button.setMenu(menu)
    return button
