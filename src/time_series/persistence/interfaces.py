"""Dependency-light persistence contracts for time-series settings scopes."""

from dataclasses import dataclass, field
from typing import Optional, Protocol
from uuid import UUID

from ...models.time_series import TimeSeriesRecord
from ..settings.model import (
    AppearanceSettings, EnsembleStyleSettings, ExportSettings, FitStyleSettings,
    ReplicaSettings, ResidualStyleSettings, SeriesStyleSettings,
)


@dataclass(frozen=True)
class TimeSeriesUserPreferences:
    """Persisted user defaults and global time-series preferences."""

    series_defaults: SeriesStyleSettings = field(default_factory=SeriesStyleSettings)
    ensemble_defaults: EnsembleStyleSettings = field(default_factory=EnsembleStyleSettings)
    fit_defaults: FitStyleSettings = field(default_factory=FitStyleSettings)
    residual_defaults: ResidualStyleSettings = field(default_factory=ResidualStyleSettings)
    replica_defaults: ReplicaSettings = field(default_factory=ReplicaSettings)
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)
    export: ExportSettings = field(default_factory=ExportSettings)


@dataclass(frozen=True)
class TimeSeriesProjectState:
    """Versioned project-owned state; record serialization is implemented later."""

    schema_version: int = 1
    records: tuple[TimeSeriesRecord, ...] = ()
    active_id: Optional[UUID] = None


class PreferencesPersistenceError(RuntimeError):
    """Raised when user preferences cannot be loaded or saved safely."""


class UserPreferencesRepository(Protocol):
    """Load and save typed user defaults and application preferences."""

    def load(self) -> TimeSeriesUserPreferences: ...
    def save_series_defaults(self, settings: SeriesStyleSettings) -> None: ...
    def save_ensemble_defaults(self, settings: EnsembleStyleSettings) -> None: ...
    def save_fit_defaults(self, settings: FitStyleSettings) -> None: ...
    def save_residual_defaults(self, settings: ResidualStyleSettings) -> None: ...
    def save_replica_defaults(self, settings: ReplicaSettings) -> None: ...
    def save_appearance(self, settings: AppearanceSettings) -> None: ...
    def save_export(self, settings: ExportSettings) -> None: ...


class ProjectStateRepository(Protocol):
    """Persistence boundary for project-owned time-series state."""

    def load_time_series_state(self) -> Optional[TimeSeriesProjectState]: ...
    def save_time_series_state(self, state: TimeSeriesProjectState) -> None: ...
    def clear_time_series_state(self) -> None: ...


class NullProjectStateRepository:
    """No-op project-state adapter used until versioned serialization is approved."""

    def load_time_series_state(self):
        return None

    def save_time_series_state(self, state):
        return None

    def clear_time_series_state(self):
        return None
