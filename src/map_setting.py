import numpy as np
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    Qgis,
    QgsColorRampTransformer,
    QgsFeatureRequest,
    QgsGradientColorRamp,
    QgsGradientStop,
    QgsGraduatedSymbolRenderer,
    QgsProperty,
    QgsRectangle,
    QgsRendererRange,
    QgsSimpleMarkerSymbolLayer,
    QgsSingleSymbolRenderer,
    QgsSymbol,
    QgsSymbolLayer,
    QgsUnitTypes,
)
from qgis.core import QgsRasterShader, QgsColorRampShader, QgsSingleBandPseudoColorRenderer
from osgeo import gdal


from . import color_maps
from .layer_utils import vector_layer as vector_layer_utils
from .layer_utils import grd_layer as grd_layer_utils
from .get_version import qgisVresion
from .std_statistics import (
    STD_FAST_EXACT_THRESHOLD,
    STD_FAST_GRID_SIZE,
    STD_FAST_SAMPLE_SIZE,
    summarize_std_values,
)
from .ui.map_settings.marker_state import (
    DEFAULT_MARKER_SHAPE, DEFAULT_OUTLINE_COLOR, DEFAULT_OUTLINE_WIDTH_MM,
    normalize_marker_shape,
)
from .qt_compat import NO_PEN, SOLID_LINE
from .ui.map_settings.range_state import StdCalculationMode


class velocity():
    def __init__(self):
        self.min_value = None
        self.max_value = None
        self.mean_value = None
        self.std_value = None


