from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.core import QgsGeometry
from qgis.PyQt.QtGui import QCursor

from ..time_series.map_indicator_settings import factory_map_indicator_settings
from ..time_series.map_indicator_style import (
    PENDING_FILL_ALPHA,
    PENDING_LINE_WIDTH,
    semantic_indicator_color,
)
from ..qt_compat import (
    CROSS_CURSOR, LEFT_MOUSE_BUTTON, POLYGON_GEOMETRY, RIGHT_MOUSE_BUTTON,
)


class PolygonMarker(QgsMapTool):
    def __init__(self, canvas, role="target", settings_provider=None) -> None:
        super().__init__(canvas)
        self.canvas = canvas
        self.rubber_band = QgsRubberBand(self.canvas, POLYGON_GEOMETRY)
        self.points = []
        self.role = role
        self._settings_provider = settings_provider or factory_map_indicator_settings

        self.setStyle()

    def setStyle(self) -> None:
        """Apply the shared target/reference feedback presentation."""
        self.applyStyle(self.rubber_band)

    def applyStyle(self, rubber_band) -> None:
        """Apply this marker's semantic drawing style to a rubber band."""
        settings = self._settings_provider()
        alpha = round(255 * settings.opacity_percent / 100.0)
        stroke = semantic_indicator_color(self.role, settings, alpha=alpha)
        fill = semantic_indicator_color(
            self.role, settings, alpha=round(PENDING_FILL_ALPHA * settings.opacity_percent / 100.0)
        )
        rubber_band.setFillColor(fill)
        rubber_band.setStrokeColor(stroke)
        rubber_band.setWidth(PENDING_LINE_WIDTH)

    def addPoint(self, point):
        self.points.append(point)
        self.rubber_band.addPoint(point, True)

    def reset(self):
        self.points = []
        self.rubber_band.reset(POLYGON_GEOMETRY)

    def stopDrawing(self):
        self.points = []


class PolygonDrawingTool(QgsMapTool):
    def __init__(self, canvas, callback=None, start_callback=None, role="target", settings_provider=None) -> None:
        super().__init__(canvas)
        self.canvas = canvas
        self.setCursor(QCursor(CROSS_CURSOR))
        self.callback = callback  # Function to call when polygon is complete
        self.start_callback = start_callback  # Function to call before starting the drawing
        self.polygon_marker = PolygonMarker(self.canvas, role=role, settings_provider=settings_provider)
        self.preview_rubber_band = QgsRubberBand(self.canvas, POLYGON_GEOMETRY)
        self.polygon_marker.applyStyle(self.preview_rubber_band)
        self.first_point = True
        self.last_point = False

    def canvasPressEvent(self, event) -> None:
        """Add the clicked point to the polygon"""
        if event.button() == LEFT_MOUSE_BUTTON:
            if self.first_point:
                self._startNewDrawing()
            if self.last_point:
                self.cancelDrawing()
                self.last_point = False

            # Add the clicked point to the polygon
            point = self.toMapCoordinates(event.pos())
            self.polygon_marker.addPoint(point)
            self._clearPreview()

    def canvasMoveEvent(self, event) -> None:
        """Preview the next polygon edge/shape without committing a vertex."""
        committed_points = self.polygon_marker.points
        if not committed_points:
            self._clearPreview()
            return

        cursor_point = self.toMapCoordinates(event.pos())
        preview_points = list(committed_points)
        preview_points.append(cursor_point)
        if len(committed_points) >= 2:
            preview_points.append(committed_points[0])
        self._setPreview(preview_points)

    def canvasReleaseEvent(self, event) -> None:
        """Check for right-click to finalize the polygon"""
        if event.button() == RIGHT_MOUSE_BUTTON:
            if not self._finishDrawingIfValid():
                self.cancelDrawing()
                self.first_point = True

    def canvasDoubleClickEvent(self, event) -> None:
        """Finish a valid polygon on a left-button double-click."""
        if event.button() != LEFT_MOUSE_BUTTON:
            return

        self._finishDrawingIfValid()
        if hasattr(event, "accept"):
            event.accept()

    def _setPreview(self, points) -> None:
        """Render preview-only points without mutating committed geometry."""
        self.preview_rubber_band.reset(POLYGON_GEOMETRY)
        last_index = len(points) - 1
        for index, point in enumerate(points):
            self.preview_rubber_band.addPoint(point, index == last_index)

    def _clearPreview(self) -> None:
        """Remove temporary cursor-following polygon feedback."""
        self.preview_rubber_band.reset(POLYGON_GEOMETRY)

    def _finishDrawingIfValid(self) -> bool:
        """Finalize the current polygon and apply the shared finish state."""
        self._clearPreview()
        if len(self.polygon_marker.points) < 3:
            return False

        self.finalizePolygon()
        self.last_point = True
        self.first_point = True
        return True

    def finalizePolygon(self) -> None:
        """Create a polygon geometry"""
        if len(self.polygon_marker.points) > 2:
            polygon = QgsGeometry.fromPolygonXY([self.polygon_marker.points])
            if self.callback:
                self.callback(polygon)
        # self.clear()

    def _clearDrawingState(self) -> None:
        """Remove all in-progress polygon feedback and committed points."""
        self._clearPreview()
        self.polygon_marker.reset()

    def cancelDrawing(self) -> None:
        """Discard the current in-progress polygon drawing."""
        self._clearDrawingState()

    def refresh_style(self) -> None:
        """Refresh temporary polygon feedback styling."""
        self.polygon_marker.setStyle()
        self.polygon_marker.applyStyle(self.preview_rubber_band)

    def clear_feedback(self) -> None:
        """Clear temporary polygon interaction feedback without changing sessions."""
        self._clearDrawingState()
        self.first_point = True
        self.last_point = False

    def clear(self) -> None:
        """Reset temporary feedback and deactivate the drawing tool."""
        self.clear_feedback()
        self.deactivate()

    def _startNewDrawing(self) -> None:
        """Reset drawing feedback and begin a new polygon session."""
        self._clearDrawingState()
        if self.start_callback:
            self.start_callback()
        self.first_point = False
        self.last_point = False

    def activate(self) -> None:
        """Reset drawing feedback and run the normal QGIS activation lifecycle."""
        self._clearDrawingState()
        super().activate()

    def deactivate(self) -> None:
        """Clear all in-progress drawing feedback and deactivate the tool."""
        self._clearDrawingState()
        super().deactivate()
        # self.clear()
