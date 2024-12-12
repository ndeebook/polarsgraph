import polars as pl
from PySide6 import QtWidgets

from polarsgraph.nodes import PINK as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import (
    BaseNode, BaseSettingsWidget, set_combo_values_from_table_columns)


class ATTR:
    NAME = 'name'
    LEFT_COLUMN = 'left_column'
    RIGHT_COLUMN = 'right_column'
    HOW = 'how'


class JoinNode(BaseNode):
    type = 'join'
    category = MANIPULATE_CATEGORY
    inputs = 'left', 'right'
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        settings[ATTR.HOW] = settings.get(ATTR.HOW) or 'inner'
        super().__init__(settings)

    def _build_query(self, tables):
        df1: pl.LazyFrame = tables[0]
        df2: pl.LazyFrame = tables[1]

        # Rename columns to make them same name (always pick shorter one)
        left_col = self[ATTR.LEFT_COLUMN]
        right_col = self[ATTR.RIGHT_COLUMN]
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

        # Widgets
        self.left_column_edit = QtWidgets.QComboBox()
        self.left_column_edit.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.left_column_edit, ATTR.LEFT_COLUMN))
        self.right_column_edit = QtWidgets.QComboBox()
        self.right_column_edit.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.right_column_edit, ATTR.RIGHT_COLUMN))
        self.how_combo = QtWidgets.QComboBox()
        self.how_combo.addItems([
            'inner', 'left', 'right', 'full', 'semi', 'anti', 'cross'])
        self.how_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(self.how_combo, ATTR.HOW))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('left column', self.left_column_edit)
        form_layout.addRow('right column', self.right_column_edit)
        form_layout.addRow('how', self.how_combo)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node

        self.name_edit.setText(node[ATTR.NAME])

        left = node[ATTR.LEFT_COLUMN] or ''
        set_combo_values_from_table_columns(self.left_column_edit, input_tables[0], left)

        right = node[ATTR.RIGHT_COLUMN] or ''
        set_combo_values_from_table_columns(self.right_column_edit, input_tables[1], right)

        self.how_combo.setCurrentText(node[ATTR.HOW] or 'inner')

        self.blockSignals(False)
