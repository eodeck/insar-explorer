"""Compatibility views for typed runtime settings.

Persistence implementations live in :mod:`time_series.persistence`.
"""

from copy import deepcopy
from ..persistence.qsettings import QSettingsUserPreferencesRepository

# Transitional forwarding alias for downstream imports. New code uses the protocol.
TimeSeriesSettingsPersistence = QSettingsUserPreferencesRepository


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
