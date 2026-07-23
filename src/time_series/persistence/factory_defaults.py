"""Pure factory defaults and runtime-settings construction."""

from copy import deepcopy
from dataclasses import replace

from .interfaces import TimeSeriesUserPreferences
from ..settings.model import ReplicaSettings, TimeSeriesSettingsModel


def factory_user_preferences():
    """Return fresh normalized built-in defaults without external access."""
    return TimeSeriesUserPreferences()


def build_runtime_settings(preferences):
    """Create fresh runtime settings from persisted user preferences."""
    replica = deepcopy(preferences.replica_defaults)
    # Enabled and interval remain session/controller state under the accepted contract.
    replica = replace(replica, enabled=False, interval_mm=ReplicaSettings().interval_mm)
    return TimeSeriesSettingsModel(
        series_defaults=deepcopy(preferences.series_defaults),
        ensemble_defaults=deepcopy(preferences.ensemble_defaults),
        fit_defaults=deepcopy(preferences.fit_defaults),
        residual_defaults=deepcopy(preferences.residual_defaults),
        fit_current=deepcopy(preferences.fit_defaults),
        residual_current=deepcopy(preferences.residual_defaults),
        replica=replica,
        appearance=deepcopy(preferences.appearance),
        export=deepcopy(preferences.export),
    )
