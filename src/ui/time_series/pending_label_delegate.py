"""Presentation delegate for the editable pending time-series label."""

from qgis.PyQt import QtGui, QtWidgets

from ...qt_compat import (
    STYLE_STATE_HAS_FOCUS,
    STYLE_STATE_MOUSE_OVER,
    STYLE_STATE_SELECTED,
)


class PendingLabelDelegate(QtWidgets.QStyledItemDelegate):
    """Paint a subtle hover-only affordance for the editable Label cell."""

    HOVER_ALPHA = 24

    def paint(self, painter, option, index):
        """Paint native label text with a palette-derived hover background."""
        clean_option = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(clean_option, index)

        if clean_option.state & STYLE_STATE_MOUSE_OVER:
            highlight = clean_option.palette.color(self._highlight_role())
            hover_colour = QtGui.QColor(highlight)
            hover_colour.setAlpha(self.HOVER_ALPHA)
            painter.save()
            painter.fillRect(clean_option.rect, hover_colour)
            painter.restore()

        clean_option.state &= ~(
            STYLE_STATE_SELECTED | STYLE_STATE_HAS_FOCUS | STYLE_STATE_MOUSE_OVER
        )
        super(PendingLabelDelegate, self).paint(painter, clean_option, index)

    @staticmethod
    def _highlight_role():
        """Return the palette Highlight role under Qt5 and Qt6 enum layouts."""
        role_enum = getattr(QtGui.QPalette, "ColorRole", QtGui.QPalette)
        return role_enum.Highlight
