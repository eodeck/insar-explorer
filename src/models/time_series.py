"""Typed models and pure builders for time-series plot state."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, List, Mapping, Optional
from uuid import UUID, uuid4

import numpy as np

try:
    from ..time_series.settings.model import (
        EnsembleStyleSettings,
        FitStyleSettings,
        ReplicaStyleSettings,
        ResidualStyleSettings,
        SeriesStyleSettings,
    )
except ImportError:  # plain-Python test/import compatibility
    from time_series.settings.model import (
        EnsembleStyleSettings,
        FitStyleSettings,
        ReplicaStyleSettings,
        ResidualStyleSettings,
        SeriesStyleSettings,
    )


def randomTimeSeriesColor() -> str:
    """Return a random canonical ``#RRGGBB`` color string."""
    channels = np.random.randint(0, 256, size=3)
    return "#{:02x}{:02x}{:02x}".format(*(int(channel) for channel in channels))


def _readonlyArray(values: Any, *, dtype: Any = None, ndmin: int = 0) -> np.ndarray:
    """Return a defensive, read-only numpy array copy."""
    array = np.array(values, dtype=dtype, copy=True, ndmin=ndmin)
    array.setflags(write=False)
    return array


class SpatialSelectionKind(str, Enum):
    """Supported spatial-selection geometry categories."""

    POINT = "point"
    POLYGON = "polygon"


@dataclass(frozen=True)
class SpatialSelection:
    """Renderer-independent spatial selection used by a time-series record."""

    value: Any
    kind: SpatialSelectionKind

    @classmethod
    def from_legacy(cls, value: Any) -> Optional["SpatialSelection"]:
        """Convert an existing point/polygon selection object into typed state."""
        if value is None:
            return None
        if isinstance(value, cls):
            return value
        kind = SpatialSelectionKind.POLYGON if hasattr(value, "geom") else SpatialSelectionKind.POINT
        return cls(value=value, kind=kind)


@dataclass(frozen=True)
class FitConfiguration:
    """Per-series fit and residual calculation configuration."""

    enabled: bool = False
    model: Optional[str] = None
    seasonal: bool = False
    show_residuals: bool = False


@dataclass(frozen=True)
class ReplicaConfiguration:
    """Per-series replica-generation configuration."""

    enabled: bool = False
    interval_mm: float = 0.0
    pair_count: int = 0


@dataclass(frozen=True)
class TimeSeriesAnalysis:
    """All analysis behavior owned by one time-series record."""

    fit: FitConfiguration = field(default_factory=FitConfiguration)
    replica: ReplicaConfiguration = field(default_factory=ReplicaConfiguration)


@dataclass(frozen=True)
class TimeSeriesData:
    """Numeric properties for one time series, independent of spatial provenance."""

    dates: np.ndarray
    ts_values: np.ndarray
    ref_values: np.ndarray
    plot_values: Optional[np.ndarray] = None
    plot_multiple_values: Optional[np.ndarray] = None
    min_plot_values: Optional[np.ndarray] = None
    max_plot_values: Optional[np.ndarray] = None
    residuals_values: Optional[np.ndarray] = None

    def hasFinitePlotValues(self) -> bool:
        """Return True when at least one plotted value is finite."""
        if self.plot_values is None:
            return False
        values = np.asarray(self.plot_values, dtype=np.float64)
        return bool(np.sum(np.isfinite(values)) > 0)

    def hasEnsembleData(self) -> bool:
        """Return True when this snapshot contains multiple member time series."""
        return bool(
            self.plot_multiple_values is not None
            and np.asarray(self.plot_multiple_values).ndim == 2
            and np.asarray(self.plot_multiple_values).shape[1] > 1
        )

    def dateStrings(self) -> List[str]:
        """Return dates formatted for ASCII export."""
        return [date.strftime('%Y-%m-%d') for date in self.dates]

    def withResiduals(self, residuals_values: Any) -> "TimeSeriesData":
        """Return a copy of this immutable series data with residual values attached."""
        residuals = None if residuals_values is None else _readonlyArray(residuals_values, dtype=float)
        return replace(self, residuals_values=residuals)


@dataclass(frozen=True)
class TimeSeriesPresentation:
    """All renderer-independent presentation state owned by one series."""

    series: SeriesStyleSettings = field(default_factory=SeriesStyleSettings)
    ensemble: EnsembleStyleSettings = field(default_factory=EnsembleStyleSettings)
    fit: FitStyleSettings = field(default_factory=FitStyleSettings)
    residual: ResidualStyleSettings = field(default_factory=ResidualStyleSettings)
    replica: ReplicaStyleSettings = field(default_factory=ReplicaStyleSettings)
    label: Optional[str] = None
    visible: bool = True
    # Reserved metadata for a later layering feature; the Phase 6 renderer
    # does not currently expose or apply per-series z-order editing.
    z_order: Optional[int] = None


