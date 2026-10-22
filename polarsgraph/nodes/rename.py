import polars as pl
from PySide6 import QtWidgets, QtCore

from polarsgraph.attrs import StrAttr
from polarsgraph.nodes import BLUE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


RENAMES = 'renames'
PREFIX = 'columns_prefix'


class RenameNode(BaseNode):
    type = 'rename'
    category = MANIPULATE_CATEGORY
    input_plugs = 'table',
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [StrAttr(PREFIX, label='Columns prefix')]

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]

        rename_dict = self[RENAMES]
        existing_columns = df.collect_schema().names()
        if rename_dict:
            rename_dict = {
                k: v for k, v in rename_dict.items() if k in existing_columns}
            df = df.rename(rename_dict)

        prefix = self[PREFIX]
        if prefix:
            df = df.rename({c: f'{prefix}{c}' for c in existing_columns})

        self.tables['table'] = df


class RenameSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        self.input_table = None

        self.column_rename_table = QtWidgets.QTableWidget()
        self.column_rename_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.column_rename_table.setColumnCount(2)
        self.column_rename_table.setHorizontalHeaderLabels(
            ['Current name', 'New name'])

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.build_attr_form(RenameNode.attrs))
        layout.addWidget(self.column_rename_table)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]
        self.load_attrs(node, input_tables)
        self.populate_rename_table()
        self.blockSignals(False)

    def populate_rename_table(self):
        self.column_rename_table.blockSignals(True)

        if self.input_table is None:
            columns = []
        else:
            columns = self.input_table.collect_schema().names()
        self.column_rename_table.setRowCount(len(columns))

        for i, column in enumerate(columns):
            # Add original column name
            column_item = QtWidgets.QTableWidgetItem(column)
            column_item.setFlags(QtCore.Qt.ItemIsEnabled)
            self.column_rename_table.setItem(i, 0, column_item)

            # Add text input for new name
            rename_input = QtWidgets.QLineEdit()
            if column in (self.node[RENAMES] or {}):
                rename_input.setText(self.node[RENAMES][column])
            rename_input.editingFinished.connect(self._handle_rename_changes)
            self.column_rename_table.setCellWidget(i, 1, rename_input)

        self.column_rename_table.blockSignals(False)

    def _handle_rename_changes(self):
        renames = {}
        for row in range(self.column_rename_table.rowCount()):
            original_column_name = self.column_rename_table.item(row, 0).text()
            new_column_name = self.column_rename_table.cellWidget(
                row, 1).text()
            if new_column_name:  # Only store if new name is provided
                renames[original_column_name] = new_column_name

        self.node[RENAMES] = renames
        self.emit_changed()
