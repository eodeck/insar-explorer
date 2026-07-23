"""Read-only legacy style-schema helper used during first-run migration.

The bundled configuration is immutable application data.  This helper performs
normalization only and never writes to the legacy JSON source.
"""

from collections.abc import Mapping
from copy import deepcopy

from ....external.setting_manager_ui.json_settings import JsonSettings
from ...models.time_series import TimeSeriesStyle
from ..fit_style_controller import FIT_STYLE_KEYS, FitStyle
from ..ensemble_style import (
    ENSEMBLE_MEMBER_LINE_SOLID_STYLE,
    ENSEMBLE_MEMBER_LINE_STYLE,
    ENSEMBLE_STYLE_KEYS,
    EnsembleStyle,
    EnsembleStyleController,
)
from ..residual_style_controller import RESIDUAL_STYLE_KEYS, ResidualStyle
from ..style_schema import (
    FIT_LINE_STYLE_OPTIONS,
    FIT_LINE_WIDTH_DEFAULT,
    FIT_LINE_WIDTH_RANGE,
    LINE_STYLE_OPTIONS,
    LINE_WIDTH_RANGE,
    MARKER_OPTIONS,
    MARKER_SIZE_RANGE,
    PERSISTED_STYLE_KEYS,
    normalize_color,
    normalize_fit_line_style,
    normalize_line_style,
    normalize_marker,
    normalize_number,
    normalize_residual_line_style,
    normalize_residual_marker,
    RESIDUAL_DEFAULT_COLOR,
    RESIDUAL_LINE_WIDTH_RANGE,
    RESIDUAL_MARKER_SIZE_RANGE,
)


