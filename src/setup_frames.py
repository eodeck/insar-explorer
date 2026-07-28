from ..external import pyqtgraph as pg

from qgis.PyQt.QtWidgets import QVBoxLayout

from .ui.toolbars import TimeSeriesToolbar


def setupTsFrame(ui):
    ui.plot_widget = pg.GraphicsLayoutWidget(parent=ui.frame_plot_ts)
    ui.plot_widget.setBackground('w')
    ui.plot_widget.plot_items = []
    ui.time_series_toolbar = TimeSeriesToolbar(ui.frame_plot_ts)

    ui.frame_plot_layout = QVBoxLayout(ui.frame_plot_ts)
    ui.frame_plot_layout.setContentsMargins(0, 0, 0, 0)
    ui.frame_plot_layout.setSpacing(1)
    ui.frame_plot_layout.addWidget(ui.plot_widget)
    ui.frame_plot_layout.addWidget(ui.time_series_toolbar)
