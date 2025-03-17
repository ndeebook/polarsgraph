import polars as pl
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt

from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes.base import (
    FORMATS, BaseNode, BaseSettingsWidget, BaseDisplay,
    get_format_exp, set_combo_values_from_table_columns)


class ATTR:
    NAME = 'name'
    SOURCE_COLUMN = 'source_column'
    SOURCE_ROW = 'source_row'
    FORMAT = 'format'


class LabelNode(BaseNode):
    type = 'label'
    category = DISPLAY_CATEGORY
    inputs = 'table',
    outputs = 'widget',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

        self._display_widget = None

    def _build_query(self, tables: list[pl.LazyFrame]):
        # Update display
        if not self.display_widget:
            return

        source_column_name = self[ATTR.SOURCE_COLUMN]
        source_row = self[ATTR.SOURCE_ROW]
        source_row = int(source_row) if source_row else 0
        fmt = self[ATTR.FORMAT]

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

        # Widgets
        self.source_column_edit = QtWidgets.QComboBox()
        self.source_column_edit.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.source_column_edit, ATTR.SOURCE_COLUMN))

        self.row_edit = QtWidgets.QLineEdit()
        self.row_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(
                self.row_edit, ATTR.SOURCE_ROW, data_type=int))

        self.format_combo = QtWidgets.QComboBox()
        self.format_combo.addItems(FORMATS)
        self.format_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.format_combo, ATTR.FORMAT))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('source column', self.source_column_edit)
        form_layout.addRow('source row', self.row_edit)
        form_layout.addRow('format', self.format_combo)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])

        row = node[ATTR.SOURCE_ROW]
        self.row_edit.setText(str(row) if row else '0')

        source_col = node[ATTR.SOURCE_COLUMN]
        set_combo_values_from_table_columns(
            self.source_column_edit, input_tables[0], source_col)

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
        font_size = rect.height() * .5
        alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        font = QtGui.QFont('Verdana', font_size)
        font_family = 'Verdana'
        font_size = get_maximum_font_size(
            self.label, rect, alignment, font_size, font_family)
        font = QtGui.QFont(font_family, font_size)
        painter.setFont(font)

        painter.drawText(rect, alignment, self.label)


def get_maximum_font_size(
        text, rect, alignment, font_size=12, family='Verdana'):
    font = QtGui.QFont(family, font_size)
    metrics = QtGui.QFontMetrics(font)
    text_rect = metrics.boundingRect(rect, alignment, text)
    w_ratio = text_rect.width() / rect.width()
    h_ratio = text_rect.height() / rect.height()
    return font_size / max([w_ratio, h_ratio]) - 4
