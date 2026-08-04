"""QSettings-backed user-preference infrastructure.

Every preference is stored under an explicit, versioned key.  The repository
normalizes fields independently so one malformed value cannot invalidate an
otherwise usable preference set.
"""

from typing import Any, Iterable

from .factory_defaults import factory_user_preferences
from .interfaces import PreferencesPersistenceError, TimeSeriesUserPreferences
from ..settings.model import (
    AppearanceSettings,
    EnsembleStyleSettings,
    ExportSettings,
    FitAnalysisDefaults,
    FitStyleSettings,
    ReplicaAnalysisDefaults,
    ReplicaSettings,
    ResidualStyleSettings,
    SeriesStyleSettings,
)

SCHEMA_VERSION = 2
DEFAULT_PREFIX = "insar_explorer/time_series"


def _qsettings_status_code(status: Any) -> int:
    """Return a stable integer for Qt 5 ints and Qt 6 enum wrappers."""
    if status is None:
        return 0
    value = getattr(status, "value", status)
    if callable(value):
        value = value()
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        name = getattr(status, "name", "")
        if callable(name):
            name = name()
        return 0 if str(name).split(".")[-1] == "NoError" else -1


def _runtime_versions() -> str:
    """Return non-sensitive QGIS/Qt runtime details for diagnostics."""
    details = []
    try:
        from qgis.core import Qgis
        details.append(f"QGIS={getattr(Qgis, 'QGIS_VERSION', 'unknown')}")
    except Exception:
        details.append("QGIS=unavailable")
    try:
        from qgis.PyQt.QtCore import PYQT_VERSION_STR, QT_VERSION_STR
        details.extend((f"Qt={QT_VERSION_STR}", f"PyQt={PYQT_VERSION_STR}"))
    except Exception:
        details.extend(("Qt=unavailable", "PyQt=unavailable"))
    return ", ".join(details)


def read_bool(value: Any, default: bool) -> bool:
    """Coerce common QSettings Boolean representations safely."""
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
    return default


def read_int(value: Any, default: int, minimum=None, maximum=None) -> int:
    """Coerce a bounded integer or return its field default."""
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if minimum is not None and result < minimum:
        return default
    if maximum is not None and result > maximum:
        return default
    return result


def read_float(value: Any, default: float, minimum=None, maximum=None) -> float:
    """Coerce a bounded float or return its field default."""
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if minimum is not None and result < minimum:
        return default
    if maximum is not None and result > maximum:
        return default
    return result


def read_choice(value: Any, default: str, allowed: Iterable[str]) -> str:
    """Return a stable string choice when allowed, otherwise the default."""
    normalized = str(value) if value is not None else default
    return normalized if normalized in allowed else default


