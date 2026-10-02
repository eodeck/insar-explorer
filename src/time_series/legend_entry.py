"""Pure initialisation rules for immutable per-series legend entry state."""

from __future__ import annotations

from ..models.time_series import PointAttributeSnapshot, SeriesLegendSettings
from .settings.model import LegendEntryDefaults, RelatedLegendDefaults
from .velocity_fields import get_velocity_field_name


def resolve_initial_legend_settings(
    attributes: PointAttributeSnapshot,
    legend_defaults: LegendEntryDefaults,
    related_defaults: RelatedLegendDefaults,
) -> SeriesLegendSettings:
    """Resolve new-record settings without a live source-layer dependency.

    An explicit user default remains authoritative when its field is available.
    Otherwise, the first available field is selected without applying its
    inclusion preference.  Factory selection uses the same canonical
    velocity-name detection used by the map settings workflow.
    """
    names = attributes.field_names()
    if legend_defaults.configured:
        saved_field_is_available = legend_defaults.field_name in names
        field_name = legend_defaults.field_name if saved_field_is_available else (names[0] if names else None)
        include_field = bool(legend_defaults.include_field and saved_field_is_available)
    else:
        field_name = get_velocity_field_name(names) or (names[0] if names else None)
        include_field = False
    include_label = bool(legend_defaults.include_label or not include_field)
    return SeriesLegendSettings(
        field_name=field_name,
        prefix=legend_defaults.prefix,
        suffix=legend_defaults.suffix,
        include_label=include_label,
        include_field=include_field,
        include_fit=related_defaults.include_fit,
        include_replica=related_defaults.include_replica,
        include_ensemble=related_defaults.include_ensemble,
        use_label_only=related_defaults.use_label_only,
    )
