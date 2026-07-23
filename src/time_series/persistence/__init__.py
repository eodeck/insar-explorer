"""Typed persistence boundaries for time-series settings scopes."""

from .factory_defaults import build_runtime_settings, factory_user_preferences
from .qsettings import QSettingsUserPreferencesRepository
from .migration import LegacyPreferencesMigrator
from .interfaces import (
    NullProjectStateRepository, PreferencesPersistenceError,
    ProjectStateRepository, TimeSeriesProjectState, TimeSeriesUserPreferences,
    UserPreferencesRepository,
)

__all__ = [
    "build_runtime_settings", "factory_user_preferences",
    "NullProjectStateRepository", "PreferencesPersistenceError",
    "ProjectStateRepository", "TimeSeriesProjectState",
    "TimeSeriesUserPreferences", "UserPreferencesRepository",
    "QSettingsUserPreferencesRepository", "LegacyPreferencesMigrator",
]