# (scope, dataclass field, key suffix, value kind, optional constraints)
KEY_SPECS = (
    ("series_defaults", "marker", "series/marker", "str", None),
    ("series_defaults", "marker_size", "series/marker_size", "float", (0, 100)),
    ("series_defaults", "marker_color", "series/marker_color", "str", None),
    ("series_defaults", "marker_opacity", "series/marker_opacity", "float", (0, 1)),
    ("series_defaults", "marker_edge_color", "series/marker_edge_color", "str", None),
    ("series_defaults", "line_style", "series/line_style", "str", None),
    ("series_defaults", "line_color", "series/line_color", "str", None),
    ("series_defaults", "line_opacity", "series/line_opacity", "float", (0, 1)),
    ("series_defaults", "line_width", "series/line_width", "float", (0, 100)),
    ("ensemble_defaults", "member_line_color", "ensemble/member_line_color", "str", None),
    ("ensemble_defaults", "member_line_width", "ensemble/member_line_width", "float", (0, 20)),
    ("ensemble_defaults", "member_line_alpha", "ensemble/member_line_alpha", "float", (0, 1)),
    ("ensemble_defaults", "fill_color", "ensemble/fill_color", "str", None),
    ("ensemble_defaults", "fill_alpha", "ensemble/fill_alpha", "float", (0, 1)),
    ("fit_defaults", "line_style", "fit/line_style", "str", None),
    ("fit_defaults", "line_color", "fit/line_color", "str", None),
    ("fit_defaults", "line_width", "fit/line_width", "float", (0, 100)),
    ("fit_defaults", "line_alpha", "fit/line_alpha", "float", (0, 1)),
    ("residual_defaults", "marker", "residual/marker", "str", None),
    ("residual_defaults", "marker_color", "residual/marker_color", "str", None),
    ("residual_defaults", "marker_edge_color", "residual/marker_edge_color", "str", None),
    ("residual_defaults", "marker_size", "residual/marker_size", "float", (0, 100)),
    ("residual_defaults", "marker_alpha", "residual/marker_alpha", "float", (0, 1)),
    ("residual_defaults", "line_style", "residual/line_style", "str", None),
    ("residual_defaults", "line_color", "residual/line_color", "str", None),
    ("residual_defaults", "line_width", "residual/line_width", "float", (0, 100)),
    ("residual_defaults", "line_alpha", "residual/line_alpha", "float", (0, 1)),
    ("replica_defaults", "pair_count", "replica/pair_count", "int", (1, 10)),
    ("replica_defaults", "color_1", "replica/color_1", "str", None),
    ("replica_defaults", "color_2", "replica/color_2", "str", None),
    ("replica_defaults", "opacity", "replica/opacity", "float", (0, 1)),
    ("replica_defaults", "marker", "replica/marker", "str", None),
    ("replica_defaults", "marker_size", "replica/marker_size", "float", (0, 100)),
    ("fit_analysis_defaults", "enabled", "analysis_defaults/fit/enabled", "bool", None),
    ("fit_analysis_defaults", "model", "analysis_defaults/fit/model", "choice",
     ("poly-1", "poly-2", "poly-3", "exp", "log")),
    ("fit_analysis_defaults", "seasonal", "analysis_defaults/fit/seasonal", "bool", None),
    ("fit_analysis_defaults", "show_residuals", "analysis_defaults/fit/show_residuals", "bool", None),
    ("replica_analysis_defaults", "enabled", "analysis_defaults/replica/enabled", "bool", None),
    ("replica_analysis_defaults", "pair_count", "analysis_defaults/replica/pair_count", "int", (1, 10)),
    ("replica_analysis_defaults", "interval_mm", "analysis_defaults/replica/interval_mm", "float", (0.1, 10000)),
    ("appearance", "time_series_title", "appearance/time_series_title", "str", None),
    ("appearance", "residual_title", "appearance/residual_title", "str", None),
    ("appearance", "time_series_x_label", "appearance/time_series_x_label", "str", None),
    ("appearance", "residual_x_label", "appearance/residual_x_label", "str", None),
    ("appearance", "time_series_y_label", "appearance/time_series_y_label", "str", None),
    ("appearance", "residual_y_label", "appearance/residual_y_label", "str", None),
    ("appearance", "font_size", "appearance/font_size", "float", (1, 200)),
    ("appearance", "grid_mode", "appearance/grid_mode", "choice", AppearanceSettings.GRID_MODES),
    ("appearance", "plot_background", "appearance/plot_background", "str", None),
    ("appearance", "canvas_background", "appearance/canvas_background", "str", None),
    ("appearance", "date_format", "appearance/date_format", "str", None),
    ("export", "dpi", "export/dpi", "choice", ExportSettings.DPI_OPTIONS),
    ("export", "aspect_ratio", "export/aspect_ratio", "float", (1, 10)),
    ("export", "include_attribution", "export/include_attribution", "bool", None),
)

_SCOPE_TYPES = {
    "series_defaults": SeriesStyleSettings,
    "ensemble_defaults": EnsembleStyleSettings,
    "fit_defaults": FitStyleSettings,
    "residual_defaults": ResidualStyleSettings,
    "replica_defaults": ReplicaSettings,
    "fit_analysis_defaults": FitAnalysisDefaults,
    "replica_analysis_defaults": ReplicaAnalysisDefaults,
    "appearance": AppearanceSettings,
    "export": ExportSettings,
}


