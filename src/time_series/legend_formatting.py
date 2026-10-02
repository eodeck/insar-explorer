"""Pure record-owned text resolution for native time-series legends."""

from __future__ import annotations

import math


LEGEND_SEPARATOR = " · "


def base_series_legend_label(record):
    """Return the mandatory label used for stable related-entry names."""
    return (record.presentation.label or "").strip() or "Unnamed"


def _display_value(value):
    """Return a safe compact value or ``None`` for unavailable attributes."""
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    text = str(value).strip()
    return text or None


def _format_field_block(prefix, suffix, values):
    """Apply normalized field affixes once around one or more value parts."""
    prefix = str(prefix or "").strip()
    suffix = str(suffix or "").strip()
    value_block = LEGEND_SEPARATOR.join(values)
    return " ".join(part for part in (prefix, value_block, suffix) if part)


def format_series_legend_label(record):
    """Format one base label using immutable record snapshots only.

    Missing selected-field values are omitted.  A target-only value is shown
    without a marker; when both target and reference values are available,
    explicit ``T:`` and ``R:`` markers avoid implying a numeric difference.
    """
    label = base_series_legend_label(record)
    settings = record.presentation.legend
    label = label if settings.include_label else ""
    if (not settings.include_field or not settings.field_name or record.target is None
            or record.target.kind.value != "point"):
        return label
    target = _display_value(record.target_attributes.value(settings.field_name))
    reference = _display_value(record.reference_attributes.value(settings.field_name))
    if target is not None and reference is not None:
        field_text = _format_field_block(
            settings.prefix, settings.suffix, ("T: " + target, "R: " + reference)
        )
        return LEGEND_SEPARATOR.join(part for part in (label, field_text) if part)
    if target is not None:
        field_text = _format_field_block(settings.prefix, settings.suffix, (target,))
        return LEGEND_SEPARATOR.join(part for part in (label, field_text) if part)
    if reference is not None:
        field_text = _format_field_block(settings.prefix, settings.suffix, ("R: " + reference,))
        return LEGEND_SEPARATOR.join(part for part in (label, field_text) if part)
    return label
