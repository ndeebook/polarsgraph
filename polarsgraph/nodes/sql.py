import os

import polars as pl
from PySide6 import QtWidgets, QtGui

from polarsgraph.attrs import TextAttr
from polarsgraph.nodes import PURPLE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


QUERY = 'query'


class SQLNode(BaseNode):
    type = 'sql'
    category = MANIPULATE_CATEGORY
    input_plugs = 'table1', 'table2', 'table3'
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [TextAttr(QUERY, label='SQL Query')]

    def _build_query(self, tables):
        query = self[QUERY]
        if not query:
            raise ValueError('Please provide a SQL query')

        context = {
            f'table{i}': table
            for i, table in enumerate(tables, start=1)
            if table is not None
        }
        if not context:
            raise ValueError('At least one input table must be connected')

        ctx = pl.SQLContext(**context)
        self.tables['table'] = ctx.execute(query)


class SqlSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        if os.name == 'nt':
            fixed_font = self.font()
            fixed_font.setFamily('consolas')
        else:
            fixed_font = QtGui.QFontDatabase.systemFont(
                QtGui.QFontDatabase.SystemFont.FixedFont)
        editor_font = QtGui.QFont(fixed_font)
        editor_font.setPointSizeF(editor_font.pointSizeF() * 1.2)

        (query_attr,) = SQLNode.attrs
        _, query_widget = self.register_attr(query_attr)
        query_widget.setStyleSheet(
            'QPlainTextEdit{background-color:#333333;color:#9cdcfe}')
        query_widget.setFont(editor_font)

        form = QtWidgets.QFormLayout()
        form.addRow('Name', self.name_edit)

        hint = QtWidgets.QLabel(
            'Input tables are available as: table1, table2, table3')
        hint.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QtWidgets.QLabel('SQL Query'))
        layout.addWidget(query_widget)
        layout.addWidget(hint)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.blockSignals(False)
