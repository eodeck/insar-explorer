"""Immutable committed time-series copy/paste snapshots and narrow updates."""

from dataclasses import dataclass, replace
from enum import Enum
from uuid import UUID

from ..models.time_series import TimeSeriesRecord
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
class TimeSeriesSettingsClipboard:
    """One coherent, immutable settings capture from a committed source."""

    source_record_id: UUID
    style: StyleSnapshot
    fit: FitSnapshot
    replica: ReplicaSnapshot

    def has(self, category: CopyPasteCategory) -> bool:
        """Return whether a supported paste category is available."""
        return category in (
            CopyPasteCategory.STYLE,
            CopyPasteCategory.FIT,
            CopyPasteCategory.REPLICA,
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
