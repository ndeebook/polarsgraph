"""
The cells colors are defined by columns with same name + `~color` suffix
CSV Example:
    Value,Value~color
    .6,#5512BE

The `format` node does this but it can be implemented with new nodes
"""

import polars as pl
from PySide6 import QtWidgets

from polarsgraph.attrs import BoolAttr, ChoiceAttr, IntAttr, StrAttr
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.nodes.base import (
    DISPLAY_INDEX_ATTR, BaseNode, BaseSettingsWidget)

from polarsgraph.nodes.table.tablewidget import (
    AUTO_RESIZE_MAX_ROWS, FIT, FROZEN_COLUMNS, FROZEN_ROWS,
    ROUND_FLOATS_DIGITS, ROWS_NUMBER_OFFSET, SHOW_ROW_NUMBERS, TITLE,
    TableDisplay)


DISPLAY_INDEX_OPTIONS = ['auto'] + [str(i) for i in range(1, 10)]


class TableNode(BaseNode):
    type = 'table'
    category = DISPLAY_CATEGORY
    input_plugs = 'table',
    output_plugs = 'widget',
    default_color = DEFAULT_COLOR
    attrs = [
        StrAttr(TITLE, label='Title'),
        ChoiceAttr(DISPLAY_INDEX_ATTR, DISPLAY_INDEX_OPTIONS,
                   label='Display index'),
        BoolAttr(SHOW_ROW_NUMBERS, default=True, label='Show row numbers'),
        BoolAttr(FIT, default=False, label='Fit to view'),
        IntAttr(FROZEN_COLUMNS, default=0, label='Frozen columns', maximum=99),
        IntAttr(FROZEN_ROWS, default=0, label='Frozen rows', maximum=99),
        IntAttr(ROWS_NUMBER_OFFSET, default=0,
                label='Rows number offset', maximum=99),
        IntAttr(ROUND_FLOATS_DIGITS, default=0,
                label='Round digits count (0 = off)', maximum=99),
        IntAttr(AUTO_RESIZE_MAX_ROWS, default=0,
                label='Auto-resize columns (max rows, 0 = off)',
                maximum=9999),
    ]

    def __init__(self, settings=None):
        super().__init__(settings)

        self._display_widget = None

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]
        if df is None:
            return self.clear()

        # Update display
        if not self.display_widget:
            return
        self.display_widget.set_table(df.collect())

    def clear(self):
        self.display_widget.set_table(pl.DataFrame())

    @property
    def display_widget(self):
        if not self._display_widget:
            self._display_widget = TableDisplay(self)
            self._display_widget.action_requested.connect(
                self.app.handle_display_request)
        return self._display_widget


class TableSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.build_attr_form(TableNode.attrs))

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.input_table: pl.LazyFrame = input_tables[0]
        self.blockSignals(False)
