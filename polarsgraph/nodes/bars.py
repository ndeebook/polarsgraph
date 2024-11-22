import traceback

import yaml
import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore, QtCharts
from PySide6.QtCore import Qt

from polarsgraph.log import logger
from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget, BaseDisplay


TABLE_HANDLE_CSS = 'QScrollBar::handle:vertical {min-height: 30px;}'


class ATTR:
    NAME = 'name'


class BarsNode(BaseNode):
    type = 'bars'
    category = DISPLAY_CATEGORY
    inputs = 'table',
    outputs = 'widget',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

        self._display_widget = None

    def _build_query(self, tables):
        self.tables['table'] = tables[0]
        # Update display
        if not self.display_widget:
            return
        self.display_widget.set_table(tables[0])

    @property
    def display_widget(self):
        if not self._display_widget:
            self._display_widget = BarsDisplay()
        return self._display_widget


class BarsSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        ...

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.blockSignals(False)


class BarsDisplay(BaseDisplay):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.node: BarsNode = None
        self._resizing = False

        # Widgets
        self.chart_view = QtCharts.QChartView()

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chart_view)

    def set_table(self, table):
        chart = QtCharts.QChart()
        self.bar_series = QtCharts.QHorizontalStackedBarSeries()
        chart.addSeries(self.bar_series)
        chart.setTitle('Bars Chart')
        self.chart_view.setChart(chart)
        if table is None:
            return

    def get_pixmap(self):
        pixmap = QtGui.QPixmap(self.chart_view.size())
        self.chart_view.render(pixmap)
        return pixmap

    def save_image(self):
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save spreadsheet', '', '*.png')
        if not filepath:
            return
        self.get_pixmap().save(filepath)

    def image_to_clipboard(self):
        QtWidgets.QApplication.clipboard().setPixmap(self.get_pixmap())
