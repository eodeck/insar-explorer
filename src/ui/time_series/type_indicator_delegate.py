"""Presentation delegate for non-interactive time-series type indicators."""

from qgis.PyQt import QtWidgets

from ...qt_compat import (
    STYLE_STATE_HAS_FOCUS,
    STYLE_STATE_MOUSE_OVER,
    STYLE_STATE_SELECTED,
)


class TimeSeriesTypeIndicatorDelegate(QtWidgets.QStyledItemDelegate):
    """Paint centred status decorations without selection or button-like chrome."""

    def paint(self, painter, option, index):
        """Paint the model decoration while suppressing interactive cell states."""
        clean_option = QtWidgets.QStyleOptionViewItem(option)
        clean_option.state &= ~(
            STYLE_STATE_SELECTED | STYLE_STATE_HAS_FOCUS | STYLE_STATE_MOUSE_OVER
        )
        self.initStyleOption(clean_option, index)
        clean_option.state &= ~(
            STYLE_STATE_SELECTED | STYLE_STATE_HAS_FOCUS | STYLE_STATE_MOUSE_OVER
        )
        super(TimeSeriesTypeIndicatorDelegate, self).paint(
            painter, clean_option, index
        )
