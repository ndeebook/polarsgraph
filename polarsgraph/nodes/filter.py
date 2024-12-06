import polars as pl
from PySide6 import QtWidgets

from polarsgraph.nodes import BLUE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import (
    BaseNode, BaseSettingsWidget, convert_value, convert_values,
    set_combo_values)


class ATTR:
    NAME = 'name'
    COLUMN = 'column'
    CONDITION = 'condition'
    VALUE = 'value'


CONDITIONS_LABELS = {
    '==': 'equal',
    '!=': 'not equal',
    '>': 'greater than',
    '<': 'smaller than',
    'is_in': 'is in',
    'not_in': 'is not in',
}
LABELS_CONDITIONS = {label: c for c, label in CONDITIONS_LABELS.items()}


class FilterNode(BaseNode):
    type = 'filter'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        settings[ATTR.CONDITION] = settings.get(ATTR.CONDITION) or '=='
        super().__init__(settings)

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]

        condition = self[ATTR.CONDITION]
        column = self[ATTR.COLUMN]
        value = self[ATTR.VALUE]
        data_type = df.collect_schema()[column]

        if condition == '==':
            df = df.filter(pl.col(column) == convert_value(value, data_type))
        elif condition == '!=':
            df = df.filter(pl.col(column) != convert_value(value, data_type))
        elif condition == '>':
            df = df.filter(pl.col(column) > convert_value(value, data_type))
        elif condition == '<':
            df = df.filter(pl.col(column) < convert_value(value, data_type))
        elif condition in ('is_in', 'not_in'):
            values = [v.strip() for v in value.split(',')]
            values = convert_values(values, data_type)
            exp = pl.col(column).is_in(values)
            if condition == 'not_in':
                exp = ~exp
            df = df.filter(exp)

        self.tables['table'] = df


class FilterSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.column_combo = QtWidgets.QComboBox()
        self.column_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(self.column_combo, ATTR.COLUMN))

        self.condition_combo = QtWidgets.QComboBox()
        self.condition_combo.addItems(LABELS_CONDITIONS)
        self.condition_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.condition_combo, ATTR.CONDITION,
                mapper=LABELS_CONDITIONS))

        self.value_edit = QtWidgets.QLineEdit()
        self.value_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(
                self.value_edit, ATTR.VALUE))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow(ATTR.COLUMN.title(), self.column_combo)
        form_layout.addRow(ATTR.CONDITION.title(), self.condition_combo)
        form_layout.addRow(ATTR.VALUE.title(), self.value_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]

        self.name_edit.setText(node[ATTR.NAME])

        condition = node[ATTR.CONDITION] or list(CONDITIONS_LABELS)[0]
        label = CONDITIONS_LABELS[condition]
        self.condition_combo.setCurrentText(label)

        set_combo_values(
            self.column_combo, self.input_table, node[ATTR.COLUMN])

        self.value_edit.setText(node[ATTR.VALUE] or '')

        self.blockSignals(False)
