"""Reusable joined split-button control for compact toolbars."""

from qgis.PyQt.QtCore import QObject, QSize, QTimer, pyqtSignal
from qgis.PyQt.QtGui import QCursor, QIcon
from qgis.PyQt.QtWidgets import QApplication, QHBoxLayout, QToolButton, QWidget

from ...qt_compat import (
    DOWN_ARROW,
    EVENT_CLOSE,
    EVENT_ENTER,
    EVENT_HIDE,
    EVENT_LEAVE,
)


SPLIT_TOOL_BUTTON_STYLESHEET = """
QToolButton[splitPart="primary"],
QToolButton[splitPart="secondary"] {
    margin: 0;
    padding: 0;
}
QToolButton[visualRole="flat"] {
    border: 1px solid transparent;
    background: transparent;
}
QToolButton[visualRole="command"] {
    border: 1px solid palette(mid);
    background-color: palette(button);
    color: palette(button-text);
}
QToolButton[splitPosition="left"] {
    border-top-left-radius: 3px;
    border-bottom-left-radius: 3px;
    border-top-right-radius: 0;
    border-bottom-right-radius: 0;
}
QToolButton[splitPosition="right"] {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}
QToolButton[visualRole="flat"][splitPosition="right"] {
    border-left-color: palette(midlight);
}
QToolButton[visualRole="flat"][splitPart="primary"][splitHover="true"],
QToolButton[visualRole="flat"][splitPart="secondary"][splitHover="true"] {
    background-color: palette(alternate-base);
    border-top-color: palette(mid);
    border-bottom-color: palette(mid);
}
QToolButton[visualRole="command"][splitHover="true"] {
    background-color: palette(alternate-base);
}
QToolButton[visualRole="command"]:focus {
    border-color: palette(highlight);
}
QToolButton[visualRole="command"]:disabled {
    background-color: palette(window);
    color: palette(mid);
    border-color: palette(midlight);
}
QToolButton[visualRole="command"][splitPosition="left"] {
    border-right: 0;
}
QToolButton[visualRole="command"][splitPosition="right"] {
    border-left: 1px solid palette(mid);
}
QToolButton[splitPosition="left"][splitHover="true"] {
    border-left-color: palette(mid);
}
QToolButton[splitPosition="right"][splitHover="true"] {
    border-left-color: palette(mid);
    border-right-color: palette(mid);
}
QToolButton[splitPosition="right"][splitChecked="true"] {
    border-left-color: palette(highlighted-text);
}
QToolButton[splitPart="primary"]:checked,
QToolButton[splitPart="primary"]:checked[splitHover="true"] {
    border-color: palette(highlight);
    background-color: palette(highlight);
    color: palette(highlighted-text);
}
QToolButton[visualRole="command"][splitPart]:pressed:enabled {
    background-color: palette(mid);
    border-top-color: palette(dark);
    border-bottom-color: palette(dark);
}
QToolButton[visualRole="command"][splitPosition="left"]:pressed:enabled {
    border-left-color: palette(dark);
    border-right: 0;
}
QToolButton[visualRole="command"][splitPosition="right"]:pressed:enabled {
    border-left: 1px solid palette(dark);
    border-right-color: palette(dark);
}
"""


