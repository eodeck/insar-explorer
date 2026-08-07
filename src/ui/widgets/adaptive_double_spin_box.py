"""Compact double spin box with adaptive trailing-zero display."""

from qgis.PyQt import QtWidgets


class AdaptiveDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """Display only meaningful decimals while retaining configured precision."""

    def textFromValue(self, value):
        """Format *value* with at least one and at most configured decimals."""
        text = super(AdaptiveDoubleSpinBox, self).textFromValue(value)
        decimal_point = self.locale().decimalPoint()
        if decimal_point not in text:
            return text

        integer_part, fractional_part = text.rsplit(decimal_point, 1)
        fractional_part = fractional_part.rstrip("0") or "0"
        return decimal_point.join((integer_part, fractional_part))
