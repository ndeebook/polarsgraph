import polars as pl
from PySide6 import QtWidgets

from polarsgraph.nodes import GRAY as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.attrs import ChoiceAttr
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class ConcatenateNode(BaseNode):
    type = 'concatenate'
    category = MANIPULATE_CATEGORY
    input_plugs = 'table1', 'table2'
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [ChoiceAttr('how', ['vertical', 'horizontal'])]

    def _build_query(self, tables):
        df1: pl.LazyFrame = tables[0]
        df2: pl.LazyFrame = tables[1]

        if self['how'] == 'vertical':
            # order columns the same way
            df2 = df2.select(df1.collect_schema().names())

        self.tables['table'] = pl.concat([df1, df2], how=self['how'])


class ConcatenateSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        form_layout = self.build_attr_form(ConcatenateNode.attrs)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.blockSignals(False)
