"""Private legacy style-schema helper for the config.json compatibility adapter.

This module is infrastructure-only and will be retired with the Phase 08 migration.
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
    """Translate between the Settings JSON metadata schema and ``TimeSeriesStyle``."""

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

    def save_default_style(self, style):
        """Persist style values while preserving unrelated settings and metadata."""
        plot_values = style.params.get(self.PLOT_KEY, {})
        settings = JsonSettings(self.config_file)
        block = settings.load(block_key=self.BLOCK_KEY)
        plot = block.get(self.PLOT_KEY)
        if not isinstance(plot, dict):
            raise KeyError("Missing timeseries settings/time series plot configuration block")

        for key in PERSISTED_STYLE_KEYS:
            if key not in plot_values:
                continue
            entry = plot.get(key)
            if not isinstance(entry, dict):
                raise KeyError(f"Missing time-series plot style setting: {key}")
            entry["value"] = self.normalize_property(key, plot_values[key])

        settings.save(self.BLOCK_KEY, block)



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

        style_entry = plot.get(ENSEMBLE_MEMBER_LINE_STYLE)
        if isinstance(style_entry, dict):
            current_style = style_entry.get("value", style_entry.get("default"))
            if current_style != ENSEMBLE_MEMBER_LINE_SOLID_STYLE:
                style_entry["value"] = ENSEMBLE_MEMBER_LINE_SOLID_STYLE
                settings.save(self.BLOCK_KEY, block)
        return values

    def load_default_ensemble_style(self):
        """Return normalized persisted Ensemble defaults."""
        return EnsembleStyle.fromParams({self.PLOT_KEY: self.load_ensemble_style_values()})

    def save_default_ensemble_style(self, ensemble_style):
        """Persist Ensemble defaults while retaining unrelated config metadata."""
        values = self._style_values(ensemble_style)
        settings = JsonSettings(self.config_file)
        block = settings.load(block_key=self.BLOCK_KEY)
        plot = block.get(self.PLOT_KEY)
        if not isinstance(plot, dict):
            raise KeyError("Missing timeseries settings/time series plot configuration block")
        for key in ENSEMBLE_STYLE_KEYS:
            entry = plot.get(key)
            if not isinstance(entry, dict):
                raise KeyError(f"Missing ensemble style setting: {key}")
            entry["value"] = EnsembleStyleController._normalize(key, values.get(key))
        settings.save(self.BLOCK_KEY, block)

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

    def save_default_fit_style(self, fit_style):
        """Persist fit-line defaults while preserving settings metadata."""
        values = self._style_values(fit_style)
        settings = JsonSettings(self.config_file)
        block = settings.load(block_key=self.BLOCK_KEY)
        fit = block.get("model fit")
        if not isinstance(fit, dict):
            raise KeyError("Missing timeseries settings/model fit configuration block")
        for key in FIT_STYLE_KEYS:
            entry = fit.get(key)
            if not isinstance(entry, dict):
                raise KeyError(f"Missing model-fit style setting: {key}")
            entry["value"] = self.normalize_fit_property(key, values.get(key))
        settings.save(self.BLOCK_KEY, block)


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

    def save_default_residual_style(self, residual_style):
        values = self._style_values(residual_style)
        settings = JsonSettings(self.config_file)
        block = settings.load(block_key=self.BLOCK_KEY)
        residual = block.get("residual plot")
        if not isinstance(residual, dict):
            raise KeyError("Missing timeseries settings/residual plot configuration block")
        for key in RESIDUAL_STYLE_KEYS:
            entry = residual.get(key)
            if not isinstance(entry, dict):
                if key == "marker edge color":
                    continue
                raise KeyError(f"Missing residual style setting: {key}")
            entry["value"] = self.normalize_residual_property(key, values.get(key))
        settings.save(self.BLOCK_KEY, block)

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
