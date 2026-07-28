"""Canonical resolution for session-only manual Y-axis bounds."""

import math


def resolve_manual_y_range(data_lower, data_upper, manual_lower=None, manual_upper=None):
    """Resolve a Manual-mode Y range or return ``None`` when it is unusable.

    ``None`` manual endpoints follow the corresponding finite data endpoint.
    A flat data range is expanded only for the fully automatic Auto/Auto case,
    matching the established Manual rendering fallback without padding mixed or
    explicitly manual bounds.
    """
    try:
        data_lower = float(data_lower)
        data_upper = float(data_upper)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(data_lower) and math.isfinite(data_upper)):
        return None
    if data_lower > data_upper:
        return None

    lower_is_auto = manual_lower is None
    upper_is_auto = manual_upper is None
    lower = data_lower if lower_is_auto else manual_lower
    upper = data_upper if upper_is_auto else manual_upper
    try:
        lower = float(lower)
        upper = float(upper)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lower) and math.isfinite(upper)):
        return None

    if lower == upper and lower_is_auto and upper_is_auto:
        return lower - 1.0, upper + 1.0
    if lower >= upper:
        return None
    return lower, upper


def resolve_y_axis_display_range(
    data_lower, data_upper, manual_lower=None, manual_upper=None,
):
    """Return ``(lower, upper, padding)`` for one independently rendered Y axis.

    A fully automatic axis uses the canonical From Data presentation, including
    its normal pyqtgraph padding.  Any explicit Manual endpoint uses the shared
    Manual resolver and zero presentation padding so manual values remain exact.
    ``None`` is returned when the effective range is unusable.
    """
    fully_auto = manual_lower is None and manual_upper is None
    resolved = resolve_manual_y_range(
        data_lower, data_upper, manual_lower, manual_upper
    )
    if resolved is None:
        return None
    lower, upper = resolved
    return lower, upper, 0.05 if fully_auto else 0.0
