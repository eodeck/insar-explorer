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

    An explicit user default is authoritative, even when its field is missing
    from this source.  Factory selection uses the same canonical velocity-name
    detection used by the map settings workflow.
    """
    names = attributes.field_names()
    if legend_defaults.configured:
        field_name = legend_defaults.field_name if legend_defaults.field_name in names else None
    else:
        field_name = get_velocity_field_name(names)
    return SeriesLegendSettings(
        field_name=field_name,
        prefix=legend_defaults.prefix,
        suffix=legend_defaults.suffix,
        include_label=legend_defaults.include_label,
        include_fit=related_defaults.include_fit,
        include_replica=related_defaults.include_replica,
        include_ensemble=related_defaults.include_ensemble,
    )
