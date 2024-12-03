import polars as pl
from PySide6 import QtWidgets

from polarsgraph.nodes import BLUE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class ATTR:
    NAME = 'name'
    COLUMNS = 'columns'
    ORDERS = 'orders'


class SortNode(BaseNode):
    type = 'sort'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]

        sort_columns = self[ATTR.COLUMNS] or []
        sort_columns = [col for col in sort_columns if col]
        if sort_columns:
            sort_order = self[ATTR.ORDERS][:len(sort_columns)]
            df = df.sort(
                by=sort_columns, descending=[not asc for asc in sort_order])

        self.tables['table'] = df


class SortSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.sort_combo1 = QtWidgets.QComboBox()
        self.sort_combo2 = QtWidgets.QComboBox()
        self.sort_combo3 = QtWidgets.QComboBox()
        self.order_cb1 = QtWidgets.QCheckBox('Ascending')
        self.order_cb1.setChecked(True)
        self.order_cb2 = QtWidgets.QCheckBox('Ascending')
        self.order_cb2.setChecked(True)
        self.order_cb3 = QtWidgets.QCheckBox('Ascending')
        self.order_cb3.setChecked(True)

        # Signals
        self.sort_combo1.currentTextChanged.connect(
            self.update_order_settings)
        self.sort_combo2.currentTextChanged.connect(
            self.update_order_settings)
        self.sort_combo3.currentTextChanged.connect(
            self.update_order_settings)
        self.order_cb1.stateChanged.connect(self.update_order_settings)
        self.order_cb2.stateChanged.connect(self.update_order_settings)
        self.order_cb3.stateChanged.connect(self.update_order_settings)

        # Layouts
        sort_layout1 = QtWidgets.QHBoxLayout()
        sort_layout1.addWidget(self.sort_combo1)
        sort_layout1.addWidget(self.order_cb1)

        sort_layout2 = QtWidgets.QHBoxLayout()
        sort_layout2.addWidget(self.sort_combo2)
        sort_layout2.addWidget(self.order_cb2)

        sort_layout3 = QtWidgets.QHBoxLayout()
        sort_layout3.addWidget(self.sort_combo3)
        sort_layout3.addWidget(self.order_cb3)

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('Sort Column 1', sort_layout1)
        form_layout.addRow('Sort Column 2', sort_layout2)
        form_layout.addRow('Sort Column 3', sort_layout3)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def populate_sort_combos(self):
        columns = self.input_table.collect_schema().names()
        combos = self.sort_combo1, self.sort_combo2, self.sort_combo3
        orders_checkboxes = self.order_cb1, self.order_cb2, self.order_cb3
        for i, combo in enumerate(combos):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem('')  # Optional blank item (for skipping)
            combo.addItems(columns)
            try:
                saved_column = self.node[ATTR.COLUMNS][i]
                saved_order = self.node[ATTR.ORDERS][i]
                checkbox = orders_checkboxes[i]
            except (TypeError, IndexError):
                pass
            else:
                if saved_column not in columns:
                    combo.addItem(saved_column)
                combo.setCurrentText(saved_column)
                checkbox.setChecked(saved_order)
            combo.blockSignals(False)

    def update_order_settings(self):
        self.node[ATTR.COLUMNS] = [
            self.sort_combo1.currentText() or None,
            self.sort_combo2.currentText() or None,
            self.sort_combo3.currentText() or None,
        ]

        self.node[ATTR.ORDERS] = [
            self.order_cb1.isChecked(),
            self.order_cb2.isChecked(),
            self.order_cb3.isChecked(),
        ]

        self.emit_changed()

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]

        self.name_edit.setText(node[ATTR.NAME])

        self.populate_sort_combos()

        self.blockSignals(False)
