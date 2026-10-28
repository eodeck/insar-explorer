import os
from dataclasses import dataclass

import numpy as np
from qgis.PyQt.QtWidgets import QApplication
from qgis.core import QgsPointXY, QgsGeometry, QgsMapLayer, QgsRectangle, QgsFeatureRequest, QgsSettings, Qgis
from qgis.gui import QgsHighlight
from qgis.core import QgsProject, QgsCoordinateTransform, QgsCoordinateReferenceSystem
from qgis.PyQt.QtGui import QColor, QCursor

from . import plot_timeseries as pts
from .bootstrap import ensure_time_series_services
from .layer_utils import grd_layer as grd_layer_utils
from .layer_utils import raster_layer as raster_layer_utils
from .layer_utils import vector_layer as vector_layer_utils
from .models.time_series import (
    MapPointSnapshot, SpatialSelection, SpatialSelectionKind, TimeSeriesSource,
)
from .qt_compat import WAIT_CURSOR
from .time_series.map_indicator_style import (
    semantic_indicator_color,
)
from .time_series.reference_session import ActiveReference
from .time_series.target_session import CanonicalTargetSnapshot
from .ui.status_messages import STATUS_WARNING


NO_VALID_TIME_SERIES_WARNING = "No valid time-series data are available at this location."
INVALID_TIME_SERIES_LAYER_WARNING = "The selected layer cannot provide time-series data."


@dataclass
class Coordinates:
    x: float
    y: float
    crs: QgsCoordinateReferenceSystem

    def __repr__(self):
        return f"Coordinates(CRS={self.crs.authid()}, {self.as_wkt()})"

    def crs_str(self):
        if not self.crs.isValid():
            return "CRS=Unknown"
        return f"CRS={self.crs.authid()}"

    def to_wgs84(self) -> "Coordinates":
        if self.crs.authid() == 'EPSG:4326':
            return self
        src = self.crs
        dst = QgsCoordinateReferenceSystem('EPSG:4326')
        transform = QgsCoordinateTransform(src, dst, QgsProject.instance())
        pt = QgsGeometry.fromPointXY(QgsPointXY(self.x, self.y))
        geom = QgsGeometry(pt)  # copy
        geom.transform(transform)
        p = geom.asPoint()
        return Coordinates(float(p.x()), float(p.y()), dst)

    def to_crs(self, target_crs) -> "Coordinates":
        if isinstance(target_crs, str):
            target_crs = QgsCoordinateReferenceSystem(target_crs)
        if self.crs.authid() == target_crs.authid():
            return self
        transform = QgsCoordinateTransform(self.crs, target_crs, QgsProject.instance())
        geom = QgsGeometry.fromPointXY(QgsPointXY(self.x, self.y))
        geom.transform(transform)
        p = geom.asPoint()
        return Coordinates(float(p.x()), float(p.y()), target_crs)

    def as_wkt(self) -> str:
        return f"POINT ({self.x} {self.y})"

    def as_wkt_wgs84(self) -> str:
        c = self.to_wgs84()
        return f"POINT ({c.x} {c.y})"


@dataclass
class PolygonGeometry:
    geom: QgsGeometry
    crs: QgsCoordinateReferenceSystem

    def __repr__(self):
        return f"PolygonGeometry(crs={self.crs.authid()}, wkt={self.geom.asWkt()})"

    def crs_str(self):
        if not self.crs.isValid():
            return "CRS=Unknown"
        return f"CRS={self.crs.authid()}"

    def to_crs(self, target_crs) -> "PolygonGeometry":
        if isinstance(target_crs, str):
            target_crs = QgsCoordinateReferenceSystem(target_crs)
        if self.crs.authid() == target_crs.authid():
            return PolygonGeometry(QgsGeometry(self.geom), self.crs)
        transform = QgsCoordinateTransform(self.crs, target_crs, QgsProject.instance())
        g = QgsGeometry(self.geom)  # copy
        g.transform(transform)
        return PolygonGeometry(g, target_crs)

    def as_wkt(self) -> str:
        return self.geom.asWkt()

    def as_wkt_wgs84(self) -> str:
        wgs84_geom = self.to_crs('EPSG:4326').geom
        return wgs84_geom.asWkt()


