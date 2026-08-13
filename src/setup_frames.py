from ..external import pyqtgraph as pg

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QVBoxLayout

from .ui.toolbars import TimeSeriesToolbar


class TimeSeriesPlotWidget(pg.GraphicsLayoutWidget):
    """Graphics layout widget that reports when hover inspection must clear."""

    mouseLeft = pyqtSignal()

    def leaveEvent(self, event):
        """Clear plot-local hover state when the pointer leaves the widget."""
        self.mouseLeft.emit()
        super().leaveEvent(event)


def setupTsFrame(ui):
    ui.plot_widget = TimeSeriesPlotWidget(parent=ui.frame_plot_ts)
    ui.plot_widget.setBackground('w')
    ui.plot_widget.plot_items = []
    ui.time_series_toolbar = TimeSeriesToolbar(ui.frame_plot_ts)

    ui.frame_plot_layout = QVBoxLayout(ui.frame_plot_ts)
    ui.frame_plot_layout.setContentsMargins(0, 0, 0, 0)
    ui.frame_plot_layout.setSpacing(1)
    ui.frame_plot_layout.addWidget(ui.plot_widget)
    ui.frame_plot_layout.addWidget(ui.time_series_toolbar)
