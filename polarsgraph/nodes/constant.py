import polars as pl
from PySide6 import QtWidgets

from polarsgraph.nodes import PINK as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import (
    BaseNode, BaseSettingsWidget, set_combo_values_from_table_columns)


class ATTR:
    NAME = 'name'
    NEW_COLUMN_NAME = 'new_column_name'
    SOURCE_COLUMN = 'source_column'
    SOURCE_ROW = 'source_row'


class ConstantNode(BaseNode):
    type = 'constant ref'  # "ref" because hardcoded constant = `Derive` node
    category = MANIPULATE_CATEGORY
    inputs = 'table', 'constant source'
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        settings[ATTR.NEW_COLUMN_NAME] = (
            settings.get(ATTR.NEW_COLUMN_NAME) or 'ref')
        super().__init__(settings)

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]
        source_df: pl.LazyFrame = tables[1]

        new_column_name = self[ATTR.NEW_COLUMN_NAME]
        source_column_name = self[ATTR.SOURCE_COLUMN]
        source_row = self[ATTR.SOURCE_ROW]
        source_row = int(source_row) if source_row else 0
        value = source_df.select(
            pl.col(source_column_name).get(source_row)).collect()[0, 0]

        self.tables['table'] = df.with_columns(
            pl.lit(value).alias(new_column_name))


class ConstantSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.new_column_name_edit = QtWidgets.QLineEdit()
        self.new_column_name_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(
                self.new_column_name_edit, ATTR.NEW_COLUMN_NAME))

        self.source_column_edit = QtWidgets.QComboBox()
        self.source_column_edit.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.source_column_edit, ATTR.SOURCE_COLUMN))

        self.row_edit = QtWidgets.QLineEdit()
        self.row_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(
                self.row_edit, ATTR.SOURCE_ROW, data_type=int))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('new column name', self.new_column_name_edit)
        form_layout.addRow('source column', self.source_column_edit)
        form_layout.addRow('source row', self.row_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node

        self.name_edit.setText(node[ATTR.NAME])

        self.new_column_name_edit.setText(
            node[ATTR.NEW_COLUMN_NAME] or 'ref')

        row = node[ATTR.SOURCE_ROW]
        self.row_edit.setText(str(row) if row else '0')

        source_col = node[ATTR.SOURCE_COLUMN]
        set_combo_values_from_table_columns(
            self.source_column_edit, input_tables[1], source_col)

        self.blockSignals(False)