def time_series_source_from_layer(layer: QgsMapLayer = None, h5_path: str = None) -> TimeSeriesSource:
    """Capture immutable provenance for a genuine new time-series extraction."""
    if h5_path:
        abs_path = os.path.abspath(h5_path)
        label = raster_layer_utils.h5_layer_utils.format_h5_display_name(abs_path) or os.path.basename(abs_path)
        layer_id = str(layer.id()) if layer is not None else f"h5:{abs_path}"
        return TimeSeriesSource(layer_id=layer_id, layer_name=label)
    if layer is not None:
        return TimeSeriesSource(layer_id=str(layer.id()), layer_name=str(layer.name()))
    raise ValueError("a source layer is required for time-series extraction")


class MapClickHandler:
    """
    A class to handle map click events

    Attributes:
        ui: The user interface object of the plugin.
        iface: The QGIS interface object.
        highlight: The QgsHighlight object used to highlight selected features.

    """
    def __init__(
        self, plugin, msg_signal=None, indicator_settings_service=None
    ):
        self.ui = plugin.dockwidget
        self.iface = plugin.iface
        self.msg_signal = msg_signal
        self.highlight = None
        self.reference_highlight = None
        self.map_reference_clicked_value = 0
        self.new_record_analysis_provider = None
        if indicator_settings_service is None:
            indicator_settings_service = (
                ensure_time_series_services(plugin).map_indicator_settings
            )
        self._indicator_settings = indicator_settings_service

    def _analysisForNewRecord(self):
        """Capture controller-facing analysis immediately before new record creation."""
        if self.new_record_analysis_provider is None:
            return None
        return self.new_record_analysis_provider()

    def identifyClickedFeatureID(self, point: QgsPointXY, layer: QgsMapLayer = None) -> int:
        """
        Identify the closest feature to the clicked point
        :param point: QgsPointXY
        :param layer: QgsMapLayer
        :return: closest feature ID
        """
        if not layer:
            layer = self.iface.activeLayer()

        status, message = vector_layer_utils.checkVectorLayer(layer)
        if status is False:
            self.msg_signal.emit(message, STATUS_WARNING, 0)
            return

        closest_feature_id = self.findFeatureAtPoint(layer, point, self.iface.mapCanvas(),
                                                     only_the_closest_one=True, only_ids=True)

        return closest_feature_id

    def identifyClickedFeature(self, point: QgsPointXY, layer: QgsMapLayer = None, ref=False) -> QgsGeometry:
        """
        Identify the closest feature to the clicked point and display its attributes
        :param point: QgsPointXY
        :param layer: QgsMapLayer
        :param ref: bool
        :return: closest feature
        """
        if not layer:
            layer = self.iface.activeLayer()
        closest_feature_id = self.identifyClickedFeatureID(point, layer)

        if not ref:
            self.clearFeatureHighlight()
        else:
            self.clearReferenceFeatureHighlight()

        closest_feature = None
        if closest_feature_id is not None:
            closest_feature = layer.getFeature(closest_feature_id)
            # attributes_text = "\n".join(
            #     [f"{field.name()}: {value}" for field, value in zip(layer.fields(), closest_feature.attributes())]
            # )
            # point = closest_feature.geometry().asPoint()
            # if point:
            #     x, y = point.x(), point.y()
            #     coordinates_text = f"Coordinates: ({x:.5f}, {y:.5f})\n"
            # self.ui.te_info.setPlainText(f"Selected feature:\n{coordinates_text+attributes_text}")
            if not ref:
                self.highlightSelectedFeatures(closest_feature.geometry())
            else:
                self.highlightSelectedReferenceFeature(closest_feature.geometry())

        return closest_feature

    def highlightSelectedFeatures(self, geometry: QgsGeometry, layer: QgsMapLayer = None) -> None:
        """
        Highlight the selected feature
        :param geometry: QgsGeometry
        :param layer: QgsMapLayer
        """
        if not layer:
            layer = self.iface.activeLayer()
        self.clearFeatureHighlight()
        self.highlight = QgsHighlight(self.iface.mapCanvas(), geometry, layer)
        settings = self._indicator_settings.active
        color = semantic_indicator_color("target", settings, alpha=round(255 * settings.opacity_percent / 100.0))
        fill = QColor(0, 0, 0, 0)
        self.highlight.setColor(color)
        if hasattr(self.highlight, "setFillColor"):
            self.highlight.setFillColor(fill)
        self.highlight.show()

    def highlightSelectedReferenceFeature(self, geometry: QgsGeometry, layer: QgsMapLayer = None) -> None:
        if not layer:
            layer = self.iface.activeLayer()
        self.clearReferenceFeatureHighlight()
        self.reference_highlight = QgsHighlight(self.iface.mapCanvas(), geometry, layer)
        settings = self._indicator_settings.active
        color = semantic_indicator_color("reference", settings, alpha=round(255 * settings.opacity_percent / 100.0))
        fill = QColor(0, 0, 0, 0)
        self.reference_highlight.setColor(color)
        if hasattr(self.reference_highlight, "setFillColor"):
            self.reference_highlight.setFillColor(fill)
        self.reference_highlight.show()

    def clearFeatureHighlight(self) -> None:
        if self.highlight:
            canvas = self.iface.mapCanvas()
            canvas.scene().removeItem(self.highlight)
            self.highlight = None

    def clearReferenceFeatureHighlight(self) -> None:
        """
        Clear reference feature highlight
        """
        if self.reference_highlight:
            canvas = self.iface.mapCanvas()
            canvas.scene().removeItem(self.reference_highlight)
            self.reference_highlight = None

    @classmethod
    def findFeatureAtPoint(cls, layer, point, canvas, only_the_closest_one=True, only_ids=False):
        """
        Find the closest feature to the clicked point
        :param layer: QgsMapLayer
        :param point: QgsPointXY
        :param canvas: QgsMapCanvas
        :param only_the_closest_one: bool
        :param only_ids: bool
        :return: closest feature or feature ID
        """
        QApplication.setOverrideCursor(QCursor(WAIT_CURSOR))
        settings = QgsSettings()
        radius = settings.value("/Map/searchRadiusMM", Qgis.DEFAULT_SEARCH_RADIUS_MM, type=float)
        if radius <= 0:
            radius = Qgis.DEFAULT_SEARCH_RADIUS_MM
        radius = canvas.extent().width() * radius / canvas.size().width()
        radius *= 5
        rect = QgsRectangle(point.x() - radius, point.y() - radius, point.x() + radius, point.y() + radius)
        rect = canvas.mapSettings().mapToLayerCoordinates(layer, rect)
        point_map = canvas.mapSettings().mapToLayerCoordinates(layer, point)
        ret = None

        if only_the_closest_one:
            request = QgsFeatureRequest()
            request.setFilterRect(rect)
            min_dist = -1
            feature_id = None
            for f in layer.getFeatures(request):
                geom = f.geometry()
                distance = geom.distance(QgsGeometry.fromPointXY(point_map))
                if min_dist < 0 or distance < min_dist:
                    min_dist = distance
                    feature_id = f.id()
            if only_ids:
                ret = feature_id
            elif feature_id is not None:
                ret = layer.getFeature(feature_id)
        else:
            ids = [f.id() for f in layer.getFeatures()]
            if only_ids:
                ret = ids
            else:
                ret = []
                request = QgsFeatureRequest()
                request.setFilterFids(ids)
                for f in layer.getFeatures(request):
                    ret.append(f)

        QApplication.restoreOverrideCursor()
        return ret


