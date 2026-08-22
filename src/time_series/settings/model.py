"""Pure runtime ownership model for Time Series plotting settings."""

from copy import deepcopy
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from typing import Callable, ClassVar, List, Optional

from ..style_schema import (
    FIT_LINE_STYLE_DEFAULT, FIT_LINE_WIDTH_DEFAULT, FIT_LINE_WIDTH_RANGE,
    LINE_WIDTH_RANGE, MARKER_SIZE_RANGE, REPLICA_DEFAULT_COLOR_1,
    REPLICA_DEFAULT_COLOR_2, REPLICA_MARKER_SIZE_DEFAULT, RESIDUAL_DEFAULT_COLOR,
    RESIDUAL_LINE_WIDTH_RANGE, RESIDUAL_MARKER_SIZE_DEFAULT,
    RESIDUAL_MARKER_SIZE_RANGE, normalize_alpha,
    normalize_color,
    normalize_fit_line_style, normalize_line_style, normalize_marker,
    normalize_number, normalize_residual_line_style, normalize_residual_marker,
)
from .change_set import SettingsChangeSet


@dataclass(frozen=True)
class SeriesStyleSettings:
    """Persistent defaults used when creating a new primary series snapshot."""

    marker: str = "o"
    marker_color: str = "#1f77b4"
    marker_opacity: float = 0.8
    marker_edge_color: str = "black"
    marker_size: float = 5.0
    line_style: str = "-"
    line_color: str = "#1f77b4"
    line_opacity: float = 0.8
    line_width: float = 1.0

    @classmethod
    def from_params(cls, params):
        """Build normalized settings from a legacy parameter dictionary."""
        values = params.get("time series plot", {}) if isinstance(params, dict) else {}
        return cls(
            marker=normalize_marker(values.get("marker"), "o"),
            marker_color=normalize_color(values.get("marker color"), "#1f77b4"),
            marker_opacity=normalize_alpha(values.get("marker alpha"), 0.8),
            marker_edge_color=normalize_color(values.get("marker edge color"), "black"),
            marker_size=normalize_number(values.get("marker size"), MARKER_SIZE_RANGE, 5.0),
            line_style=normalize_line_style(values.get("line style"), "-"),
            line_color=normalize_color(values.get("line color"), "#1f77b4"),
            line_opacity=normalize_alpha(values.get("line alpha"), 0.8),
            line_width=normalize_number(values.get("line width"), LINE_WIDTH_RANGE, 1.0),
        )

    def as_params(self):
        """Return values using the current config/plot key names."""
        return {"marker": self.marker, "marker color": self.marker_color,
                "marker alpha": self.marker_opacity, "marker edge color": self.marker_edge_color,
                "marker size": self.marker_size, "line style": self.line_style,
                "line color": self.line_color, "line alpha": self.line_opacity,
                "line width": self.line_width}

    def to_time_series_style(self, base_params=None):
        """Create an independent legacy style for compatibility consumers."""
        from ...models.time_series import TimeSeriesStyle

        params = deepcopy(base_params) if isinstance(base_params, dict) else {}
        params.setdefault("time series plot", {}).update(self.as_params())
        return TimeSeriesStyle.fromParams(params)


@dataclass(frozen=True)
class FitStyleSettings:
    """Persistent defaults for fitted time-series curves."""

    line_style: str = FIT_LINE_STYLE_DEFAULT
    line_color: str = "#242424"
    line_width: float = FIT_LINE_WIDTH_DEFAULT
    line_alpha: float = 1.0

    @classmethod
    def fromParams(cls, params):
        """Build normalized fit defaults from legacy parameters."""
        values = params.get("model fit", {}) if isinstance(params, dict) else {}
        return cls(
            line_style=normalize_fit_line_style(values.get("line style")),
            line_color=normalize_color(values.get("line color"), "#242424"),
            line_width=normalize_number(values.get("line width"), FIT_LINE_WIDTH_RANGE, FIT_LINE_WIDTH_DEFAULT),
            line_alpha=normalize_alpha(values.get("line alpha"), 1.0),
        )

    def asParams(self):
        """Return values using legacy model-fit keys."""
        return {"line style": self.line_style, "line color": self.line_color,
                "line width": self.line_width, "line alpha": self.line_alpha}


