import polars as pl
from PySide6 import QtWidgets

from polarsgraph.nodes import BLUE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.attrs import CompoundAttr
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


COLUMNS_KEY = 'columns'
ORDERS_KEY = 'orders'
SORT_SLOTS = 3


class SortRowsAttr(CompoundAttr):
    """
    N (column, ascending) pairs: one combobox + one 'Ascending' checkbox per
    row. Owns both the COLUMNS and ORDERS keys on the node.
    """

    def __init__(
            self, columns_key=COLUMNS_KEY, orders_key=ORDERS_KEY,
            n=SORT_SLOTS, label='Sort by'):
        super().__init__(keys=(columns_key, orders_key), label=label)
        self.columns_key = columns_key
        self.orders_key = orders_key
        self.n = n
        self.combos: list[QtWidgets.QComboBox] = []
        self.checkboxes: list[QtWidgets.QCheckBox] = []

    def default_values(self):
        return {self.orders_key: [True] * self.n}

    def _make_widget(self, _):
        container = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        for _ in range(self.n):
            row = QtWidgets.QHBoxLayout()
            combo = QtWidgets.QComboBox()
            cb = QtWidgets.QCheckBox('Ascending')
            cb.setChecked(True)
            row.addWidget(combo, 1)
            row.addWidget(cb)
            v.addLayout(row)
            self.combos.append(combo)
            self.checkboxes.append(cb)
        return container

    def _connect(self, sw):
        for combo in self.combos:
            combo.currentTextChanged.connect(lambda *_: self._write(sw))
        for cb in self.checkboxes:
            cb.stateChanged.connect(lambda *_: self._write(sw))

    def _write(self, sw):
        sw.node[self.columns_key] = [
            c.currentText() or None for c in self.combos]
        sw.node[self.orders_key] = [cb.isChecked() for cb in self.checkboxes]
        sw.emit_changed()

    def load(self, _sw, node, input_tables):
        df = input_tables[0] if input_tables else None
        try:
            columns = df.collect_schema().names()
        except AttributeError:
            columns = []
        saved_cols = node[self.columns_key] or []
        saved_orders = node[self.orders_key] or []
        for i, (combo, cb) in enumerate(zip(self.combos, self.checkboxes)):
            combo.blockSignals(True)
            cb.blockSignals(True)
            combo.clear()
            combo.addItem('')
            combo.addItems(columns)
            try:
                saved_col = saved_cols[i]
            except IndexError:
                saved_col = None
            if saved_col and saved_col not in columns:
                combo.addItem(saved_col)
            combo.setCurrentText(saved_col or '')
            try:
                cb.setChecked(bool(saved_orders[i]))
            except IndexError:
                cb.setChecked(True)
            combo.blockSignals(False)
            cb.blockSignals(False)


class SortNode(BaseNode):
    type = 'sort'
    category = MANIPULATE_CATEGORY
    input_plugs = 'table',
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [SortRowsAttr()]

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]

        sort_columns = self[COLUMNS_KEY] or []
        sort_columns = [col for col in sort_columns if col]
        if sort_columns:
            sort_order = self[ORDERS_KEY][:len(sort_columns)]
            df = df.sort(
                by=sort_columns, descending=[not asc for asc in sort_order])

        self.tables['table'] = df

    def sort_by(self, col_to_sort):
        columns = list(self[COLUMNS_KEY] or [])
        orders = list(self[ORDERS_KEY] or [])
        while len(columns) < SORT_SLOTS:
            columns.append(None)
        while len(orders) < SORT_SLOTS:
            orders.append(True)

        c1, c2, _ = columns
        o1, o2, o3 = orders

        # Just reverse order if already primary sort column
        if c1 == col_to_sort:
            self[COLUMNS_KEY] = columns
            self[ORDERS_KEY] = [not o1, o2, o3]
            return

        # Column not in list: shift existing down, put new column first
        if col_to_sort not in columns:
            self[COLUMNS_KEY] = [col_to_sort, c1, c2]
            self[ORDERS_KEY] = [True, o1, o2]
            return

        # Column already in list: move it to first position
        index = columns.index(col_to_sort)
        columns.insert(0, columns.pop(index))
        orders.insert(0, orders.pop(index))
        self[COLUMNS_KEY] = columns
        self[ORDERS_KEY] = orders


class SortSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        form_layout = self.build_attr_form(SortNode.attrs)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.blockSignals(False)
