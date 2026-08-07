"""Neutral geometry resolution for time-series map indicators."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping, Optional

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsGeometry,
    QgsPointXY,
)

from ..models.time_series import SpatialSelection


@dataclass(frozen=True)
class PointIndicatorLocation:
    """Resolved point and CRS used by map overlays."""

    point: QgsPointXY
    source_crs: QgsCoordinateReferenceSystem


def _valid_crs_copy(value) -> Optional[QgsCoordinateReferenceSystem]:
    """Return a defensive valid CRS copy, or ``None``."""
    if value is None:
        return None
    crs = QgsCoordinateReferenceSystem(value)
    return crs if crs.isValid() else None


def _finite_point(x, y) -> Optional[QgsPointXY]:
    """Return a point only when both coordinates are finite numbers."""
    try:
        x_value = float(x)
        y_value = float(y)
    except (TypeError, ValueError):
        return None
    if not isfinite(x_value) or not isfinite(y_value):
        return None
    return QgsPointXY(x_value, y_value)


def resolve_point_indicator_location(
    selection: Optional[SpatialSelection],
) -> Optional[PointIndicatorLocation]:
    """Return a point and source CRS for a supported point selection."""
    if selection is None:
        return None

    snapshot = selection.map_location
    if snapshot is not None:
        point = _finite_point(snapshot.x, snapshot.y)
        crs = _valid_crs_copy(snapshot.crs)
        if point is not None and crs is not None:
            return PointIndicatorLocation(point, crs)
        return None

    value = selection.value
    if value is None:
        return None

    if isinstance(value, Mapping):
        point = _finite_point(value.get("x"), value.get("y"))
        crs = _valid_crs_copy(value.get("crs"))
    elif hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "crs"):
        point = _finite_point(value.x, value.y)
        crs = _valid_crs_copy(value.crs)
    else:
        point = None
        crs = None

    if point is None or crs is None:
        return None
    return PointIndicatorLocation(point, crs)


def resolve_polygon_indicator_geometry(selection: Optional[SpatialSelection]):
    """Return polygon geometry and source CRS for a supported selection."""
    if selection is None:
        return None
    value = selection.value
    if value is None:
        return None
    if isinstance(value, Mapping):
        geometry = value.get("geom")
        crs = _valid_crs_copy(value.get("crs"))
    elif hasattr(value, "geom") and hasattr(value, "crs"):
        geometry = value.geom
        crs = _valid_crs_copy(value.crs)
    elif isinstance(value, QgsGeometry):
        geometry = value
        crs = None
    else:
        return None
    if geometry is None or crs is None:
        return None
    return QgsGeometry(geometry), crs