@dataclass(frozen=True)
class ResidualStyleSettings:
    """Persistent defaults for residual series."""

    marker: str = "o"
    marker_color: str = RESIDUAL_DEFAULT_COLOR
    marker_edge_color: str = "black"
    marker_size: float = RESIDUAL_MARKER_SIZE_DEFAULT
    marker_alpha: float = 0.8
    line_style: str = ""
    line_color: str = RESIDUAL_DEFAULT_COLOR
    line_width: float = 1.0
    line_alpha: float = 0.8

    @classmethod
    def fromParams(cls, params):
        """Build normalized residual defaults from legacy parameters."""
        values = params.get("residual plot", {}) if isinstance(params, dict) else {}
        return cls(
            marker=normalize_residual_marker(values.get("marker"), "o"),
            marker_color=normalize_color(values.get("marker color"), RESIDUAL_DEFAULT_COLOR),
            marker_edge_color=normalize_color(values.get("marker edge color"), "black"),
            marker_size=normalize_number(
                values.get("marker size"),
                RESIDUAL_MARKER_SIZE_RANGE,
                RESIDUAL_MARKER_SIZE_DEFAULT),
            marker_alpha=normalize_alpha(values.get("marker alpha"), 0.8),
            line_style=normalize_residual_line_style(values.get("line style"), ""),
            line_color=normalize_color(values.get("line color"), RESIDUAL_DEFAULT_COLOR),
            line_width=normalize_number(values.get("line width"), RESIDUAL_LINE_WIDTH_RANGE, 1.0),
            line_alpha=normalize_alpha(values.get("line alpha"), 0.8),
        )

    def asParams(self):
        """Return values using legacy residual-plot keys."""
        return {"marker": self.marker, "marker color": self.marker_color,
                "marker edge color": self.marker_edge_color,
                "marker size": self.marker_size, "marker alpha": self.marker_alpha,
                "line style": self.line_style, "line color": self.line_color,
                "line width": self.line_width, "line alpha": self.line_alpha}


@dataclass(frozen=True)
class EnsembleStyleSettings:
    """Persistent defaults for ensemble member lines and spread."""

    member_line_color: str = "gray"
    member_line_width: float = 0.5
    member_line_alpha: float = 0.5
    fill_color: str = "#1f77b4"
    fill_alpha: float = 0.2

    @classmethod
    def fromParams(cls, params):
        """Build normalized ensemble defaults from legacy parameters."""
        values = params.get("time series plot", {}) if isinstance(params, dict) else {}
        return cls(
            member_line_color=normalize_color(values.get("series line color"), "gray"),
            member_line_width=normalize_number(values.get("series line width"), (0.0, 20.0), 0.5),
            member_line_alpha=normalize_number(values.get("series line alpha"), (0.0, 1.0), 0.5),
            fill_color=normalize_color(values.get("series fill color"), "#1f77b4"),
            fill_alpha=normalize_number(values.get("series fill alpha"), (0.0, 1.0), 0.2),
        )

    def asParams(self):
        """Return values using legacy time-series plot keys."""
        return {"series line color": self.member_line_color,
                "series line width": self.member_line_width,
                "series line alpha": self.member_line_alpha,
                "series fill color": self.fill_color,
                "series fill alpha": self.fill_alpha}