def presentation_from_legacy_params(
    params: Optional[Mapping[str, Any]], *, label: Optional[str] = None,
    visible: bool = True, z_order: Optional[int] = None,
) -> TimeSeriesPresentation:
    """Build typed per-series presentation from legacy plot parameters."""
    copied = deepcopy(dict(params)) if isinstance(params, Mapping) else {}
    return TimeSeriesPresentation(
        series=SeriesStyleSettings.from_params(copied),
        ensemble=EnsembleStyleSettings.fromParams(copied),
        fit=FitStyleSettings.fromParams(copied),
        residual=ResidualStyleSettings.fromParams(copied),
        replica=ReplicaStyleSettings.fromParams(copied),
        label=label,
        visible=bool(visible),
        z_order=z_order,
    )


def presentation_to_legacy_params(presentation: TimeSeriesPresentation) -> dict[str, Any]:
    """Build a defensive legacy parameter dictionary for compatibility consumers."""
    plot = {}
    plot.update(presentation.series.as_params())
    plot.update(presentation.ensemble.asParams())
    plot.update(presentation.replica.asParams())
    return {
        "time series plot": deepcopy(plot),
        "model fit": deepcopy(presentation.fit.asParams()),
        "residual plot": deepcopy(presentation.residual.asParams()),
    }


@dataclass(frozen=True)
class TimeSeriesStyle:
    """Defensive compatibility projection of typed per-series presentation."""

    params: dict
    label: Optional[str] = None
    visible: bool = True
    z_order: Optional[int] = None

    @classmethod
    def fromParams(cls, params: Optional[dict], **kwargs: Any) -> "TimeSeriesStyle":
        """Create copied legacy style metadata for compatibility consumers."""
        copied_params = deepcopy(params) if params is not None else {}
        copied_params.get("time series plot", {}).pop("replica pair count", None)
        return cls(params=copied_params, **kwargs)


@dataclass
class DefaultTimeSeriesStyle:
    """Mutable source of typed defaults used only for newly created records."""

    def __init__(self, style: TimeSeriesStyle):
        self._presentation = presentation_from_legacy_params(
            style.params, label=style.label, visible=style.visible, z_order=style.z_order
        )

    @classmethod
    def fromParams(cls, params: Optional[dict]) -> "DefaultTimeSeriesStyle":
        return cls(TimeSeriesStyle.fromParams(params))

    def snapshotPresentation(self) -> TimeSeriesPresentation:
        """Return an immutable presentation snapshot for a newly created record."""
        return replace(self._presentation)

    def snapshotStyle(self) -> TimeSeriesStyle:
        """Return a defensive compatibility projection."""
        presentation = self.snapshotPresentation()
        return TimeSeriesStyle(
            presentation_to_legacy_params(presentation), presentation.label,
            presentation.visible, presentation.z_order,
        )

    def replaceFromSeries(self, style: TimeSeriesStyle) -> None:
        self._presentation = presentation_from_legacy_params(
            style.params, label=style.label, visible=style.visible, z_order=style.z_order
        )

    @property
    def params(self) -> dict:
        return presentation_to_legacy_params(self._presentation)


@dataclass
class TimeSeriesGraphics:
    """Pyqtgraph items associated with one plotted time-series snapshot."""

    scatter: Any = None
    line: Any = None
    plot_multiple_fill: List[Any] = field(default_factory=list)
    plot_multiple_lines: List[Any] = field(default_factory=list)
    replicate_up: List[Any] = field(default_factory=list)
    replicate_dn: List[Any] = field(default_factory=list)
    fit_plot: Any = None
    residual_scatter: Any = None
    residual_line: Any = None
    main_y_data: List[Any] = field(default_factory=list)
    residual_y_data: List[Any] = field(default_factory=list)


@dataclass(frozen=True)
class TimeSeriesRecord:
    """Renderer-independent stored state for one time series."""

    data: TimeSeriesData
    presentation: TimeSeriesPresentation
    analysis: TimeSeriesAnalysis = field(default_factory=TimeSeriesAnalysis)
    id: UUID = field(default_factory=uuid4)
    target: Optional[SpatialSelection] = None
    reference: Optional[SpatialSelection] = None

    def __post_init__(self) -> None:
        """Normalize legacy selection values while preserving immutable ownership."""
        object.__setattr__(self, "target", SpatialSelection.from_legacy(self.target))
        object.__setattr__(self, "reference", SpatialSelection.from_legacy(self.reference))

    @property
    def style(self) -> TimeSeriesStyle:
        """Return a defensive legacy style projection of authoritative presentation."""
        return TimeSeriesStyle(
            presentation_to_legacy_params(self.presentation),
            label=self.presentation.label,
            visible=self.presentation.visible,
            z_order=self.presentation.z_order,
        )


