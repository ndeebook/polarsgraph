import math
import random
import traceback
from functools import lru_cache

import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget, BaseDisplay


COLOR = dict(
    text=Qt.GlobalColor.white,
    bg=QtGui.QColor('#2F2F2F'),
    bg_lines=QtGui.QColor('#111111'),
)

DEFAULT_COLORS = [
    '#4F77A8',
    '#76B7B1',
    '#F28E2C',
    '#E15659',
    '#59A14F',
    '#ECC947',
    '#B17AA1',
    '#FE9DA6',
    '#9B755E',
]


class ATTR:
    NAME = 'name'
    TITLE = 'title'
    COLORS = 'colors'


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
            self._display_widget = BarsDisplay(self)
        return self._display_widget


class BarsSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.title_edit = QtWidgets.QLineEdit()
        self.title_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(self.title_edit, ATTR.TITLE))

        self.colors_table = QtWidgets.QTableWidget(minimumHeight=250)
        self.colors_table.setColumnCount(2)
        self.colors_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.colors_table.setHorizontalHeaderLabels(['Column', ''])
        self.colors_table.cellChanged.connect(self.set_colors_from_table)
        self.colors_table.cellClicked.connect(self.edit_color)

        add_button = QtWidgets.QPushButton(
            'add', clicked=self.add_column)
        remove_button = QtWidgets.QPushButton(
            'remove', clicked=self.remove_selected_rows)

        # Layout
        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(remove_button)

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow(ATTR.TITLE.title(), self.title_edit)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(QtWidgets.QLabel('Colors:'))
        layout.addWidget(self.colors_table)
        layout.addLayout(buttons_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.title_edit.setText(node[ATTR.TITLE] or '')
        self.populate_color_table()
        self.blockSignals(False)

    def _add_row(self, row_index, column='', color=None):
        self.colors_table.blockSignals(True)
        try:
            color = color or DEFAULT_COLORS[row_index]
        except IndexError:
            color = '#111111'
        column_item = QtWidgets.QTableWidgetItem(column)
        # column_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.colors_table.setItem(row_index, 0, column_item)

        column_item2 = QtWidgets.QTableWidgetItem(color)
        column_item2.setFlags(
            Qt.ItemFlag.ItemIsEnabled & ~Qt.ItemFlag.ItemIsEditable)
        column_item2.setBackground(QtGui.QColor(color))

        self.colors_table.setItem(row_index, 1, column_item2)
        self.colors_table.blockSignals(False)

    def populate_color_table(self):
        self.colors_table.blockSignals(True)
        colors = self.node[ATTR.COLORS] or {}
        self.colors_table.setRowCount(len(colors))
        for i, (column, color) in enumerate(colors.items()):
            self._add_row(i, column, color)
        self.colors_table.blockSignals(False)

    def set_colors_from_table(self):
        colors = {}
        for row_index in range(self.colors_table.rowCount()):
            column = self.colors_table.item(row_index, 0).text()
            color = self.colors_table.item(row_index, 1).text()
            colors[column] = color
        self.node[ATTR.COLORS] = colors
        self.emit_changed()

    def edit_color(self, row_index, col):
        if col != 1:
            return
        color = QtWidgets.QColorDialog.getColor()
        if not color.isValid():
            return
        self.colors_table.item(row_index, 1).setBackground(color)
        self.colors_table.item(row_index, 1).setText(color.name())
        self.set_colors_from_table()

    def add_column(self):
        count = self.colors_table.rowCount()
        self.colors_table.setRowCount(count + 1)
        self._add_row(count)

    def remove_selected_rows(self):
        for index in self.colors_table.selectedIndexes():
            column = self.colors_table.item(index.row(), 0).text()
            self.node[ATTR.COLORS].pop(column, None)
        self.populate_color_table()


class BarsDisplay(BaseDisplay):
    def __init__(self, node, parent=None):
        super().__init__(parent)

        self.node: BarsNode = node
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
        table = table.collect()
        self.chart_view.set_data(table, self.node)

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

    def set_data(self, table, node):
        self.dataframe = table
        self.node = node
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Get widget dimensions
        rect = self.rect()
        margin = 10
        title_offset = 10
        legend_offset = 24

        # Background
        painter.fillRect(rect, COLOR['bg'])

        # Title
        try:
            totals = self.dataframe.select(
                self.dataframe.columns[1:]).sum_horizontal()
            max_value = get_graph_end_value(totals.max())
        except BaseException:
            painter.drawText(rect, Qt.AlignmentFlag.AlignHCenter, 'Error')
            print(traceback.format_exc())
            return
        title = self.node[ATTR.TITLE] or self.node[ATTR.NAME]
        painter.drawText(rect, Qt.AlignmentFlag.AlignHCenter, title)

        # BG Lines
        bg_rect = rect.adjusted(
            margin, margin + title_offset, -margin, -margin - legend_offset)
        bar_height = bg_rect.height() / len(self.dataframe)

        line_positions = 0, 0.25, 0.5, 0.75, 1.0
        painter.setPen(QtGui.QPen(COLOR['bg_lines'], .5))
        bottom = bg_rect.bottom()
        for pos in line_positions:
            x = bg_rect.left() + pos * bg_rect.width()
            painter.drawLine(x, rect.top(), x, bottom)
            if pos == 0:
                continue
            if pos == line_positions[-1]:
                pos_rect = QtCore.QRectF(
                    rect.right() - 200 + margin, bottom - 20, 200, 50)
                alignment = Qt.AlignCenter | Qt.AlignRight
            else:
                pos_rect = QtCore.QRectF(x - 100, bottom - 20, 200, 50)
                alignment = Qt.AlignCenter
            painter.drawText(pos_rect, alignment, f'{int(max_value * pos)}')

        # Legend
        colors = self.node[ATTR.COLORS] or {}
        colors = {n: QtGui.QColor(c) for n, c in colors.items()}
        colors = get_bars_colors(self.dataframe.columns[1:], colors)
        y = rect.bottom() - legend_offset + margin / 2
        width = (rect.width() - 200) / len(colors) - margin
        painter.setPen(Qt.NoPen)
        for i, (label, color) in enumerate(colors.items()):
            x = 100 + i * (width + margin)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            legend_rect = QtCore.QRectF(
                x, y, width, legend_offset - margin)
            painter.drawRect(legend_rect)
            painter.setPen(COLOR['text'])
            painter.drawText(legend_rect, Qt.AlignCenter, label)

        # Draw each row as a horizontal stacked bar
        for i, row in enumerate(self.dataframe.iter_rows(named=True)):
            y = title_offset + margin + i * bar_height
            x = margin
            total_width = 0
            for j, column in enumerate(self.dataframe.columns[1:]):
                value = row[column] or 0
                width = (value / max_value) * rect.width()

                # Set color for the bar segment
                painter.setPen(Qt.NoPen)
                painter.setBrush(colors[column])

                # Draw bar segment
                bar_rect = QtCore.QRectF(x, y, width, bar_height * .7)
                painter.drawRect(bar_rect)
                x += width
                total_width += width

            # Draw label
            label = row[self.dataframe.columns[0]]
            painter.setPen(COLOR['text'])
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
                bar_rect = QtCore.QRectF(
                    0, y, total_width - margin/2, bar_height * .7)
                painter.drawText(
                    bar_rect, Qt.AlignRight | Qt.AlignVCenter, total)


@lru_cache()
def get_next_hue(previous_hue):
    hue = random.randint(0, 255)
    while abs(previous_hue - hue) < 100:
        hue = random.randint(0, 255)
    return hue


def get_bars_colors(names, colors=None):
    previous_hue = 100
    colors = colors or {}
    for name in names:
        if name in colors:
            continue
        hue = get_next_hue(previous_hue)
        colors[name] = QtGui.QColor.fromHsv(hue, 122, 122)
        previous_hue = hue
    return colors


def auto_round(value):
    if value < 10:
        return round(value, 2)
    if value < 100:
        return round(value, 1)
    return int(value)


def get_graph_end_value(max_value):
    if max_value < 0:
        return -get_graph_end_value(-max_value)
    if max_value > 1:
        size = len(str(math.ceil(max_value)))
        step = 10 ** (size - 2)
    else:
        step = 1
        while max_value * step < 1:
            step *= 10
        step = 1 / step
    result = int(max_value / step) * step
    while result <= max_value * 1.01:
        result += step
    return result
