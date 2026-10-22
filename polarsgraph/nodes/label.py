import polars as pl
from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.attrs import (
    ChoiceAttr, ColumnChoiceAttr, IntAttr, TextAttr)
from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes.base import (
    DISPLAY_INDEX_ATTR, FORMATS, BaseNode, BaseSettingsWidget, BaseDisplay,
    get_format_exp)


FILL_RECT = 'fill'
USE_FONT_SIZE = 'font size'
DEFAULT_FONT_SIZE = 12

HARDCODED_TEXT = 'hardcoded_text'
SOURCE_COLUMN = 'source_column'
SOURCE_ROW = 'source_row'
FORMAT = 'format'
SIZE_TYPE = 'size_type'
FONT_SIZE = 'font_size'

DISPLAY_INDEX_OPTIONS = ['auto'] + [str(i) for i in range(1, 10)]


class LabelNode(BaseNode):
    type = 'label'
    category = DISPLAY_CATEGORY
    input_plugs = 'table',
    output_plugs = 'widget',
    default_color = DEFAULT_COLOR
    attrs = [
        ChoiceAttr(DISPLAY_INDEX_ATTR, DISPLAY_INDEX_OPTIONS,
                   label='Display index'),
        TextAttr(HARDCODED_TEXT, label='Text',
                 placeholder='(Leave empty to use linked value)'),
        ChoiceAttr(SIZE_TYPE, [FILL_RECT, USE_FONT_SIZE], label='Size type'),
        IntAttr(FONT_SIZE, default=DEFAULT_FONT_SIZE, label='Font size'),
        ColumnChoiceAttr(SOURCE_COLUMN, label='Source column'),
        IntAttr(SOURCE_ROW, default=0, label='Source row'),
        ChoiceAttr(FORMAT, FORMATS, label='Format'),
    ]

    def __init__(self, settings=None):
        super().__init__(settings)
        self._display_widget = None

    def _build_query(self, tables: list[pl.LazyFrame]):
        # Update display
        if not self.display_widget:
            return

        hardcoded_text = self[HARDCODED_TEXT]
        if hardcoded_text:
            return self.display_widget.set_label(hardcoded_text)

        source_column_name = self[SOURCE_COLUMN]
        source_row = self[SOURCE_ROW]
        source_row = int(source_row) if source_row else 0
        fmt = self[FORMAT]

        df = tables[0]
        col = pl.col(source_column_name)
        exp = get_format_exp(col, fmt)
        value = df.select(exp.get(source_row)).collect()[0, 0]

        self.display_widget.set_label(str(value))

    def clear(self):
        pass

    @property
    def display_widget(self):
        if not self._display_widget:
            self._display_widget = LabelDisplay(self)
        return self._display_widget


class LabelSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        form = self.build_attr_form(LabelNode.attrs)
        # Cap the HARDCODED_TEXT widget height to match prior UI.
        LabelNode.attrs[1].widget.setMaximumHeight(200)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addStretch()

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.blockSignals(False)


class LabelDisplay(BaseDisplay):
    def __init__(self, node, parent=None):
        super().__init__(parent)

        self.node: LabelNode = node
        self.label = ''

    def set_label(self, value):
        self.label = str(value)
        self.repaint()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = self.rect()
        font_family = 'Verdana'
        font_size = int(rect.height() * .5)
        font = QtGui.QFont(font_family, font_size)
        alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        if self.node[SIZE_TYPE] == USE_FONT_SIZE:
            font_size = self.node[FONT_SIZE] or DEFAULT_FONT_SIZE
        else:
            font_size = get_maximum_font_size(
                self.label, rect, alignment, font_size, font_family)
        font = QtGui.QFont(font_family, font_size)
        painter.setFont(font)

        painter.drawText(rect, alignment, self.label)


def get_maximum_font_size(
        text: str,
        rect: QtCore.QRect,
        alignment: Qt.AlignmentFlag,
        font_size=DEFAULT_FONT_SIZE,
        family: str = 'Verdana',
        level=0):
    # FIXME: improve this

    width, height = rect.width(), rect.height()
    if not width or not height:
        return font_size
    if level > 6:
        return font_size

    # print(font_size)
    margin = 20
    width = width - margin if width > margin else width
    height = height - margin if height > margin else height
    font = QtGui.QFont(family, font_size)
    next_level = level + 1

    # Get text size
    metrics = QtGui.QFontMetrics(font)
    text_rect = metrics.boundingRect(rect, alignment, text)
    text_width, text_height = text_rect.width(), text_rect.height()

    # Check if text is bigger than rect
    text_overflows = text_width >= width or text_height >= height
    if text_overflows:
        # Compute from a smaller font size to try no overflow
        return get_maximum_font_size(
            text, rect, alignment, font_size / 2, family, next_level)

    # Compute font size from ratio of text beeing too small:
    w_ratio = text_width / width
    h_ratio = text_height / height
    new_size = round(font_size / max([w_ratio, h_ratio]), 2)
    if level == 0 or new_size / 2 > font_size:
        # Get a more accurate size
        return get_maximum_font_size(
            text, rect, alignment, new_size, family, next_level)

    # print(f'[{new_size}] {text_width} - {width} | {text_height} - {height}')

    return int(new_size * .95)
