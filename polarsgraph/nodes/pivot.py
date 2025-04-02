import polars as pl
from PySide6 import QtWidgets

from polarsgraph.nodes import PINK as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import (
    BaseNode, BaseSettingsWidget, set_combo_values_from_table_columns)


class ATTR:
    NAME = 'name'
    INDEX = 'index'
    COLUMN = 'column'
    VALUES = 'values'


class PivotNode(BaseNode):
    type = 'pivot'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, tables):
        df: pl.DataFrame = tables[0].collect()

        index_column = self[ATTR.INDEX]
        column_column = self[ATTR.COLUMN]
        values_column = self[ATTR.VALUES]

        self.tables['table'] = df.pivot(
            values=values_column,
            index=index_column,
            columns=column_column
        ).lazy()


class PivotSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        self.input_table = None

        # Widgets
        self.index_combo = QtWidgets.QComboBox()
        self.index_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.index_combo, ATTR.INDEX))
        self.column_combo = QtWidgets.QComboBox()
        self.column_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.column_combo, ATTR.COLUMN))
        self.values_combo = QtWidgets.QComboBox()
        self.values_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.values_combo, ATTR.VALUES))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow(ATTR.INDEX.title(), self.index_combo)
        form_layout.addRow(ATTR.COLUMN.title(), self.column_combo)
        form_layout.addRow(ATTR.VALUES.title(), self.values_combo)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]

        self.name_edit.setText(node[ATTR.NAME])

        index_col = node[ATTR.INDEX] or ''
        column_col = node[ATTR.COLUMN] or ''
        values_col = node[ATTR.VALUES] or ''
        set_combo_values_from_table_columns(
            self.index_combo, self.input_table, index_col,
            extra_values=[''])
        set_combo_values_from_table_columns(
            self.column_combo, self.input_table, column_col,
            extra_values=[''])
        set_combo_values_from_table_columns(
            self.values_combo, self.input_table, values_col,
            extra_values=[''])

        self.blockSignals(False)
