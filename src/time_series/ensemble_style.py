"""Snapshot-owned ensemble style model and property-level mutation service."""

from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Iterable

from ..models.time_series import TimeSeriesSnapshot, TimeSeriesStyle, presentation_from_legacy_params
from .style_schema import normalize_color, normalize_number

ENSEMBLE_MEMBER_LINE_STYLE = "series line style"
ENSEMBLE_MEMBER_LINE_SOLID_STYLE = "-"
ENSEMBLE_MEMBER_LINE_COLOR = "series line color"
ENSEMBLE_MEMBER_LINE_WIDTH = "series line width"
ENSEMBLE_MEMBER_LINE_ALPHA = "series line alpha"
ENSEMBLE_FILL_COLOR = "series fill color"
ENSEMBLE_FILL_ALPHA = "series fill alpha"

ENSEMBLE_STYLE_KEYS = (
    ENSEMBLE_MEMBER_LINE_COLOR,
    ENSEMBLE_MEMBER_LINE_WIDTH,
    ENSEMBLE_MEMBER_LINE_ALPHA,
    ENSEMBLE_FILL_COLOR,
    ENSEMBLE_FILL_ALPHA,
)
ENSEMBLE_MEMBER_WIDTH_RANGE = (0.0, 20.0)
ENSEMBLE_MEMBER_WIDTH_STEP = 0.1
ENSEMBLE_MEMBER_WIDTH_DEFAULT = 0.5
ENSEMBLE_OPACITY_RANGE = (0.0, 1.0)


@dataclass(frozen=True)
class EnsembleStyle:
    """Appearance of member lines and spread for one ensemble snapshot."""

    member_line_color: str = "gray"
    member_line_width: float = ENSEMBLE_MEMBER_WIDTH_DEFAULT
    member_line_alpha: float = 0.5
    fill_color: str = "#1f77b4"
    fill_alpha: float = 0.2

    @classmethod
    def fromParams(cls, params):
        """Build normalized ensemble appearance from copied plot parameters."""
        values = params.get("time series plot", {}) if isinstance(params, dict) else {}
        return cls(
            member_line_color=normalize_color(values.get(ENSEMBLE_MEMBER_LINE_COLOR), "gray"),
            member_line_width=normalize_number(
                values.get(ENSEMBLE_MEMBER_LINE_WIDTH), ENSEMBLE_MEMBER_WIDTH_RANGE, ENSEMBLE_MEMBER_WIDTH_DEFAULT
            ),
            member_line_alpha=normalize_number(values.get(ENSEMBLE_MEMBER_LINE_ALPHA), ENSEMBLE_OPACITY_RANGE, 0.5),
            fill_color=normalize_color(values.get(ENSEMBLE_FILL_COLOR), "#1f77b4"),
            fill_alpha=normalize_number(values.get(ENSEMBLE_FILL_ALPHA), ENSEMBLE_OPACITY_RANGE, 0.2),
        )

    def asParams(self):
        """Return persisted/runtime values using existing canonical keys."""
        return {
            ENSEMBLE_MEMBER_LINE_COLOR: self.member_line_color,
            ENSEMBLE_MEMBER_LINE_WIDTH: self.member_line_width,
            ENSEMBLE_MEMBER_LINE_ALPHA: self.member_line_alpha,
            ENSEMBLE_FILL_COLOR: self.fill_color,
            ENSEMBLE_FILL_ALPHA: self.fill_alpha,
        }


class EnsembleStyleController:
    """Apply ensemble-only changes to explicit ensemble-capable snapshots."""

    STYLE_KEYS = {
        "member_color": ENSEMBLE_MEMBER_LINE_COLOR,
        "member_width": ENSEMBLE_MEMBER_LINE_WIDTH,
        "member_opacity": ENSEMBLE_MEMBER_LINE_ALPHA,
        "fill_color": ENSEMBLE_FILL_COLOR,
        "fill_opacity": ENSEMBLE_FILL_ALPHA,
    }

    @staticmethod
    def applicableSnapshots(snapshots: Iterable[TimeSeriesSnapshot]):
        """Return selection targets that already contain ensemble data."""
        return [snapshot for snapshot in snapshots if snapshot.data.hasEnsembleData()]

    def ensembleStyle(self, snapshot: TimeSeriesSnapshot):
        """Return normalized snapshot-owned ensemble appearance."""
        return EnsembleStyle.fromParams(snapshot.style.params)

    def mixedProperties(self, snapshots):
        """Return ensemble property names with mixed selected values."""
        snapshots = self.applicableSnapshots(snapshots)
        if len(snapshots) < 2:
            return set()
        mixed = set()
        for name, key in self.STYLE_KEYS.items():
            values = [repr(s.style.params.get("time series plot", {}).get(key)) for s in snapshots]
            if len(set(values)) > 1:
                mixed.add(name)
        return mixed

    def applyProperty(self, snapshots, property_name, value):
        """Apply one normalized ensemble property to applicable snapshots only."""
        return self.applyValues(snapshots, {self.STYLE_KEYS[property_name]: value})

    def applyValues(self, snapshots, values):
        """Apply supplied ensemble values while preserving all other style metadata."""
        changed = []
        for snapshot in self.applicableSnapshots(snapshots):
            params = deepcopy(snapshot.style.params)
            plot = params.setdefault("time series plot", {})
            for key in ENSEMBLE_STYLE_KEYS:
                if key in values:
                    plot[key] = self._normalize(key, values[key])
            updated_style = TimeSeriesStyle.fromParams(
                params, label=snapshot.style.label, visible=snapshot.style.visible,
                z_order=snapshot.style.z_order,
            )
            changed.append(replace(snapshot, presentation=presentation_from_legacy_params(
                updated_style.params, label=updated_style.label,
                visible=updated_style.visible, z_order=updated_style.z_order,
            )))
        return changed

    @staticmethod
    def _normalize(key, value):
        if key in (ENSEMBLE_MEMBER_LINE_COLOR, ENSEMBLE_FILL_COLOR):
            return normalize_color(value, "gray" if key == ENSEMBLE_MEMBER_LINE_COLOR else "#1f77b4")
        if key == ENSEMBLE_MEMBER_LINE_WIDTH:
            return normalize_number(value, ENSEMBLE_MEMBER_WIDTH_RANGE, ENSEMBLE_MEMBER_WIDTH_DEFAULT)
        if key in (ENSEMBLE_MEMBER_LINE_ALPHA, ENSEMBLE_FILL_ALPHA):
            return normalize_number(value, ENSEMBLE_OPACITY_RANGE, 0.5 if key == ENSEMBLE_MEMBER_LINE_ALPHA else 0.2)
        return value
