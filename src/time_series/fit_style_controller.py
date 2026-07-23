"""Fit-line style model and selection-oriented mutation service."""

from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Iterable

from ..models.time_series import TimeSeriesSnapshot, TimeSeriesStyle
from .style_schema import (
    FIT_LINE_STYLE_DEFAULT,
    FIT_LINE_STYLE_OPTIONS,
    FIT_LINE_WIDTH_DEFAULT,
    FIT_LINE_WIDTH_RANGE,
    normalize_color,
    normalize_fit_line_style,
    normalize_number, normalize_alpha,
)

FIT_STYLE_KEYS = ("line style", "line color", "line width", "line alpha")


@dataclass(frozen=True)
class FitStyle:
    """Normalized appearance values for a fitted time-series curve."""

    line_style: str = FIT_LINE_STYLE_DEFAULT
    line_color: str = "#242424"
    line_width: float = FIT_LINE_WIDTH_DEFAULT
    line_alpha: float = 1.0

    @classmethod
    def fromParams(cls, params):
        """Build a normalized fit style from complete plot parameters."""
        values = params.get("model fit", {}) if isinstance(params, dict) else {}
        return cls(
            line_style=normalize_fit_line_style(values.get("line style")),
            line_color=normalize_color(values.get("line color"), "#242424"),
            line_width=normalize_number(
                values.get("line width"), FIT_LINE_WIDTH_RANGE, FIT_LINE_WIDTH_DEFAULT
            ),
            line_alpha=normalize_alpha(values.get("line alpha"), 1.0),
        )

    def asParams(self):
        """Return JSON-compatible values keyed for the existing model-fit section."""
        return {
            "line style": self.line_style,
            "line color": self.line_color,
            "line width": self.line_width,
            "line alpha": self.line_alpha,
        }


class FitStyleController:
    """Apply fit-only style changes without touching series or residual styling."""

    STYLE_KEYS = {
        "line_type": "line style",
        "line_color": "line color",
        "line_width": "line width",
        "line_opacity": "line alpha",
    }

    def fitStyle(self, snapshot: TimeSeriesSnapshot):
        """Return the normalized fit style for one snapshot."""
        return FitStyle.fromParams(snapshot.style.params)

    def applyProperty(self, snapshots: Iterable[TimeSeriesSnapshot], property_name, value):
        """Apply one fit property to supplied snapshots and return changed targets."""
        key = self.STYLE_KEYS[property_name]
        changed = []
        for snapshot in snapshots:
            params = deepcopy(snapshot.style.params)
            params.setdefault("model fit", {})[key] = self._normalize(key, value)
            updated_style = TimeSeriesStyle.fromParams(
                params,
                label=snapshot.style.label,
                visible=snapshot.style.visible,
                z_order=snapshot.style.z_order,
            )
            changed.append(replace(snapshot, style=updated_style))
        return changed

    def applyValues(self, snapshots: Iterable[TimeSeriesSnapshot], values):
        """Apply normalized fit values to supplied snapshots only."""
        changed = []
        for snapshot in snapshots:
            params = deepcopy(snapshot.style.params)
            fit = params.setdefault("model fit", {})
            for key in FIT_STYLE_KEYS:
                if key in values:
                    fit[key] = self._normalize(key, values[key])
            updated_style = TimeSeriesStyle.fromParams(
                params,
                label=snapshot.style.label,
                visible=snapshot.style.visible,
                z_order=snapshot.style.z_order,
            )
            changed.append(replace(snapshot, style=updated_style))
        return changed

    @staticmethod
    def _normalize(key, value):
        """Normalize one fit property using the shared series control schema."""
        if key == "line style":
            return normalize_fit_line_style(value)
        if key == "line color":
            return normalize_color(value, "#242424")
        if key == "line width":
            return normalize_number(value, FIT_LINE_WIDTH_RANGE, FIT_LINE_WIDTH_DEFAULT)
        if key == "line alpha":
            return normalize_alpha(value, 1.0)
        return value

    @staticmethod
    def supportedOptions():
        """Return supported fit-line selector options for diagnostics."""
        return {"line style": FIT_LINE_STYLE_OPTIONS}