@dataclass(frozen=True)
class ReplicaStyleSettings:
    """Per-series visual settings for Replica markers."""

    color_1: str = REPLICA_DEFAULT_COLOR_1
    color_2: str = REPLICA_DEFAULT_COLOR_2
    opacity: float = 0.8
    marker: str = "o"
    marker_size: float = REPLICA_MARKER_SIZE_DEFAULT

    def __post_init__(self):
        object.__setattr__(
            self, "color_1", normalize_color(self.color_1, REPLICA_DEFAULT_COLOR_1)
        )
        object.__setattr__(
            self, "color_2", normalize_color(self.color_2, REPLICA_DEFAULT_COLOR_2)
        )
        object.__setattr__(self, "opacity", normalize_alpha(self.opacity, 0.8))
        object.__setattr__(self, "marker", normalize_marker(self.marker, "o"))
        object.__setattr__(
            self, "marker_size",
            normalize_number(
                self.marker_size, MARKER_SIZE_RANGE, REPLICA_MARKER_SIZE_DEFAULT
            ),
        )

    @classmethod
    def fromParams(cls, params):
        """Build visual Replica settings from legacy plot parameters."""
        values = params.get("time series plot", {}) if isinstance(params, dict) else {}
        return cls(
            color_1=values.get(
                "replica color 1",
                values.get("replicate color 1", REPLICA_DEFAULT_COLOR_1),
            ),
            color_2=values.get(
                "replica color 2",
                values.get("replicate color 2", REPLICA_DEFAULT_COLOR_2),
            ),
            opacity=values.get("replica alpha", values.get("replicate alpha", 0.8)),
            marker=values.get("replica marker", values.get("replicate marker", "o")),
            marker_size=values.get(
                "replica marker size",
                values.get("replicate marker size", REPLICA_MARKER_SIZE_DEFAULT),
            ),
        )

    def asParams(self):
        """Return visual values using legacy time-series plot keys."""
        return {
            "replica color 1": self.color_1,
            "replica color 2": self.color_2,
            "replica alpha": self.opacity,
            "replica marker": self.marker,
            "replica marker size": self.marker_size,
        }


@dataclass(frozen=True)
class ReplicaSettings:
    """Runtime and persistent settings for global Replica rendering."""

    enabled: bool = False
    interval_mm: float = 27.8
    pair_count: int = 1
    color_1: str = REPLICA_DEFAULT_COLOR_1
    color_2: str = REPLICA_DEFAULT_COLOR_2
    opacity: float = 0.8
    marker: str = "o"
    marker_size: float = REPLICA_MARKER_SIZE_DEFAULT

    def __post_init__(self):
        """Normalize every Replica field at the immutable domain boundary."""
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "interval_mm", max(0.1, min(10000.0, float(self.interval_mm))))
        object.__setattr__(self, "pair_count", max(1, min(10, int(self.pair_count))))
        object.__setattr__(
            self, "color_1", normalize_color(self.color_1, REPLICA_DEFAULT_COLOR_1)
        )
        object.__setattr__(
            self, "color_2", normalize_color(self.color_2, REPLICA_DEFAULT_COLOR_2)
        )
        object.__setattr__(self, "opacity", normalize_alpha(self.opacity, 0.8))
        object.__setattr__(self, "marker", normalize_marker(self.marker, "o"))
        object.__setattr__(
            self, "marker_size",
            normalize_number(
                self.marker_size, MARKER_SIZE_RANGE, REPLICA_MARKER_SIZE_DEFAULT
            ),
        )


@dataclass(frozen=True)
class FitAnalysisDefaults:
    """User defaults copied into fit configuration for future records only."""

    enabled: bool = False
    model: str = "poly-1"
    seasonal: bool = False
    show_residuals: bool = False

    def __post_init__(self):
        from ..fit_state import DEFAULT_FIT_MODEL, FIT_MODELS

        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(
            self, "model", self.model if self.model in FIT_MODELS else DEFAULT_FIT_MODEL
        )
        object.__setattr__(self, "seasonal", bool(self.seasonal))
        object.__setattr__(
            self,
            "show_residuals",
            bool(self.enabled) and bool(self.show_residuals),
        )


@dataclass(frozen=True)
class ReplicaAnalysisDefaults:
    """User defaults copied into Replica configuration for future records only."""

    enabled: bool = False
    pair_count: int = 1
    interval_mm: float = 27.8

    def __post_init__(self):
        object.__setattr__(self, "enabled", bool(self.enabled))
        object.__setattr__(self, "pair_count", max(1, min(10, int(self.pair_count))))
        object.__setattr__(
            self, "interval_mm", max(0.1, min(10000.0, float(self.interval_mm)))
        )


@dataclass(frozen=True)
class AxisManualRange:
    """Session-only Y editor policies and retained numeric bound values.

    ``lower`` and ``upper`` are the active editor endpoints: ``None`` means
    Auto and a finite number means Manual.  ``retained_lower`` and
    ``retained_upper`` preserve the last numeric draft even while the
    corresponding endpoint is Auto.
    """

    lower: Optional[float] = None
    upper: Optional[float] = None
    retained_lower: Optional[float] = None
    retained_upper: Optional[float] = None

    def __post_init__(self):
        if self.lower is not None and self.retained_lower is None:
            object.__setattr__(self, "retained_lower", self.lower)
        if self.upper is not None and self.retained_upper is None:
            object.__setattr__(self, "retained_upper", self.upper)


