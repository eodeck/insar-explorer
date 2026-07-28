import os
import re
from xml.etree import ElementTree
from contextlib import contextmanager
from dataclasses import dataclass

from ..external.pyqtgraph import exporters
from qgis.PyQt.QtGui import QColor, QFont, QImage, QPainter
from qgis.PyQt.QtWidgets import QApplication

from .qt_compat import ALIGN_RIGHT_VCENTER


@dataclass(frozen=True)
class ExportResult:
    """Describe the final outcome of a plot export."""

    success: bool
    filename: str = ""
    error: str = ""


class TimeSeriesPlotExporter:
    """Export the existing time-series plot without rebuilding it."""

    BASE_DPI = 96.0
    DEFAULT_DPI = 300
    DEFAULT_ASPECT_RATIO = 4.0
    DEFAULT_ATTRIBUTION_TEXT = 'Created with InSAR Explorer'
    DEFAULT_CREDIT_MARGIN = 8
    DEFAULT_CREDIT_FONT_SIZE = 9
    DEFAULT_CREDIT_FOOTER_HEIGHT = 22
    DEFAULT_MIN_LOGICAL_WIDTH = 1200

    def __init__(self, plotter):
        self.plotter = plotter

    def export(self, filename=None):
        """Export one plot and return an explicit validated result."""
        if not filename:
            return ExportResult(False, error="No export filename was provided.")
        if not self.plotter.series_history:
            return ExportResult(False, filename, "No time-series plot is available to export.")

        plot_widget = self.plotter.ui.plot_widget
        export_item = getattr(plot_widget, 'ci', None) or plot_widget.scene()
        if export_item is None:
            return ExportResult(False, filename, "The plot export item is unavailable.")

        suffix = os.path.splitext(filename)[1].lower()
        if suffix not in ('.png', '.jpg', '.svg'):
            return ExportResult(False, filename, f"Unsupported export format: {suffix or '(none)'}")

        dpi, aspect_ratio, attribution_text = self._exportSettings()
        logical_width, logical_height = self._logicalExportSize(plot_widget, aspect_ratio)
        export_width = max(1, int(round(logical_width * dpi / self.BASE_DPI)))
        export_height = max(1, int(round(logical_height * dpi / self.BASE_DPI)))

        try:
            with self._temporaryExportGeometry(plot_widget, logical_width, logical_height):
                if suffix == '.svg':
                    exporter = exporters.SVGExporter(export_item)
                    self._setExporterParameter(exporter, 'width', logical_width)
                    self._setExporterParameter(exporter, 'height', logical_height)
                    exporter.export(filename)
                    error = self._addCreditToSvg(
                        filename, logical_width, logical_height, attribution_text
                    )
                else:
                    exporter = exporters.ImageExporter(export_item)
                    self._setExporterParameter(exporter, 'width', export_width)
                    self._setExporterParameter(exporter, 'height', export_height)
                    exporter.export(filename)
                    error = self._addCreditToRaster(filename, dpi, attribution_text)
        except Exception as exc:
            return ExportResult(False, filename, f"Plot export failed: {exc}")

        if error:
            return ExportResult(False, filename, error)
        error = self._validateFinalOutput(filename, suffix, attribution_text)
        if error:
            return ExportResult(False, filename, error)
        return ExportResult(True, filename)

    def _exportSettings(self):
        settings_model = getattr(self.plotter, 'settings_model', None)
        if settings_model is not None:
            settings = settings_model.export
            dpi_value = settings.dpi
            aspect_value = settings.aspect_ratio
            include_attribution = settings.include_attribution
        else:
            export_parms = getattr(self.plotter, 'parms', {}).get('export', {})
            dpi_value = export_parms.get('dpi')
            aspect_value = export_parms.get('aspect ratio')
            include_attribution = export_parms.get('include attribution', True)

        try:
            dpi = int(dpi_value)
        except (TypeError, ValueError, OverflowError):
            dpi = self.DEFAULT_DPI
        if str(dpi) not in {'72', '150', '300', '600', '1200'}:
            dpi = self.DEFAULT_DPI
        try:
            aspect_ratio = float(aspect_value)
        except (TypeError, ValueError, OverflowError):
            aspect_ratio = self.DEFAULT_ASPECT_RATIO
        aspect_ratio = max(1.0, min(10.0, aspect_ratio))
        attribution_text = (
            self.DEFAULT_ATTRIBUTION_TEXT if include_attribution else ""
        )
        return dpi, aspect_ratio, attribution_text

    def _logicalExportSize(self, plot_widget, aspect_ratio):
        widget_width = int(round(plot_widget.width() or self.DEFAULT_MIN_LOGICAL_WIDTH))
        logical_width = max(1, widget_width, self.DEFAULT_MIN_LOGICAL_WIDTH)
        logical_height = max(1, int(round(logical_width / aspect_ratio)))
        return logical_width, logical_height

    @contextmanager
    def _temporaryExportGeometry(self, plot_widget, width, height):
        central_item = getattr(plot_widget, 'ci', None)
        old_central_size = central_item.size() if central_item is not None else None
        scene = plot_widget.scene()
        old_scene_rect = scene.sceneRect() if scene is not None else None
        old_updates_enabled = plot_widget.updatesEnabled()

        try:
            plot_widget.setUpdatesEnabled(False)
            self._resizeCentralItem(plot_widget, width, height)
            self._flushPlotGeometry(plot_widget)
            yield
        finally:
            if old_central_size is not None:
                try:
                    central_item.resize(old_central_size)
                except (AttributeError, TypeError):
                    central_item.resize(
                        old_central_size.width(), old_central_size.height()
                    )
            if scene is not None and old_scene_rect is not None:
                scene.setSceneRect(old_scene_rect)
            self._flushPlotGeometry(plot_widget)
            plot_widget.setUpdatesEnabled(old_updates_enabled)
            plot_widget.update()

    def _resizeCentralItem(self, plot_widget, width, height):
        central_item = getattr(plot_widget, 'ci', None)
        if central_item is None:
            return
        try:
            central_item.resize(width, height)
        except AttributeError:
            pass
        scene = plot_widget.scene()
        if scene is not None:
            try:
                scene.setSceneRect(0, 0, width, height)
            except TypeError:
                pass

    def _flushPlotGeometry(self, plot_widget):
        """Force pyqtgraph layout and ViewBox transforms to match the export size."""
        plot_widget.updateGeometry()
        plot_widget.update()
        QApplication.processEvents()

        central_item = getattr(plot_widget, 'ci', None)
        layout = getattr(central_item, 'layout', None)
        if layout is not None:
            try:
                layout.activate()
            except AttributeError:
                pass

        for plot_item in getattr(plot_widget, 'plot_items', []):
            try:
                view_box = plot_item.getViewBox()
            except AttributeError:
                continue
            if hasattr(view_box, '_matrixNeedsUpdate'):
                view_box._matrixNeedsUpdate = True
            try:
                view_box.updateMatrix()
            except AttributeError:
                pass

        QApplication.processEvents()

    def _addCreditToRaster(self, filename, dpi, attribution_text):
        plot_image = QImage(filename)
        if plot_image.isNull():
            return "The exported raster image could not be read."
        if not attribution_text:
            return ""

        suffix = os.path.splitext(filename)[1].lower()
        if suffix not in ('.png', '.jpg'):
            return

        scale = max(1.0, float(dpi) / self.BASE_DPI)
        margin = int(round(self.DEFAULT_CREDIT_MARGIN * scale))
        footer_height = int(round(self.DEFAULT_CREDIT_FOOTER_HEIGHT * scale))

        image = QImage(
            plot_image.width(),
            plot_image.height() + footer_height,
            plot_image.format()
        )
        image.fill(self._figureBackgroundColor())

        font = QFont()
        font.setPixelSize(max(
            1, int(round(self.DEFAULT_CREDIT_FONT_SIZE * scale))
        ))

        painter = QPainter(image)
        try:
            painter.drawImage(0, 0, plot_image)
            painter.setFont(font)
            painter.setPen(QColor(110, 110, 110))
            painter.drawText(
                margin,
                plot_image.height(),
                image.width() - 2 * margin,
                footer_height,
                ALIGN_RIGHT_VCENTER,
                attribution_text
            )
        finally:
            painter.end()

        # QImage uses dots per metre for physical resolution metadata.
        dots_per_metre = max(1, int(round(float(dpi) / 0.0254)))
        image.setDotsPerMeterX(dots_per_metre)
        image.setDotsPerMeterY(dots_per_metre)
        if not image.save(filename):
            return "The exported raster image could not be saved."
        return ""

    def _addCreditToSvg(self, filename, width, height, attribution_text):
        if not attribution_text:
            return ""

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                svg_text = f.read()
        except OSError as exc:
            return f"The exported SVG could not be read: {exc}"

        margin = self.DEFAULT_CREDIT_MARGIN
        font_size = self.DEFAULT_CREDIT_FONT_SIZE
        footer_height = self.DEFAULT_CREDIT_FOOTER_HEIGHT
        total_height = height + footer_height

        svg_text = self._resizeSvgCanvas(svg_text, width, total_height)
        escaped_attribution = self._escapeSvgText(attribution_text)
        background = self._figureBackgroundColor().name()
        footer = (
            f'\n<rect id="insar-explorer-export-attribution-background" '
            f'x="0" y="{height:.3f}" width="{width:.3f}" height="{footer_height:.3f}" '
            f'fill="{background}"/>\n'
            f'<text id="insar-explorer-export-attribution" '
            f'x="{width - margin:.3f}" y="{height + footer_height / 2.0:.3f}" '
            f'text-anchor="end" dominant-baseline="middle" '
            f'font-family="Arial, Helvetica, sans-serif" '
            f'font-size="{font_size}px" fill="#6e6e6e">'
            f'{escaped_attribution}</text>\n'
        )

        insert_at = svg_text.lower().rfind('</svg>')
        if insert_at < 0:
            return "The exported SVG is malformed: missing closing svg element."
        svg_text = svg_text[:insert_at] + footer + svg_text[insert_at:]
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(svg_text)
        except OSError as exc:
            return f"The exported SVG could not be written: {exc}"
        return ""

    def _validateFinalOutput(self, filename, suffix, attribution_text):
        """Return an error message unless the final output is usable."""
        if not os.path.isfile(filename):
            return "The export did not create an output file."
        try:
            if os.path.getsize(filename) <= 0:
                return "The exported file is empty."
        except OSError as exc:
            return f"The exported file could not be inspected: {exc}"
        if suffix == '.svg':
            try:
                ElementTree.parse(filename)
            except (ElementTree.ParseError, OSError):
                return "The exported SVG is not valid XML."
            if attribution_text:
                try:
                    with open(filename, 'r', encoding='utf-8') as svg_file:
                        text = svg_file.read()
                except OSError as exc:
                    return f"The exported SVG could not be read: {exc}"
                required = (
                    'insar-explorer-export-attribution',
                    'insar-explorer-export-attribution-background',
                )
                if not all(marker in text for marker in required):
                    return "The exported SVG attribution footer is incomplete."
        return ""

    def _resizeSvgCanvas(self, svg_text, width, height):
        match = re.search(r'<svg\b[^>]*>', svg_text, flags=re.IGNORECASE)
        if match is None:
            return svg_text

        root = match.group(0)

        root = re.sub(
            r'\s+(width|height|viewBox)\s*=\s*("[^"]*"|\'[^\']*\')',
            '',
            root,
            flags=re.IGNORECASE
        )

        root = root[:-1] + (
            f' width="{width:.3f}"'
            f' height="{height:.3f}"'
            f' viewBox="0 0 {width:.3f} {height:.3f}">'
        )

        return svg_text[:match.start()] + root + svg_text[match.end():]

    def _figureBackgroundColor(self):
        color = self.plotter.settings_model.appearance.canvas_background
        return QColor(color)

    def _escapeSvgText(self, text):
        return (str(text)
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))

    def _setExporterParameter(self, exporter, name, value):
        """Set a pyqtgraph exporter parameter across supported API variants."""
        parameters = exporter.parameters()
        try:
            parameters[name] = int(value)
        except Exception:
            pass
        try:
            parameters.param(name).setValue(int(value))
        except Exception:
            pass
