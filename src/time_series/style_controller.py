"""Selection-oriented time-series style mutation service."""

from copy import deepcopy
from dataclasses import replace
from typing import Iterable

from .fit_style_controller import FIT_STYLE_KEYS
from .style_schema import PERSISTED_STYLE_KEYS
from ..models.time_series import (
    TimeSeriesSnapshot,
    TimeSeriesStyle,
    presentation_from_legacy_params,
    randomTimeSeriesColor,
)


class TimeSeriesStyleController:
    """Apply property-level style changes to explicitly selected snapshots."""

    STYLE_KEYS = {
        "marker_type": "marker",
        "marker_color": "marker color",
        "marker_size": "marker size",
        "marker_opacity": "marker alpha",
        "line_type": "line style",
        "line_color": "line color",
        "line_width": "line width",
        "line_opacity": "line alpha",
    }

    def selectedSeriesStyles(self, snapshots: Iterable[TimeSeriesSnapshot]):
        """Return styles for explicit selection targets without assuming ordering."""
        return [snapshot.style for snapshot in snapshots]

    def mixedProperties(self, snapshots: Iterable[TimeSeriesSnapshot]):
        """Return editable property names whose values differ across selected styles."""
        snapshots = list(snapshots)
        if len(snapshots) < 2:
            return set()
        mixed = set()
        for property_name, key in self.STYLE_KEYS.items():
            values = [repr(snapshot.style.params.get("time series plot", {}).get(key)) for snapshot in snapshots]
            if len(set(values)) > 1:
                mixed.add(property_name)
        return mixed

    def applyProperty(self, snapshots: Iterable[TimeSeriesSnapshot], property_name, value):
        """Apply one style property to every supplied snapshot and return changed targets."""
        key = self.STYLE_KEYS[property_name]
        changed = []
        for snapshot in snapshots:
            params = deepcopy(snapshot.style.params)
            params.setdefault("time series plot", {})[key] = value
            updated_style = TimeSeriesStyle.fromParams(
                params,
                label=snapshot.style.label,
                visible=snapshot.style.visible,
                z_order=snapshot.style.z_order,
            )
            changed.append(replace(snapshot, presentation=presentation_from_legacy_params(
                updated_style.params, label=updated_style.label,
                visible=updated_style.visible, z_order=updated_style.z_order,
            )))
        return changed

    @staticmethod
    def _globalSettings(params):
        """Return figure-wide settings without snapshot-owned series style values."""
        global_params = {}
        for section, section_values in params.items():
            if section == "export":
                continue
            if section == "model fit":
                global_params[section] = {
                    key: deepcopy(value)
                    for key, value in section_values.items()
                    if key not in FIT_STYLE_KEYS
                }
                continue
            if section != "time series plot":
                global_params[section] = deepcopy(section_values)
                continue
            global_params[section] = {
                key: deepcopy(value)
                for key, value in section_values.items()
                if key not in PERSISTED_STYLE_KEYS
            }
        return global_params

    def globalSettingsChanged(self, previous_params, current_params):
        """Return whether any figure-wide plot setting changed."""
        return self._globalSettings(previous_params) != self._globalSettings(current_params)

    def applyGlobalSettings(self, snapshots, runtime_params):
        """Synchronize figure-wide settings while preserving every series style key."""
        global_params = self._globalSettings(runtime_params)
        changed = []
        for snapshot in snapshots:
            params = deepcopy(snapshot.style.params)
            for section, section_values in global_params.items():
                if section != "time series plot":
                    params[section] = deepcopy(section_values)
                    continue
                plot = params.setdefault(section, {})
                for key, value in section_values.items():
                    plot[key] = deepcopy(value)
            updated_style = TimeSeriesStyle.fromParams(
                params,
                label=snapshot.style.label,
                visible=snapshot.style.visible,
                z_order=snapshot.style.z_order,
            )
            changed.append(replace(snapshot, presentation=presentation_from_legacy_params(
                updated_style.params, label=updated_style.label,
                visible=updated_style.visible, z_order=updated_style.z_order,
            )))
        return changed

    def applyStyleValues(self, snapshots, changed_style_values):
        """Apply only changed series-style values to explicit selection targets."""
        changed = []
        for snapshot in snapshots:
            params = deepcopy(snapshot.style.params)
            plot = params.setdefault("time series plot", {})
            for key, value in changed_style_values.items():
                plot[key] = deepcopy(value)
            updated_style = TimeSeriesStyle.fromParams(
                params,
                label=snapshot.style.label,
                visible=snapshot.style.visible,
                z_order=snapshot.style.z_order,
            )
            changed.append(replace(snapshot, presentation=presentation_from_legacy_params(
                updated_style.params, label=updated_style.label,
                visible=updated_style.visible, z_order=updated_style.z_order,
            )))
        return changed

    def applySettingsChanges(self, snapshots, runtime_params, changed_style_values):
        """Merge global settings and changed defaults into explicit selection targets."""
        changed = []
        for snapshot in snapshots:
            params = deepcopy(snapshot.style.params)
            for section, section_values in runtime_params.items():
                if section == "model fit":
                    fit = params.setdefault(section, {})
                    for key, value in section_values.items():
                        if key not in FIT_STYLE_KEYS:
                            fit[key] = deepcopy(value)
                    continue
                if section != "time series plot":
                    params[section] = deepcopy(section_values)
                    continue
                plot = params.setdefault(section, {})
                for key, value in section_values.items():
                    if key not in PERSISTED_STYLE_KEYS:
                        plot[key] = deepcopy(value)
                for key, value in changed_style_values.items():
                    plot[key] = deepcopy(value)
            updated_style = TimeSeriesStyle.fromParams(
                params,
                label=snapshot.style.label,
                visible=snapshot.style.visible,
                z_order=snapshot.style.z_order,
            )
            changed.append(replace(snapshot, presentation=presentation_from_legacy_params(
                updated_style.params, label=updated_style.label,
                visible=updated_style.visible, z_order=updated_style.z_order,
            )))
        return changed

    def randomizeColor(self, snapshots: Iterable[TimeSeriesSnapshot]):
        """Apply one random coupled marker/line color to each selected snapshot."""
        changed = []
        for snapshot in snapshots:
            color = randomTimeSeriesColor()
            params = deepcopy(snapshot.style.params)
            plot = params.setdefault("time series plot", {})
            plot["marker color"] = color
            plot["line color"] = color
            updated_style = TimeSeriesStyle.fromParams(
                params,
                label=snapshot.style.label,
                visible=snapshot.style.visible,
                z_order=snapshot.style.z_order,
            )
            changed.append(replace(snapshot, presentation=presentation_from_legacy_params(
                updated_style.params, label=updated_style.label,
                visible=updated_style.visible, z_order=updated_style.z_order,
            )))
        return changed