class TSClickHandler(MapClickHandler):
    # TODO: separate PointClickHandler from TSClickHandler
    def __init__(
        self, plugin, msg_signal=None, indicator_settings_service=None
    ):
        super().__init__(plugin, msg_signal=msg_signal)
        services = ensure_time_series_services(plugin)
        self.reference_session = services.reference_session
        self.target_session = services.target_session
        self.plot_ts = pts.PlotTs(
            self.ui,
            settings_model=services.settings_model,
            user_preferences=services.user_preferences,
            project_state_repository=services.project_state_repository,
            pending_session=services.pending_session,
        )
        self.raster_layer = raster_layer_utils.RasterTimeseries()
        self.selected_field_name = None

    def dispose(self):
        """Release renderer-owned Qt and settings subscriptions."""
        self.plot_ts.dispose()

    def resetLayerTransientState(self):
        """Clear active-layer extraction state without touching committed records."""
        self.reference_session.clear()
        self.target_session.clear()
        self.clearFeatureHighlight()
        self.clearReferenceFeatureHighlight()
        self.raster_layer.reset()
        self.plot_ts.discard_pending()

    def clearTimeSeriesWorkspace(self):
        """Clear active extraction state and every committed time-series record."""
        self.reference_session.clear()
        self.target_session.clear()
        self.clearFeatureHighlight()
        self.clearReferenceFeatureHighlight()
        self.raster_layer.reset()
        self.plot_ts.clear()

    def reset(self):
        """Compatibility entry point for an intentional full workspace reset."""
        self.clearTimeSeriesWorkspace()

    def setH5FilePath(self, file_path: str):
        self.raster_layer.setH5FilePath(file_path)

    def h5FilePath(self) -> str:
        return self.raster_layer.h5_file_path

    def activeH5FilePath(self, layer=None) -> str:
        return self.raster_layer.resolveActiveH5FilePath(layer)

    def hasValidH5Timeseries(self, layer=None) -> bool:
        return self.raster_layer.hasValidH5Timeseries(layer)

    def _resolveRasterTargetCrs(self, layer):
        """Determine the CRS used by the active raster/H5 pixel grid."""
        h5_path = self.raster_layer.resolveActiveH5FilePath(layer)
        if h5_path:
            _, use_layer_crs = self.raster_layer.h5_reader.resolve_geotransform(h5_path, layer=layer)
            if use_layer_crs and layer is not None and layer.crs().isValid():
                return layer.crs()
            return QgsCoordinateReferenceSystem("EPSG:4326")
        if layer is not None and layer.crs().isValid():
            return layer.crs()
        return self.iface.mapCanvas().mapSettings().destinationCrs()

    def choosePointClicked(self, *, point: QgsPointXY, layer: QgsMapLayer = None, ref=False, start_callback=None):
        if start_callback:  # use start_callback to remove previous polygon from map
            start_callback()
        if not layer:
            layer = self.iface.activeLayer()

        status_vector, _ = vector_layer_utils.checkVectorLayerTimeseries(layer)
        status_raster, _ = grd_layer_utils.checkGrdTimeseries(
            layer, h5_file_path=self.raster_layer.h5_file_path
        )
        if status_vector:
            self.choosePointClickedVector(point=point, layer=layer, ref=ref)
        elif status_raster:
            self.choosePointClickedRaster(point=point, layer=layer, ref=ref)
        else:
            self._warnInvalidTimeSeriesLayer()
            return

    def _warnNoValidTimeSeriesData(self):
        """Report one recoverable warning for a completed no-data selection attempt."""
        self.msg_signal.emit(NO_VALID_TIME_SERIES_WARNING, STATUS_WARNING, 5000)

    def _warnInvalidTimeSeriesLayer(self):
        """Report one recoverable warning for an invalid time-series layer."""
        self.msg_signal.emit(INVALID_TIME_SERIES_LAYER_WARNING, STATUS_WARNING, 5000)

    @staticmethod
    def _hasUsableTimeSeriesValues(values):
        """Return True when an extracted value matrix contains at least one finite value."""
        if values is None:
            return False
        try:
            array = np.asarray(values, dtype=float)
        except (TypeError, ValueError):
            return False
        return bool(array.size and np.isfinite(array).any())

    def _referenceInputsForNewTarget(self):
        """Return active reference values and the complete typed selection."""
        reference = self.reference_session.current()
        if reference is None:
            return None, None
        return reference.values_array(), reference.selection

    def _commitSelectedReference(self, reference):
        """Publish reference session state after pending update succeeds."""
        self.reference_session.set(reference)

    def _commitSelectedTarget(
        self, *, dates, values, selection, source, plot_multiple=False, attributes=None
    ):
        """Publish the latest successful target extraction for future pending records."""
        self.target_session.set(CanonicalTargetSnapshot.create(
            dates=dates, values=values, selection=selection, source=source,
            plot_multiple=plot_multiple, attributes=attributes,
        ))

    def _reconstructPendingFromActiveSelections(self, reference=None):
        """Rebuild pending data from canonical target and current reference snapshots.

        The active target session stores the unreferenced extraction.  Reference
        changes therefore never reuse the already-derived pending observations,
        preventing stale reset values and cumulative reference subtraction.
        Existing pending identity and user-owned presentation/analysis are
        preserved by the immutable update path; a missing pending record creates
        a new record from the accepted new-record defaults.
        """
        target = self.target_session.current()
        if target is None:
            return False
        active_reference = reference
        ref_values = None if active_reference is None else active_reference.values_array()
        ref_coords = None if active_reference is None else active_reference.selection
        pending_before = self.plot_ts.pending_record()
        previous_id = None if pending_before is None else pending_before.id
        self.plot_ts.plotTs(
            dates=np.asarray(target.dates),
            ts_values=target.values_array(),
            ref_values=ref_values,
            coords=target.selection if pending_before is None else None,
            ref_coords=ref_coords,
            plot_multiple=target.plot_multiple,
            update=pending_before is not None,
            analysis=(
                self._analysisForNewRecord() if pending_before is None else None
            ),
            source_provenance=target.source,
            target_attributes=target.attributes,
            reference_attributes=(None if active_reference is None else active_reference.attributes),
            report_statistics=True,
        )
        pending_after = self.plot_ts.pending_record()
        if pending_after is None:
            return False
        if pending_before is None:
            return pending_after.id != previous_id
        return pending_after.id == previous_id

    def _applySelectedReference(self, *, dates, values, selection, attributes=None):
        """Reconstruct pending from canonical target data for a new reference."""
        reference = ActiveReference.create(
            dates=dates, values=values, selection=selection, attributes=attributes
        )
        success = self._reconstructPendingFromActiveSelections(reference)
        if self.target_session.current() is None:
            success = True
        if success:
            self._commitSelectedReference(reference)
        return success

    def choosePointClickedVector(self, *, point: QgsPointXY, layer: QgsMapLayer = None, ref=False):
        if not layer:
            layer = self.iface.activeLayer()

        status, _ = vector_layer_utils.checkVectorLayerTimeseries(layer)
        if status is False:
            self._warnInvalidTimeSeriesLayer()
            return

        feature = self.identifyClickedFeature(point, layer=layer, ref=ref)
        if feature is None:
            self._warnNoValidTimeSeriesData()
            return

        crds = Coordinates(x=feature.geometry().asPoint().x(), y=feature.geometry().asPoint().y(), crs=layer.crs())
        coords = None
        ref_coords = None

        raw_attributes = vector_layer_utils.getFeatureAttributes(feature)
        snapshot_attributes = vector_layer_utils.captureFeatureAttributes(feature)
        date_values = vector_layer_utils.extractDateValueAttributes(raw_attributes)
        if not ref:
            ts_values = date_values[:, 1]
            ref_values, ref_coords = self._referenceInputsForNewTarget()
            coords = crds
        else:
            ref_values = date_values[:, 1]
            if self.selected_field_name:
                self.map_reference_clicked_value = (
                    vector_layer_utils.getFeatureFieldValue(raw_attributes, self.selected_field_name))
            ts_values = None
            ref_coords = crds

        dates = date_values[:, 0]
        analysis = self._analysisForNewRecord() if not ref else None
        if ref:
            if not self._hasUsableTimeSeriesValues(ref_values):
                self._warnNoValidTimeSeriesData()
                return
            if not self._applySelectedReference(
                dates=dates, values=ref_values, selection=ref_coords, attributes=snapshot_attributes
            ):
                self._warnNoValidTimeSeriesData()
                return
        else:
            previous = self.plot_ts.pending_record()
            previous_id = None if previous is None else previous.id
            self.plot_ts.plotTs(
                dates=dates, ts_values=ts_values, ref_values=ref_values,
                coords=coords, ref_coords=ref_coords, update=False,
                analysis=analysis, source_provenance=time_series_source_from_layer(layer),
                target_attributes=snapshot_attributes,
                reference_attributes=(None if self.reference_session.current() is None
                                      else self.reference_session.current().attributes),
                report_statistics=True,
            )
            pending = self.plot_ts.pending_record()
            if pending is not None and pending.id != previous_id:
                self._commitSelectedTarget(
                    dates=dates, values=ts_values, selection=pending.target,
                    source=pending.source, plot_multiple=False, attributes=snapshot_attributes,
                )
            else:
                self._warnNoValidTimeSeriesData()

    def choosePointClickedRaster(self, *, point: QgsPointXY, layer: QgsMapLayer = None, ref=False):
        if not layer:
            layer = self.iface.activeLayer()

        status, _ = grd_layer_utils.checkGrdTimeseries(
            layer, h5_file_path=self.raster_layer.h5_file_path
        )
        if status is False:
            self._warnInvalidTimeSeriesLayer()
            return

        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        target_crs = self._resolveRasterTargetCrs(layer)
        target_point = QgsPointXY(point)
        if canvas_crs.isValid() and target_crs.isValid() and canvas_crs != target_crs:
            try:
                transform = QgsCoordinateTransform(canvas_crs, target_crs, QgsProject.instance())
                target_point = transform.transform(point)
            except Exception:
                target_point = QgsPointXY(point)

        date_values = self.raster_layer.getRasterTimeseriesAttributes(layer, point=target_point)

        if date_values.size == 0:
            self._warnNoValidTimeSeriesData()
            return

        clicked_point = QgsGeometry.fromPointXY(target_point if layer is not None else point)
        if layer is not None:
            if not ref:
                self.highlightSelectedFeatures(clicked_point, layer=layer)
            else:
                self.highlightSelectedReferenceFeature(clicked_point, layer=layer)

        if not self._hasUsableTimeSeriesValues(date_values[:, 1]):
            self._warnNoValidTimeSeriesData()
            return

        crds = Coordinates(x=float(target_point.x()), y=float(target_point.y()), crs=target_crs)
        selection = SpatialSelection(
            value=crds,
            kind=SpatialSelectionKind.POINT,
            map_location=MapPointSnapshot(
                x=float(point.x()),
                y=float(point.y()),
                crs=QgsCoordinateReferenceSystem(canvas_crs),
            ),
        )
        coords = None
        ref_coords = None

        if not ref:
            ts_values = date_values[:, 1]
            ref_values, ref_coords = self._referenceInputsForNewTarget()
            coords = selection
        else:
            ref_values = date_values[:, 1]
            clicked_val = self.raster_layer.getClickedPixelValue(layer, point=target_point)
            self.map_reference_clicked_value = clicked_val if clicked_val is not None else 0
            ts_values = None
            ref_coords = selection

        dates = date_values[:, 0]
        analysis = self._analysisForNewRecord() if not ref else None
        if ref:
            if not self._applySelectedReference(
                dates=dates, values=ref_values, selection=ref_coords
            ):
                self._warnNoValidTimeSeriesData()
                return
        else:
            previous = self.plot_ts.pending_record()
            previous_id = None if previous is None else previous.id
            h5_path = self.raster_layer.resolveActiveH5FilePath(layer)
            self.plot_ts.plotTs(
                dates=dates, ts_values=ts_values, ref_values=ref_values,
                coords=coords, ref_coords=ref_coords, update=False,
                analysis=analysis,
                source_provenance=time_series_source_from_layer(layer, h5_path),
                report_statistics=True,
            )
            pending = self.plot_ts.pending_record()
            if pending is not None and pending.id != previous_id:
                self._commitSelectedTarget(
                    dates=dates, values=ts_values, selection=pending.target,
                    source=pending.source, plot_multiple=False,
                )
            else:
                self._warnNoValidTimeSeriesData()

    def resetReferencePoint(self):
        """Clear reference state and reconstruct canonical unreferenced pending data."""
        self.reference_session.clear()
        self.clearReferenceFeatureHighlight()
        if self.target_session.current() is not None:
            self._reconstructPendingFromActiveSelections(reference=None)


