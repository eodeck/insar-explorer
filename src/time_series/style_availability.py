"""Selection-aware availability for Time Series style layers."""

from dataclasses import dataclass
from typing import Iterable, Tuple


@dataclass(frozen=True)
class TimeSeriesStyleAvailability:
    """Describe editable style layers for the current snapshot selection."""

    selected_count: int = 0
    series_target_count: int = 0
    fit_target_count: int = 0
    residual_target_count: int = 0
    ensemble_target_count: int = 0
    fit_feature_enabled: bool = False
    residual_feature_enabled: bool = False

    @property
    def series_available(self):
        return self.series_target_count > 0

    @property
    def fit_available(self):
        """Return whether a rendered Fit layer is available for rerendering."""
        return self.fit_target_count > 0

    @property
    def residual_available(self):
        """Return whether a rendered Residual layer is available for rerendering."""
        return self.residual_target_count > 0

    @property
    def fit_style_available(self):
        """Return whether Fit appearance editing is enabled by feature state."""
        return bool(self.fit_feature_enabled)

    @property
    def residual_style_available(self):
        """Return whether Residual appearance editing is enabled by feature state."""
        return bool(self.fit_feature_enabled and self.residual_feature_enabled)

    @property
    def ensemble_available(self):
        return self.ensemble_target_count > 0

    @classmethod
    def fromSelection(cls, snapshots: Iterable, fit_enabled=False, residual_enabled=False):
        """Build availability from model/controller state, never toolbar widgets."""
        selected: Tuple = tuple(snapshots or ())
        count = len(selected)
        ensemble_count = sum(
            1 for snapshot in selected
            if getattr(snapshot, "data", None) is not None
            and snapshot.data.hasEnsembleData()
        )
        return cls(
            selected_count=count,
            series_target_count=count,
            fit_target_count=count if fit_enabled else 0,
            residual_target_count=count if residual_enabled and fit_enabled else 0,
            ensemble_target_count=ensemble_count,
            fit_feature_enabled=bool(fit_enabled),
            residual_feature_enabled=bool(residual_enabled),
        )
