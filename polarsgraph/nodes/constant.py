import polars as pl
from PySide6 import QtWidgets

from polarsgraph.attrs import ColumnChoiceAttr, IntAttr, StrAttr
from polarsgraph.nodes import PINK as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


NEW_COLUMN_NAME = 'new_column_name'
SOURCE_COLUMN = 'source_column'
SOURCE_ROW = 'source_row'


class ConstantNode(BaseNode):
    type = 'constant ref'  # "ref" because hardcoded constant = `Derive` node
    category = MANIPULATE_CATEGORY
    input_plugs = 'table', 'constant source'
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [
        StrAttr(NEW_COLUMN_NAME, default='ref', label='New column name'),
        ColumnChoiceAttr(
            SOURCE_COLUMN, label='Source column', input_index=1),
        IntAttr(SOURCE_ROW, default=0, label='Source row'),
    ]

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]
        source_df: pl.LazyFrame = tables[1]

        new_column_name = self[NEW_COLUMN_NAME]
        source_column_name = self[SOURCE_COLUMN]
        source_row = self[SOURCE_ROW]
        source_row = int(source_row) if source_row else 0
        value = source_df.select(
            pl.col(source_column_name).get(source_row)).collect()[0, 0]

        self.tables['table'] = df.with_columns(
            pl.lit(value).alias(new_column_name))


class ConstantSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.build_attr_form(ConstantNode.attrs))

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.blockSignals(False)