@dataclass(frozen=True)
class YAxisSettings:
    """Session-only Y-axis policy, manual ranges, and transient viewport state."""

    policy: str = "from_data"
    series_manual: AxisManualRange = field(default_factory=AxisManualRange)
    residual_manual: AxisManualRange = field(default_factory=AxisManualRange)
    series_display_mode: str = "from_data"
    residual_display_mode: str = "from_data"
    series_custom_view: bool = False
    residual_custom_view: bool = False

    def relevant_manual_ranges(self, residual_available=False):
        """Return the editor ranges that participate in the active Y policy."""
        ranges = (self.series_manual,)
        if residual_available:
            ranges += (self.residual_manual,)
        return ranges

    def has_configured_manual(self, residual_available=False):
        """Return whether any currently relevant endpoint is explicitly Manual."""
        return any(
            manual.lower is not None or manual.upper is not None
            for manual in self.relevant_manual_ranges(residual_available)
        )

    def policy_for_manual_editor(self, residual_available=False):
        """Return the truthful aggregate policy for the current editor state."""
        return "manual" if self.has_configured_manual(residual_available) else "from_data"

    def has_custom_view(self, residual_available=False):
        """Return whether any currently visible Y axis has a custom viewport."""
        return self.series_custom_view or (
            residual_available and self.residual_custom_view
        )

    def display_mode_for_axis(self, axis_name):
        """Return the effective saved-range/display selection for one Y axis."""
        if axis_name == "series_y":
            return self.series_display_mode
        if axis_name == "residual_y":
            return self.residual_display_mode
        raise ValueError(f"Unsupported Y axis: {axis_name}")

    def policy_for_effective_display(self, residual_available=False):
        """Return the aggregate toolbar policy from currently visible local modes."""
        modes = (self.series_display_mode,)
        if residual_available:
            modes += (self.residual_display_mode,)
        return "manual" if "manual" in modes else "from_data"

    def select_all_from_data(self):
        """Select From Data for every Y axis without altering saved Manual ranges."""
        return replace(
            self,
            policy="from_data",
            series_display_mode="from_data",
            residual_display_mode="from_data",
            series_custom_view=False,
            residual_custom_view=False,
        )

    def select_manual_for_visible_axes(self, residual_available=False):
        """Select saved Manual rendering for every currently relevant Y axis."""
        state = replace(
            self, series_display_mode="manual", series_custom_view=False
        )
        if residual_available:
            state = replace(
                state, residual_display_mode="manual", residual_custom_view=False
            )
        return replace(state, policy="manual")

    def select_from_data_for_visible_axes(self, residual_available=False):
        """Select From Data rendering without discarding saved Manual ranges."""
        state = replace(
            self, series_display_mode="from_data", series_custom_view=False
        )
        if residual_available:
            state = replace(
                state, residual_display_mode="from_data", residual_custom_view=False
            )
        return replace(state, policy="from_data")

    def commit_current_view(self, axis_name, lower, upper, residual_available=False):
        """Commit one visible axis viewport as Manual without changing its sibling."""
        manual = AxisManualRange(lower, upper, lower, upper)
        if axis_name == "series":
            state = replace(
                self,
                series_manual=manual,
                series_display_mode="manual",
                series_custom_view=False,
            )
        elif axis_name == "residual":
            state = replace(
                self,
                residual_manual=manual,
                residual_display_mode="manual",
                residual_custom_view=False,
            )
        else:
            raise ValueError(f"Unsupported Y axis: {axis_name}")
        return replace(
            state, policy=state.policy_for_effective_display(residual_available)
        )