class InsarMap:
    def __init__(self, iface):
        self.iface = iface
        self.selected_field_name = None
        self.symbol_size = 1
        self.min_value = -5
        self.max_value = 5
        self.offset_value = 0
        self.data_min = None
        self.data_max = None
        self.data_mean = None
        self.data_stdv = None
        self.marker_shape = DEFAULT_MARKER_SHAPE
        self.stroke_color = DEFAULT_OUTLINE_COLOR
        self.stroke_width = DEFAULT_OUTLINE_WIDTH_MM
        self.alpha = 0.9
        self.num_classes = 9
        self.color_ramp_name = color_maps.DEFAULT_COLORMAP_ID
        self.color_ramp_reverse_flag = False
        self.continuous_colormap = True
        self.data_type = "vector"
        self._std_statistics_cache = {}
        self._std_cache_connected_layer_ids = set()

    def reset(self):
        self.data_min = None
        self.data_max = None
        self.data_mean = None
        self.data_stdv = None
        self.clearStdStatisticsCache()

    @staticmethod
    def _layerIdentity(layer):
        """Return a stable cache identity for one QGIS layer object."""
        layer_id = getattr(layer, "id", None)
        if callable(layer_id):
            return layer_id()
        return id(layer)

    def clearStdStatisticsCache(self, layer_id=None):
        """Clear cached Std statistics globally or for one changed layer."""
        if layer_id is None:
            self._std_statistics_cache.clear()
        else:
            self._std_statistics_cache = {
                key: value
                for key, value in self._std_statistics_cache.items()
                if key[0] != layer_id
            }
        self.data_mean = None
        self.data_stdv = None

    def _trackStdStatisticsLayerChanges(self, layer):
        """Conservatively invalidate cached statistics when vector data changes."""
        layer_id = self._layerIdentity(layer)
        if layer_id in self._std_cache_connected_layer_ids:
            return

        def invalidate(*args, layer_id=layer_id):
            self.clearStdStatisticsCache(layer_id)
            self.data_min = None
            self.data_max = None

        for signal_name in (
            "attributeValueChanged",
            "featureAdded",
            "featureDeleted",
            "dataChanged",
            "committedAttributeValuesChanges",
            "committedFeaturesAdded",
            "committedFeaturesRemoved",
        ):
            signal = getattr(layer, signal_name, None)
            if signal is not None and hasattr(signal, "connect"):
                signal.connect(invalidate)

        destroyed = getattr(layer, "destroyed", None)
        if destroyed is not None and hasattr(destroyed, "connect"):
            def forget_layer(*args, layer_id=layer_id):
                self.clearStdStatisticsCache(layer_id)
                self._std_cache_connected_layer_ids.discard(layer_id)

            destroyed.connect(forget_layer)
        self._std_cache_connected_layer_ids.add(layer_id)

    @staticmethod
    def _noGeometryFeatureRequestFlag():
        """Return the no-geometry request flag across supported QGIS APIs."""
        flag = getattr(QgsFeatureRequest, "NoGeometry", None)
        if flag is not None:
            return flag
        return Qgis.FeatureRequestFlag.NoGeometry

    def _stdStatisticsRequest(self, layer, field_index, *, filter_rect=None, limit=None):
        """Build an attribute-only request for exact or bounded statistics."""
        request = QgsFeatureRequest()
        # Use the integer-index overload. Passing QgsFields as a second argument
        # selects the name-based overload in PyQGIS and rejects integer indexes.
        request.setSubsetOfAttributes([field_index])
        request.setFlags(self._noGeometryFeatureRequestFlag())
        if filter_rect is not None:
            request.setFilterRect(filter_rect)
        if limit is not None:
            request.setLimit(max(0, int(limit)))
        return request

    @staticmethod
    def _hasUsableSamplingExtent(layer):
        """Return whether a layer extent can support spatial stratification."""
        try:
            extent = layer.extent()
        except (AttributeError, RuntimeError):
            return False
        if extent is None:
            return False
        is_null = getattr(extent, "isNull", None)
        if callable(is_null) and is_null():
            return False
        is_empty = getattr(extent, "isEmpty", None)
        if callable(is_empty) and is_empty():
            return False
        try:
            return extent.width() > 0 and extent.height() > 0
        except (AttributeError, TypeError):
            return False

    def _boundedFastStdValues(self, layer, field_index):
        """Return a deterministic bounded sample spanning a spatial layer."""
        target = max(1, int(STD_FAST_SAMPLE_SIZE))
        if not self._hasUsableSamplingExtent(layer):
            request = self._stdStatisticsRequest(
                layer, field_index, limit=target
            )
            return [feature[field_index] for feature in layer.getFeatures(request)]

        extent = layer.extent()
        grid_size = min(
            max(1, int(STD_FAST_GRID_SIZE)),
            max(1, int(np.sqrt(target))),
        )
        cell_count = grid_size * grid_size
        base_quota, remainder = divmod(target, cell_count)
        cell_width = extent.width() / grid_size
        cell_height = extent.height() / grid_size

        sampled_values = []
        seen_feature_ids = set()
        cell_index = 0
        for row in range(grid_size):
            y_min = extent.yMinimum() + row * cell_height
            y_max = (
                extent.yMaximum()
                if row == grid_size - 1
                else extent.yMinimum() + (row + 1) * cell_height
            )
            for column in range(grid_size):
                quota = base_quota + (1 if cell_index < remainder else 0)
                cell_index += 1
                if quota <= 0:
                    continue
                x_min = extent.xMinimum() + column * cell_width
                x_max = (
                    extent.xMaximum()
                    if column == grid_size - 1
                    else extent.xMinimum() + (column + 1) * cell_width
                )
                request = self._stdStatisticsRequest(
                    layer,
                    field_index,
                    filter_rect=QgsRectangle(x_min, y_min, x_max, y_max),
                    limit=quota,
                )
                for feature in layer.getFeatures(request):
                    feature_id = feature.id()
                    if feature_id in seen_feature_ids:
                        continue
                    seen_feature_ids.add(feature_id)
                    sampled_values.append(feature[field_index])
                    if len(sampled_values) >= target:
                        return sampled_values
        return sampled_values

    def _vectorStdStatistics(self, layer, mode):
        """Return cached exact or deterministic sampled statistics for a field."""
        field_name = self.selected_field_name
        if field_name is None:
            return None, "layer field name is None"
        field_index = layer.fields().indexFromName(field_name)
        if field_index < 0:
            return None, "Layer field was not found."

        if mode is None:
            mode = StdCalculationMode.EXACT
        elif not isinstance(mode, StdCalculationMode):
            try:
                mode = StdCalculationMode(mode)
            except (TypeError, ValueError):
                return None, "Unsupported standard-deviation calculation mode."

        layer_id = self._layerIdentity(layer)
        cache_key = (layer_id, field_name, mode.value)
        cached = self._std_statistics_cache.get(cache_key)
        if cached is not None:
            return cached, ""

        self._trackStdStatisticsLayerChanges(layer)
        is_exact = True
        if mode is StdCalculationMode.FAST:
            feature_count = max(0, int(layer.featureCount()))
            if feature_count > STD_FAST_EXACT_THRESHOLD:
                values = self._boundedFastStdValues(layer, field_index)
                is_exact = False
            else:
                request = self._stdStatisticsRequest(layer, field_index)
                values = (
                    feature[field_index] for feature in layer.getFeatures(request)
                )
        else:
            request = self._stdStatisticsRequest(layer, field_index)
            values = (feature[field_index] for feature in layer.getFeatures(request))

        statistics = summarize_std_values(values, is_exact=is_exact)
        if statistics is None:
            self._std_statistics_cache.pop(cache_key, None)
            return None, "No valid values are available for range statistics."

        self._std_statistics_cache[cache_key] = statistics
        return statistics, ""

    def setSymbologyRangeFromData(self, layer=None, n_std=None, std_calculation_mode=None):
        if not layer:
            layer = self.iface.activeLayer()

        status_vector, message = vector_layer_utils.checkVectorLayer(layer)
        status_raster, message = grd_layer_utils.checkGrdLayer(layer)
        if status_vector:
            self.data_type = "vector"
            return self.getDataRangeFromVectorLayer(
                layer, n_std, std_calculation_mode=std_calculation_mode
            )
        elif status_raster:
            self.data_type = "raster"
            return self.getDataRangeFromRasterLayer(layer, n_std)
        else:
            message = 'Invalid Layer: Please select a valid layer.'
            return message

    def getDataRangeFromVectorLayer(self, layer, n_std=None, std_calculation_mode=None):
        field_name = self.selected_field_name
        if field_name is None:
            return "layer field name is None"

        if n_std is None:
            if self.data_min is None or self.data_max is None:
                if qgisVresion() > (3, 20):
                    min_max = layer.minimumAndMaximumValue(layer.fields().indexFromName(field_name))
                else:
                    min_max = [layer.minimumValue(layer.fields().indexFromName(field_name)),
                               layer.maximumValue(layer.fields().indexFromName(field_name))]
                self.data_min, self.data_max = min_max
                if self.data_min is None or self.data_max is None:
                    values = [feature[field_name] for feature in layer.getFeatures() if feature[field_name] is not None]
                    self.data_min = np.nanmin(values)
                    self.data_max = np.nanmax(values)

            self.min_value = self.data_min
            self.max_value = self.data_max
        else:
            statistics, error = self._vectorStdStatistics(
                layer, std_calculation_mode
            )
            if error:
                return error
            self.data_mean = statistics.mean
            self.data_stdv = statistics.std
            self.min_value = self.data_mean - n_std * self.data_stdv
            self.max_value = self.data_mean + n_std * self.data_stdv

        return ""

    def getDataRangeFromRasterLayer(self, layer, n_std=None):
        if n_std is None:
            if self.data_min is None or self.data_max is None:
                self.data_min = layer.dataProvider().bandStatistics(1).minimumValue
                self.data_max = layer.dataProvider().bandStatistics(1).maximumValue
            self.min_value = self.data_min
            self.max_value = self.data_max
        else:
            if self.data_mean is None or self.data_stdv is None:
                self.data_mean = layer.dataProvider().bandStatistics(1).mean
                self.data_stdv = layer.dataProvider().bandStatistics(1).stdDev
            # if mean/stdv is nan load the data as array
            if not np.isfinite(self.data_mean) or not np.isfinite(self.data_stdv):
                self.data_mean, self.data_stdv = self.getDataRangeFromGdal(layer)

            self.min_value = self.data_mean - n_std * self.data_stdv
            self.max_value = self.data_mean + n_std * self.data_stdv

        return ""

    def getDataRangeFromGdal(self, layer):
        file_path = layer.dataProvider().dataSourceUri()
        dataset = gdal.Open(file_path)
        if not dataset:
            return float('nan'), float('nan')

        band = dataset.GetRasterBand(1)
        if not band:
            return float('nan'), float('nan')

        stats = band.GetStatistics(True, True)
        if not stats:
            return float('nan'), float('nan')

        data_mean = stats[2]  # Mean value
        data_stdv = stats[3]  # Standard deviation

        return data_mean, data_stdv

    def setSymbology(self, layer=None, color_ramp_name=None):

        if not color_ramp_name:
            color_ramp_name = self.color_ramp_name

        if not layer:
            layer = self.iface.activeLayer()

        status_vector, message = vector_layer_utils.checkVectorLayer(layer)
        status_raster, message = grd_layer_utils.checkGrdLayer(layer)
        if status_vector is False and status_raster is False:
            message = "Could not set the symbology. Check layer validity."
            return message

        if status_vector or status_raster:
            interval = (self.max_value - self.min_value) / self.num_classes

            color_ramp_id = color_maps.canonical_colormap_id(color_ramp_name)
            self.color_ramp_name = color_ramp_id
            color_ramp = color_maps.COLORMAP_BY_ID[color_ramp_id].factory()

            if self.color_ramp_reverse_flag:
                color_ramp.reverse()

            max_length = max(len(f"{self.min_value:.2f}"), len(f"{self.max_value:.2f}"))

        if status_vector:
            if self.continuous_colormap:
                self.setSymbologyVectorContinuous(layer, color_ramp)
            else:
                self.setSymbologyVector(layer, interval, max_length, color_ramp)
            return ""
        elif status_raster:
            if self.continuous_colormap:
                self.setSymbologyRasterContinuous(layer, color_ramp)
            else:
                self.setSymbologyRaster(layer, interval, max_length, color_ramp)
            return ""
        else:
            message = "Could not set the symbology. Check layer validity."
            return message

    @staticmethod
    def _markerShape(shape_name):
        """Resolve one stable marker-shape value across QGIS enum layouts."""
        shape_owner = getattr(QgsSimpleMarkerSymbolLayer, "Shape", None)
        if shape_owner is None:
            shape_owner = QgsSimpleMarkerSymbolLayer
        enum_names = {
            "circle": "Circle",
            "square": "Square",
            "triangle_up": "Triangle",
            "triangle_down": "Triangle",
            "diamond": "Diamond",
            "star": "Star",
        }
        shape_name = normalize_marker_shape(shape_name)
        return getattr(shape_owner, enum_names.get(shape_name, "Circle"))

    @staticmethod
    def _millimeterRenderUnit():
        """Return the QGIS millimetre render unit across QGIS 3 and QGIS 4."""
        render_unit = getattr(Qgis, "RenderUnit", None)
        if render_unit is not None and hasattr(render_unit, "Millimeters"):
            return render_unit.Millimeters
        return QgsUnitTypes.RenderMillimeters

    def _configurePointMarkerSymbol(self, symbol):
        """Apply point-marker shape, size, outline, and opacity consistently."""
        symbol_layer = symbol.symbolLayer(0)
        if not isinstance(symbol_layer, QgsSimpleMarkerSymbolLayer):
            return symbol_layer
        marker_shape = normalize_marker_shape(self.marker_shape)
        symbol_layer.setShape(self._markerShape(marker_shape))
        symbol_layer.setAngle(180.0 if marker_shape == "triangle_down" else 0.0)
        symbol_layer.setSize(float(self.symbol_size))
        if hasattr(symbol_layer, "setSizeUnit"):
            symbol_layer.setSizeUnit(self._millimeterRenderUnit())
        stroke_width = float(self.stroke_width)
        if stroke_width <= 0.0:
            symbol_layer.setStrokeStyle(NO_PEN)
        else:
            symbol_layer.setStrokeStyle(SOLID_LINE)
            symbol_layer.setStrokeColor(QColor(self.stroke_color))
            symbol_layer.setStrokeWidth(stroke_width)
            if hasattr(symbol_layer, "setStrokeWidthUnit"):
                symbol_layer.setStrokeWidthUnit(self._millimeterRenderUnit())
        symbol.setOpacity(self.alpha)
        return symbol_layer

    @staticmethod
    def _qgisGradientColorRamp(color_ramp):
        """Convert the plugin ramp to a native smooth QGIS gradient ramp."""
        stops = list(color_ramp.ramp)
        if not stops:
            return QgsGradientColorRamp()
        if len(stops) == 1:
            color = QColor(stops[0][1])
            return QgsGradientColorRamp(color, color, False, [])

        gradient_stops = [
            QgsGradientStop(float(position), QColor(color))
            for position, color in stops[1:-1]
        ]
        return QgsGradientColorRamp(
            QColor(stops[0][1]),
            QColor(stops[-1][1]),
            False,
            gradient_stops,
        )

    @staticmethod
    def _symbolLayerColorProperty(geometry_type):
        """Return the data-defined color property for one vector geometry type."""
        property_name = "StrokeColor" if int(geometry_type) == 1 else "FillColor"
        legacy_name = "Property{}".format(property_name)
        legacy = getattr(QgsSymbolLayer, legacy_name, None)
        if legacy is not None:
            return legacy
        return getattr(QgsSymbolLayer.Property, property_name)

    def setSymbologyRasterContinuous(self, layer, color_ramp):
        """Apply a genuinely interpolated raster shader for the active range."""
        effective_min = float(self.min_value) + float(self.offset_value)
        effective_max = float(self.max_value) + float(self.offset_value)
        shader = QgsRasterShader()
        shader.setMinimumValue(effective_min)
        shader.setMaximumValue(effective_max)
        color_ramp_shader = QgsColorRampShader()
        color_ramp_shader.setMinimumValue(effective_min)
        color_ramp_shader.setMaximumValue(effective_max)
        color_ramp_shader.setColorRampType(QgsColorRampShader.Interpolated)

        span = float(self.max_value) - float(self.min_value)
        items = []
        for position, ramp_color in color_ramp.ramp:
            raw_value = float(self.min_value) + float(position) * span
            value = raw_value + float(self.offset_value)
            color = QColor(ramp_color)
            color.setAlphaF(self.alpha)
            items.append(
                QgsColorRampShader.ColorRampItem(value, color, f"{raw_value:.2f}")
            )

        color_ramp_shader.setColorRampItemList(items)
        color_ramp_shader.setColorRampType(QgsColorRampShader.Interpolated)
        shader.setRasterShaderFunction(color_ramp_shader)
        renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
        renderer.setClassificationMin(effective_min)
        renderer.setClassificationMax(effective_max)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        self.iface.mapCanvas().refresh()

    def setSymbologyVectorContinuous(self, layer, color_ramp):
        """Apply per-feature continuous ramp coloring through a QGIS transformer."""
        field_name = self.selected_field_name
        if field_name is None:
            return "layer field name is None"

        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        symbol_layer = symbol.symbolLayer(0)
        if int(layer.geometryType()) == 0:
            symbol_layer = self._configurePointMarkerSymbol(symbol)
        elif hasattr(symbol, "setOpacity"):
            symbol.setOpacity(self.alpha)

        property_value = QgsProperty.fromField(field_name)
        property_value.setTransformer(
            QgsColorRampTransformer(
                float(self.min_value) + float(self.offset_value),
                float(self.max_value) + float(self.offset_value),
                self._qgisGradientColorRamp(color_ramp),
            )
        )
        symbol_layer.setDataDefinedProperty(
            self._symbolLayerColorProperty(layer.geometryType()),
            property_value,
        )

        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        layer.triggerRepaint()
        self.iface.mapCanvas().refresh()
        return ""

    def setSymbologyRaster(self, layer, interval, max_length, color_ramp):

        shader = QgsRasterShader()
        color_ramp_shader = QgsColorRampShader()
        color_ramp_shader.setColorRampType(QgsColorRampShader.Interpolated)

        color_ramp_items = []
        for i in range(self.num_classes):
            value = self.min_value + i * interval
            adjusted_value = value + self.offset_value

            color_ratio = float(i) / (self.num_classes - 1)
            color = color_ramp.getColor(color_ratio)
            color.setAlphaF(self.alpha)

            label = f"{value:>{max_length}.2f}  -  {value + interval:<{max_length}.2f}"
            # if i == 0:
            #     label = f"{value:6.1f}"
            # elif i == self.num_classes - 1:
            #     label = f"{value + interval:6.1f}"
            # else:
            #     label = ""

            if i == self.num_classes - 1:
                color_ramp_items.append(QgsColorRampShader.ColorRampItem(float('inf'), color, label))
            else:
                color_ramp_items.append(QgsColorRampShader.ColorRampItem(adjusted_value, color, label))

        color_ramp_shader.setColorRampItemList(color_ramp_items)
        color_ramp_shader.setColorRampType(QgsColorRampShader.Discrete)
        shader.setRasterShaderFunction(color_ramp_shader)

        renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, shader)
        # renderer.setClassificationMin(self.min_value + self.offset_value)
        # renderer.setClassificationMax(self.max_value + self.offset_value)

        layer.setRenderer(renderer)
        layer.triggerRepaint()
        self.iface.mapCanvas().refresh()

    def setSymbologyVector(self, layer, interval, max_length, color_ramp):

        ranges = []
        for i in range(self.num_classes):
            lower = self.min_value + i * interval
            upper = lower + interval
            label = f"{lower:>{max_length}.2f}  -  {upper:<{max_length}.2f}"

            symbol = QgsSymbol.defaultSymbol(layer.geometryType())

            if self.num_classes == 1:
                color_ratio = 0.5
            else:
                color_ratio = float(i) / (self.num_classes - 1)
            color = color_ramp.getColor(color_ratio)
            color.setAlphaF(self.alpha)
            symbol.setColor(color)
            if int(layer.geometryType()) == 0:
                self._configurePointMarkerSymbol(symbol)
            elif hasattr(symbol, "setOpacity"):
                symbol.setOpacity(self.alpha)

            if i == 0:
                lower = float('-inf')
            if i == self.num_classes - 1:
                upper = float('inf')

            lower += self.offset_value
            upper += self.offset_value

            range_item = QgsRendererRange(lower, upper, symbol, label)
            ranges.append(range_item)

        field_name = self.selected_field_name
        if field_name is None:
            return "layer field name is None"
        else:
            renderer = QgsGraduatedSymbolRenderer(field_name, ranges)
            # renderer.setMode(QgsGraduatedSymbolRenderer.Custom)

        layer.setRenderer(renderer)
        layer.triggerRepaint()
        self.iface.mapCanvas().refresh()

        return ""
