"""Immutable committed time-series copy/paste snapshots and narrow updates."""

from dataclasses import dataclass, replace
from enum import Enum
from uuid import UUID

from ..models.time_series import SeriesLegendSettings, SpatialSelectionKind, TimeSeriesRecord
from .settings.model import (
    EnsembleStyleSettings, FitStyleSettings, ReplicaStyleSettings,
    ResidualStyleSettings, SeriesStyleSettings,
)
from ..models.time_series import FitConfiguration, ReplicaConfiguration


class CopyPasteCategory(str, Enum):
    """Supported committed-record presentation clipboard categories."""

    STYLE = "style"
    FIT = "fit"
    REPLICA = "replica"
    Y_AXIS = "y_axis"
    LEGEND = "legend"
    ALL_PRESENTATION = "all_presentation"


@dataclass(frozen=True)
class StyleSnapshot:
    """Main-series and ensemble presentation only."""

    series: SeriesStyleSettings
    ensemble: EnsembleStyleSettings


@dataclass(frozen=True)
class FitSnapshot:
    """Fit/residual configuration and presentation without calculated output."""

    configuration: FitConfiguration
    fit_style: FitStyleSettings
    residual_style: ResidualStyleSettings


@dataclass(frozen=True)
class ReplicaSnapshot:
    """Replica configuration and presentation without calculated output."""

    configuration: ReplicaConfiguration
    style: ReplicaStyleSettings


@dataclass(frozen=True)
class YAxisSideSnapshot:
    """Per-series Y-axis assignment only; no plot/domain range state."""

    side: str


@dataclass(frozen=True)
class LegendEntrySnapshot:
    """Per-series legend-entry configuration without record identity or attributes."""

    settings: SeriesLegendSettings


@dataclass(frozen=True)
class TimeSeriesSettingsClipboard:
    """One coherent, immutable settings capture from a committed source."""

    source_record_id: UUID
    style: StyleSnapshot
    fit: FitSnapshot
    replica: ReplicaSnapshot
    y_axis: YAxisSideSnapshot
    legend: LegendEntrySnapshot

    def has(self, category: CopyPasteCategory) -> bool:
        """Return whether a supported paste category is available."""
        return category in (
            CopyPasteCategory.STYLE,
            CopyPasteCategory.FIT,
            CopyPasteCategory.REPLICA,
            CopyPasteCategory.Y_AXIS,
            CopyPasteCategory.LEGEND,
            CopyPasteCategory.ALL_PRESENTATION,
        )


def capture_style(record: TimeSeriesRecord) -> StyleSnapshot:
    """Capture immutable main-series presentation from one record."""
    return StyleSnapshot(record.presentation.series, record.presentation.ensemble)


def capture_fit(record: TimeSeriesRecord) -> FitSnapshot:
    """Capture immutable Fit/residual settings from one record."""
    return FitSnapshot(record.analysis.fit, record.presentation.fit, record.presentation.residual)


def capture_replica(record: TimeSeriesRecord) -> ReplicaSnapshot:
    """Capture immutable Replica settings from one record."""
    return ReplicaSnapshot(record.analysis.replica, record.presentation.replica)


def capture_y_axis_side(record: TimeSeriesRecord) -> YAxisSideSnapshot:
    """Capture only the record-owned Left/Right Y-axis assignment."""
    return YAxisSideSnapshot(record.presentation.y_axis_side)


def capture_legend_entry(record: TimeSeriesRecord) -> LegendEntrySnapshot:
    """Capture only the current per-series legend-entry configuration."""
    return LegendEntrySnapshot(record.presentation.legend)


def apply_style_snapshot(record: TimeSeriesRecord, snapshot: StyleSnapshot) -> TimeSeriesRecord:
    """Replace only main-series and ensemble presentation fields."""
    return replace(record, presentation=replace(
        record.presentation, series=snapshot.series, ensemble=snapshot.ensemble
    ))


def apply_fit_snapshot(record: TimeSeriesRecord, snapshot: FitSnapshot) -> TimeSeriesRecord:
    """Replace only Fit/residual configuration and presentation."""
    return replace(
        record,
        data=record.data.withResiduals(None),
        analysis=replace(record.analysis, fit=snapshot.configuration),
        presentation=replace(
            record.presentation, fit=snapshot.fit_style, residual=snapshot.residual_style
        ),
    )


def apply_replica_snapshot(record: TimeSeriesRecord, snapshot: ReplicaSnapshot) -> TimeSeriesRecord:
    """Replace only Replica configuration and presentation."""
    return replace(
        record,
        analysis=replace(record.analysis, replica=snapshot.configuration),
        presentation=replace(record.presentation, replica=snapshot.style),
    )


def _legend_field_is_available(record: TimeSeriesRecord, field_name: str) -> bool:
    """Return whether a copied field is present in the record-owned snapshots."""
    return (
        field_name in record.target_attributes.field_names()
        or field_name in record.reference_attributes.field_names()
    )


def apply_y_axis_side_snapshot(
    record: TimeSeriesRecord, snapshot: YAxisSideSnapshot
) -> TimeSeriesRecord:
    """Replace only the per-series Y-axis side, normalized by presentation state."""
    side = str(snapshot.side).strip().lower()
    if side not in {"left", "right"}:
        side = "left"
    return replace(
        record, presentation=replace(record.presentation, y_axis_side=side)
    )


def apply_legend_entry_snapshot(record: TimeSeriesRecord, snapshot: LegendEntrySnapshot) -> TimeSeriesRecord:
    """Replace compatible legend settings while keeping destination identity intact."""
    copied = snapshot.settings
    current = record.presentation.legend
    if record.target is not None and record.target.kind == SpatialSelectionKind.POLYGON:
        settings = replace(
            current,
            field_name=None,
            include_label=True,
            include_field=False,
            include_fit=copied.include_fit,
            include_replica=copied.include_replica,
            include_ensemble=copied.include_ensemble,
            use_label_only=copied.use_label_only,
        )
    elif copied.field_name and _legend_field_is_available(record, copied.field_name):
        settings = copied
    else:
        settings = replace(
            current,
            include_label=True,
            include_field=False,
            include_fit=copied.include_fit,
            include_replica=copied.include_replica,
            include_ensemble=copied.include_ensemble,
            use_label_only=copied.use_label_only,
        )
    return replace(record, presentation=replace(record.presentation, legend=settings))
