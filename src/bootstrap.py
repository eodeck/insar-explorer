"""Application composition for time-series settings dependencies."""

from dataclasses import dataclass
import os

from .time_series.persistence import (
    NullProjectStateRepository,
    ProjectStateRepository,
    UserPreferencesRepository,
    build_runtime_settings,
)
from .time_series.settings.model import TimeSeriesSettingsModel


@dataclass(frozen=True)
class TimeSeriesServices:
    """Composed time-series dependencies supplied to application objects."""

    user_preferences: UserPreferencesRepository
    project_state_repository: ProjectStateRepository
    settings_model: TimeSeriesSettingsModel


def create_time_series_services(plugin_dir, diagnostic=None):
    """Compose QSettings preferences with one-time legacy JSON migration."""
    from .time_series.persistence import (
        LegacyPreferencesMigrator, QSettingsUserPreferencesRepository,
    )
    from .time_series.persistence.legacy_json import LegacyJsonUserPreferencesRepository

    config_path = os.path.join(plugin_dir, "src", "config", "config.json")
    user_preferences = QSettingsUserPreferencesRepository(diagnostic=diagnostic)
    legacy = LegacyJsonUserPreferencesRepository(config_path)
    LegacyPreferencesMigrator(
        user_preferences,
        legacy_repository=legacy,
        legacy_path=config_path,
        diagnostic=diagnostic,
    ).migrate_if_needed()
    preferences = user_preferences.load()
    return TimeSeriesServices(
        user_preferences=user_preferences,
        project_state_repository=NullProjectStateRepository(),
        settings_model=build_runtime_settings(preferences),
    )

def _services_are_complete(services):
    """Return whether an object exposes the complete service bundle contract."""
    return all(
        getattr(services, name, None) is not None
        for name in (
            "user_preferences",
            "project_state_repository",
            "settings_model",
        )
    )


def ensure_time_series_services(plugin):
    """Return reset-safe composed services for one plugin instance.

    Existing complete services are reused by identity. Plugin instances created
    before Phase 07, or instances whose bundle is incomplete, are repaired by
    composing and attaching one bundle from ``plugin.plugin_dir``.
    """
    services = getattr(plugin, "time_series_services", None)
    if _services_are_complete(services):
        return services

    plugin_dir = getattr(plugin, "plugin_dir", None)
    if not plugin_dir:
        raise RuntimeError(
            "Cannot compose time-series services without plugin_dir"
        )

    diagnostic = getattr(plugin, "report_time_series_diagnostic", None)
    services = create_time_series_services(plugin_dir, diagnostic=diagnostic)
    plugin.time_series_services = services
    return services

