"""QGIS map-canvas presentation for selected committed time-series records."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Dict, Iterable, Optional, Tuple
from uuid import UUID

from qgis.PyQt.QtGui import QColor
from qgis.core import QgsCoordinateTransform, QgsGeometry, QgsPointXY, QgsProject
from qgis.gui import QgsRubberBand, QgsVertexMarker

from ..models.time_series import SpatialSelection, SpatialSelectionKind, TimeSeriesRecord
from ..qt_compat import POLYGON_GEOMETRY
from .map_indicator_geometry import (
    resolve_point_indicator_location,
    resolve_polygon_indicator_geometry,
)
from .map_indicator_settings import factory_map_indicator_settings
from .map_indicator_style import (
    COMMITTED_COLOR_ALPHA,
    COMMITTED_COLOR_ALPHA_WHILE_PENDING,
    COMMITTED_FILL_ALPHA,
    COMMITTED_LINE_WIDTH,
    COMMITTED_POINT_PEN_WIDTH,
    PENDING_FILL_ALPHA,
    PENDING_LINE_WIDTH,
    PENDING_POINT_PEN_WIDTH,
    derive_point_indicator_sizes,
    semantic_indicator_color,
    transparent_point_fill,
)


def _enum_value(owner, enum_name, value_name):
    """Resolve scoped QGIS enums while retaining QGIS 3 legacy aliases."""
    enum_owner = getattr(owner, enum_name, None)
    if enum_owner is not None and hasattr(enum_owner, value_name):
        return getattr(enum_owner, value_name)
    return getattr(owner, value_name)


_VERTEX_MARKER_BOX = _enum_value(QgsVertexMarker, "IconType", "ICON_BOX")
_VERTEX_MARKER_CIRCLE = _enum_value(QgsVertexMarker, "IconType", "ICON_CIRCLE")
_POINT_CURRENT_BOX = "current_box"
_POINT_MARKER = "marker"


def point_marker_icon_for_role(role: str):
    """Return the fixed point-marker icon for a target or reference role.

    Targets use hollow circles and references use hollow squares. The mapping
    is presentation-only and is shared by pending and committed overlays.
    """
    if role == "target":
        return _VERTEX_MARKER_CIRCLE
    if role == "reference":
        return _VERTEX_MARKER_BOX
    raise ValueError("unsupported point-indicator role: {!r}".format(role))


def _new_point_marker(canvas, point, role: str):
    """Create one transparent point-marker layer using fixed role semantics."""
    marker = QgsVertexMarker(canvas)
    marker.setCenter(point)
    marker.setIconType(point_marker_icon_for_role(role))
    marker.setFillColor(transparent_point_fill())
    return marker


@dataclass(frozen=True)
class OverlayItem:
    """One canvas item with explicit overlay-layer presentation metadata."""

    item: object
    role: str
    geometry_kind: SpatialSelectionKind
    presentation_part: str = "primary"


def _point_in_canvas_crs(canvas, point, source_crs):
    """Return a point in the canvas CRS without constructing invalid transforms."""
    destination_crs = canvas.mapSettings().destinationCrs()
    if not source_crs.isValid():
        raise ValueError("point indicator source CRS is invalid")
    if not destination_crs.isValid() or source_crs == destination_crs:
        return point
    transform = QgsCoordinateTransform(
        source_crs, destination_crs, QgsProject.instance()
    )
    return transform.transform(point)


def _resolve_point_for_canvas(canvas, selection):
    """Resolve a point selection to the coordinate expected by the map canvas.

    A finite ``map_location`` is the authoritative canvas click position when
    the canvas has no valid destination CRS.  In a CRS-aware canvas, retain the
    normal domain/location resolver so source CRS validation and reprojection
    semantics remain unchanged.
    """
    map_location = selection.map_location
    if map_location is not None:
        x = float(map_location.x)
        y = float(map_location.y)
        if math.isfinite(x) and math.isfinite(y):
            destination_crs = canvas.mapSettings().destinationCrs()
            if not destination_crs.isValid():
                return QgsPointXY(x, y)

    location = resolve_point_indicator_location(selection)
    if location is None:
        raise ValueError(
            "point selection has no finite location usable by the map canvas"
        )
    return _point_in_canvas_crs(
        canvas, location.point, location.source_crs
    )


def _new_current_point_indicator_items(canvas, point, role: str):
    """Create role marker plus box for one current working point selection."""
    current_box = QgsVertexMarker(canvas)
    current_box.setCenter(point)
    current_box.setIconType(_VERTEX_MARKER_BOX)
    current_box.setFillColor(transparent_point_fill())
    marker = _new_point_marker(canvas, point, role)
    return (
        OverlayItem(
            current_box, role, SpatialSelectionKind.POINT, _POINT_CURRENT_BOX
        ),
        OverlayItem(marker, role, SpatialSelectionKind.POINT, _POINT_MARKER),
    )


def _new_record_point_indicator_items(canvas, point, role: str):
    """Create the semantic role marker for one record-owned point selection."""
    marker = _new_point_marker(canvas, point, role)
    return (
        OverlayItem(marker, role, SpatialSelectionKind.POINT, _POINT_MARKER),
    )


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
        self._standalone_target: Optional[SpatialSelection] = None
        self._standalone_reference: Optional[SpatialSelection] = None
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

    def project_reference(self, selection: SpatialSelection) -> None:
        """Render a committed Reference selection before a Target exists."""
        self.clear()
        self._standalone_target = None
        self._standalone_reference = selection
        reference_items = self._create_selection_items(
            selection, self._ROLE_REFERENCE
        )
        self._items = RecordOverlayItems(reference_items=reference_items)

    def project_selections(
        self,
        target: Optional[SpatialSelection],
        reference: Optional[SpatialSelection],
    ) -> None:
        """Render completed active-layer selections without a pending record."""
        self.clear()
        self._standalone_target = target
        self._standalone_reference = reference
        target_items = self._create_selection_items(target, self._ROLE_TARGET)
        reference_items = self._create_selection_items(
            reference, self._ROLE_REFERENCE
        )
        self._items = RecordOverlayItems(target_items, reference_items)

    def refresh_style(self) -> None:
        """Rebuild pending items so settings may change marker ownership."""
        record = self._record
        standalone_target = self._standalone_target
        standalone_reference = self._standalone_reference
        if record is not None:
            self.project_record(record)
        elif standalone_target is not None or standalone_reference is not None:
            self.project_selections(standalone_target, standalone_reference)

    def clear(self) -> None:
        """Remove every stable pending target/reference indicator."""
        self._remove_owned_items(self._items)
        self._items = RecordOverlayItems()
        self._record = None
        self._standalone_target = None
        self._standalone_reference = None

    def _create_selection_items(
        self, selection: Optional[SpatialSelection], role: str
    ) -> Tuple[OverlayItem, ...]:
        if selection is None:
            return ()
        try:
            if selection.kind == SpatialSelectionKind.POINT:
                point_items = self._create_point_items(selection, role)
                for overlay in point_items:
                    self._apply_style(overlay)
                return point_items
            if selection.kind == SpatialSelectionKind.POLYGON:
                item = self._create_polygon_item(selection)
                if item is None:
                    return ()
                overlay = OverlayItem(item, role, selection.kind)
                self._apply_style(overlay)
                return (overlay,)
            return ()
        except Exception as error:
            scope = (
                "pending_map_overlay_point_location"
                if selection.kind == SpatialSelectionKind.POINT
                else "pending_map_overlay"
            )
            self._report(scope, error)
            return ()

    def _create_point_items(self, selection, role: str) -> Tuple[OverlayItem, ...]:
        point = _resolve_point_for_canvas(self._canvas, selection)
        return _new_current_point_indicator_items(self._canvas, point, role)

    def _create_polygon_item(self, selection):
        resolved = resolve_polygon_indicator_geometry(selection)
        if resolved is None:
            return None
        geometry, source_crs = resolved
        if geometry.isEmpty():
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
            is_current_box = overlay.presentation_part == _POINT_CURRENT_BOX
            overlay.item.setColor(color)
            overlay.item.setFillColor(transparent_point_fill())
            overlay.item.setPenWidth(PENDING_POINT_PEN_WIDTH)
            sizes = derive_point_indicator_sizes(settings.point_size)
            overlay.item.setIconSize(
                sizes.current_box if is_current_box else sizes.current_marker
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
        standalone_target = self._standalone_target
        standalone_reference = self._standalone_reference
        if record is not None:
            self.project_record(record)
        elif standalone_target is not None or standalone_reference is not None:
            self.project_selections(standalone_target, standalone_reference)

    def _canvas_destroyed(self, *_):
        self._canvas = None
        self._items = RecordOverlayItems()
        self._record = None
        self._standalone_target = None
        self._standalone_reference = None

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
        """Rebuild selected items so settings may change marker ownership."""
        records = tuple(self._records_by_id.values())
        for record in records:
            self.show_record(record)

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
                point_items = self._create_point_items(selection, role)
                for overlay in point_items:
                    self._apply_style(overlay)
                return point_items
            if selection.kind == SpatialSelectionKind.POLYGON:
                item = self._create_polygon_item(selection)
                if item is None:
                    return ()
                overlay = OverlayItem(item, role, selection.kind)
                self._apply_style(overlay)
                return (overlay,)
            return ()
        except Exception as error:
            scope = (
                "committed_map_overlay_point_location"
                if selection.kind == SpatialSelectionKind.POINT
                else "committed_map_overlay"
            )
            self._report(scope, error)
            return ()

    def _create_point_items(self, selection, role: str) -> Tuple[OverlayItem, ...]:
        point = _resolve_point_for_canvas(self._canvas, selection)
        return _new_record_point_indicator_items(self._canvas, point, role)

    def _create_polygon_item(self, selection):
        resolved = resolve_polygon_indicator_geometry(selection)
        if resolved is None:
            return None
        geometry, source_crs = resolved
        if geometry.isEmpty():
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
        alpha = (
            COMMITTED_COLOR_ALPHA_WHILE_PENDING
            if self._pending_active
            else COMMITTED_COLOR_ALPHA
        )
        settings = self._settings_provider()
        alpha = round(alpha * settings.opacity_percent / 100.0)
        color = semantic_indicator_color(overlay.role, settings, alpha=alpha)
        if overlay.geometry_kind == SpatialSelectionKind.POINT:
            overlay.item.setColor(color)
            overlay.item.setFillColor(transparent_point_fill())
            overlay.item.setPenWidth(COMMITTED_POINT_PEN_WIDTH)
            sizes = derive_point_indicator_sizes(settings.point_size)
            overlay.item.setIconSize(sizes.record_marker)
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
