import numpy as np
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsGraduatedSymbolRenderer, QgsRendererRange, QgsSymbol
from qgis.core import QgsRasterShader, QgsColorRampShader, QgsSingleBandPseudoColorRenderer
from osgeo import gdal


from . import color_maps
from .layer_utils import vector_layer as vector_layer_utils
from .layer_utils import grd_layer as grd_layer_utils
from .get_version import qgisVresion


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
        self.stroke_width = 0.01
        self.alpha = 0.9
        self.num_classes = 9
        self.color_ramp_name = color_maps.DEFAULT_COLORMAP_ID
        self.color_ramp_reverse_flag = False
        self.data_type = "vector"

    def reset(self):
        self.data_min = None
        self.data_max = None
        self.data_mean = None
        self.data_stdv = None

    def setSymbologyRangeFromData(self, layer=None, n_std=None, std_calculation_mode=None):
        if not layer:
            layer = self.iface.activeLayer()

        status_vector, message = vector_layer_utils.checkVectorLayer(layer)
        status_raster, message = grd_layer_utils.checkGrdLayer(layer)
        if status_vector:
            self.data_type = "vector"
            self.getDataRangeFromVectorLayer(layer, n_std)
        elif status_raster:
            self.data_type = "raster"
            self.getDataRangeFromRasterLayer(layer, n_std)
        else:
            message = '<span style="color:red;">Invalid Layer: Please select a valid layer.</span>'
            return message

    def getDataRangeFromVectorLayer(self, layer, n_std=None):
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
            if self.data_mean is None or self.data_stdv is None:
                values = [feature[field_name] for feature in layer.getFeatures() if feature[field_name] is not None]
                self.data_mean = np.nanmean(values)
                self.data_stdv = np.nanstd(values)
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
            message = '<span style="color:red;">Could not set the symbology. Check layer validity.</span>'
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
            self.setSymbologyVector(layer, interval, max_length, color_ramp)
            return ""
        elif status_raster:
            self.setSymbologyRaster(layer, interval, max_length, color_ramp)
            return ""
        else:
            message = '<span style="color:red;">Could not set the symbology. Check layer validity.</span>'
            return message

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
            symbol.setSize(self.symbol_size)
            symbol.symbolLayer(0).setStrokeWidth(self.stroke_width)
            symbol.symbolLayer(0).setStrokeColor(QColor("gray"))

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