@dataclass(frozen=True, init=False)
class XAxisSettings:
    """Session-only per-bound X-axis policies, manual dates, and viewport state."""

    start_policy: str = "from_data"
    end_policy: str = "from_data"
    manual_editor_start_policy: str = "from_data"
    manual_editor_end_policy: str = "from_data"
    manual_start: Optional[datetime] = None
    manual_end: Optional[datetime] = None
    custom_view: bool = False

    def __init__(
        self, start_policy="from_data", end_policy="from_data",
        manual_editor_start_policy=None, manual_editor_end_policy=None,
        manual_start=None, manual_end=None, custom_view=False, policy=None,
    ):
        """Create active and remembered editor policies with legacy migration."""
        if policy in {"from_data", "manual"}:
            start_policy = end_policy = policy
        start_policy = self._normalize_policy(start_policy)
        end_policy = self._normalize_policy(end_policy)
        if manual_editor_start_policy is None:
            manual_editor_start_policy = start_policy
        if manual_editor_end_policy is None:
            manual_editor_end_policy = end_policy
        object.__setattr__(self, "start_policy", start_policy)
        object.__setattr__(self, "end_policy", end_policy)
        object.__setattr__(self, "manual_editor_start_policy", self._normalize_policy(manual_editor_start_policy))
        object.__setattr__(self, "manual_editor_end_policy", self._normalize_policy(manual_editor_end_policy))
        object.__setattr__(self, "manual_start", manual_start)
        object.__setattr__(self, "manual_end", manual_end)
        object.__setattr__(self, "custom_view", bool(custom_view))

    @staticmethod
    def _normalize_policy(value):
        """Normalize one X-bound policy at the settings-domain boundary."""
        return value if value in {"from_data", "manual"} else "from_data"

    @property
    def policy(self):
        """Return the toolbar-compatible aggregate policy for this bound pair."""
        return "from_data" if self.both_from_data else "manual"

    @property
    def both_from_data(self):
        """Return whether both X bounds follow the available data extent."""
        return self.start_policy == "from_data" and self.end_policy == "from_data"

    def effective_range(self, data_start, data_end):
        """Resolve and validate the effective range from data and manual bounds."""
        start = data_start if self.start_policy == "from_data" else self.manual_start
        end = data_end if self.end_policy == "from_data" else self.manual_end
        if start is None or end is None or start >= end:
            return None
        return start, end


@dataclass(frozen=True)
class AppearanceSettings:
    """Persistent plot-wide appearance defaults currently represented in config."""

    time_series_title: str = ""
    residual_title: str = ""
    time_series_x_label: str = "Date"
    residual_x_label: str = "Date"
    time_series_y_label: str = "Deformation"
    residual_y_label: str = "Residual"
    font_size: float = 10.0
    grid_mode: str = "both"
    plot_background: str = "white"
    canvas_background: str = "white"
    date_format: Optional[str] = "%Y-%m-%d"

    GRID_MODES: ClassVar[tuple] = ("both", "horizontal", "vertical", "none")

    def __post_init__(self):
        """Normalize the canonical grid mode without introducing a Boolean alias."""
        object.__setattr__(self, "grid_mode", self.normalize_grid_mode(self.grid_mode))
        object.__setattr__(self, "plot_background", normalize_color(self.plot_background, "white"))
        object.__setattr__(self, "canvas_background", normalize_color(self.canvas_background, "white"))

    @classmethod
    def normalize_grid_mode(cls, value):
        """Return one supported canonical grid mode, defaulting invalid values to both."""
        return value if value in cls.GRID_MODES else "both"


@dataclass(frozen=True)
class ExportSettings:
    """Persistent normalized defaults for plot export."""

    dpi: str = "300"
    aspect_ratio: float = 4.0
    include_attribution: bool = True

    DPI_OPTIONS = ("72", "150", "300", "600", "1200")

    @staticmethod
    def _normalize_bool(value, fallback=True):
        """Return a strict boolean while tolerating common persisted scalar forms."""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off", ""}:
                return False
        return fallback

    @classmethod
    def normalized(cls, dpi=None, aspect_ratio=None, include_attribution=None):
        """Build settings with schema-compatible normalization."""
        dpi = str(dpi) if dpi is not None else cls().dpi
        if dpi not in cls.DPI_OPTIONS:
            dpi = cls().dpi
        try:
            aspect_ratio = float(aspect_ratio)
        except (TypeError, ValueError, OverflowError):
            aspect_ratio = cls().aspect_ratio
        aspect_ratio = max(1.0, min(10.0, aspect_ratio))
        include_attribution = cls._normalize_bool(
            include_attribution, cls().include_attribution
        )
        return cls(
            dpi=dpi,
            aspect_ratio=aspect_ratio,
            include_attribution=include_attribution,
        )


