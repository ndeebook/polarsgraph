import polars as pl
from PySide6 import QtWidgets
from PySide6.QtCore import Qt

from polarsgraph.nodes import BLUE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import (
    FORMATS, BaseNode, BaseSettingsWidget, get_format_exp)


class ATTR:
    NAME = 'name'
    COLUMN_FORMATS = 'formats'


class FormatNode(BaseNode):
    type = 'format'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]

        # Apply formats to columns
        column_formats = self[ATTR.COLUMN_FORMATS] or {}
        for col_name, fmt in column_formats.items():
            if not fmt:
                continue
            df = df.with_columns(get_format_exp(pl.col(col_name), fmt))

        self.tables['table'] = df


class FormatSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        self.input_table = None

        # Table for column format selection
        self.column_format_table = QtWidgets.QTableWidget()
        self.column_format_table.setColumnCount(2)
        self.column_format_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.column_format_table.setHorizontalHeaderLabels(
            ['Column', 'Format'])

        refresh_button = QtWidgets.QPushButton('Refresh columns list')
        refresh_button.clicked.connect(self.populate_format_table)

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self.column_format_table)
        layout.addWidget(refresh_button)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.input_table: pl.LazyFrame = input_tables[0]

        self.populate_format_table()

        self.blockSignals(False)

    def populate_format_table(self):
        if self.input_table is None:
            columns = []
        else:
            columns = self.input_table.collect_schema().names()
        self.column_format_table.blockSignals(True)
        self.column_format_table.setRowCount(len(columns))

        settings_formats = self.node[ATTR.COLUMN_FORMATS] or {}

        for i, column in enumerate(columns):
            # Add column name
            column_item = QtWidgets.QTableWidgetItem(column)
            column_item.setFlags(Qt.ItemIsEnabled)
            self.column_format_table.setItem(i, 0, column_item)

            # Add format dropdown
            format_combo = QtWidgets.QComboBox()
            format_combo.addItems(FORMATS)
            format_combo.setCurrentText(settings_formats.get(column, ''))
            format_combo.currentTextChanged.connect(
                lambda _, col=column: self._handle_format_change(col))
            self.column_format_table.setCellWidget(i, 1, format_combo)

        self.column_format_table.blockSignals(False)

    def _handle_format_change(self, column):
        formats = {}
        for row in range(self.column_format_table.rowCount()):
            column_item = self.column_format_table.item(row, 0)
            if not column_item:
                continue
            col_name = column_item.text()
            format_combo = self.column_format_table.cellWidget(row, 1)
            if format_combo:
                formats[col_name] = format_combo.currentText()

        self.node[ATTR.COLUMN_FORMATS] = formats
        self.emit_changed()


def format_duration(seconds):
    seconds = int(seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return '%ih %02dm %02ds' % (hours, minutes, seconds)
    elif minutes:
        return '%im %02ds' % (minutes, seconds)
    else:
        return '%i seconds' % seconds