# Transitional compatibility alias; remove after downstream APIs use record terminology.
TimeSeriesSnapshot = TimeSeriesRecord


def _normalizeValueMatrix(
    values: Any,
    *,
    date_count: int,
    sort_idx: np.ndarray,
    name: str,
    allow_scalar_expand: bool,
) -> np.ndarray:
    """Normalize a scalar/vector/matrix into a date-row matrix with explicit validation."""
    if values is None:
        array = np.zeros((date_count, 1), dtype=float)
    else:
        raw = np.array(values, dtype=float, copy=True)
        if raw.ndim == 0:
            if allow_scalar_expand:
                array = np.full((date_count, 1), float(raw), dtype=float)
            elif date_count == 1:
                array = raw.reshape(1, 1)
            else:
                raise ValueError(f"{name} row count must match dates length")
        elif raw.ndim == 1:
            if raw.size == date_count:
                array = raw.reshape(date_count, 1)
            elif allow_scalar_expand and raw.size == 1:
                array = np.full((date_count, 1), float(raw[0]), dtype=float)
            else:
                raise ValueError(f"{name} row count must match dates length")
        elif raw.ndim == 2:
            if raw.shape[0] == date_count:
                array = raw
            elif raw.shape[1] == date_count:
                array = raw.T
            elif allow_scalar_expand and raw.shape == (1, 1):
                array = np.full((date_count, 1), float(raw[0, 0]), dtype=float)
            else:
                expected = "1 or match dates length" if allow_scalar_expand else "match dates length"
                raise ValueError(f"{name} row count must be {expected}")
        else:
            raise ValueError(f"{name} must be a scalar, vector, or 2D matrix")

    if array.shape[0] != date_count:
        expected = "1 or match dates length" if allow_scalar_expand else "match dates length"
        raise ValueError(f"{name} row count must be {expected}")
    if date_count > 1:
        array = array[sort_idx, :]
    return _readonlyArray(array, dtype=float, ndmin=2)


def buildTimeSeriesData(
    *,
    dates: Any,
    ts_values: Any = None,
    ref_values: Any = None,
) -> TimeSeriesData:
    """Normalize raw values into an immutable TimeSeriesData instance."""
    if dates is None:
        raise ValueError("dates are required to build time-series data")

    input_dates = np.asarray(dates)
    if input_dates.ndim != 1:
        raise ValueError("dates must be a one-dimensional sequence")
    if len(input_dates) == 0:
        raise ValueError("dates must contain at least one value")

    sort_idx = np.argsort(input_dates)
    sorted_dates = _readonlyArray(input_dates[sort_idx])
    date_count = len(sorted_dates)

    prepared_ts = _normalizeValueMatrix(
        ts_values,
        date_count=date_count,
        sort_idx=sort_idx,
        name="ts_values",
        allow_scalar_expand=False,
    )
    prepared_ref = _normalizeValueMatrix(
        ref_values,
        date_count=date_count,
        sort_idx=sort_idx,
        name="ref_values",
        allow_scalar_expand=True,
    )

    if prepared_ts.shape[0] != date_count:
        raise ValueError("ts_values row count must match dates length")
    if prepared_ref.shape[0] not in (1, date_count):
        raise ValueError("ref_values row count must be 1 or match dates length")

    reference_mean = np.mean(prepared_ref, axis=1, keepdims=True)
    values_minus_reference = prepared_ts - reference_mean
    if prepared_ts.shape[1] > 1:
        min_plot_values = _readonlyArray(np.min(values_minus_reference, axis=1), dtype=float)
        max_plot_values = _readonlyArray(np.max(values_minus_reference, axis=1), dtype=float)
        plot_multiple_values = _readonlyArray(values_minus_reference, dtype=float, ndmin=2)
    else:
        min_plot_values = None
        max_plot_values = None
        plot_multiple_values = None

    plot_values = _readonlyArray(np.mean(prepared_ts, axis=1) - np.mean(prepared_ref, axis=1), dtype=float)
    return TimeSeriesData(
        dates=sorted_dates,
        ts_values=prepared_ts,
        ref_values=prepared_ref,
        plot_values=plot_values,
        plot_multiple_values=plot_multiple_values,
        min_plot_values=min_plot_values,
        max_plot_values=max_plot_values,
    )
