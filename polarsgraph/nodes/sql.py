import os

import polars as pl
from PySide6 import QtWidgets, QtGui

from polarsgraph.nodes import PURPLE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class ATTR:
    NAME = 'name'
    QUERY = 'query'


class SQLNode(BaseNode):
    type = 'sql'
    category = MANIPULATE_CATEGORY
    inputs = 'table1', 'table2', 'table3'
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def _build_query(self, tables):
        query = self[ATTR.QUERY]
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

        self.query_edit = QtWidgets.QPlainTextEdit()
        self.query_edit.textChanged.connect(
            lambda: self.line_edit_to_settings(self.query_edit, ATTR.QUERY))
        self.query_edit.setStyleSheet(
            'QPlainTextEdit{background-color:#333333;color:#9cdcfe}')
        self.query_edit.setFont(editor_font)

        hint = QtWidgets.QLabel(
            'Input tables are available as: table1, table2, table3')
        hint.setWordWrap(True)

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(QtWidgets.QLabel('SQL Query'))
        layout.addWidget(self.query_edit)
        layout.addWidget(hint)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.query_edit.setPlainText(node[ATTR.QUERY] or '')
        self.blockSignals(False)