class SplitToolButton(QWidget):
    """Toolbar split button with a primary action and secondary action."""

    primaryTriggered = pyqtSignal()
    primaryToggled = pyqtSignal(bool)
    secondaryTriggered = pyqtSignal()

    Left = "left"
    Right = "right"

    Flat = "flat"
    Command = "command"

    PRIMARY_WIDTH = 28
    SECONDARY_WIDTH = 15
    TOTAL_WIDTH = PRIMARY_WIDTH + SECONDARY_WIDTH
    HEIGHT = 22

    def __init__(
        self,
        icon=None,
        primary_checkable=False,
        parent=None,
        object_name="split_tool_button",
        arrow_side=Right,
        visual_role=Flat,
    ):
        """Build a compact joined control with independent action regions."""
        if arrow_side not in (self.Left, self.Right):
            raise ValueError(
                "arrow_side must be SplitToolButton.Left or SplitToolButton.Right"
            )
        if visual_role not in (self.Flat, self.Command):
            raise ValueError(
                "visual_role must be SplitToolButton.Flat or "
                "SplitToolButton.Command"
            )

        super().__init__(parent)
        self.arrow_side = arrow_side
        self.visual_role = visual_role
        self.setProperty("visualRole", visual_role)
        self.setObjectName(object_name)
        self.setFixedSize(self.TOTAL_WIDTH, self.HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.primary_button = QToolButton(self)
        self.primary_button.setObjectName(f"{object_name}_primary")
        self.primary_button.setProperty("splitPart", "primary")
        self.primary_button.setProperty("visualRole", visual_role)
        self.primary_button.setCheckable(bool(primary_checkable))
        self.primary_button.setAutoRaise(visual_role == self.Flat)
        self.primary_button.setFixedSize(self.PRIMARY_WIDTH, self.HEIGHT)
        if icon is not None:
            self.primary_button.setIcon(icon if isinstance(icon, QIcon) else QIcon(icon))

        self.secondary_button = QToolButton(self)
        self.secondary_button.setObjectName(f"{object_name}_secondary")
        self.secondary_button.setProperty("splitPart", "secondary")
        self.secondary_button.setProperty("visualRole", visual_role)
        self.secondary_button.setCheckable(False)
        self.secondary_button.setAutoRaise(visual_role == self.Flat)
        self.secondary_button.setArrowType(DOWN_ARROW)
        self.secondary_button.setFixedSize(self.SECONDARY_WIDTH, self.HEIGHT)

        self._hover_reconcile_timer = QTimer(self)
        self._hover_reconcile_timer.setSingleShot(True)
        self._hover_reconcile_timer.timeout.connect(self.reconcileHoverFromCursor)

        self.secondary_button.setProperty("splitChecked", False)
        for button in (self.primary_button, self.secondary_button):
            button.setProperty("splitHover", False)
            button.installEventFilter(self)

        if self.arrow_side == self.Left:
            left_button = self.secondary_button
            right_button = self.primary_button
        else:
            left_button = self.primary_button
            right_button = self.secondary_button

        left_button.setProperty("splitPosition", "left")
        right_button.setProperty("splitPosition", "right")

        self.setStyleSheet(SPLIT_TOOL_BUTTON_STYLESHEET)
        layout.addWidget(left_button)
        layout.addWidget(right_button)
        QWidget.setTabOrder(left_button, right_button)

        self.primary_button.clicked.connect(self.primaryTriggered.emit)
        self.primary_button.toggled.connect(self._onPrimaryToggled)
        self.secondary_button.clicked.connect(self.secondaryTriggered.emit)

    def visualRole(self):
        """Return the configured visual role."""
        return self.visual_role

    def eventFilter(self, watched, event):
        """Keep hover presentation unified while crossing child boundaries."""
        if watched in (self.primary_button, self.secondary_button):
            if event.type() == EVENT_ENTER:
                self._setUnifiedHover(True)
            elif event.type() == EVENT_LEAVE:
                self._hover_reconcile_timer.start(0)
        return super().eventFilter(watched, event)

    def reconcileHoverFromCursor(self):
        """Recompute shared hover from the widget currently under the cursor."""
        widget = QApplication.widgetAt(QCursor.pos())
        hovered = (
            self.isVisible()
            and self.isEnabled()
            and widget is not None
            and (widget is self or self.isAncestorOf(widget))
        )
        self._setUnifiedHover(hovered)

    def _onPrimaryToggled(self, checked):
        """Synchronize checked presentation before emitting user intent."""
        self._setSecondaryCheckedState(checked)
        self.primaryToggled.emit(bool(checked))

    def _setSecondaryCheckedState(self, checked):
        """Mirror primary checked state onto secondary styling only."""
        checked = bool(checked)
        if self.secondary_button.property("splitChecked") == checked:
            return
        self.secondary_button.setProperty("splitChecked", checked)
        self._refreshStyle(self.secondary_button)

    def _setUnifiedHover(self, hovered):
        """Apply the shared hover property to both split regions."""
        hovered = bool(hovered)
        for button in (self.primary_button, self.secondary_button):
            if button.property("splitHover") == hovered:
                continue
            button.setProperty("splitHover", hovered)
            self._refreshStyle(button)

    @staticmethod
    def _refreshStyle(widget):
        """Reapply dynamic-property stylesheet selectors to a widget."""
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def setChecked(self, checked):
        """Set primary checked state without emitting user-action signals."""
        previous = self.primary_button.blockSignals(True)
        try:
            self.primary_button.setChecked(bool(checked))
        finally:
            self.primary_button.blockSignals(previous)
        self._setSecondaryCheckedState(checked)
        self._refreshStyle(self.primary_button)

    def isChecked(self):
        """Return the primary checked state."""
        return self.primary_button.isChecked()

    def setPrimaryEnabled(self, enabled):
        """Enable or disable the primary action region."""
        self.primary_button.setEnabled(bool(enabled))
        self._clearHoverIfInactive()

    def setSecondaryEnabled(self, enabled):
        """Enable or disable the secondary action region."""
        self.secondary_button.setEnabled(bool(enabled))
        self._clearHoverIfInactive()

    def setPrimaryToolTip(self, text):
        """Set the primary action tooltip."""
        self.primary_button.setToolTip(text)

    def setSecondaryToolTip(self, text):
        """Set the secondary action tooltip."""
        self.secondary_button.setToolTip(text)

    def setPrimaryStatusTip(self, text):
        """Set the primary action status tip."""
        self.primary_button.setStatusTip(text)

    def setPrimaryAccessibleName(self, text):
        """Set the primary action accessible name."""
        self.primary_button.setAccessibleName(text)

    def setPrimaryAccessibleDescription(self, text):
        """Set the primary action accessible description."""
        self.primary_button.setAccessibleDescription(text)

    def setSecondaryAccessibleName(self, text):
        """Set the secondary action accessible name."""
        self.secondary_button.setAccessibleName(text)

    def setSecondaryAccessibleDescription(self, text):
        """Set the secondary action accessible description."""
        self.secondary_button.setAccessibleDescription(text)

    def setPrimaryIcon(self, icon):
        """Set the primary action icon without exposing the child button."""
        self.primary_button.setIcon(icon)

    def setIconSize(self, size):
        """Set the primary action icon size."""
        self.primary_button.setIconSize(size if isinstance(size, QSize) else QSize(size, size))

    def hideEvent(self, event):
        """Clear transient hover presentation when the control is hidden."""
        self._setUnifiedHover(False)
        super().hideEvent(event)

    def setEnabled(self, enabled):
        """Clear transient hover presentation when disabling the control."""
        if not enabled:
            self._setUnifiedHover(False)
        super().setEnabled(enabled)

    def _clearHoverIfInactive(self):
        """Clear shared hover when neither action region remains enabled."""
        if not self.primary_button.isEnabled() and not self.secondary_button.isEnabled():
            self._setUnifiedHover(False)

class SplitButtonPopupHoverReconciler(QObject):
    """Reconcile one split button after an associated popup disappears."""

    def __init__(self, split_button, parent=None):
        """Observe popup lifecycle events for ``split_button``."""
        super().__init__(parent)
        self._split_button = split_button

    def eventFilter(self, watched, event):
        """Schedule cursor-based hover reconciliation after hide or close."""
        if event.type() in (EVENT_HIDE, EVENT_CLOSE):
            QTimer.singleShot(0, self._split_button.reconcileHoverFromCursor)
        return super().eventFilter(watched, event)

