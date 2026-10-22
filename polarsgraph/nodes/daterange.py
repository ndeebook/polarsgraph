from datetime import timedelta

import polars as pl
from PySide6 import QtWidgets
from PySide6.QtCore import Qt

from polarsgraph.attrs import ColumnChoiceAttr, StrAttr
from polarsgraph.nodes import PINK as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget
from polarsgraph.nodes.groupby import (
    DATATYPE_DEFAULT_AGG, DELETE_LABEL, NULL_LABEL, CUSTOM_VALUE_LABEL)


DATE_COLUMN = 'date_column'
KEY_COLUMN = 'key_column'
VALUE_COLUMN = 'value_column'
COLUMNS_AGGREGATIONS = 'columns_aggregations'
CUSTOM_VALUE = 'custom_value'


class DateRangeNode(BaseNode):
    type = 'daterange'
    category = MANIPULATE_CATEGORY
    input_plugs = 'table',
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [
        ColumnChoiceAttr(DATE_COLUMN, label='Date column', extra_values=['']),
        ColumnChoiceAttr(KEY_COLUMN, label='Key column', extra_values=['']),
        ColumnChoiceAttr(
            VALUE_COLUMN, label='Value column', extra_values=['']),
        StrAttr(CUSTOM_VALUE, label='Custom value'),
    ]

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]
        schema = df.collect_schema()

        date_col = self[DATE_COLUMN]
        key_col = self[KEY_COLUMN]
        value_col = self[VALUE_COLUMN]
        custom_value = self[CUSTOM_VALUE] or ''

        if not date_col or not value_col:
            self.tables['table'] = df
            return

        collected = df.collect()
        min_date = collected[date_col].min()
        max_date = collected[date_col].max()

        if min_date is None or max_date is None:
            self.tables['table'] = df
            return

        column_aggregations = self[COLUMNS_AGGREGATIONS] or {}
        agg_exprs = []
        for col_name in schema.names():
            if col_name in (date_col, key_col):
                continue
            agg_name = column_aggregations.get(col_name)
            if agg_name == DELETE_LABEL:
                continue

            if agg_name == CUSTOM_VALUE_LABEL:
                if schema[col_name] == pl.String:
                    agg_expr = pl.lit(custom_value).alias(col_name)
                else:
                    agg_expr = pl.lit(0).alias(col_name)
            elif agg_name == NULL_LABEL:
                agg_expr = pl.lit(None).alias(col_name)
            elif agg_name:
                col = pl.col(col_name)
                agg_expr = getattr(col, agg_name)()
            else:
                continue

            agg_exprs.append(agg_expr)

        # Build full date range starting one day before the first change
        min_date -= timedelta(days=1)
        date_type = schema[date_col]
        if isinstance(date_type, pl.Datetime):
            all_dates = pl.datetime_range(
                min_date, max_date, interval='1d', eager=True)
        else:
            all_dates = pl.date_range(
                min_date, max_date, interval='1d', eager=True)
        dates_df = pl.DataFrame({'date': all_dates})

        value_cols = [
            c for c in schema.names()
            if c not in (date_col, key_col)
            and column_aggregations.get(c) != DELETE_LABEL]

        # As-of expand: cross join dates × unique keys so every entity appears
        # on every date (weight=null→0 when no history yet), then join_asof to
        # get the most recent value per (date, key)
        keys_df = collected.select(key_col).unique()
        all_pairs = dates_df.join(keys_df, how='cross').sort('date')
        result = (
            all_pairs
            .join_asof(
                collected.select(
                    [date_col, key_col] + value_cols)
                .sort(date_col),
                left_on='date',
                right_on=date_col,
                by=key_col,
                strategy='backward')
            .with_columns([
                pl.col(c).fill_null(0) for c in value_cols
                if schema[c].is_numeric() or schema[c] == pl.Boolean])
            .group_by('date')
            .agg(pl.col(value_col).mean())
            .sort('date')
        )

        self.tables['table'] = result.lazy()


class DateRangeSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        self.input_table = None

        self.column_agg_table = QtWidgets.QTableWidget()
        self.column_agg_table.setColumnCount(2)
        self.column_agg_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        mode = QtWidgets.QAbstractItemView.ScrollPerPixel
        self.column_agg_table.setVerticalScrollMode(mode)
        self.column_agg_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.column_agg_table.setHorizontalHeaderLabels(
            ['Column', 'Aggregation'])

        refresh_button = QtWidgets.QPushButton('Refresh list')
        refresh_button.clicked.connect(self.populate_aggregation_table)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.build_attr_form(DateRangeNode.attrs))
        layout.addWidget(refresh_button)
        layout.addWidget(self.column_agg_table, stretch=1)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]
        self.load_attrs(node, input_tables)
        self.populate_aggregation_table()
        self.blockSignals(False)

    def populate_aggregation_table(self):
        if self.input_table is None:
            columns = {}
        else:
            columns = self.input_table.collect_schema()

        date_col = self.node[DATE_COLUMN]
        key_col = self.node[KEY_COLUMN]
        agg_columns = {
            c: dt for c, dt in columns.items()
            if c not in (date_col, key_col)}

        self.column_agg_table.blockSignals(True)
        self.column_agg_table.setRowCount(len(agg_columns))

        settings_aggs = self.node[COLUMNS_AGGREGATIONS] or {}
        for i, (column, datatype) in enumerate(agg_columns.items()):
            column_item = QtWidgets.QTableWidgetItem(column)
            column_item.setFlags(Qt.ItemIsEnabled)
            self.column_agg_table.setItem(i, 0, column_item)

            agg_combo = QtWidgets.QComboBox()
            agg_combo.addItems([
                'sum', 'mean', 'min', 'max', 'count', 'n_unique',
                DELETE_LABEL, NULL_LABEL, CUSTOM_VALUE_LABEL])
            if column in settings_aggs:
                agg_combo.setCurrentText(settings_aggs[column])
            else:
                agg_combo.setCurrentText(
                    DATATYPE_DEFAULT_AGG.get(datatype, 'min'))
            agg_combo.currentTextChanged.connect(
                self._handle_aggregations_change)
            self.column_agg_table.setCellWidget(i, 1, agg_combo)

        self.column_agg_table.blockSignals(False)
        if self.input_table is not None:
            self._handle_aggregations_change()

    def _handle_aggregations_change(self):
        columns_aggregations = {}
        for row in range(self.column_agg_table.rowCount()):
            column_item = self.column_agg_table.item(row, 0)
            if not column_item:
                continue
            column_name = column_item.text()
            combo = self.column_agg_table.cellWidget(row, 1)
            if combo:
                columns_aggregations[column_name] = combo.currentText()
        self.node[COLUMNS_AGGREGATIONS] = columns_aggregations
        self.emit_changed()
