"""Qt/QGIS enum compatibility helpers for QGIS 3/Qt5 and QGIS 4/Qt6.

Application code should import compatibility constants from this module instead
of branching on Qt binding versions or using enum aliases directly.
"""

try:
    from qgis.PyQt.QtCore import QEvent, QPoint, QRect, QSize, Qt
    try:
        from qgis.PyQt.QtGui import QAction, QActionGroup, QGuiApplication
    except ImportError:
        from qgis.PyQt.QtWidgets import QAction, QActionGroup
        from qgis.PyQt.QtGui import QGuiApplication
    from qgis.PyQt.QtWidgets import QApplication, QColorDialog, QFrame, QMessageBox, QSizePolicy, QToolButton
except ImportError:
    from PySide6.QtCore import QEvent, QPoint, QRect, QSize, Qt
    from PySide6.QtGui import QAction, QActionGroup, QGuiApplication
    from PySide6.QtWidgets import QApplication, QColorDialog, QFrame, QMessageBox, QSizePolicy, QToolButton

try:
    from qgis.core import QgsMapLayer, QgsWkbTypes
except ImportError:
    QgsMapLayer = None
    QgsWkbTypes = None


def _enum_value(owner, enum_name, value_name, legacy_name=None):
    """Return a scoped enum value when available, otherwise a legacy alias."""
    enum_owner = getattr(owner, enum_name, None)
    if enum_owner is not None and hasattr(enum_owner, value_name):
        return getattr(enum_owner, value_name)
    return getattr(owner, legacy_name or value_name)


# QEvent enums
EVENT_ENTER = _enum_value(QEvent, "Type", "Enter")
EVENT_LEAVE = _enum_value(QEvent, "Type", "Leave")
EVENT_HIDE = _enum_value(QEvent, "Type", "Hide")
EVENT_CLOSE = _enum_value(QEvent, "Type", "Close")

# QtCore.Qt enums
BOTTOM_DOCK_WIDGET_AREA = _enum_value(Qt, "DockWidgetArea", "BottomDockWidgetArea")
ALIGN_RIGHT = _enum_value(Qt, "AlignmentFlag", "AlignRight")
ALIGN_VCENTER = _enum_value(Qt, "AlignmentFlag", "AlignVCenter")
ALIGN_RIGHT_VCENTER = ALIGN_RIGHT | ALIGN_VCENTER
YELLOW = _enum_value(Qt, "GlobalColor", "yellow")
RED = _enum_value(Qt, "GlobalColor", "red")
WAIT_CURSOR = _enum_value(Qt, "CursorShape", "WaitCursor")
LEFT_MOUSE_BUTTON = _enum_value(Qt, "MouseButton", "LeftButton")
KEY_SPACE = _enum_value(Qt, "Key", "Key_Space")
RIGHT_MOUSE_BUTTON = _enum_value(Qt, "MouseButton", "RightButton")
DOWN_ARROW = _enum_value(Qt, "ArrowType", "DownArrow")
ITEM_IS_EDITABLE = _enum_value(Qt, "ItemFlag", "ItemIsEditable")
DASH_LINE = _enum_value(Qt, "PenStyle", "DashLine")
DOT_LINE = _enum_value(Qt, "PenStyle", "DotLine")
DASH_DOT_LINE = _enum_value(Qt, "PenStyle", "DashDotLine")
PEN_STYLE_BY_NAME = {
    "--": DASH_LINE,
    ":": DOT_LINE,
    "-.": DASH_DOT_LINE,
}

# Qt window flags
POPUP_WINDOW_FLAG = _enum_value(Qt, "WindowType", "Popup")


# QFrame enums
FRAME_SHAPE_STYLED_PANEL = _enum_value(QFrame, "Shape", "StyledPanel")

