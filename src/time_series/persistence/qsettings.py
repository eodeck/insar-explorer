"""QSettings-backed user-preference infrastructure.

Keys are explicit and versioned so future migrations can evolve individual
fields without serializing opaque dataclass blobs.
"""
from dataclasses import fields

from .factory_defaults import factory_user_preferences
from .interfaces import PreferencesPersistenceError, TimeSeriesUserPreferences
from ..settings.model import (
    AppearanceSettings, EnsembleStyleSettings, ExportSettings, FitStyleSettings,
    ReplicaSettings, ResidualStyleSettings, SeriesStyleSettings,
)

SCHEMA_VERSION = 1
DEFAULT_PREFIX = "insar_explorer/time_series"


def read_bool(value, default):
    if isinstance(value, bool): return value
    if isinstance(value, (int, float)) and value in (0, 1): return bool(value)
    if isinstance(value, str):
        v=value.strip().lower()
        if v in {"true","1","yes","on"}: return True
        if v in {"false","0","no","off",""}: return False
    return default


def read_int(value, default, minimum=None, maximum=None):
    try: result=int(value)
    except (TypeError, ValueError, OverflowError): return default
    if minimum is not None and result < minimum: return default
    if maximum is not None and result > maximum: return default
    return result


def read_float(value, default, minimum=None, maximum=None):
    try: result=float(value)
    except (TypeError, ValueError, OverflowError): return default
    if minimum is not None and result < minimum: return default
    if maximum is not None and result > maximum: return default
    return result


def read_choice(value, default, allowed):
    value=str(value) if value is not None else default
    return value if value in allowed else default


# scope, field, key suffix, type, optional constraints
KEY_SPECS = (
    *[("series_defaults", n, "series/"+k, t, c) for n,k,t,c in (
      ("marker","marker","str",None),("marker_size","marker_size","float",(0,100)),
      ("marker_color","marker_color","str",None),("marker_opacity","marker_opacity","float",(0,1)),
      ("marker_edge_color","marker_edge_color","str",None),("line_style","line_style","str",None),
      ("line_color","line_color","str",None),("line_opacity","line_opacity","float",(0,1)),
      ("line_width","line_width","float",(0,100)) )],
    *[("ensemble_defaults", n, "ensemble/"+k, t, c) for n,k,t,c in (
      ("member_line_color","member_line_color","str",None),("member_line_width","member_line_width","float",(0,20)),
      ("member_line_alpha","member_line_alpha","float",(0,1)),("fill_color","fill_color","str",None),
      ("fill_alpha","fill_alpha","float",(0,1)) )],
    *[("fit_defaults", n, "fit/"+k, t, c) for n,k,t,c in (
      ("line_style","line_style","str",None),("line_color","line_color","str",None),
      ("line_width","line_width","float",(0,100)),("line_alpha","line_alpha","float",(0,1)) )],
    *[("residual_defaults", n, "residual/"+k, t, c) for n,k,t,c in (
      ("marker","marker","str",None),("marker_color","marker_color","str",None),
      ("marker_edge_color","marker_edge_color","str",None),("marker_size","marker_size","float",(0,100)),
      ("marker_alpha","marker_alpha","float",(0,1)),("line_style","line_style","str",None),
      ("line_color","line_color","str",None),("line_width","line_width","float",(0,100)),
      ("line_alpha","line_alpha","float",(0,1)) )],
    *[("replica_defaults", n, "replica/"+k, t, c) for n,k,t,c in (
      ("pair_count","pair_count","int",(1,10)),("color_1","color_1","str",None),
      ("color_2","color_2","str",None),("opacity","opacity","float",(0,1)),
      ("marker","marker","str",None),("marker_size","marker_size","float",(0,100)) )],
    *[("appearance", n, "appearance/"+k, t, c) for n,k,t,c in (
      ("time_series_title","time_series_title","str",None),("residual_title","residual_title","str",None),
      ("time_series_x_label","time_series_x_label","str",None),("residual_x_label","residual_x_label","str",None),
      ("time_series_y_label","time_series_y_label","str",None),("residual_y_label","residual_y_label","str",None),
      ("font_size","font_size","float",(1,200)),("grid_mode","grid_mode","choice",AppearanceSettings.GRID_MODES),
      ("plot_background","plot_background","str",None),("canvas_background","canvas_background","str",None),
      ("date_format","date_format","str",None) )],
    *[("export", n, "export/"+k, t, c) for n,k,t,c in (
      ("dpi","dpi","choice",ExportSettings.DPI_OPTIONS),("aspect_ratio","aspect_ratio","float",(1,10)),
      ("include_attribution","include_attribution","bool",None) )],
)