class PolygonClickHandler(MapClickHandler):
    def __init__(
        self, plugin, msg_signal=None, indicator_settings_service=None
    ):
        super().__init__(plugin, msg_signal=msg_signal)
        self.polygon = None

    def identifyFeaturesInPolygon(self, layer: QgsMapLayer, polygon: QgsGeometry, ref=False) -> list:
        if not layer:
            layer = self.iface.activeLayer()

        # reproject the polygon to the layer's CRS
        layer_crs = layer.crs()
        project_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        transform = QgsCoordinateTransform(project_crs, layer_crs, QgsProject.instance())
        polygon.transform(transform)

        # Check whether layer is a vector layer
        status, message = vector_layer_utils.checkVectorLayer(layer)
        if status is False:
            self.msg_signal.emit(message, STATUS_WARNING, 0)
            return []

        # Check whether polygon geometry is valid
        if not polygon or not polygon.isGeosValid():
            self.msg_signal.emit("Invalid polygon geometry.", STATUS_WARNING, 0)
            return []

        # Prepare a feature request that uses the bounding box of the polygon
        request = QgsFeatureRequest().setFilterRect(polygon.boundingBox())

        # Identify features intersecting the polygon
        features = []
        for feature in layer.getFeatures(request):
            if feature.geometry().intersects(polygon):
                features.append(feature)

        if not features:
            self._warnNoValidTimeSeriesData()

        if len(features) == 0:
            return None

        return features

    def choosePolygonDrawn(self, *, polygon: QgsGeometry, layer: QgsMapLayer = None, ref=False):
        if not layer:
            layer = self.iface.activeLayer()

        status_vector, _ = vector_layer_utils.checkVectorLayerTimeseries(layer)
        status_raster, _ = grd_layer_utils.checkGrdTimeseries(
            layer, h5_file_path=self.raster_layer.h5_file_path
        )

        if status_vector:
            self.choosePolygonDrawnVector(layer=layer, polygon=polygon, ref=ref)
        elif status_raster:
            self.choosePolygonDrawnRaster(layer=layer, polygon=polygon, ref=ref)
        else:
            self._warnInvalidTimeSeriesLayer()
            return

    def choosePolygonDrawnRaster(self, *, layer: QgsMapLayer = None, polygon=None, ref=False):
        if not layer:
            layer = self.iface.activeLayer()

        if not self.raster_layer.hasValidH5Timeseries(layer):
            self._warnInvalidTimeSeriesLayer()
            return

        if not polygon or not polygon.isGeosValid():
            self.msg_signal.emit("Invalid polygon geometry.", STATUS_WARNING, 0)
            return

        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        target_crs = self._resolveRasterTargetCrs(layer)
        poly_target = QgsGeometry(polygon)
        if canvas_crs.isValid() and target_crs.isValid() and canvas_crs != target_crs:
            try:
                transform = QgsCoordinateTransform(canvas_crs, target_crs, QgsProject.instance())
                poly_target.transform(transform)
            except Exception:
                poly_target = QgsGeometry(polygon)

        dates, values = self.raster_layer.getPolygonTimeseriesAttributes(layer, poly_target)
        if dates.size == 0 or values.size == 0 or not self._hasUsableTimeSeriesValues(values):
            self._warnNoValidTimeSeriesData()
            return

        crds = PolygonGeometry(geom=poly_target, crs=target_crs)
        coords = None
        ref_coords = None

        if not ref:
            ts_values = values
            ref_values, ref_coords = self._referenceInputsForNewTarget()
            coords = crds
        else:
            ref_values = values
            ts_values = None
            ref_coords = crds

        analysis = self._analysisForNewRecord() if not ref else None
        if ref:
            if not self._applySelectedReference(
                dates=dates, values=ref_values, selection=ref_coords
            ):
                self._warnNoValidTimeSeriesData()
                return
        else:
            previous = self.plot_ts.pending_record()
            previous_id = None if previous is None else previous.id
            h5_path = self.raster_layer.resolveActiveH5FilePath(layer)
            self.plot_ts.plotTs(
                dates=dates, ts_values=ts_values, ref_values=ref_values,
                coords=coords, ref_coords=ref_coords, plot_multiple=True,
                update=False, analysis=analysis,
                source_provenance=time_series_source_from_layer(layer, h5_path),
                report_statistics=True,
            )
            pending = self.plot_ts.pending_record()
            if pending is not None and pending.id != previous_id:
                self._commitSelectedTarget(
                    dates=dates, values=ts_values, selection=pending.target,
                    source=pending.source, plot_multiple=True,
                )
            else:
                self._warnNoValidTimeSeriesData()

    def choosePolygonDrawnVector(self, *, layer: QgsMapLayer = None, polygon=None, ref=False):
        if not layer:
            layer = self.iface.activeLayer()

        status, _ = vector_layer_utils.checkVectorLayerTimeseries(layer)
        if status is False:
            self._warnInvalidTimeSeriesLayer()
            return

        features = self.identifyFeaturesInPolygon(layer=layer, polygon=polygon, ref=ref)

        if features:
            date_values = []
            for feature in features:
                attributes = vector_layer_utils.getFeatureAttributes(feature)
                date_values.append(vector_layer_utils.extractDateValueAttributes(attributes))

            dates = date_values[0][:, 0]
            values_column = [arr[:, 1] for arr in date_values]
            values = np.stack(values_column, axis=1)

            crds = PolygonGeometry(geom=polygon, crs=layer.crs())
            coords = None
            ref_coords = None

            if not ref:
                ts_values = values
                ref_values, ref_coords = self._referenceInputsForNewTarget()
                coords = crds
            else:
                ref_values = values
                ts_values = None
                ref_coords = crds

                if self.selected_field_name:
                    clicked_values = vector_layer_utils.getFeatureFieldValue(attributes, self.selected_field_name)
                    self.map_reference_clicked_value = np.mean(clicked_values)

            analysis = self._analysisForNewRecord() if not ref else None
            if ref:
                if not self._hasUsableTimeSeriesValues(ref_values):
                    self._warnNoValidTimeSeriesData()
                    return
                if not self._applySelectedReference(
                    dates=dates, values=ref_values, selection=ref_coords
                ):
                    self._warnNoValidTimeSeriesData()
                    return
            else:
                previous = self.plot_ts.pending_record()
                previous_id = None if previous is None else previous.id
                self.plot_ts.plotTs(
                    dates=dates, ts_values=ts_values, ref_values=ref_values,
                    coords=coords, ref_coords=ref_coords, plot_multiple=True,
                    update=False, analysis=analysis,
                    source_provenance=time_series_source_from_layer(layer),
                    report_statistics=True,
                )
                pending = self.plot_ts.pending_record()
                if pending is not None and pending.id != previous_id:
                    self._commitSelectedTarget(
                        dates=dates, values=ts_values, selection=pending.target,
                        source=pending.source, plot_multiple=True,
                    )
                else:
                    self._warnNoValidTimeSeriesData()


