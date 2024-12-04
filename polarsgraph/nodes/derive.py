"""
{column_name} + ({column_name} + 1 / 2)
@func(arg1, arg2)
"""
import polars as pl

from PySide6 import QtWidgets

from polarsgraph.nodes import ORANGE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


HELP_TEXT = """Examples:
    {column_name} + ({column_name} + 1 / 2)
    @round({column_name}, 2)"""


class ATTR:
    NAME = 'name'
    COLUMN = 'column'
    FORMULA = 'formula'


class DeriveNode(BaseNode):
    type = 'derive'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, tables):
        table: pl.LazyFrame = tables[0]
        formula = self[ATTR.FORMULA]
        column_name = self[ATTR.COLUMN] or 'Derived column'
        table = table.with_columns(pl.lit(formula).alias(column_name))
        self.tables['table'] = table


class DeriveSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.column_edit = QtWidgets.QLineEdit()
        self.column_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(self.column_edit, ATTR.COLUMN))

        self.formula_edit = QtWidgets.QPlainTextEdit()
        self.formula_edit.textChanged.connect(
            lambda: self.line_edit_to_settings(
                self.formula_edit, ATTR.FORMULA))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('Column name', self.column_edit)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(QtWidgets.QLabel('Formula'))
        layout.addWidget(self.formula_edit)
        layout.addWidget(QtWidgets.QLabel(HELP_TEXT))

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.column_edit.setText(node[ATTR.COLUMN] or '')
        self.formula_edit.setPlainText(node[ATTR.FORMULA] or '')
        self.blockSignals(False)
