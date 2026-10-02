"""Central light/dark functional icon resolution and live refresh support."""

import logging
import weakref

from qgis.PyQt import QtCore, QtGui, QtWidgets

_LOG = logging.getLogger(__name__)
_ICON_PROPERTY = "insar_icon_name"
_registered = weakref.WeakSet()
_icon_keys = {}


def _palette_role(name):
    """Resolve a QPalette role across scoped Qt6 and legacy Qt5 enums."""
    roles = getattr(QtGui.QPalette, "ColorRole", None)
    if roles is not None and hasattr(roles, name):
        return getattr(roles, name)
    return getattr(QtGui.QPalette, name)


def _luminance(color):
    """Return relative sRGB luminance for a QColor."""
    channels = []
    for value in (color.redF(), color.greenF(), color.blueF()):
        channels.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def is_dark_theme(palette=None):
    """Return whether the active application palette is effectively dark."""
    if palette is None:
        app = QtWidgets.QApplication.instance()
        palette = app.palette() if app is not None else QtGui.QPalette()
    window = palette.color(_palette_role("Window"))
    text = palette.color(_palette_role("WindowText"))
    return _luminance(window) < _luminance(text)


def icon_path(name):
    """Return the themed Qt resource path for a logical functional icon name."""
    logical = str(name).strip()
    if logical.endswith(".svg"):
        logical = logical[:-4]
    if not logical or "/" in logical or "\\" in logical:
        raise ValueError("Icon name must be a simple logical name")
    theme = "dark" if is_dark_theme() else "light"
    return ":/icons/{}/{}.svg".format(theme, logical)


def icon(name):
    """Return a QIcon for a logical functional icon name."""
    path = icon_path(name)
    if not QtCore.QFile.exists(path):
        _LOG.warning("Missing InSAR Explorer icon resource: %s", path)
        return QtGui.QIcon()
    themed = QtGui.QIcon(path)
    logical = str(name)
    if logical.endswith(".svg"):
        logical = logical[:-4]
    _icon_keys[themed.cacheKey()] = logical
    return themed


def set_themed_icon(target, name):
    """Assign and register a logical themed icon on a widget, action, or split button."""
    logical = str(name).strip()
    target.setProperty(_ICON_PROPERTY, logical)
    _registered.add(target)
    _apply_themed_icon(target, logical)
    return target


def _apply_themed_icon(target, logical):
    themed = icon(logical)
    setter = getattr(target, "setIcon", None)
    if callable(setter):
        setter(themed)
        return
    primary_setter = getattr(target, "setPrimaryIcon", None)
    if callable(primary_setter):
        primary_setter(themed)
        return
    raise TypeError("Object does not support themed icon assignment")


def refresh_themed_icon(target):
    """Refresh one previously registered themed icon."""
    logical = target.property(_ICON_PROPERTY)
    if logical:
        _apply_themed_icon(target, logical)


def refresh_all_themed_icons():
    """Refresh all live themed widgets/actions after a palette change."""
    targets = set(_registered)
    app = QtWidgets.QApplication.instance()
    if app is not None:
        for widget in app.allWidgets():
            targets.add(widget)
            actions = getattr(widget, "actions", None)
            if callable(actions):
                targets.update(actions())
            menu_action = getattr(widget, "menuAction", None)
            if callable(menu_action):
                targets.add(menu_action())

    for target in tuple(targets):
        try:
            logical = target.property(_ICON_PROPERTY)
            if not logical:
                getter = getattr(target, "icon", None)
                if callable(getter):
                    current = getter()
                    logical = _icon_keys.get(current.cacheKey())
                    if logical:
                        target.setProperty(_ICON_PROPERTY, logical)
                        _registered.add(target)
            if logical:
                _apply_themed_icon(target, logical)
        except RuntimeError:
            _registered.discard(target)
