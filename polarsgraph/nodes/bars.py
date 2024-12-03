import math
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
        margin = 10
        rect = self.rect()
        totals = self.dataframe.select(
            self.dataframe.columns[1:]).sum_horizontal()
        max_value = get_next_big_value(totals.max())

        # Background
        painter.fillRect(rect, self.palette().color(
            QtGui.QPalette.ColorRole.Base))

        # BG Lines
        rect.adjust(margin, margin, -margin, -margin)
        bar_height = rect.height() / (len(self.dataframe))

        line_positions = 0, 0.25, 0.5, 0.75, 1.0
        painter.setPen(QtGui.QPen(QtCore.Qt.black, .5))
        for pos in line_positions:
            x = rect.left() + pos * rect.width()
            painter.drawLine(x, rect.top(), x, rect.bottom())

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
                bar_rect = QtCore.QRectF(x, y, width, bar_height * .7)
                painter.drawRect(bar_rect)
                x += width

            # Draw label
            label = row[self.dataframe.columns[0]]
            painter.setPen(self.palette().color(QtGui.QPalette.WindowText))
            line_rect = QtCore.QRectF(
                margin * 2, y, rect.width() - margin * 2, bar_height * .7)
            updated_text_rect = painter.drawText(
                line_rect, Qt.AlignLeft | Qt.AlignVCenter, label)

            # Draw total
            total = f'{auto_round(totals[i])}'
            if bar_rect.right() < updated_text_rect.right() + 40:
                bar_rect.setX(updated_text_rect.right() + margin)
                bar_rect.setWidth(1000)
                painter.drawText(
                    bar_rect, Qt.AlignLeft | Qt.AlignVCenter, f'({total})')
            else:
                bar_rect.setWidth(width - margin)
                painter.drawText(
                    bar_rect, Qt.AlignRight | Qt.AlignVCenter, total)


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