class ClickHandler(TSClickHandler, PolygonClickHandler):
    def __init__(
        self, plugin, msg_signal=None, indicator_settings_service=None
    ):
        TSClickHandler.__init__(self, plugin, msg_signal=msg_signal)
        PolygonClickHandler.__init__(self, plugin, msg_signal=msg_signal)

    def referenceValueForField(self, field_name, layer=None):
        """Return the selected field value at the active reference selection.

        Reuse the canonical reference geometry so linked Map Settings can be
        refreshed after a field change without reselecting the reference.
        """
        reference = self.reference_session.current()
        if reference is None:
            return None
        if not layer:
            layer = self.iface.activeLayer()
        if layer is None:
            return None

        selection = reference.selection
        status_vector, _ = vector_layer_utils.checkVectorLayer(layer)
        if status_vector:
            if not field_name:
                return None
            field_index = layer.fields().indexFromName(field_name)
            if field_index < 0:
                return None

            if selection.kind is SpatialSelectionKind.POINT:
                point_value = selection.value
                if not hasattr(point_value, "x") or not hasattr(point_value, "y"):
                    return None
                point = QgsPointXY(float(point_value.x), float(point_value.y))
                source_crs = getattr(point_value, "crs", None)
                canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
                if source_crs is not None and source_crs.authid() != canvas_crs.authid():
                    transform = QgsCoordinateTransform(
                        source_crs, canvas_crs, QgsProject.instance()
                    )
                    point = transform.transform(point)
                feature = self.findFeatureAtPoint(
                    layer, point, self.iface.mapCanvas(), only_the_closest_one=True
                )
                if feature is None:
                    return None
                value = feature[field_index]
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    return None
                return numeric if np.isfinite(numeric) else None

            polygon_value = selection.value
            geometry = getattr(polygon_value, "geom", None)
            if geometry is None:
                return None
            geometry = QgsGeometry(geometry)
            source_crs = getattr(polygon_value, "crs", None)
            if source_crs is not None and source_crs.authid() != layer.crs().authid():
                transform = QgsCoordinateTransform(
                    source_crs, layer.crs(), QgsProject.instance()
                )
                geometry.transform(transform)
            request = QgsFeatureRequest().setFilterRect(geometry.boundingBox())
            values = []
            for feature in layer.getFeatures(request):
                if not feature.geometry().intersects(geometry):
                    continue
                try:
                    numeric = float(feature[field_index])
                except (TypeError, ValueError):
                    continue
                if np.isfinite(numeric):
                    values.append(numeric)
            return float(np.mean(values)) if values else None

        status_raster, _ = grd_layer_utils.checkGrdLayer(layer)
        if status_raster and selection.kind is SpatialSelectionKind.POINT:
            target_crs = self._resolveRasterTargetCrs(layer)
            point_value = selection.value
            if hasattr(point_value, "x") and hasattr(point_value, "y"):
                point = QgsPointXY(float(point_value.x), float(point_value.y))
                source_crs = getattr(point_value, "crs", None)
                if source_crs is not None and target_crs.isValid() and source_crs.authid() != target_crs.authid():
                    transform = QgsCoordinateTransform(
                        source_crs, target_crs, QgsProject.instance()
                    )
                    point = transform.transform(point)
            elif selection.map_location is not None:
                point = QgsPointXY(
                    float(selection.map_location.x),
                    float(selection.map_location.y),
                )
                canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
                if canvas_crs.isValid() and target_crs.isValid() and canvas_crs.authid() != target_crs.authid():
                    transform = QgsCoordinateTransform(
                        canvas_crs, target_crs, QgsProject.instance()
                    )
                    point = transform.transform(point)
            else:
                return None
            value = self.raster_layer.getClickedPixelValue(layer, point=point)
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return None
            return numeric if np.isfinite(numeric) else None

        return None