# QSizePolicy enums
SIZE_POLICY_FIXED = _enum_value(QSizePolicy, "Policy", "Fixed")
SIZE_POLICY_MAXIMUM = _enum_value(QSizePolicy, "Policy", "Maximum")
SIZE_POLICY_EXPANDING = _enum_value(QSizePolicy, "Policy", "Expanding")
SIZE_POLICY_PREFERRED = _enum_value(QSizePolicy, "Policy", "Preferred")

# QToolButton enums
TOOL_BUTTON_INSTANT_POPUP = _enum_value(
    QToolButton,
    "ToolButtonPopupMode",
    "InstantPopup",
)
TOOL_BUTTON_MENU_BUTTON_POPUP = _enum_value(
    QToolButton,
    "ToolButtonPopupMode",
    "MenuButtonPopup",
)

# QMessageBox enums
MESSAGE_ICON_INFORMATION = _enum_value(QMessageBox, "Icon", "Information")
MESSAGE_ICON_CRITICAL = _enum_value(QMessageBox, "Icon", "Critical")
MESSAGE_ICON_WARNING = _enum_value(QMessageBox, "Icon", "Warning")
MESSAGE_BUTTON_OK = _enum_value(QMessageBox, "StandardButton", "Ok")

# QColorDialog enums
DONT_USE_NATIVE_DIALOG = _enum_value(QColorDialog, "ColorDialogOption", "DontUseNativeDialog")

# QGIS enums with scoped/legacy compatibility. These are only available inside QGIS.
POLYGON_GEOMETRY = (
    _enum_value(QgsWkbTypes, "GeometryType", "PolygonGeometry")
    if QgsWkbTypes is not None else None
)
VECTOR_LAYER = (
    _enum_value(QgsMapLayer, "LayerType", "VectorLayer")
    if QgsMapLayer is not None else None
)
RASTER_LAYER = (
    _enum_value(QgsMapLayer, "LayerType", "RasterLayer")
    if QgsMapLayer is not None else None
)


def exec_dialog(dialog):
    """Execute a Qt dialog across PyQt5/PyQt6 bindings."""
    if hasattr(dialog, "exec"):
        return dialog.exec()
    return dialog.exec_()


def available_screen_geometry(global_point, widget=None):
    """Return available screen geometry for a global point across Qt 5 and Qt 6."""
    screen_at = getattr(QGuiApplication, "screenAt", None)
    screen = screen_at(global_point) if callable(screen_at) else None
    if screen is None:  # Qt 5 fallback and headless-safe primary-screen fallback.
        screen = QGuiApplication.primaryScreen()
    if screen is not None:
        return screen.availableGeometry()

    desktop = getattr(QApplication, "desktop", lambda: None)()
    if desktop is not None:
        return desktop.availableGeometry(widget) if widget is not None else desktop.availableGeometry()
    return QRect(global_point, global_point)


def screen_aware_popup_position(anchor_rect, popup_size, available_geometry):
    """Place a popup below its anchor, or above it, then clamp it to the screen."""
    width = max(0, popup_size.width())
    height = max(0, popup_size.height())
    left = available_geometry.left()
    top = available_geometry.top()
    right = available_geometry.right() + 1
    bottom = available_geometry.bottom() + 1

    x = anchor_rect.left()
    below_y = anchor_rect.bottom() + 1
    above_y = anchor_rect.top() - height
    if below_y + height <= bottom:
        y = below_y
    elif above_y >= top:
        y = above_y
    else:
        y = below_y

    x = min(max(x, left), max(left, right - width))
    y = min(max(y, top), max(top, bottom - height))
    return QPoint(x, y)


def configure_compact_command_button(button, size=24, icon_size=16):
    """Apply the shared compact appearance for momentary command buttons."""
    button.setCheckable(False)
    set_flat = getattr(button, "setFlat", None)
    if callable(set_flat):
        set_flat(False)
    button.setFixedSize(size, size)
    button.setIconSize(QSize(icon_size, icon_size))
    button.setSizePolicy(SIZE_POLICY_FIXED, SIZE_POLICY_FIXED)
    return button