@dataclass
class TimeSeriesSettingsModel:
    """Authoritative runtime settings for Time Series plotting."""

    series_defaults: SeriesStyleSettings = field(default_factory=SeriesStyleSettings)
    fit_defaults: FitStyleSettings = field(default_factory=FitStyleSettings)
    residual_defaults: ResidualStyleSettings = field(default_factory=ResidualStyleSettings)
    fit_current: FitStyleSettings = field(default_factory=FitStyleSettings)
    residual_current: ResidualStyleSettings = field(default_factory=ResidualStyleSettings)
    ensemble_defaults: EnsembleStyleSettings = field(default_factory=EnsembleStyleSettings)
    replica: ReplicaSettings = field(default_factory=ReplicaSettings)
    fit_analysis_defaults: FitAnalysisDefaults = field(default_factory=FitAnalysisDefaults)
    replica_analysis_defaults: ReplicaAnalysisDefaults = field(default_factory=ReplicaAnalysisDefaults)
    y_axis: YAxisSettings = field(default_factory=YAxisSettings)
    x_axis: XAxisSettings = field(default_factory=XAxisSettings)
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)
    export: ExportSettings = field(default_factory=ExportSettings)
    _listeners: List[Callable[[SettingsChangeSet], None]] = field(default_factory=list, init=False, repr=False)
    _batch_depth: int = field(default=0, init=False, repr=False)
    _batched_changes: SettingsChangeSet = field(default_factory=SettingsChangeSet, init=False, repr=False)

    def subscribe(self, callback):
        """Register a callback and return an unsubscribe function."""
        self._listeners.append(callback)
        return lambda: self._listeners.remove(callback) if callback in self._listeners else None

    def replace_domain(self, domain, value):
        """Replace one typed submodel and report precisely what changed."""
        old = getattr(self, domain)
        if old == value:
            return SettingsChangeSet()
        setattr(self, domain, deepcopy(value))
        old_values = asdict(old)
        new_values = asdict(value)
        changed = [key for key in set(old_values) | set(new_values) if old_values.get(key) != new_values.get(key)]
        change = SettingsChangeSet.for_properties(domain, changed)
        if self._batch_depth:
            self._batched_changes = self._batched_changes.merge(change)
        else:
            self.notify(change)
        return change

    def notify(self, change):
        """Notify listeners once for one completed logical update."""
        if not change.domains:
            return
        for callback in tuple(self._listeners):
            callback(change)

    @contextmanager
    def batch_update(self):
        """Merge multiple domain replacements into one listener notification."""
        self._batch_depth += 1
        try:
            yield self
        finally:
            self._batch_depth -= 1
            if self._batch_depth == 0 and self._batched_changes.domains:
                change = self._batched_changes
                self._batched_changes = SettingsChangeSet()
                self.notify(change)

    def replace_domains(self, values):
        """Replace multiple submodels and return one merged change set."""
        merged = SettingsChangeSet()
        with self.batch_update():
            for domain, value in values.items():
                merged = merged.merge(self.replace_domain(domain, value))
        return merged

    def update_property(self, domain, property_name, value):
        """Update one property through immutable submodel replacement."""
        current = getattr(self, domain)
        return self.replace_domain(domain, replace(current, **{property_name: value}))

    def persistent_payload(self):
        """Return persistent domains only; session policies and manual ranges are excluded."""
        return {
            "series_defaults": self.series_defaults.as_params(),
            "fit_defaults": self.fit_defaults.asParams(),
            "residual_defaults": self.residual_defaults.asParams(),
            "ensemble_defaults": self.ensemble_defaults.asParams(),
            "replica_defaults": {"interval_mm": self.replica.interval_mm, "pair_count": self.replica.pair_count},
            "fit_analysis_defaults": asdict(self.fit_analysis_defaults),
            "replica_analysis_defaults": asdict(self.replica_analysis_defaults),
            "appearance": asdict(self.appearance),
            "export": asdict(self.export),
        }

    def copy(self):
        """Return a defensive model copy without sharing listeners."""
        return TimeSeriesSettingsModel(**{name: deepcopy(getattr(self, name)) for name in (
            "series_defaults", "fit_defaults", "residual_defaults", "fit_current",
            "residual_current", "ensemble_defaults", "replica", "fit_analysis_defaults",
            "replica_analysis_defaults", "y_axis", "x_axis", "appearance", "export")})
