"""Residual-series style model and selection-oriented mutation service."""

from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Iterable

from ..models.time_series import TimeSeriesSnapshot, TimeSeriesStyle
from .style_schema import (
    RESIDUAL_DEFAULT_COLOR, RESIDUAL_LINE_WIDTH_RANGE, RESIDUAL_MARKER_SIZE_RANGE, normalize_alpha, normalize_color,
    normalize_number, normalize_residual_line_style, normalize_residual_marker,
)

RESIDUAL_STYLE_KEYS = (
    "marker", "marker color", "marker edge color", "marker size", "marker alpha",
    "line style", "line color", "line width", "line alpha",
)


@dataclass(frozen=True)
class ResidualStyle:
    """Normalized appearance values for one residual data series."""
    marker: str = "o"
    marker_color: str = RESIDUAL_DEFAULT_COLOR
    marker_edge_color: str = "black"
    marker_size: float = 5.0
    marker_alpha: float = 0.8
    line_style: str = ""
    line_color: str = RESIDUAL_DEFAULT_COLOR
    line_width: float = 1.0
    line_alpha: float = 0.8

    @classmethod
    def fromParams(cls, params):
        values = params.get("residual plot", {}) if isinstance(params, dict) else {}
        return cls(
            marker=normalize_residual_marker(values.get("marker"), "o"),
            marker_color=normalize_color(values.get("marker color"), RESIDUAL_DEFAULT_COLOR),
            marker_edge_color=normalize_color(values.get("marker edge color"), "black"),
            marker_size=normalize_number(values.get("marker size"), RESIDUAL_MARKER_SIZE_RANGE, 5.0),
            marker_alpha=normalize_alpha(values.get("marker alpha"), 0.8),
            line_style=normalize_residual_line_style(values.get("line style"), ""),
            line_color=normalize_color(values.get("line color"), RESIDUAL_DEFAULT_COLOR),
            line_width=normalize_number(values.get("line width"), RESIDUAL_LINE_WIDTH_RANGE, 1.0),
            line_alpha=normalize_alpha(values.get("line alpha"), 0.8),
        )

    def asParams(self):
        return {
            "marker": self.marker, "marker color": self.marker_color,
            "marker edge color": self.marker_edge_color, "marker size": self.marker_size, "marker alpha": self.marker_alpha,
            "line style": self.line_style, "line color": self.line_color,
            "line width": self.line_width, "line alpha": self.line_alpha,
        }


class ResidualStyleController:
    """Apply residual-only style changes without touching series or fit styling."""
    STYLE_KEYS = {
        "marker_type": "marker", "marker_color": "marker color",
        "marker_edge_color": "marker edge color", "marker_size": "marker size", "marker_opacity": "marker alpha",
        "line_type": "line style",
        "line_color": "line color", "line_width": "line width",
        "line_opacity": "line alpha",
    }

    def residualStyle(self, snapshot: TimeSeriesSnapshot):
        return ResidualStyle.fromParams(snapshot.style.params)

    def applyProperty(self, snapshots: Iterable[TimeSeriesSnapshot], property_name, value):
        return self.applyValues(snapshots, {self.STYLE_KEYS[property_name]: value})

    def applyValues(self, snapshots: Iterable[TimeSeriesSnapshot], values):
        changed = []
        for snapshot in snapshots:
            params = deepcopy(snapshot.style.params)
            residual = params.setdefault("residual plot", {})
            for key in RESIDUAL_STYLE_KEYS:
                if key in values:
                    residual[key] = self._normalize(key, values[key])
            updated_style = TimeSeriesStyle.fromParams(
                params, label=snapshot.style.label, visible=snapshot.style.visible,
                z_order=snapshot.style.z_order,
            )
            changed.append(replace(snapshot, style=updated_style))
        return changed

    def randomizeColor(self, snapshots):
        from random import randint
        color = "#{:02x}{:02x}{:02x}".format(randint(0,255), randint(0,255), randint(0,255))
        return self.applyValues(snapshots, {"marker color": color, "line color": color})

    @staticmethod
    def _normalize(key, value):
        if key == "marker": return normalize_residual_marker(value, "o")
        if key == "marker size": return normalize_number(value, RESIDUAL_MARKER_SIZE_RANGE, 5.0)
        if key == "line style": return normalize_residual_line_style(value, "")
        if key == "line width": return normalize_number(value, RESIDUAL_LINE_WIDTH_RANGE, 1.0)
        if key == "marker color": return normalize_color(value, RESIDUAL_DEFAULT_COLOR)
        if key == "marker edge color": return normalize_color(value, "black")
        if key == "line color": return normalize_color(value, RESIDUAL_DEFAULT_COLOR)
        if key == "marker alpha": return normalize_alpha(value, 0.8)
        if key == "line alpha": return normalize_alpha(value, 0.8)
        return value