class TimeSeriesStyleConfig:
    """Read typed styles from the retired Settings JSON metadata schema."""

    BLOCK_KEY = "timeseries settings"
    PLOT_KEY = "time series plot"

    def __init__(self, config_file):
        """Store the configuration path without caching persisted values."""
        self.config_file = config_file

    def load_style_values(self):
        """Load and normalize every persisted series-style value."""
        settings = JsonSettings(self.config_file)
        block = settings.load(block_key=self.BLOCK_KEY)
        plot = block.get(self.PLOT_KEY, {})
        values = {}
        for key in PERSISTED_STYLE_KEYS:
            entry = plot.get(key, {})
            value = entry.get("value", entry.get("default")) if isinstance(entry, dict) else None
            values[key] = self.normalize_property(key, value)
        return values

    def load_default_style(self, base_params=None):
        """Return normalized defaults merged into a defensive parameter copy."""
        params = deepcopy(base_params) if isinstance(base_params, dict) else {}
        params.setdefault(self.PLOT_KEY, {}).update(self.load_style_values())
        return TimeSeriesStyle.fromParams(params)

    def load_ensemble_style_values(self):
        """Load and normalize persisted Ensemble defaults from existing plot keys."""
        settings = JsonSettings(self.config_file)
        block = settings.load(block_key=self.BLOCK_KEY)
        plot = block.get(self.PLOT_KEY, {})
        values = {}
        for key in ENSEMBLE_STYLE_KEYS:
            entry = plot.get(key, {})
            value = entry.get("value", entry.get("default")) if isinstance(entry, dict) else None
            values[key] = EnsembleStyleController._normalize(key, value)

        # The historical UI only supports solid member lines.  Normalize the
        # in-memory migration value without mutating bundled application data.
        if ENSEMBLE_MEMBER_LINE_STYLE in values:
            values[ENSEMBLE_MEMBER_LINE_STYLE] = ENSEMBLE_MEMBER_LINE_SOLID_STYLE
        return values

    def load_default_ensemble_style(self):
        """Return normalized persisted Ensemble defaults."""
        return EnsembleStyle.fromParams({self.PLOT_KEY: self.load_ensemble_style_values()})

    def load_fit_style_values(self):
        """Load and normalize persisted fit-line defaults."""
        settings = JsonSettings(self.config_file)
        block = settings.load(block_key=self.BLOCK_KEY)
        fit = block.get("model fit", {})
        values = {}
        for key in FIT_STYLE_KEYS:
            entry = fit.get(key, {})
            value = entry.get("value", entry.get("default")) if isinstance(entry, dict) else None
            values[key] = self.normalize_fit_property(key, value)
        return values

    def load_default_fit_style(self):
        """Return normalized persisted fit-line defaults."""
        return FitStyle.fromParams({"model fit": self.load_fit_style_values()})

    def load_residual_style_values(self):
        """Load and normalize persisted residual-series defaults."""
        settings = JsonSettings(self.config_file)
        block = settings.load(block_key=self.BLOCK_KEY)
        residual = block.get("residual plot", {})
        values = {}
        for key in RESIDUAL_STYLE_KEYS:
            entry = residual.get(key, {})
            value = entry.get("value", entry.get("default")) if isinstance(entry, dict) else None
            values[key] = self.normalize_residual_property(key, value)
        return values

    def load_default_residual_style(self):
        return ResidualStyle.fromParams({"residual plot": self.load_residual_style_values()})

    @staticmethod
    def _style_values(style):
        """Return a defensive plain mapping for a serializable style value object."""
        serializer = getattr(style, "asParams", None)
        if callable(serializer):
            values = serializer()
        elif isinstance(style, Mapping):
            values = style
        else:
            raise TypeError(
                f"Unsupported style value type: {type(style).__name__}"
            )

        if not isinstance(values, Mapping):
            raise TypeError(
                "Style asParams() must return a mapping, "
                f"got {type(values).__name__}"
            )
        return dict(values)

    def normalize_residual_property(self, key, value):
        if key == "marker": return normalize_residual_marker(value, "o")
        if key == "marker size": return normalize_number(value, RESIDUAL_MARKER_SIZE_RANGE, 5.0)
        if key == "line style": return normalize_residual_line_style(value, "")
        if key == "line width": return normalize_number(value, RESIDUAL_LINE_WIDTH_RANGE, 1.0)
        if key == "marker color": return normalize_color(value, RESIDUAL_DEFAULT_COLOR)
        if key == "marker edge color": return normalize_color(value, "black")
        if key == "line color": return normalize_color(value, RESIDUAL_DEFAULT_COLOR)
        if key == "marker alpha": return normalize_number(value, (0.0, 1.0), 0.8)
        if key == "line alpha": return normalize_number(value, (0.0, 1.0), 0.8)
        return value

    def normalize_fit_property(self, key, value):
        """Normalize one fit-line property through the canonical shared schema."""
        if key == "line style":
            return normalize_fit_line_style(value)
        if key == "line color":
            return normalize_color(value, "#242424")
        if key == "line width":
            return normalize_number(value, FIT_LINE_WIDTH_RANGE, FIT_LINE_WIDTH_DEFAULT)
        if key == "line alpha":
            return normalize_number(value, (0.0, 1.0), 1.0)
        return value

    def normalize_property(self, key, value):
        """Normalize one property according to the canonical plugin schema."""
        if key == "marker":
            return normalize_marker(value, "o")
        if key == "line style":
            return normalize_line_style(value, "")
        if key == "marker size":
            return normalize_number(value, MARKER_SIZE_RANGE, 5.0)
        if key == "line width":
            return normalize_number(value, LINE_WIDTH_RANGE, 1.0)
        if key in ("marker color", "line color", "marker edge color"):
            fallback = "black" if key == "marker edge color" else "#1f77b4"
            return normalize_color(value, fallback)
        if key in ("marker alpha", "line alpha"):
            return normalize_number(value, (0.0, 1.0), 0.8)
        return value

    @staticmethod
    def supported_options():
        """Return schema options for validation and diagnostics."""
        return {
            "marker": MARKER_OPTIONS,
            "line style": LINE_STYLE_OPTIONS,
            "fit line style": FIT_LINE_STYLE_OPTIONS,
        }
