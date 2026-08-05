"""QGIS map-canvas presentation for selected committed time-series records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Tuple
from uuid import UUID

from qgis.PyQt.QtGui import QColor
from qgis.core import QgsCoordinateTransform, QgsGeometry, QgsPointXY, QgsProject
from qgis.gui import QgsRubberBand, QgsVertexMarker

from ..models.time_series import SpatialSelection, SpatialSelectionKind, TimeSeriesRecord
from ..qt_compat import POLYGON_GEOMETRY
from .map_indicator_settings import factory_map_indicator_settings
from .map_indicator_style import (
    COMMITTED_COLOR_ALPHA,
    COMMITTED_COLOR_ALPHA_WHILE_PENDING,
    COMMITTED_FILL_ALPHA,
    COMMITTED_LINE_WIDTH,
    COMMITTED_POINT_INNER_SIZE,
    COMMITTED_POINT_OUTER_SIZE,
    COMMITTED_POINT_PEN_WIDTH,
    PENDING_FILL_ALPHA,
    PENDING_LINE_WIDTH,
    PENDING_POINT_INNER_SIZE,
    PENDING_POINT_OUTER_SIZE,
    PENDING_POINT_PEN_WIDTH,
    point_indicator_outer_color,
    semantic_indicator_color,
    transparent_point_fill,
)


def _enum_value(owner, enum_name, value_name):
    """Resolve scoped QGIS enums while retaining QGIS 3 legacy aliases."""
    enum_owner = getattr(owner, enum_name, None)
    if enum_owner is not None and hasattr(enum_owner, value_name):
        return getattr(enum_owner, value_name)
    return getattr(owner, value_name)


_VERTEX_MARKER_CIRCLE = _enum_value(QgsVertexMarker, "IconType", "ICON_CIRCLE")
_POINT_OUTER_RING = "outer_ring"
_POINT_INNER_RING = "inner_ring"


@dataclass(frozen=True)
class OverlayItem:
    """One canvas item with explicit overlay-layer presentation metadata."""

    item: object
    role: str
    geometry_kind: SpatialSelectionKind
    presentation_part: str = "primary"


@dataclass(frozen=True)
class RecordOverlayItems:
    """Canvas items owned by one committed record UUID."""

    target_items: Tuple[OverlayItem, ...] = ()
    reference_items: Tuple[OverlayItem, ...] = ()

    def all_items(self) -> Tuple[OverlayItem, ...]:
        return self.target_items + self.reference_items


class TimeSeriesMapOverlayRegistry:
    """Own committed selection overlays by stable record UUID."""

    def __init__(self) -> None:
        self._items_by_record_id: Dict[UUID, RecordOverlayItems] = {}

    def record_ids(self) -> Tuple[UUID, ...]:
        """Return currently represented record UUIDs."""
        return tuple(self._items_by_record_id)

    def get(self, record_id: UUID) -> Optional[RecordOverlayItems]:
        return self._items_by_record_id.get(record_id)

    def set(self, record_id: UUID, items: RecordOverlayItems) -> None:
        self._items_by_record_id[record_id] = items

    def values(self) -> Tuple[RecordOverlayItems, ...]:
        """Return all currently owned item groups."""
        return tuple(self._items_by_record_id.values())

    def pop(self, record_id: UUID) -> Optional[RecordOverlayItems]:
        return self._items_by_record_id.pop(record_id, None)

    def clear(self) -> Tuple[RecordOverlayItems, ...]:
        items = tuple(self._items_by_record_id.values())
        self._items_by_record_id.clear()
        return items


class PendingTimeSeriesMapOverlayController:
    """Project the complete pending record snapshot onto the map canvas.

    Drawing tools may own temporary interaction feedback, but this controller is
    the sole owner of stable pending target/reference indicators.
    """

    _ROLE_TARGET = "target"
    _ROLE_REFERENCE = "reference"

    def __init__(self, canvas, diagnostic: Optional[Callable[[str, Exception], None]] = None, settings_provider=None):
        self._canvas = canvas
        self._settings_provider = settings_provider or factory_map_indicator_settings
        self._diagnostic = diagnostic
        self._record: Optional[TimeSeriesRecord] = None
        self._items = RecordOverlayItems()
        destroyed = getattr(canvas, "destroyed", None)
        if destroyed is not None:
            destroyed.connect(self._canvas_destroyed)
        destination_crs_changed = getattr(canvas, "destinationCrsChanged", None)
        if destination_crs_changed is not None:
            destination_crs_changed.connect(self._refresh_for_destination_crs)

    @property
    def items(self) -> RecordOverlayItems:
        """Return currently owned stable pending canvas items."""
        return self._items

    def project_record(self, record: TimeSeriesRecord) -> None:
        """Render the complete target/reference geometry for one pending record."""
        self.clear()
        self._record = record
        target_items = self._create_selection_items(record.target, self._ROLE_TARGET)
        reference_items = self._create_selection_items(
            record.reference, self._ROLE_REFERENCE
        )
        self._items = RecordOverlayItems(target_items, reference_items)

    def refresh_style(self) -> None:
        """Restyle owned pending items from one current settings snapshot."""
        for overlay in self._items.all_items():
            self._apply_style(overlay)

    def clear(self) -> None:
        """Remove every stable pending target/reference indicator."""
        self._remove_owned_items(self._items)
        self._items = RecordOverlayItems()
        self._record = None

    def _create_selection_items(
        self, selection: Optional[SpatialSelection], role: str
    ) -> Tuple[OverlayItem, ...]:
        if selection is None:
            return ()
        try:
            if selection.kind == SpatialSelectionKind.POINT:
                point_items = self._create_point_items(selection.value, role)
                for overlay in point_items:
                    self._apply_style(overlay)
                return point_items
            if selection.kind == SpatialSelectionKind.POLYGON:
                item = self._create_polygon_item(selection.value)
                if item is None:
                    return ()
                overlay = OverlayItem(item, role, selection.kind)
                self._apply_style(overlay)
                return (overlay,)
            return ()
        except Exception as error:
            self._report("pending_map_overlay", error)
            return ()

    def _create_point_items(self, value, role: str) -> Tuple[OverlayItem, ...]:
        point, source_crs = CommittedSelectionOverlayController._point_and_crs(value)
        if point is None or source_crs is None or not source_crs.isValid():
            return ()
        destination_crs = self._canvas.mapSettings().destinationCrs()
        if source_crs != destination_crs:
            transform = QgsCoordinateTransform(
                source_crs, destination_crs, QgsProject.instance()
            )
            point = transform.transform(point)
        outer = self._new_point_marker(point)
        inner = self._new_point_marker(point)
        return (
            OverlayItem(outer, role, SpatialSelectionKind.POINT, _POINT_OUTER_RING),
            OverlayItem(inner, role, SpatialSelectionKind.POINT, _POINT_INNER_RING),
        )

    def _new_point_marker(self, point):
        marker = QgsVertexMarker(self._canvas)
        marker.setCenter(point)
        marker.setIconType(_VERTEX_MARKER_CIRCLE)
        marker.setFillColor(transparent_point_fill())
        return marker

    def _create_polygon_item(self, value):
        geometry, source_crs = CommittedSelectionOverlayController._geometry_and_crs(value)
        if geometry is None or geometry.isEmpty() or source_crs is None:
            return None
        geometry = QgsGeometry(geometry)
        destination_crs = self._canvas.mapSettings().destinationCrs()
        if source_crs.isValid() and source_crs != destination_crs:
            transform = QgsCoordinateTransform(
                source_crs, destination_crs, QgsProject.instance()
            )
            geometry.transform(transform)
        band = QgsRubberBand(self._canvas, POLYGON_GEOMETRY)
        band.setToGeometry(geometry, None)
        return band

    def _apply_style(self, overlay: OverlayItem) -> None:
        settings = self._settings_provider()
        alpha = round(255 * settings.opacity_percent / 100.0)
        color = semantic_indicator_color(overlay.role, settings, alpha=alpha)
        if overlay.geometry_kind == SpatialSelectionKind.POINT:
            is_outer = overlay.presentation_part == _POINT_OUTER_RING
            overlay.item.setColor(
                point_indicator_outer_color(settings, alpha=alpha)
                if is_outer
                else color
            )
            overlay.item.setFillColor(transparent_point_fill())
            overlay.item.setPenWidth(PENDING_POINT_PEN_WIDTH)
            overlay.item.setIconSize(
                PENDING_POINT_OUTER_SIZE if is_outer else PENDING_POINT_INNER_SIZE
            )
            return
        fill = QColor(color)
        fill.setAlpha(round(PENDING_FILL_ALPHA * settings.opacity_percent / 100.0))
        overlay.item.setStrokeColor(color)
        overlay.item.setFillColor(fill)
        overlay.item.setWidth(PENDING_LINE_WIDTH)

    def _remove_owned_items(self, owned: RecordOverlayItems) -> None:
        scene = None if self._canvas is None else self._canvas.scene()
        for overlay in owned.all_items():
            try:
                if scene is not None:
                    scene.removeItem(overlay.item)
            except Exception as error:
                self._report("pending_map_overlay_cleanup", error)

    def _refresh_for_destination_crs(self, *_):
        record = self._record
        if record is not None:
            self.project_record(record)

    def _canvas_destroyed(self, *_):
        self._canvas = None
        self._items = RecordOverlayItems()
        self._record = None

    def _report(self, scope: str, error: Exception) -> None:
        if self._diagnostic is not None:
            self._diagnostic(scope, error)


class CommittedSelectionOverlayController:
    """Present selected committed target/reference snapshots on a QGIS canvas.

    Domain records remain renderer-independent. This controller owns all QGIS
    canvas items and updates them incrementally from UUID-based list selection.
    """

    _ROLE_TARGET = "target"
    _ROLE_REFERENCE = "reference"

    def __init__(self, canvas, diagnostic: Optional[Callable[[str, Exception], None]] = None, settings_provider=None):
        self._canvas = canvas
        self._settings_provider = settings_provider or factory_map_indicator_settings
        self._diagnostic = diagnostic
        self._registry = TimeSeriesMapOverlayRegistry()
        self._records_by_id: Dict[UUID, TimeSeriesRecord] = {}
        self._pending_active = False
        destroyed = getattr(canvas, "destroyed", None)
        if destroyed is not None:
            destroyed.connect(self._canvas_destroyed)
        destination_crs_changed = getattr(canvas, "destinationCrsChanged", None)
        if destination_crs_changed is not None:
            destination_crs_changed.connect(self._refresh_for_destination_crs)

    @property
    def registry(self) -> TimeSeriesMapOverlayRegistry:
        """Expose registry state for presentation coordination and tests."""
        return self._registry

    def update_selection(
        self,
        record_ids: Iterable[UUID],
        record_provider: Callable[[UUID], Optional[TimeSeriesRecord]],
    ) -> None:
        """Incrementally synchronize committed overlays to selected UUIDs."""
        requested = []
        seen = set()
        for value in record_ids:
            record_id = value if isinstance(value, UUID) else UUID(str(value))
            if record_id not in seen:
                seen.add(record_id)
                requested.append(record_id)

        current = set(self._records_by_id)
        desired = set(requested)
        for record_id in current - desired:
            self.hide_record(record_id)
        for record_id in requested:
            if record_id in current:
                continue
            record = record_provider(record_id)
            if record is not None:
                self.show_record(record)

    def show_record(self, record: TimeSeriesRecord) -> None:
        """Create target/reference items for one committed record."""
        self.hide_record(record.id)
        self._records_by_id[record.id] = record
        target_items = self._create_selection_items(record.target, self._ROLE_TARGET)
        reference_items = self._create_selection_items(
            record.reference, self._ROLE_REFERENCE
        )
        if target_items or reference_items:
            self._registry.set(
                record.id,
                RecordOverlayItems(target_items, reference_items),
            )

    def refresh_record(self, record: TimeSeriesRecord) -> None:
        """Recreate one record's items after a geometry snapshot change."""
        if record.id in self._records_by_id:
            self.show_record(record)

    def hide_record(self, record_id: UUID) -> None:
        """Remove all canvas items owned by one committed UUID."""
        owned = self._registry.pop(record_id)
        self._records_by_id.pop(record_id, None)
        if owned is not None:
            self._remove_owned_items(owned)

    def refresh_style(self) -> None:
        """Restyle every selected committed overlay."""
        for record_items in self._registry.values():
            for overlay in record_items.all_items():
                self._apply_style(overlay)

    def set_pending_active(self, active: bool) -> None:
        """Subdue committed overlays further while pending geometry is active."""
        active = bool(active)
        if self._pending_active == active:
            return
        self._pending_active = active
        for record_items in self._registry.values():
            for overlay in record_items.all_items():
                self._apply_style(overlay)

    def clear_committed(self) -> None:
        """Remove every committed selection overlay without touching pending items."""
        for owned in self._registry.clear():
            self._remove_owned_items(owned)
        self._records_by_id.clear()

    def clear_all(self) -> None:
        """Clear all controller-owned overlay state for reset/unload."""
        self.clear_committed()
        self._pending_active = False

    def _create_selection_items(
        self, selection: Optional[SpatialSelection], role: str
    ) -> Tuple[OverlayItem, ...]:
        if selection is None:
            return ()
        try:
            if selection.kind == SpatialSelectionKind.POINT:
                point_items = self._create_point_items(selection.value, role)
                for overlay in point_items:
                    self._apply_style(overlay)
                return point_items
            if selection.kind == SpatialSelectionKind.POLYGON:
                item = self._create_polygon_item(selection.value)
                if item is None:
                    return ()
                overlay = OverlayItem(item, role, selection.kind)
                self._apply_style(overlay)
                return (overlay,)
            return ()
        except Exception as error:
            self._report("committed_map_overlay", error)
            return ()

    def _create_point_items(self, value, role: str) -> Tuple[OverlayItem, ...]:
        point, source_crs = self._point_and_crs(value)
        if point is None or source_crs is None or not source_crs.isValid():
            return ()
        destination_crs = self._canvas.mapSettings().destinationCrs()
        if source_crs != destination_crs:
            transform = QgsCoordinateTransform(
                source_crs, destination_crs, QgsProject.instance()
            )
            point = transform.transform(point)
        outer = self._new_point_marker(point)
        inner = self._new_point_marker(point)
        return (
            OverlayItem(outer, role, SpatialSelectionKind.POINT, _POINT_OUTER_RING),
            OverlayItem(inner, role, SpatialSelectionKind.POINT, _POINT_INNER_RING),
        )

    def _new_point_marker(self, point):
        marker = QgsVertexMarker(self._canvas)
        marker.setCenter(point)
        marker.setIconType(_VERTEX_MARKER_CIRCLE)
        marker.setFillColor(transparent_point_fill())
        return marker

    def _create_polygon_item(self, value):
        geometry, source_crs = self._geometry_and_crs(value)
        if geometry is None or geometry.isEmpty() or source_crs is None:
            return None
        geometry = QgsGeometry(geometry)
        destination_crs = self._canvas.mapSettings().destinationCrs()
        if source_crs.isValid() and source_crs != destination_crs:
            transform = QgsCoordinateTransform(
                source_crs, destination_crs, QgsProject.instance()
            )
            geometry.transform(transform)
        band = QgsRubberBand(self._canvas, POLYGON_GEOMETRY)
        band.setToGeometry(geometry, None)
        return band

    @staticmethod
    def _point_and_crs(value):
        if value is None:
            return None, None
        if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "crs"):
            return QgsPointXY(float(value.x), float(value.y)), value.crs
        if isinstance(value, QgsGeometry) and not value.isEmpty():
            return QgsPointXY(value.asPoint()), None
        return None, None

    @staticmethod
    def _geometry_and_crs(value):
        if value is None:
            return None, None
        if hasattr(value, "geom") and hasattr(value, "crs"):
            return value.geom, value.crs
        if isinstance(value, QgsGeometry):
            return value, None
        return None, None

    def _apply_style(self, overlay: OverlayItem) -> None:
        alpha = (
            COMMITTED_COLOR_ALPHA_WHILE_PENDING
            if self._pending_active
            else COMMITTED_COLOR_ALPHA
        )
        settings = self._settings_provider()
        alpha = round(alpha * settings.opacity_percent / 100.0)
        color = semantic_indicator_color(overlay.role, settings, alpha=alpha)
        if overlay.geometry_kind == SpatialSelectionKind.POINT:
            is_outer = overlay.presentation_part == _POINT_OUTER_RING
            overlay.item.setColor(
                point_indicator_outer_color(settings, alpha=alpha) if is_outer else color
            )
            overlay.item.setFillColor(transparent_point_fill())
            overlay.item.setPenWidth(COMMITTED_POINT_PEN_WIDTH)
            outer_size = COMMITTED_POINT_OUTER_SIZE - (1 if self._pending_active else 0)
            inner_size = COMMITTED_POINT_INNER_SIZE - (1 if self._pending_active else 0)
            overlay.item.setIconSize(outer_size if is_outer else inner_size)
            return
        fill = QColor(color)
        fill_alpha = (
            max(8, COMMITTED_FILL_ALPHA - 6)
            if self._pending_active
            else COMMITTED_FILL_ALPHA
        )
        fill.setAlpha(round(fill_alpha * settings.opacity_percent / 100.0))
        overlay.item.setStrokeColor(color)
        overlay.item.setFillColor(fill)
        overlay.item.setWidth(COMMITTED_LINE_WIDTH)

    def _remove_owned_items(self, owned: RecordOverlayItems) -> None:
        scene = None if self._canvas is None else self._canvas.scene()
        for overlay in owned.all_items():
            try:
                if scene is not None:
                    scene.removeItem(overlay.item)
            except Exception as error:
                self._report("committed_map_overlay_cleanup", error)

    def _refresh_for_destination_crs(self, *_):
        """Reproject selected snapshots after the canvas destination CRS changes."""
        records = tuple(self._records_by_id.values())
        self.clear_committed()
        for record in records:
            self.show_record(record)

    def _canvas_destroyed(self, *_):
        self._canvas = None
        self._registry.clear()
        self._records_by_id.clear()

    def _report(self, scope: str, error: Exception) -> None:
        if self._diagnostic is not None:
            self._diagnostic(scope, error)