_SCOPE_TYPES = {"series_defaults":SeriesStyleSettings,"ensemble_defaults":EnsembleStyleSettings,
 "fit_defaults":FitStyleSettings,"residual_defaults":ResidualStyleSettings,
 "replica_defaults":ReplicaSettings,"appearance":AppearanceSettings,"export":ExportSettings}


class QSettingsUserPreferencesRepository:
    """Persist typed user preferences in QGIS/Qt user settings."""
    def __init__(self, settings=None, prefix=DEFAULT_PREFIX, diagnostic=None):
        if settings is None:
            from qgis.PyQt.QtCore import QSettings
            settings=QSettings()
        self._settings=settings
        self.prefix=prefix.rstrip("/")
        self._diagnostic=diagnostic

    def key(self, suffix): return f"{self.prefix}/{suffix}"
    def contains(self, suffix):
        try: return bool(self._settings.contains(self.key(suffix)))
        except Exception: return False
    def _raw(self, suffix, default):
        try: return self._settings.value(self.key(suffix), default)
        except Exception as exc:
            if self._diagnostic: self._diagnostic("Unable to read time-series preferences.", exc)
            return default
    def _coerce(self, raw, default, kind, constraints):
        if kind=="bool": return read_bool(raw, default)
        if kind=="int": return read_int(raw, default, *(constraints or (None,None)))
        if kind=="float": return read_float(raw, default, *(constraints or (None,None)))
        if kind=="choice": return read_choice(raw, default, constraints)
        if raw is None: return default
        return str(raw)

    def load(self):
        defaults=factory_user_preferences(); values={}
        for scope, typ in _SCOPE_TYPES.items():
            base=getattr(defaults, scope); kwargs={}
            for s, field, suffix, kind, constraints in KEY_SPECS:
                if s != scope: continue
                default=getattr(base, field)
                kwargs[field]=self._coerce(self._raw(suffix, default), default, kind, constraints)
            if typ is ExportSettings:
                values[scope]=ExportSettings.normalized(**kwargs)
            elif typ is ReplicaSettings:
                values[scope]=ReplicaSettings(enabled=False, interval_mm=ReplicaSettings().interval_mm, **kwargs)
            else: values[scope]=typ(**kwargs)
        return TimeSeriesUserPreferences(**values)

    def _write(self, suffix, value):
        try:
            self._settings.setValue(self.key(suffix), value)
        except Exception as exc:
            raise PreferencesPersistenceError(
                "Unable to save time-series preferences."
            ) from exc

    def read_migration_completed(self, suffix):
        """Return whether a migration completion marker is explicitly true."""
        if not self.contains(suffix):
            return False
        return read_bool(self._raw(suffix, False), False)

    def write_schema_version(self, version, *, sync=True):
        """Write the preference schema version."""
        self._write("schema_version", int(version))
        if sync:
            self.sync()

    def write_migration_completed(self, suffix, completed, *, sync=True):
        """Write one migration completion marker."""
        self._write(suffix, bool(completed))
        if sync:
            self.sync()

    def remove(self, suffix, *, sync=True):
        """Remove one namespaced preference key."""
        try:
            self._settings.remove(self.key(suffix))
        except Exception as exc:
            raise PreferencesPersistenceError(
                "Unable to update time-series preferences."
            ) from exc
        if sync:
            self.sync()
    def sync(self):
        try:
            sync=getattr(self._settings,"sync",None)
            if sync: sync()
            status=getattr(self._settings,"status",None)
            if status and status() not in (None,0): raise RuntimeError("QSettings sync failed")
        except PreferencesPersistenceError: raise
        except Exception as exc: raise PreferencesPersistenceError("Unable to save time-series preferences.") from exc
    def save_scope(self, scope, settings, only_missing=False, sync=True):
        for s, field, suffix, _, _ in KEY_SPECS:
            if s==scope and (not only_missing or not self.contains(suffix)):
                self._write(suffix, getattr(settings, field))
        self._write("schema_version", SCHEMA_VERSION)
        if sync: self.sync()
    def save_preferences_missing(self, preferences, sync=True):
        for scope in _SCOPE_TYPES: self.save_scope(scope, getattr(preferences, scope), only_missing=True, sync=False)
        if sync: self.sync()
    def save_series_defaults(self,s): self.save_scope("series_defaults",s)
    def save_ensemble_defaults(self,s): self.save_scope("ensemble_defaults",s)
    def save_fit_defaults(self,s): self.save_scope("fit_defaults",s)
    def save_residual_defaults(self,s): self.save_scope("residual_defaults",s)
    def save_replica_defaults(self,s): self.save_scope("replica_defaults",s)
    def save_appearance(self,s): self.save_scope("appearance",s)
    def save_export(self,s): self.save_scope("export",s)
