import polars as pl
from PySide6 import QtWidgets

from polarsgraph.attrs import ChoiceAttr, ColumnChoiceAttr
from polarsgraph.nodes import PINK as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


LEFT_COLUMN = 'left_column'
RIGHT_COLUMN = 'right_column'
HOW = 'how'

JOIN_STRATEGIES = ['inner', 'left', 'right', 'full', 'semi', 'anti', 'cross']


class JoinNode(BaseNode):
    type = 'join'
    category = MANIPULATE_CATEGORY
    input_plugs = 'left', 'right'
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [
        ColumnChoiceAttr(LEFT_COLUMN, label='Left column', input_index=0),
        ColumnChoiceAttr(RIGHT_COLUMN, label='Right column', input_index=1),
        ChoiceAttr(HOW, JOIN_STRATEGIES, label='How'),
    ]

    def _build_query(self, tables):
        df1: pl.LazyFrame = tables[0]
        df2: pl.LazyFrame = tables[1]

        # Rename columns to make them same name (always pick shorter one)
        left_col = self[LEFT_COLUMN]
        right_col = self[RIGHT_COLUMN]
        column_name = left_col
        if left_col != right_col:
            column_name = (
                left_col if len(left_col) < len(right_col) else right_col)
            df1 = df1.rename({left_col: column_name})
            df2 = df2.rename({right_col: column_name})

        # Join
        strategy = self['how']
        self.tables['table'] = df1.join(
            df2,
            on=column_name,
            how=strategy,
            coalesce=True,
            suffix='' if strategy != 'full' else '_right',
        )


class JoinSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.build_attr_form(JoinNode.attrs))

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.blockSignals(False)
