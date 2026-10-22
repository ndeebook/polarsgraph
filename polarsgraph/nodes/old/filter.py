import polars as pl
from PySide6 import QtWidgets

from polarsgraph.attrs import ChoiceAttr, ColumnChoiceAttr, StrAttr
from polarsgraph.nodes import BLUE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import (
    BaseNode, BaseSettingsWidget, convert_value, convert_values)


COLUMN = 'column'
CONDITION = 'condition'
VALUE = 'value'


CONDITIONS = ['==', '!=', '>', '<', 'is_in', 'not_in', 'contains']


class FilterNode(BaseNode):
    type = 'filter'
    deprecated = True
    category = MANIPULATE_CATEGORY
    input_plugs = 'table',
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [
        ColumnChoiceAttr(COLUMN, label='Column'),
        ChoiceAttr(CONDITION, CONDITIONS, label='Condition'),
        StrAttr(VALUE, label='Value'),
    ]

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]

        condition = self[CONDITION]
        column = self[COLUMN]
        value = self[VALUE]
        data_type = df.collect_schema()[column]

        if condition in ('is_in', 'not_in'):
            values = [v.strip() for v in value.split(',')]
            values = convert_values(values, data_type)
            exp = pl.col(column).is_in(values)
            if condition == 'not_in':
                exp = ~exp
            df = df.filter(exp)
        elif condition == 'contains':
            if ',' in value:
                exp = pl.col(column).str.contains_any(
                    [v.strip() for v in value.split(',')])
            else:
                exp = pl.col(column).str.contains(value)
            df = df.filter(exp)
        else:
            value = convert_value(value, data_type)
            if condition == '==':
                if not value and data_type == pl.String:
                    df = df.filter(
                        pl.col(column).is_null() | (pl.col(column) == ''))
                else:
                    df = df.filter(pl.col(column) == value)
            elif condition == '!=':
                if not value and data_type == pl.String:
                    df = df.filter(
                        ~(pl.col(column).is_null() | (pl.col(column) == '')))
                else:
                    df = df.filter(
                        (pl.col(column) != value) | pl.col(column).is_null())
            elif condition == '>':
                df = df.filter(pl.col(column) > value)
            elif condition == '<':
                df = df.filter(pl.col(column) < value)

        self.tables['table'] = df


class FilterSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.build_attr_form(FilterNode.attrs))

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]
        self.load_attrs(node, input_tables)
        self.blockSignals(False)
