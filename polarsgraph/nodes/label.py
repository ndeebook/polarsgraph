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
FONT_FAMILY = 'Verdana'
FILL_MARGIN = 10
REFERENCE_PIXEL_SIZE = 100

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

        rect = QtCore.QRectF(self.rect())
        alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        if self.node[SIZE_TYPE] == USE_FONT_SIZE:
            font_size = self.node[FONT_SIZE] or DEFAULT_FONT_SIZE
            painter.setFont(QtGui.QFont(FONT_FAMILY, font_size))
            painter.drawText(rect, alignment, self.label)
        else:
            rect.adjust(FILL_MARGIN, FILL_MARGIN, -FILL_MARGIN, -FILL_MARGIN)
            draw_fitted_text(painter, rect, alignment, self.label)


def draw_fitted_text(
        painter: QtGui.QPainter,
        rect: QtCore.QRectF,
        alignment: Qt.AlignmentFlag,
        text: str,
        family: str = FONT_FAMILY):
    """
    Draw text as large as possible in rect.
    Text is laid out once at a reference size then scaled by the painter,
    so the result is linear with rect size (no font size rounding/hinting
    jumps).
    """
    if not text or rect.width() <= 0 or rect.height() <= 0:
        return

    font = QtGui.QFont(family)
    font.setPixelSize(REFERENCE_PIXEL_SIZE)
    font.setHintingPreference(QtGui.QFont.HintingPreference.PreferNoHinting)
    text_rect = QtGui.QFontMetricsF(font).boundingRect(
        QtCore.QRectF(), alignment, text)
    if not text_rect.width() or not text_rect.height():
        return

    scale = min(
        rect.width() / text_rect.width(),
        rect.height() / text_rect.height())

    painter.save()
    painter.translate(rect.topLeft())
    painter.scale(scale, scale)
    painter.setFont(font)
    painter.drawText(
        QtCore.QRectF(0, 0, rect.width() / scale, rect.height() / scale),
        alignment, text)
    painter.restore()
