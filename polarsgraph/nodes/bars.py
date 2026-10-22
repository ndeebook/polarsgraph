import math
import random
import traceback
from functools import lru_cache

import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.attrs import ChoiceAttr, StrAttr
from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes.base import (
    DISPLAY_INDEX_ATTR, BaseNode, BaseSettingsWidget, BaseDisplay)


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


TITLE = 'title'
COLORS = 'colors'

DISPLAY_INDEX_OPTIONS = ['auto'] + [str(i) for i in range(1, 10)]


class BarsNode(BaseNode):
    type = 'bars'
    category = DISPLAY_CATEGORY
    input_plugs = 'table',
    output_plugs = 'widget',
    default_color = DEFAULT_COLOR
    attrs = [
        ChoiceAttr(DISPLAY_INDEX_ATTR, DISPLAY_INDEX_OPTIONS,
                   label='Display index'),
        StrAttr(TITLE, label='Title'),
    ]

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

        self.input_table = None

        # Colors table is a dynamic per-column widget — kept custom.
        self.colors_table = QtWidgets.QTableWidget(minimumHeight=250)
        self.colors_table.setColumnCount(2)
        self.colors_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.colors_table.setHorizontalHeaderLabels(['Column', ''])
        self.colors_table.cellChanged.connect(self.set_colors_from_table)
        self.colors_table.cellClicked.connect(self.edit_color)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.build_attr_form(BarsNode.attrs))
        layout.addWidget(QtWidgets.QLabel('Colors:'))
        layout.addWidget(self.colors_table)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]
        self.load_attrs(node, input_tables)
        self.populate_color_table()
        self.blockSignals(False)

    def _add_row(self, row_index, column='', color=None):
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

    def populate_color_table(self):
        self.colors_table.blockSignals(True)

        colors = self.node[COLORS] or {}

        if self.input_table is None:
            columns = []
        else:
            columns = self.input_table.collect_schema().names()[1:]

        self.colors_table.setRowCount(len(columns))
        for i, column in enumerate(columns):
            self._add_row(i, column, colors.get(column))

        self.colors_table.blockSignals(False)
        self.set_colors_from_table()

    def set_colors_from_table(self):
        colors = {}
        for row_index in range(self.colors_table.rowCount()):
            column = self.colors_table.item(row_index, 0).text()
            color = self.colors_table.item(row_index, 1).text()
            colors[column] = color
        self.node[COLORS] = colors
        self.emit_changed()

    def edit_color(self, row_index, col):
        if col != 1:
            return
        color = QtWidgets.QColorDialog.getColor()
        if not color.isValid():
            return
        self.colors_table.item(row_index, 1).setBackground(color)
        self.colors_table.item(row_index, 1).setText(color.name().upper())
        self.set_colors_from_table()


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
        self.segments = []
        self.hover_segment = None
        self.setMouseTracking(True)

    def set_data(self, table, node):
        self.dataframe = table
        self.node = node
        self.hover_segment = None
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Get widget dimensions
        rect = self.rect()
        margin = 10
        title_offset = 10
        legend_offset = 24

        self.segments = []

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
        title = self.node[TITLE] or self.node['name']
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
        colors = self.node[COLORS] or {}
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
                width = (value / max_value) * bg_rect.width()

                # Set color for the bar segment
                painter.setPen(Qt.NoPen)
                painter.setBrush(colors[column])

                # Draw bar segment
                bar_rect = QtCore.QRectF(x, y, width, bar_height * .7)
                painter.drawRect(bar_rect)
                if value:
                    self.segments.append({
                        'rect': QtCore.QRectF(bar_rect),
                        'row_label': row[self.dataframe.columns[0]],
                        'row_total': totals[i],
                        'column': column,
                        'value': value,
                        'color': colors[column],
                    })
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

        # Hover tooltip
        if self.hover_segment is not None:
            self._draw_hover(painter, rect)

    def _draw_hover(self, painter, widget_rect):
        if self.hover_segment >= len(self.segments):
            return
        seg = self.segments[self.hover_segment]

        # Highlight the hovered segment
        painter.setPen(QtGui.QPen(QtGui.QColor('white'), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(seg['rect'])

        total = seg['row_total'] or 0
        pct = (seg['value'] / total * 100) if total else 0
        lines = [
            str(seg['row_label']),
            f"Total: {auto_round(total)}",
            f"{seg['column']}: {auto_round(seg['value'])} ({pct:.1f}%)",
        ]

        metrics = painter.fontMetrics()
        pad_x, pad_y, line_gap = 6, 4, 2
        text_w = max(metrics.horizontalAdvance(ln) for ln in lines)
        line_h = metrics.height()
        box_w = text_w + 2 * pad_x
        box_h = len(lines) * line_h + (len(lines) - 1) * line_gap + 2 * pad_y

        # Position near segment center, flip to stay in widget
        offset = 12
        anchor_x = seg['rect'].right()
        anchor_y = seg['rect'].top()
        box_x = anchor_x + offset
        box_y = anchor_y - box_h - offset
        if box_x + box_w > widget_rect.right():
            box_x = seg['rect'].left() - offset - box_w
        if box_y < widget_rect.top():
            box_y = seg['rect'].bottom() + offset
        box_x = max(widget_rect.left(), box_x)
        box_y = min(widget_rect.bottom() - box_h, box_y)

        box = QtCore.QRectF(box_x, box_y, box_w, box_h)
        painter.setPen(QtGui.QPen(seg['color'], 1))
        painter.setBrush(QtGui.QColor(0, 0, 0, 200))
        painter.drawRoundedRect(box, 3, 3)

        painter.setPen(COLOR['text'])
        y_cursor = box.top() + pad_y + metrics.ascent()
        for ln in lines:
            painter.drawText(QtCore.QPointF(box.left() + pad_x, y_cursor), ln)
            y_cursor += line_h + line_gap

    def mouseMoveEvent(self, event):
        if not self.segments:
            if self.hover_segment is not None:
                self.hover_segment = None
                self.update()
            return

        pos = event.position()
        new_hover = None
        for idx, seg in enumerate(self.segments):
            if seg['rect'].contains(pos):
                new_hover = idx
                break

        if new_hover != self.hover_segment:
            self.hover_segment = new_hover
            self.update()

    def leaveEvent(self, event):
        if self.hover_segment is not None:
            self.hover_segment = None
            self.update()
        super().leaveEvent(event)


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
