import polars as pl
from PySide6 import QtWidgets
from PySide6.QtCore import Qt

from polarsgraph.nodes import PINK as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import (
    BaseNode, BaseSettingsWidget, set_combo_values_from_table_columns)


ALL_ROWS_LABEL = '* aggregate all rows'
DELETE_LABEL = 'delete column'

EMPTY_LABEL = 'empty'
CUSTOM_VALUE_LABEL = '[custom]'


class ATTR:
    NAME = 'name'
    GROUP_BY = 'group_by'
    GROUP_BY2 = 'group_by2'
    GROUP_BY3 = 'group_by3'
    COLUMNS_AGGREGATIONS = 'columns_aggregations'
    ROUND = 'round'
    CUSTOM_VALUE = 'custom_value'


class GroupNode(BaseNode):
    type = 'group'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]
        schema = df.collect_schema()

        # Group by column(s)
        group_by_column = self[ATTR.GROUP_BY]
        group_by_column2 = self[ATTR.GROUP_BY2]
        group_by_column3 = self[ATTR.GROUP_BY3]
        group_by_columns = group_by_column, group_by_column2, group_by_column3
        custom_value = self[ATTR.CUSTOM_VALUE] or ''

        # Prepare aggregation expressions
        agg_exprs = []
        column_aggregations = self[ATTR.COLUMNS_AGGREGATIONS] or {}
        for col_name in schema.names():
            agg_name = column_aggregations.get(col_name)
            if agg_name == DELETE_LABEL:
                continue
            if col_name in group_by_columns:
                continue
            if agg_name == CUSTOM_VALUE_LABEL:
                if schema[col_name] == pl.String:
                    agg_expr = pl.lit(custom_value).alias(col_name)
                else:
                    agg_expr = pl.lit(0).alias(col_name)
            elif agg_name:
                agg_expr = getattr(pl.col(col_name), agg_name)()
            else:
                agg_expr = None
            agg_exprs.append(agg_expr)

        # Apply group by and aggregation
        if group_by_column == ALL_ROWS_LABEL:
            df = df.select(agg_exprs)
        else:
            group_by = [gb for gb in group_by_columns if gb]
            df = df.group_by(group_by).agg(agg_exprs)

        # Round
        decimals = self[ATTR.ROUND]
        if decimals not in (None, ''):
            for column, data_type in schema.items():
                if data_type not in (pl.Float32, pl.Float64):
                    continue
                df = df.with_columns(
                    pl.col(column).round(decimals).name.keep())

        self.tables['table'] = df


class GroupSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        self.input_table = None

        # Widgets
        self.group_by_column_combo = QtWidgets.QComboBox()
        self.group_by_column_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.group_by_column_combo, ATTR.GROUP_BY))
        self.group_by_column_combo2 = QtWidgets.QComboBox()
        self.group_by_column_combo2.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.group_by_column_combo2, ATTR.GROUP_BY2))
        self.group_by_column_combo3 = QtWidgets.QComboBox()
        self.group_by_column_combo3.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.group_by_column_combo3, ATTR.GROUP_BY3))

        # Table for column aggregation functions
        self.column_agg_table = QtWidgets.QTableWidget()
        self.column_agg_table.setColumnCount(2)
        self.column_agg_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        mode = QtWidgets.QAbstractItemView.ScrollPerPixel
        self.column_agg_table.setVerticalScrollMode(mode)
        self.column_agg_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOn)
        self.column_agg_table.setHorizontalHeaderLabels(
            ['Column', 'Aggregation'])

        self.round_edit = QtWidgets.QLineEdit()
        self.round_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(
                self.round_edit, ATTR.ROUND, int))

        self.customvalue_edit = QtWidgets.QLineEdit()
        self.customvalue_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(
                self.customvalue_edit, ATTR.CUSTOM_VALUE))

        refresh_button = QtWidgets.QPushButton('Refresh list')
        refresh_button.clicked.connect(self.populate_aggregation_table)

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('Group by', self.group_by_column_combo)
        form_layout.addRow('', self.group_by_column_combo2)
        form_layout.addRow('', self.group_by_column_combo3)
        form_layout.addRow('Round (number of decimals)', self.round_edit)
        form_layout.addRow('Custom value', self.customvalue_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(refresh_button)
        layout.addWidget(self.column_agg_table)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]

        self.name_edit.setText(node[ATTR.NAME])

        group_by = node[ATTR.GROUP_BY] or ALL_ROWS_LABEL
        group_by2 = node[ATTR.GROUP_BY2] or ''
        group_by3 = node[ATTR.GROUP_BY3] or ''
        set_combo_values_from_table_columns(
            self.group_by_column_combo, self.input_table, group_by,
            extra_values=[ALL_ROWS_LABEL])
        set_combo_values_from_table_columns(
            self.group_by_column_combo2, self.input_table, group_by2,
            extra_values=[''])
        set_combo_values_from_table_columns(
            self.group_by_column_combo3, self.input_table, group_by3,
            extra_values=[''])

        round_value = node[ATTR.ROUND]
        round_value = '' if round_value is None else str(round_value)
        self.round_edit.setText(round_value)

        self.customvalue_edit.setText(node[ATTR.CUSTOM_VALUE] or '')

        self.populate_aggregation_table()

        self.blockSignals(False)

    def populate_aggregation_table(self):
        columns = self.input_table.collect_schema()
        self.column_agg_table.blockSignals(True)
        self.column_agg_table.setRowCount(len(columns))

        datatype_default_agg = {
            pl.String: 'n_unique',
            pl.Null: 'min',
            pl.Date: 'min',
            pl.UInt32: 'sum',
            pl.Int64: 'sum',
            pl.Float64: 'sum',
            pl.Boolean: 'sum',  # == count True's
        }
        settings_aggs = self.node[ATTR.COLUMNS_AGGREGATIONS] or {}
        for i, (column, datatype) in enumerate(columns.items()):
            # Add column name
            column_item = QtWidgets.QTableWidgetItem(column)
            column_item.setFlags(Qt.ItemIsEnabled)
            self.column_agg_table.setItem(i, 0, column_item)

            # Add aggregation function dropdown
            agg_combo = QtWidgets.QComboBox()
            agg_combo.addItems([
                'sum', 'mean', 'min', 'max', 'count', 'n_unique',
                DELETE_LABEL, CUSTOM_VALUE_LABEL])
            if column in settings_aggs:
                agg_combo.setCurrentText(settings_aggs[column])
            else:
                agg_combo.setCurrentText(datatype_default_agg[datatype])
            agg_combo.currentTextChanged.connect(
                self._handle_aggregations_change)
            self.column_agg_table.setCellWidget(i, 1, agg_combo)
        self.column_agg_table.blockSignals(False)

    def _handle_aggregations_change(self):
        columns_aggregations = {}
        for row in range(self.column_agg_table.rowCount()):
            column_item = self.column_agg_table.item(row, 0)
            if not column_item:
                continue
            column_name = column_item.text()
            combo = self.column_agg_table.cellWidget(row, 1)
            agg_function = None
            if combo:
                agg_function = combo.currentText()
            columns_aggregations[column_name] = agg_function

        self.node[ATTR.COLUMNS_AGGREGATIONS] = columns_aggregations
        self.emit_changed()
