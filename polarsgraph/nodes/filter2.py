import polars as pl
from PySide6 import QtWidgets

from polarsgraph.nodes import BLUE as DEFAULT_COLOR, OPERATOR_MAGIC_METHODS
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import (
    BaseNode, BaseSettingsWidget, convert_value, convert_values,
    set_combo_values_from_table_columns)


class ATTR:
    NAME = 'name'
    CONDITIONS = 'conditions'
    INVERT = 'invert'


CONDITIONS_LABELS = {
    '==': '==',
    '!=': '!=',
    '>': '>',
    '<': '<',
    '>=': '>=',
    '<=': '<=',
    'is_in': 'in',
    'not_in': 'not in',
    'contains': 'contains',
}
LABELS_CONDITIONS = {label: c for c, label in CONDITIONS_LABELS.items()}
LOGICAL_OPERATORS = 'and', 'or', 'xor'


class Filter2Node(BaseNode):
    type = 'filter2'
    category = MANIPULATE_CATEGORY
    input_plugs = 'table',
    output_plugs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]
        if not self[ATTR.CONDITIONS]:
            return df
        filters = get_filters(df, self[ATTR.CONDITIONS])
        if self[ATTR.INVERT]:
            filters = ~filters.fill_null(False)
        self.tables['table'] = df.filter(filters)


def get_filters(df, conditions):
    """
    Example of conditions:
    [
        ["column_name", "==", 0],
        'and',
        ["column_name2", "!=", "test"],
    ]
    """
    column, condition, value = conditions[0]
    filters = get_filter(df, column, condition, value)
    for i in range(1, len(conditions)):
        if i % 2:
            continue
        column, condition, value = conditions[i]
        logical_operator = conditions[i - 1]
        new_filter = get_filter(df, column, condition, value)
        if logical_operator in ('&', 'and'):
            filters &= new_filter
        elif logical_operator in ('|', 'or'):
            filters |= new_filter
        elif logical_operator in ('^', 'xor'):
            filters ^= new_filter
    return filters


def get_filter(df: pl.LazyFrame, column, condition, value):
    data_type = df.collect_schema()[column]

    if condition in ('is_in', 'not_in'):
        values = [v.strip() for v in value.split(',')]
        values = convert_values(values, data_type)
        exp = pl.col(column).is_in(values)
        if condition == 'not_in':
            exp = ~exp
        return exp

    if condition == 'contains':
        if ',' in value:
            return pl.col(column).str.contains_any(
                [v.strip() for v in value.split(',')])
        else:
            return pl.col(column).str.contains(value)

    value = convert_value(value, data_type)
    # `pl.col(column) == value` is same as `pl.col(column).__eq__(value)`
    magic_method_name = OPERATOR_MAGIC_METHODS[condition]
    operator_method = getattr(pl.col(column), magic_method_name)
    return operator_method(value)


class Filter2SettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        self.input_table: pl.LazyFrame = None

        # Widgets
        self.conditions_table = QtWidgets.QTableWidget()
        self.conditions_table.setColumnCount(5)
        self.conditions_table.setHorizontalHeaderLabels(
            ['Logic', 'Column', 'Condition', 'Value', ''])
        self.conditions_table.verticalHeader().setVisible(False)
        self.conditions_table.verticalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header = self.conditions_table.horizontalHeader()
        header.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)

        self.add_button = QtWidgets.QPushButton('+ Add condition')
        self.add_button.clicked.connect(self._add_condition)

        self.invert_checkbox = QtWidgets.QCheckBox()
        self.invert_checkbox.stateChanged.connect(
            lambda: self.checkbox_to_settings(
                self.invert_checkbox, ATTR.INVERT))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow(ATTR.INVERT.title(), self.invert_checkbox)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self.add_button)
        layout.addWidget(self.conditions_table)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table = input_tables[0]

        self.name_edit.setText(node[ATTR.NAME])
        self._populate(node[ATTR.CONDITIONS] or [])

        self.blockSignals(False)

    def _populate(self, conditions):
        # Flatten [triple, op, triple, op, triple] into per-row tuples
        rows = []
        i = 0
        while i < len(conditions):
            if i == 0:
                col, cond, val = conditions[0]
                rows.append((None, col, cond, val))
                i = 1
            else:
                op = conditions[i]
                col, cond, val = conditions[i + 1]
                rows.append((op, col, cond, val))
                i += 2

        self.conditions_table.setRowCount(len(rows))
        for row_idx, (logic, col, cond, val) in enumerate(rows):
            self._set_row(row_idx, logic, col, cond, val)

    def _set_row(self, row_idx, logic, col, cond, val):
        # Logic (first row stays empty)
        if row_idx == 0:
            self.conditions_table.setCellWidget(
                row_idx, 0, QtWidgets.QWidget())
        else:
            logic_combo = QtWidgets.QComboBox()
            logic_combo.addItems(LOGICAL_OPERATORS)
            if logic in LOGICAL_OPERATORS:
                logic_combo.setCurrentText(logic)
            logic_combo.currentTextChanged.connect(self._emit_changes)
            self.conditions_table.setCellWidget(row_idx, 0, logic_combo)

        # Column
        column_combo = QtWidgets.QComboBox()
        set_combo_values_from_table_columns(
            column_combo, self.input_table, col or '')
        column_combo.currentTextChanged.connect(self._emit_changes)
        self.conditions_table.setCellWidget(row_idx, 1, column_combo)

        # Condition
        condition_combo = QtWidgets.QComboBox()
        condition_combo.addItems(LABELS_CONDITIONS)
        condition_combo.setCurrentText(
            CONDITIONS_LABELS.get(cond or '==', '=='))
        condition_combo.currentTextChanged.connect(self._emit_changes)
        self.conditions_table.setCellWidget(row_idx, 2, condition_combo)

        # Value
        value_edit = QtWidgets.QLineEdit('' if val is None else str(val))
        value_edit.editingFinished.connect(self._emit_changes)
        self.conditions_table.setCellWidget(row_idx, 3, value_edit)

        # Remove button
        remove_button = QtWidgets.QToolButton()
        remove_button.setText('✕')
        remove_button.setToolTip('Remove condition')
        remove_button.clicked.connect(self._remove_row)
        self.conditions_table.setCellWidget(row_idx, 4, remove_button)

    def _add_condition(self):
        row_idx = self.conditions_table.rowCount()
        self.conditions_table.setRowCount(row_idx + 1)
        self._set_row(row_idx, 'and', None, '==', '')
        self._emit_changes()

    def _remove_row(self):
        sender = self.sender()
        for row_idx in range(self.conditions_table.rowCount()):
            if self.conditions_table.cellWidget(row_idx, 4) is sender:
                self.conditions_table.removeRow(row_idx)
                self._emit_changes()
                # Repopulate so the new first row has its logic cell cleared
                self._populate(self.node[ATTR.CONDITIONS] or [])
                return

    def _emit_changes(self):
        conditions = []
        for row_idx in range(self.conditions_table.rowCount()):
            column = self.conditions_table.cellWidget(
                row_idx, 1).currentText()
            condition = LABELS_CONDITIONS[
                self.conditions_table.cellWidget(row_idx, 2).currentText()]
            value = self.conditions_table.cellWidget(row_idx, 3).text()
            if row_idx > 0:
                conditions.append(
                    self.conditions_table.cellWidget(row_idx, 0).currentText())
            conditions.append([column, condition, value])
        self.node[ATTR.CONDITIONS] = conditions
        self.emit_changed()
