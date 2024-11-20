import polars as pl
from PySide6 import QtGui, QtWidgets
from PySide6.QtCore import Qt

from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import (
    BaseNode, BaseSettingsWidget, set_combo_values)


ALL_ROWS_LABEL = '* aggregate all rows'
DELETE_LABEL = 'delete column'

EMPTY_LABEL = 'empty'
STATS_LABEL = '"STATS"'
LITERAL_VALUES = {
    EMPTY_LABEL: '',
    STATS_LABEL: 'STATS',
}


class ATTR:
    NAME = 'name'
    GROUP_BY = 'group_by'
    COLUMNS_AGGREGATIONS = 'columns_aggregations'
    ROUND = 'round'


class GroupNode(BaseNode):
    type = 'group'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = QtGui.QColor(166, 75, 132)

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]
        schema = df.collect_schema()

        # Group by column(s)
        group_by_column = self[ATTR.GROUP_BY]

        # Prepare aggregation expressions
        agg_exprs = []
        column_aggregations = self[ATTR.COLUMNS_AGGREGATIONS] or {}
        for col_name, agg_name in column_aggregations.items():
            if agg_name == DELETE_LABEL:
                continue
            if col_name == group_by_column:
                continue
            if agg_name in LITERAL_VALUES:
                if schema[col_name] == pl.String:
                    agg_expr = pl.lit(LITERAL_VALUES[agg_name]).alias(col_name)
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
            df = df.group_by(group_by_column).agg(agg_exprs)

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

        self.input_table = []

        # Widgets
        self.group_by_column_combo = QtWidgets.QComboBox()
        self.group_by_column_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.group_by_column_combo, ATTR.GROUP_BY))

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

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('Group by', self.group_by_column_combo)
        form_layout.addRow('Round (number of decimals)', self.round_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self.column_agg_table)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]

        self.name_edit.setText(node[ATTR.NAME])

        group_by = node[ATTR.GROUP_BY] or ALL_ROWS_LABEL
        set_combo_values(
            self.group_by_column_combo, self.input_table, group_by,
            extra_values=[ALL_ROWS_LABEL])

        round_value = node[ATTR.ROUND]
        round_value = '' if round_value is None else str(round_value)
        self.round_edit.setText(round_value)

        self.populate_aggregation_table()

        self.blockSignals(False)

    def populate_aggregation_table(self):
        columns = self.input_table.collect_schema()
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
            agg_combo.currentTextChanged.connect(
                self._handle_aggregations_change)
            agg_combo.addItems([
                'sum', 'mean', 'min', 'max', 'count', 'n_unique',
                DELETE_LABEL, *LITERAL_VALUES])
            if column in settings_aggs:
                agg_combo.setCurrentText(settings_aggs[column])
            else:
                agg_combo.setCurrentText(datatype_default_agg[datatype])
            self.column_agg_table.setCellWidget(i, 1, agg_combo)

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
