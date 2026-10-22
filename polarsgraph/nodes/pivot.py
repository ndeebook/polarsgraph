import polars as pl
from PySide6 import QtWidgets

from polarsgraph.attrs import ColumnChoiceAttr
from polarsgraph.nodes import PINK as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


INDEX = 'index'
COLUMN = 'column'
VALUES = 'values'


class PivotNode(BaseNode):
    type = 'pivot'
    category = MANIPULATE_CATEGORY
    input_plugs = 'table',
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [
        ColumnChoiceAttr(INDEX, label='Index', extra_values=['']),
        ColumnChoiceAttr(COLUMN, label='Column', extra_values=['']),
        ColumnChoiceAttr(VALUES, label='Values', extra_values=['']),
    ]

    def _build_query(self, tables):
        df: pl.DataFrame = tables[0].collect()

        index_column = self[INDEX]
        column_column = self[COLUMN]
        values_column = self[VALUES]

        self.tables['table'] = df.pivot(
            values=values_column,
            index=index_column,
            columns=column_column,
            aggregate_function='sum',
        ).lazy()


class PivotSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.build_attr_form(PivotNode.attrs))

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.blockSignals(False)
