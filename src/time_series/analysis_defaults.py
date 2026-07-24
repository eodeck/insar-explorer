"""Sticky analysis defaults for future time-series records.

This module is UI-independent. It updates typed in-memory defaults and persists
only explicit user actions; record activation and control projection never call
this coordinator.
"""

from typing import Callable, Optional

from ..models.time_series import FitConfiguration, ReplicaConfiguration, TimeSeriesAnalysis
from .persistence.interfaces import PreferencesPersistenceError, UserPreferencesRepository
from .settings.model import FitAnalysisDefaults, ReplicaAnalysisDefaults, TimeSeriesSettingsModel


class StickyAnalysisDefaultsCoordinator:
    """Persist explicit analysis-control actions as future-record defaults."""

    def __init__(
        self,
        settings_model: TimeSeriesSettingsModel,
        repository: UserPreferencesRepository,
        *,
        diagnostic: Optional[Callable[[str, Exception], None]] = None,
        defaults_changed: Optional[Callable[[TimeSeriesAnalysis], None]] = None,
    ) -> None:
        self._settings_model = settings_model
        self._repository = repository
        self._diagnostic = diagnostic
        self._defaults_changed = defaults_changed

    def snapshot(self) -> TimeSeriesAnalysis:
        """Return an immutable analysis snapshot for a future record."""
        fit = self._settings_model.fit_analysis_defaults
        replica = self._settings_model.replica_analysis_defaults
        return TimeSeriesAnalysis(
            fit=FitConfiguration(
                enabled=fit.enabled,
                model=fit.model,
                seasonal=fit.seasonal,
                show_residuals=fit.show_residuals,
            ),
            replica=ReplicaConfiguration(
                enabled=replica.enabled,
                pair_count=replica.pair_count,
                interval_mm=replica.interval_mm,
            ),
        )

    def update_fit(
        self,
        *,
        enabled: bool,
        model: str,
        seasonal: bool,
        show_residuals: bool,
    ) -> FitAnalysisDefaults:
        """Normalize and persist fit defaults from one explicit user action."""
        defaults = FitAnalysisDefaults(
            enabled=enabled,
            model=model,
            seasonal=seasonal,
            show_residuals=show_residuals,
        )
        self._settings_model.replace_domain("fit_analysis_defaults", defaults)
        self._notify_snapshot_changed()
        self._persist(
            lambda: self._repository.save_fit_analysis_defaults(defaults),
            "fit analysis defaults",
        )
        return defaults

    def update_replica(
        self,
        *,
        enabled: bool,
        pair_count: int,
        interval_mm: float,
    ) -> ReplicaAnalysisDefaults:
        """Normalize and persist Replica defaults from one explicit user action."""
        defaults = ReplicaAnalysisDefaults(
            enabled=enabled,
            pair_count=pair_count,
            interval_mm=interval_mm,
        )
        self._settings_model.replace_domain("replica_analysis_defaults", defaults)
        self._notify_snapshot_changed()
        self._persist(
            lambda: self._repository.save_replica_analysis_defaults(defaults),
            "Replica analysis defaults",
        )
        return defaults

    def _notify_snapshot_changed(self) -> None:
        if self._defaults_changed is not None:
            self._defaults_changed(self.snapshot())

    def _persist(self, operation: Callable[[], None], scope: str) -> None:
        try:
            operation()
        except PreferencesPersistenceError as exc:
            if self._diagnostic is not None:
                self._diagnostic(scope, exc)
