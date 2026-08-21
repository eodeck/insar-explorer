"""Read-only adapter for one-time migration from bundled ``config.json``.

This is the only plugin-owned infrastructure layer that understands
``JsonSettings``, legacy metadata entries, JSON block names, or the bundled
configuration schema.  It deliberately exposes no save operations.
"""

from copy import deepcopy
import warnings

from ....external.setting_manager_ui.json_settings import JsonSettings
from .legacy_style_config import TimeSeriesStyleConfig
from ..style_schema import (
    MARKER_SIZE_RANGE, REPLICA_DEFAULT_COLOR_1, REPLICA_DEFAULT_COLOR_2,
    REPLICA_MARKER_SIZE_DEFAULT, normalize_alpha, normalize_color, normalize_marker,
    normalize_number,
)
from ..settings.model import (
    EnsembleStyleSettings, ExportSettings, FitStyleSettings,
    AppearanceSettings, ReplicaSettings, ResidualStyleSettings,
    SeriesStyleSettings,
)
from .factory_defaults import factory_user_preferences
from .interfaces import TimeSeriesUserPreferences


class LegacyJsonUserPreferencesRepository:
    """Read normalized legacy preferences for one-time migration only."""

    BLOCK_KEY = "timeseries settings"

    def __init__(self, config_file):
        """Create a coordinator over the existing style adapter and JSON backend."""
        self.config_file = config_file
        self.style_config = TimeSeriesStyleConfig(config_file)

    @staticmethod
    def _mapping(value):
        """Return a mapping or an empty defensive fallback."""
        return value if isinstance(value, dict) else {}

    @classmethod
    def _value(cls, section, key, fallback=None):
        """Read one metadata value without trusting block or entry shape."""
        entry = cls._mapping(cls._mapping(section).get(key))
        value = entry.get("value", entry.get("default", fallback))
        return fallback if value is None else value

    @staticmethod
    def _safe_float(value, fallback, minimum=None, maximum=None):
        """Normalize one persisted numeric scalar with optional bounds."""
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return fallback
        if minimum is not None and number < minimum:
            return fallback
        if maximum is not None and number > maximum:
            return fallback
        return number

    @staticmethod
    def _safe_text(value, fallback=""):
        """Normalize one persisted text scalar."""
        return fallback if value is None or isinstance(value, (dict, list)) else str(value)

    @staticmethod
    def _safe_grid(value):
        """Normalize the constrained grid mode."""
        return AppearanceSettings.normalize_grid_mode(value)

    @classmethod
    def _include_attribution(cls, export):
        """Resolve the new attribution flag with isolated legacy-credit migration."""
        export = cls._mapping(export)
        if "include attribution" in export:
            value = cls._value(export, "include attribution", True)
            return ExportSettings._normalize_bool(value, True)

        credit_entry = export.get("credit")
        if credit_entry is None:
            return True
        legacy_credit = cls._value(export, "credit", None)
        if legacy_credit is None:
            return True
        return bool(str(legacy_credit).strip())

    @staticmethod
    def _normalize_pair_count(value):
        """Return the supported persistent Replica pair count."""
        if isinstance(value, bool):
            return 1
        try:
            value = int(value)
        except (TypeError, ValueError, OverflowError):
            return 1
        return max(1, min(10, value))

    def _load_block(self):
        """Load a metadata block and tolerate missing or malformed content."""
        try:
            return self._mapping(JsonSettings(self.config_file).load(block_key=self.BLOCK_KEY))
        except Exception:
            warnings.warn(
                "Legacy time-series preferences could not be loaded; factory defaults will be used.",
                RuntimeWarning,
            )
            return {}

    def load(self):
        """Load normalized preferences, falling back safely on malformed data."""
        try:
            return self._load_preferences()
        except Exception:
            warnings.warn(
                "Legacy time-series preferences were malformed; factory defaults will be used.",
                RuntimeWarning,
            )
            return factory_user_preferences()

    def _load_preferences(self):
        """Load safely recoverable values from the legacy metadata schema."""
        block = self._load_block()
        plot = self._mapping(block.get("time series plot"))
        residual = self._mapping(block.get("residual plot"))
        figure = self._mapping(block.get("figure"))
        export = self._mapping(block.get("export"))

        try:
            series_style = self.style_config.load_default_style()
            series = SeriesStyleSettings.from_params(series_style.params)
        except (KeyError, TypeError, ValueError):
            series = SeriesStyleSettings()
        try:
            fit = FitStyleSettings.fromParams({"model fit": self.style_config.load_default_fit_style().asParams()})
        except (KeyError, TypeError, ValueError, AttributeError):
            fit = FitStyleSettings()
        try:
            residual_style = ResidualStyleSettings.fromParams(
                {"residual plot": self.style_config.load_default_residual_style().asParams()}
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            residual_style = ResidualStyleSettings()
        try:
            ensemble = EnsembleStyleSettings.fromParams(
                {"time series plot": self.style_config.load_default_ensemble_style().asParams()}
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            ensemble = EnsembleStyleSettings()

        return TimeSeriesUserPreferences(
            series_defaults=series,
            fit_defaults=fit,
            residual_defaults=residual_style,
            ensemble_defaults=ensemble,
            replica_defaults=ReplicaSettings(
                enabled=False,
                interval_mm=27.8,
                pair_count=self._normalize_pair_count(self._value(plot, "replica pair count", 1)),
                color_1=normalize_color(
                    self._value(plot, "replica color 1", REPLICA_DEFAULT_COLOR_1),
                    REPLICA_DEFAULT_COLOR_1,
                ),
                color_2=normalize_color(
                    self._value(plot, "replica color 2", REPLICA_DEFAULT_COLOR_2),
                    REPLICA_DEFAULT_COLOR_2,
                ),
                opacity=normalize_alpha(self._value(plot, "replica alpha", 0.8), 0.8),
                marker=normalize_marker(self._value(plot, "replica marker", "o"), "o"),
                marker_size=normalize_number(
                    self._value(
                        plot, "replica marker size", REPLICA_MARKER_SIZE_DEFAULT
                    ),
                    MARKER_SIZE_RANGE,
                    REPLICA_MARKER_SIZE_DEFAULT,
                ),
            ),
            appearance=AppearanceSettings(
                time_series_title=self._safe_text(self._value(plot, "title", "")),
                residual_title=self._safe_text(self._value(residual, "title", "")),
                time_series_x_label=self._safe_text(self._value(plot, "xlabel", "Date"), "Date"),
                residual_x_label=self._safe_text(self._value(residual, "xlabel", "Date"), "Date"),
                time_series_y_label=self._safe_text(self._value(plot, "ylabel", "Deformation"), "Deformation"),
                residual_y_label=self._safe_text(self._value(residual, "ylabel", "Residual"), "Residual"),
                font_size=self._safe_float(self._value(plot, "font size", 10.0), 10.0, 1.0, 200.0),
                grid_mode=self._safe_grid(self._value(plot, "grid", "both")),
                plot_background=normalize_color(self._value(plot, "background color", "white"), "white"),
                canvas_background=normalize_color(self._value(figure, "background color", "white"), "white"),
                date_format=self._safe_text(self._value(plot, "date format", "%Y-%m-%d"), "%Y-%m-%d"),
            ),
            export=ExportSettings.normalized(
                dpi=self._value(export, "dpi", "300"),
                aspect_ratio=self._value(export, "aspect ratio", 4.0),
                include_attribution=self._include_attribution(export),
            ),
        )


def build_legacy_plot_params(model, existing=None):
    """Build the temporary legacy ``PlotTs.parms`` view from runtime settings.

    TODO(phase-appearance-export): Remove when all consumers accept typed submodels.
    """
    params = deepcopy(existing) if isinstance(existing, dict) else {}
    plot = params.setdefault("time series plot", {})
    plot.update(model.series_defaults.as_params())
    plot.update(model.ensemble_defaults.asParams())
    plot.update({
        "title": model.appearance.time_series_title,
        "xlabel": model.appearance.time_series_x_label,
        "ylabel": model.appearance.time_series_y_label,
        "font size": model.appearance.font_size,
        "grid": model.appearance.grid_mode,
        "background color": model.appearance.plot_background,
        "date format": model.appearance.date_format,
        "replica pair count": model.replica.pair_count,
        "replica color 1": model.replica.color_1,
        "replica color 2": model.replica.color_2,
        "replica alpha": model.replica.opacity,
        "replica marker": model.replica.marker,
        "replica marker size": model.replica.marker_size,
    })
    params.setdefault("model fit", {}).update(model.fit_current.asParams())
    residual = params.setdefault("residual plot", {})
    residual.update(model.residual_current.asParams())
    residual.update({
        "title": model.appearance.residual_title,
        "xlabel": model.appearance.residual_x_label,
        "ylabel": model.appearance.residual_y_label,
        "font size": model.appearance.font_size,
        "grid": model.appearance.grid_mode,
        "background color": model.appearance.plot_background,
        "date format": model.appearance.date_format,
    })
    params.setdefault("figure", {})["background color"] = model.appearance.canvas_background
    params["export"] = {
        "dpi": model.export.dpi,
        "aspect ratio": model.export.aspect_ratio,
        "include attribution": model.export.include_attribution,
    }
    return params
