"""
The cells colors are defined by columns with same name + `~color` suffix
CSV Example:
    Value,Value~color
    .6,#5512BE

The `format` node does this but it can be implemented with new nodes
"""

import polars as pl
from PySide6 import QtWidgets

from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget

from polarsgraph.nodes.table.tablewidget import ATTR, TableDisplay


class TableNode(BaseNode):
    type = 'table'
    category = DISPLAY_CATEGORY
    inputs = 'table',
    outputs = 'widget',
    default_color = DEFAULT_COLOR

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
        return self._display_widget


class TableSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        self.index_combo = QtWidgets.QComboBox()
        self.index_combo.addItems(['auto'] + [str(i) for i in range(1, 10)])
        self.index_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.index_combo, ATTR.DISPLAY_INDEX))

        self.frozen_columns_spinbox = QtWidgets.QSpinBox(maximum=99)
        self.frozen_columns_spinbox.valueChanged.connect(
            lambda: self.spinbox_to_settings(
                self.frozen_columns_spinbox, ATTR.FROZEN_COLUMNS))

        self.frozen_rows_spinbox = QtWidgets.QSpinBox(maximum=99)
        self.frozen_rows_spinbox.valueChanged.connect(
            lambda: self.spinbox_to_settings(
                self.frozen_rows_spinbox, ATTR.FROZEN_ROWS))

        self.rows_number_offset_spinbox = QtWidgets.QSpinBox(maximum=99)
        self.rows_number_offset_spinbox.valueChanged.connect(
            lambda: self.spinbox_to_settings(
                self.rows_number_offset_spinbox, ATTR.ROWS_NUMBER_OFFSET))

        self.round_digits_spinbox = QtWidgets.QSpinBox(maximum=99)
        self.round_digits_spinbox.valueChanged.connect(
            lambda: self.spinbox_to_settings(
                self.round_digits_spinbox, ATTR.ROUND_FLOATS_DIGITS))

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('Display index', self.index_combo)
        form_layout.addRow('Frozen columns', self.frozen_columns_spinbox)
        form_layout.addRow('Frozen rows', self.frozen_rows_spinbox)
        form_layout.addRow(
            'Rows number offset', self.rows_number_offset_spinbox)
        form_layout.addRow(
            'Round digits count (0 = off)', self.round_digits_spinbox)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.frozen_columns_spinbox.setValue(node[ATTR.FROZEN_COLUMNS] or 0)
        self.frozen_rows_spinbox.setValue(node[ATTR.FROZEN_ROWS] or 0)
        self.rows_number_offset_spinbox.setValue(
            node[ATTR.ROWS_NUMBER_OFFSET] or 0)
        self.round_digits_spinbox.setValue(
            node[ATTR.ROUND_FLOATS_DIGITS] or 0)
        index = node[ATTR.DISPLAY_INDEX]
        if index:
            self.index_combo.setCurrentText(index)
        self.input_table: pl.LazyFrame = input_tables[0]
        self.blockSignals(False)
