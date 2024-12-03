import random
from functools import lru_cache

import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

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

    def clear(self):
        pass

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
        max_value = self.dataframe.select(
            self.dataframe.columns[1:]).sum_horizontal().max()

        # Background
        painter.fillRect(rect, self.palette().color(QtGui.QPalette.Window))

        margin = 10
        rect.adjust(margin, margin, -margin, -margin)
        bar_height = rect.height() / len(self.dataframe)

        # Draw each row as a horizontal stacked bar
        colors = get_bars_colors(len(self.dataframe.columns))
        for i, row in enumerate(self.dataframe.iter_rows(named=True)):
            y = margin + i * bar_height
            x = margin
            for j, column in enumerate(self.dataframe.columns[1:]):
                value = row[column]
                width = (value / max_value) * rect.width()

                # Set color for the bar segment
                painter.setBrush(colors[j])
                painter.setPen(Qt.NoPen)

                # Draw bar segment
                bar_rect = QtCore.QRectF(x, y, width, bar_height * 0.7)
                painter.drawRect(bar_rect)
                x += width

            # Draw label
            label = row[self.dataframe.columns[0]]
            painter.setPen(self.palette().color(QtGui.QPalette.WindowText))
            bar_rect.adjust(10, 0, 300, 0)
            painter.drawText(bar_rect, Qt.AlignLeft | Qt.AlignVCenter, label)


def get_next_hue(previous_hue):
    hue = random.randint(0, 255)
    while abs(previous_hue - hue) < 100:
        hue = random.randint(0, 255)
    return hue


@lru_cache()
def get_bars_colors(count):
    previous_hue = 100
    colors = []
    for _ in range(count):
        hue = get_next_hue(previous_hue)
        colors.append(QtGui.QColor.fromHsv(hue, 122, 122))
        previous_hue = hue
    return colors
