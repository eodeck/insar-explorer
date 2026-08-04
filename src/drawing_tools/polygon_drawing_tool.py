from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.core import QgsGeometry
from qgis.PyQt.QtGui import QColor as QgsColor

from ..time_series.map_indicator_style import (
    PENDING_FILL_ALPHA,
    PENDING_LINE_WIDTH,
    semantic_indicator_color,
)
from ..qt_compat import POLYGON_GEOMETRY, LEFT_MOUSE_BUTTON, RIGHT_MOUSE_BUTTON


class PolygonMarker(QgsMapTool):
    def __init__(self, canvas, role="target") -> None:
        super().__init__(canvas)
        self.canvas = canvas
        self.rubber_band = QgsRubberBand(self.canvas, POLYGON_GEOMETRY)
        self.points = []
        self.role = role

        self.setStyle()

    def setStyle(self) -> None:
        """Apply the shared target/reference feedback presentation."""
        stroke = semantic_indicator_color(self.role)
        fill = semantic_indicator_color(self.role, alpha=PENDING_FILL_ALPHA)
        self.rubber_band.setFillColor(fill)
        self.rubber_band.setStrokeColor(stroke)
        self.rubber_band.setWidth(PENDING_LINE_WIDTH)

    def addPoint(self, point):
        self.points.append(point)
        self.rubber_band.addPoint(point, True)

    def reset(self):
        self.points = []
        self.rubber_band.reset(POLYGON_GEOMETRY)

    def stopDrawing(self):
        self.points = []


class PolygonDrawingTool(QgsMapTool):
    def __init__(self, canvas, callback=None, start_callback=None, role="target") -> None:
        super().__init__(canvas)
        self.canvas = canvas
        self.callback = callback  # Function to call when polygon is complete
        self.start_callback = start_callback  # Function to call before starting the drawing
        self.polygon_marker = PolygonMarker(self.canvas, role=role)
        self.first_point = True
        self.last_point = False

    def canvasPressEvent(self, event) -> None:
        """Add the clicked point to the polygon"""
        if event.button() == LEFT_MOUSE_BUTTON:
            if self.first_point:
                self.activate()
                if self.start_callback:
                    self.start_callback()
                self.first_point = False
            if self.last_point:
                self.cancelDrawing()
                self.last_point = False

            # Add the clicked point to the polygon
            point = self.toMapCoordinates(event.pos())
            self.polygon_marker.addPoint(point)

    def canvasReleaseEvent(self, event) -> None:
        """Check for right-click to finalize the polygon"""
        if event.button() == RIGHT_MOUSE_BUTTON:
            if len(self.polygon_marker.points) > 2:  # A valid polygon requires at least 3 points
                self.finalizePolygon()
                self.last_point = True
                self.first_point = True
            else:
                self.cancelDrawing()
                self.first_point = True

    def finalizePolygon(self) -> None:
        """Create a polygon geometry"""
        if len(self.polygon_marker.points) > 2:
            polygon = QgsGeometry.fromPolygonXY([self.polygon_marker.points])
            if self.callback:
                self.callback(polygon)
        # self.clear()

    def cancelDrawing(self) -> None:
        """Clear the drawing"""
        # self.clear()
        self.polygon_marker.stopDrawing()

    def clear_feedback(self) -> None:
        """Clear temporary polygon interaction feedback without changing sessions."""
        self.polygon_marker.reset()
        self.first_point = True
        self.last_point = False

    def clear(self) -> None:
        """Reset temporary feedback and deactivate the drawing tool."""
        self.clear_feedback()
        self.deactivate()

    def activate(self):
        self.polygon_marker.reset()
        # super().activate()

    def deactivate(self) -> None:
        """Clear the drawing and deactivate the tool"""
        super().deactivate()
        # self.clear()