class QSettingsUserPreferencesRepository:
    """Persist typed user preferences in QGIS/Qt user settings."""

    def __init__(self, settings=None, prefix: str = DEFAULT_PREFIX, diagnostic=None):
        if settings is None:
            from qgis.PyQt.QtCore import QSettings
            settings = QSettings()
        self._settings = settings
        self.prefix = prefix.rstrip("/")
        self._diagnostic = diagnostic

    def key(self, suffix: str) -> str:
        """Return one fully namespaced QSettings key."""
        return f"{self.prefix}/{suffix}"

    def contains(self, suffix: str) -> bool:
        """Return whether one namespaced key exists."""
        try:
            return bool(self._settings.contains(self.key(suffix)))
        except Exception:
            return False

    def _raw(self, suffix: str, default: Any) -> Any:
        try:
            return self._settings.value(self.key(suffix), default)
        except Exception as exc:
            if self._diagnostic:
                self._diagnostic("Unable to read time-series preferences.", exc)
            return default

    @staticmethod
    def _coerce(raw: Any, default: Any, kind: str, constraints: Any) -> Any:
        if kind == "bool":
            return read_bool(raw, default)
        if kind == "int":
            return read_int(raw, default, *(constraints or (None, None)))
        if kind == "float":
            return read_float(raw, default, *(constraints or (None, None)))
        if kind == "choice":
            return read_choice(raw, default, constraints)
        return default if raw is None else str(raw)

    def load(self) -> TimeSeriesUserPreferences:
        """Load a complete normalized preference aggregate."""
        defaults = factory_user_preferences()
        values = {}
        for scope, value_type in _SCOPE_TYPES.items():
            base = getattr(defaults, scope)
            kwargs = {}
            for spec_scope, field, suffix, kind, constraints in KEY_SPECS:
                if spec_scope == scope:
                    default = getattr(base, field)
                    kwargs[field] = self._coerce(
                        self._raw(suffix, default), default, kind, constraints
                    )
            if value_type is ExportSettings:
                values[scope] = ExportSettings.normalized(**kwargs)
            elif value_type is ReplicaSettings:
                values[scope] = ReplicaSettings(
                    enabled=False,
                    interval_mm=ReplicaSettings().interval_mm,
                    **kwargs,
                )
            else:
                values[scope] = value_type(**kwargs)
        return TimeSeriesUserPreferences(**values)

    def _write(self, suffix: str, value: Any) -> None:
        try:
            self._settings.setValue(self.key(suffix), value)
        except Exception as exc:
            raise PreferencesPersistenceError(
                "Unable to save time-series preferences."
            ) from exc

    def read_migration_completed(self, suffix: str) -> bool:
        """Return whether a migration completion marker is explicitly true."""
        return self.contains(suffix) and read_bool(self._raw(suffix, False), False)

    def write_schema_version(self, version: int, *, sync: bool = True) -> None:
        """Write the preference schema version for migration coordination."""
        self._write("schema_version", int(version))
        if sync:
            self.sync()

    def write_migration_completed(
        self, suffix: str, completed: bool, *, sync: bool = True
    ) -> None:
        """Write one migration completion marker."""
        self._write(suffix, bool(completed))
        if sync:
            self.sync()

    def remove(self, suffix: str, *, sync: bool = True) -> None:
        """Remove one namespaced migration key."""
        try:
            self._settings.remove(self.key(suffix))
        except Exception as exc:
            raise PreferencesPersistenceError(
                "Unable to update time-series preferences."
            ) from exc
        if sync:
            self.sync()

    def _status_code(self) -> int:
        status_method = getattr(self._settings, "status", None)
        return _qsettings_status_code(status_method()) if status_method else 0

    def sync(self, *, scope: str = "preferences") -> None:
        """Synchronize writes using Qt 5/Qt 6 compatible status handling.

        Qt 5 exposes ``QSettings.status()`` as an integer, while Qt 6 may
        expose a scoped enum.  The value is canonicalized locally and every
        non-zero status is treated as a persistence failure.  Same-instance
        read-back is deliberately not used as a durability signal.
        """
        try:
            sync_method = getattr(self._settings, "sync", None)
            if sync_method:
                sync_method()
            current_status = self._status_code()
            if current_status != 0:
                raise RuntimeError(
                    "QSettings synchronization failed "
                    f"(scope={scope}, status={current_status}, {_runtime_versions()})"
                )
        except PreferencesPersistenceError:
            raise
        except Exception as exc:
            raise PreferencesPersistenceError(
                "Setting applied, but it could not be saved for the next session."
            ) from exc

    def save_scope(
        self, scope: str, settings: Any, *, only_missing: bool = False,
        sync: bool = True
    ) -> None:
        """Persist one typed preference scope."""
        for spec_scope, field, suffix, _kind, _constraints in KEY_SPECS:
            if spec_scope == scope and (
                not only_missing or not self.contains(suffix)
            ):
                value = getattr(settings, field)
                self._write(suffix, value)
        self._write("schema_version", SCHEMA_VERSION)
        if sync:
            self.sync(scope=scope)

    def save_preferences_missing(
        self, preferences: TimeSeriesUserPreferences, *, sync: bool = True
    ) -> None:
        """Persist only absent keys, preserving existing QSettings values."""
        for scope in _SCOPE_TYPES:
            self.save_scope(
                scope,
                getattr(preferences, scope),
                only_missing=True,
                sync=False,
            )
        if sync:
            self.sync()

    def save_series_defaults(self, settings: SeriesStyleSettings) -> None:
        self.save_scope("series_defaults", settings)

    def save_ensemble_defaults(self, settings: EnsembleStyleSettings) -> None:
        self.save_scope("ensemble_defaults", settings)

    def save_fit_defaults(self, settings: FitStyleSettings) -> None:
        self.save_scope("fit_defaults", settings)

    def save_residual_defaults(self, settings: ResidualStyleSettings) -> None:
        self.save_scope("residual_defaults", settings)

    def save_replica_defaults(self, settings: ReplicaSettings) -> None:
        self.save_scope("replica_defaults", settings)

    def save_fit_analysis_defaults(self, settings: FitAnalysisDefaults) -> None:
        self.save_scope("fit_analysis_defaults", settings)

    def save_replica_analysis_defaults(self, settings: ReplicaAnalysisDefaults) -> None:
        self.save_scope("replica_analysis_defaults", settings)

    def save_appearance(self, settings: AppearanceSettings) -> None:
        self.save_scope("appearance", settings)

    def save_export(self, settings: ExportSettings) -> None:
        self.save_scope("export", settings)
