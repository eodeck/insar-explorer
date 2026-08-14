"""Record-owned map navigation helpers for committed time-series selections."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsPointXY,
)

from ..models.time_series import SpatialSelection, SpatialSelectionKind
from .map_indicator_geometry import (
    resolve_point_indicator_location,
    resolve_polygon_indicator_geometry,
)


@dataclass(frozen=True)
class SelectionNavigationLocation:
    """A normalized representative point and its record-owned source CRS."""

    point: QgsPointXY
    source_crs: QgsCoordinateReferenceSystem
    canvas_compatible_without_crs: bool = False


def _normalized_point(point) -> Optional[QgsPointXY]:
    """Return a finite ``QgsPointXY`` copied through numeric coordinates."""
    if point is None:
        return None
    try:
        x = float(point.x())
        y = float(point.y())
    except (AttributeError, TypeError, ValueError):
        return None
    if not math.isfinite(x) or not math.isfinite(y):
        return None
    return QgsPointXY(x, y)


def _valid_crs_copy(crs) -> Optional[QgsCoordinateReferenceSystem]:
    """Return a defensive valid CRS copy, or ``None``."""
    if crs is None:
        return None
    copy = QgsCoordinateReferenceSystem(crs)
    return copy if copy.isValid() else None


def resolve_selection_navigation_location(
    selection: Optional[SpatialSelection],
) -> Optional[SelectionNavigationLocation]:
    """Resolve one committed selection to a representative record-owned point."""
    if selection is None:
        return None

    if selection.map_location is not None:
        snapshot = selection.map_location
        point = _normalized_point(QgsPointXY(float(snapshot.x), float(snapshot.y)))
        crs = _valid_crs_copy(snapshot.crs)
        if point is not None and crs is not None:
            return SelectionNavigationLocation(
                point=point, source_crs=crs, canvas_compatible_without_crs=True
            )
        return None

    if selection.kind is SpatialSelectionKind.POINT:
        location = resolve_point_indicator_location(selection)
        if location is None:
            return None
        point = _normalized_point(location.point)
        crs = _valid_crs_copy(location.source_crs)
        if point is None or crs is None:
            return None
        return SelectionNavigationLocation(point=point, source_crs=crs)

    if selection.kind is not SpatialSelectionKind.POLYGON:
        return None

    resolved = resolve_polygon_indicator_geometry(selection)
    if resolved is None:
        return None
    geometry, source_crs = resolved
    source_crs = _valid_crs_copy(source_crs)
    if source_crs is None or geometry is None or geometry.isEmpty():
        return None

    representative = geometry.pointOnSurface()
    point = _normalized_point(
        None if representative is None or representative.isEmpty() else representative.asPoint()
    )
    if point is None:
        centroid = geometry.centroid()
        point = _normalized_point(
            None if centroid is None or centroid.isEmpty() else centroid.asPoint()
        )
    if point is None:
        return None
    return SelectionNavigationLocation(point=point, source_crs=source_crs)


def ensure_canvas_navigation_crs(canvas, project, source_crs):
    """Return the valid destination CRS without assigning an absent project CRS."""
    source_crs = _valid_crs_copy(source_crs)
    if source_crs is None:
        raise ValueError("selection source CRS is invalid")

    canvas_crs = _valid_crs_copy(canvas.mapSettings().destinationCrs())
    if canvas_crs is not None:
        return canvas_crs, False

    project_crs = _valid_crs_copy(project.crs())
    if project_crs is not None:
        canvas.setDestinationCrs(project_crs)
        return project_crs, False

    return None, False


def transform_navigation_point(location, destination_crs, project):
    """Transform a navigation location into ``destination_crs`` as ``QgsPointXY``."""
    if location is None:
        raise ValueError("navigation location is missing")
    source_crs = _valid_crs_copy(location.source_crs)
    destination_crs = _valid_crs_copy(destination_crs)
    if source_crs is None or destination_crs is None:
        raise ValueError("navigation CRS is invalid")

    point = _normalized_point(location.point)
    if point is None:
        raise ValueError("navigation point is invalid")
    if source_crs == destination_crs:
        return point

    transform = QgsCoordinateTransform(
        source_crs, destination_crs, project.transformContext()
    )
    transformed = transform.transform(
        QgsPointXY(float(point.x()), float(point.y()))
    )
    normalized = _normalized_point(transformed)
    if normalized is None:
        raise ValueError("coordinate transform produced an invalid point")
    return normalized


def recenter_canvas_preserving_scale(canvas, point, *, preserve_scale=True):
    """Recenter the canvas and restore scale only when QGIS changed it."""
    normalized = _normalized_point(point)
    if normalized is None:
        raise ValueError("canvas center point is invalid")

    old_scale = float(canvas.scale())
    canvas.setCenter(normalized)
    if preserve_scale and math.isfinite(old_scale) and old_scale > 0.0:
        new_scale = float(canvas.scale())
        if not math.isclose(new_scale, old_scale, rel_tol=1e-9, abs_tol=1e-6):
            canvas.zoomScale(old_scale)
    canvas.refresh()
