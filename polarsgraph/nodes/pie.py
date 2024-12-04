import math
import random
from functools import lru_cache

import polars as pl
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt

from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget, BaseDisplay


TABLE_HANDLE_CSS = 'QScrollBar::handle:vertical {min-height: 30px;}'


class ATTR:
    NAME = 'name'


class PieNode(BaseNode):
    type = 'pie'
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

    def clear(self):
        pass

    @property
    def display_widget(self):
        if not self._display_widget:
            self._display_widget = PieDisplay()
        return self._display_widget


class PieSettingsWidget(BaseSettingsWidget):
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


class PieDisplay(BaseDisplay):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.node: PieNode = None
        self._resizing = False

        # Widgets
        self.chart_view = CustomStackedBarChart()

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chart_view)

    def set_table(self, table: pl.LazyFrame):
        if table is None:
            return
        table = table.collect(stream=True)
        self.chart_view.set_table(table)

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


class CustomStackedBarChart(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dataframe = pl.DataFrame()

    def set_table(self, table):
        self.dataframe = table
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Get widget dimensions
        rect = self.rect()
        rect.adjust(10, 10, -10, -10)  # Add margin
        center = rect.center()
        radius = min(rect.width(), rect.height()) // 2

        # Calculate total values per row
        data = self.dataframe.select(self.dataframe.columns[1])
        total = data.sum()[0, 0]

        count = self.dataframe.shape[0]
        colors = get_pie_colors(count)
        start_angle = 0

        for i, values in enumerate(self.dataframe.iter_rows()):
            label, value, *_ = values
            span_angle = 360 * (value / total)
            if i != count - 1:
                span_angle + 10  # avoid seeing background between parts

            # Set color for the segment
            painter.setBrush(colors[i])
            painter.setPen(Qt.NoPen)

            # Draw the pie segment
            painter.drawPie(
                center.x() - radius, center.y() - radius,
                radius * 2, radius * 2,
                int(start_angle * 16), int(span_angle * 16)
            )
            start_angle += span_angle

            # Add label at the center of each row's pie
            painter.setPen(self.palette().color(QtGui.QPalette.WindowText))
            painter.drawText(
                center.x() - radius, center.y() + radius + 10 * (i + 1),
                radius * 2, 20,
                Qt.AlignCenter, label)


def get_next_hue(previous_hue):
    hue = random.randint(0, 255)
    while abs(previous_hue - hue) < 100:
        hue = random.randint(0, 255)
    return hue


@lru_cache()
def get_pie_colors(count):
    previous_hue = 100
    colors = []
    for _ in range(count):
        hue = get_next_hue(previous_hue)
        colors.append(QtGui.QColor.fromHsv(hue, 122, 122))
        previous_hue = hue
    return colors


def auto_round(value):
    if value < 10:
        return round(value, 2)
    if value < 100:
        return round(value, 1)
    return int(value)


def get_next_big_value(value):
    factor = 1
    step = 10
    while value > 1:
        factor *= step
        value /= step
    return math.ceil(value * step) * factor / step
