import polars as pl
from PySide6 import QtWidgets
from PySide6.QtCore import Qt

from polarsgraph.nodes import PINK as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import (
    BaseNode, BaseSettingsWidget, set_combo_values_from_table_columns)
from polarsgraph.nodes.group import (
    DATATYPE_DEFAULT_AGG, DELETE_LABEL, NULL_LABEL, CUSTOM_VALUE_LABEL)


class ATTR:
    NAME = 'name'
    DATE_COLUMN = 'date_column'
    KEY_COLUMN = 'key_column'
    COLUMNS_AGGREGATIONS = 'columns_aggregations'
    CUSTOM_VALUE = 'custom_value'


class DateRangeNode(BaseNode):
    type = 'daterange'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]
        schema = df.collect_schema()

        date_col = self[ATTR.DATE_COLUMN]
        key_col = self[ATTR.KEY_COLUMN]
        custom_value = self[ATTR.CUSTOM_VALUE] or ''

        if not date_col:
            self.tables['table'] = df
            return

        collected = df.collect()
        min_date = collected[date_col].min()
        max_date = collected[date_col].max()

        if min_date is None or max_date is None:
            self.tables['table'] = df
            return

        column_aggregations = self[ATTR.COLUMNS_AGGREGATIONS] or {}
        bool_mean_cols = []
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
                if schema[col_name] == pl.Boolean and agg_name == 'mean':
                    bool_mean_cols.append(col_name)
                agg_expr = getattr(col, agg_name)()
            else:
                continue

            agg_exprs.append(agg_expr)

        # Build full date range
        date_type = schema[date_col]
        if isinstance(date_type, pl.Datetime):
            all_dates = pl.datetime_range(
                min_date, max_date, interval='1d', eager=True)
        else:
            all_dates = pl.date_range(
                min_date, max_date, interval='1d', eager=True)

        # As-of expand: for each date, find each entity's current value
        # (most recent status on or before that date), then aggregate
        dates_df = pl.DataFrame({'__date__': all_dates})
        expanded = dates_df.join(collected, how='cross')
        expanded = expanded.filter(
            pl.col(date_col) <= pl.col('__date__'))

        value_cols = [
            c for c in schema.names()
            if c not in (date_col, key_col)
            and column_aggregations.get(c) != DELETE_LABEL]
        agg_last = [
            pl.col(c).sort_by(date_col).last() for c in value_cols]
        per_entity = (
            expanded.group_by(['__date__', key_col]).agg(agg_last)
            if agg_last
            else expanded.select(['__date__', key_col]).unique())

        if bool_mean_cols:
            per_entity = per_entity.with_columns(
                [pl.col(c).fill_null(False) for c in bool_mean_cols])

        if agg_exprs:
            result = (
                per_entity
                .group_by('__date__')
                .agg(agg_exprs)
                .rename({'__date__': date_col})
                .sort(date_col))
        else:
            result = (
                per_entity.select('__date__').unique()
                .rename({'__date__': date_col})
                .sort(date_col))

        self.tables['table'] = result.lazy()


class DateRangeSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        self.input_table = None

        self.date_column_combo = QtWidgets.QComboBox()
        self.date_column_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.date_column_combo, ATTR.DATE_COLUMN))

        self.key_column_combo = QtWidgets.QComboBox()
        self.key_column_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.key_column_combo, ATTR.KEY_COLUMN))

        self.column_agg_table = QtWidgets.QTableWidget()
        self.column_agg_table.setColumnCount(2)
        self.column_agg_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.Stretch)
        mode = QtWidgets.QAbstractItemView.ScrollPerPixel
        self.column_agg_table.setVerticalScrollMode(mode)
        self.column_agg_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.column_agg_table.setHorizontalHeaderLabels(
            ['Column', 'Aggregation'])

        self.customvalue_edit = QtWidgets.QLineEdit()
        self.customvalue_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(
                self.customvalue_edit, ATTR.CUSTOM_VALUE))

        refresh_button = QtWidgets.QPushButton('Refresh list')
        refresh_button.clicked.connect(self.populate_aggregation_table)

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('Date column', self.date_column_combo)
        form_layout.addRow('Key column', self.key_column_combo)
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

        date_col = node[ATTR.DATE_COLUMN] or ''
        set_combo_values_from_table_columns(
            self.date_column_combo, self.input_table, date_col,
            extra_values=[''])

        key_col = node[ATTR.KEY_COLUMN] or ''
        set_combo_values_from_table_columns(
            self.key_column_combo, self.input_table, key_col,
            extra_values=[''])

        self.customvalue_edit.setText(node[ATTR.CUSTOM_VALUE] or '')

        self.populate_aggregation_table()
        self.blockSignals(False)

    def populate_aggregation_table(self):
        if self.input_table is None:
            columns = {}
        else:
            columns = self.input_table.collect_schema()

        date_col = self.node[ATTR.DATE_COLUMN]
        key_col = self.node[ATTR.KEY_COLUMN]
        agg_columns = {
            c: dt for c, dt in columns.items()
            if c not in (date_col, key_col)}

        self.column_agg_table.blockSignals(True)
        self.column_agg_table.setRowCount(len(agg_columns))

        settings_aggs = self.node[ATTR.COLUMNS_AGGREGATIONS] or {}
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
        self.node[ATTR.COLUMNS_AGGREGATIONS] = columns_aggregations
        self.emit_changed()
