import polars as pl
from PySide6 import QtWidgets
from PySide6.QtCore import Qt

from polarsgraph.attrs import ColumnChoiceAttr, StrAttr
from polarsgraph.nodes import PINK as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


ALL_ROWS_LABEL = '* aggregate all rows'
DELETE_LABEL = 'delete column'

EMPTY_LABEL = 'empty'
CUSTOM_VALUE_LABEL = '[custom]'
NULL_LABEL = 'null (no value)'

DATATYPE_DEFAULT_AGG = {
    pl.String: 'n_unique',
    pl.Null: 'min',
    pl.Date: 'min',
    pl.Datetime: 'min',
    pl.UInt32: 'sum',
    pl.Int64: 'sum',
    pl.Float64: 'sum',
    pl.Boolean: 'sum',  # == count True's
}

GROUP_BY = 'group_by'
GROUP_BY2 = 'group_by2'
GROUP_BY3 = 'group_by3'
COLUMNS_AGGREGATIONS = 'columns_aggregations'
ROUND = 'round'
CUSTOM_VALUE = 'custom_value'


class GroupByNode(BaseNode):
    type = 'groupby'
    category = MANIPULATE_CATEGORY
    input_plugs = 'table',
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [
        ColumnChoiceAttr(
            GROUP_BY, label='Group by',
            extra_values=[ALL_ROWS_LABEL]),
        ColumnChoiceAttr(GROUP_BY2, label='', extra_values=['']),
        ColumnChoiceAttr(GROUP_BY3, label='', extra_values=['']),
        StrAttr(CUSTOM_VALUE, label='Custom value'),
    ]

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]
        schema = df.collect_schema()

        # Group by column(s)
        group_by_column = self[GROUP_BY]
        group_by_column2 = self[GROUP_BY2]
        group_by_column3 = self[GROUP_BY3]
        group_by_columns = group_by_column, group_by_column2, group_by_column3
        custom_value = self[CUSTOM_VALUE] or ''

        # Prepare aggregation expressions
        agg_exprs = []
        column_aggregations = self[COLUMNS_AGGREGATIONS] or {}
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
            elif agg_name == NULL_LABEL:
                agg_expr = pl.lit(None).alias(col_name)
            elif agg_name:
                col = pl.col(col_name)
                if agg_name == 'mean':
                    if schema[col_name] == pl.Boolean:
                        df = df.with_columns(
                            col.replace(None, False).name.keep())
                    elif schema[col_name].is_numeric():
                        df = df.with_columns(
                            col.fill_null(0).name.keep())
                agg_expr = getattr(col, agg_name)()
            else:
                # Column not configured, delete it
                continue

            agg_exprs.append(agg_expr)

        # Apply group by and aggregation
        if group_by_column == ALL_ROWS_LABEL:
            df = df.select(agg_exprs)
        else:
            group_by = [gb for gb in group_by_columns if gb]
            df = df.group_by(group_by).agg(agg_exprs)

        # Round
        decimals = self[ROUND]
        if decimals not in (None, ''):
            # Collect schema again because .mean() can turn int/bool into float
            for column, data_type in df.collect_schema().items():
                if data_type not in (pl.Float32, pl.Float64):
                    continue
                df = df.with_columns(
                    pl.col(column).round(decimals).name.keep())

        self.tables['table'] = df


class GroupSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        self.input_table = None

        # ROUND is a special-cased empty-or-int field, kept custom.
        self.round_edit = QtWidgets.QLineEdit()
        self.round_edit.editingFinished.connect(
            lambda: self.line_edit_to_settings(
                self.round_edit, ROUND, int))

        # Dynamic per-column aggregation table.
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

        # Form: name + declarative attrs + custom ROUND row (inserted before
        # CUSTOM_VALUE for visual continuity with the original layout).
        form = QtWidgets.QFormLayout()
        form.addRow('Name', self.name_edit)
        group_by_attr, group_by2_attr, group_by3_attr, custom_value_attr = (
            GroupByNode.attrs)
        for attr in (group_by_attr, group_by2_attr, group_by3_attr):
            label, widget = self.register_attr(attr)
            form.addRow(label, widget)
        form.addRow('Round (number of decimals)', self.round_edit)
        label, custom_value_widget = self.register_attr(custom_value_attr)
        form.addRow(label, custom_value_widget)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(refresh_button)
        layout.addWidget(self.column_agg_table)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]

        self.load_attrs(node, input_tables)

        # ROUND field: None/'' → '' else str
        round_value = node[ROUND]
        round_value = '' if round_value in (None, '') else str(round_value)
        self.round_edit.setText(round_value)

        self.populate_aggregation_table()

        self.blockSignals(False)

    def populate_aggregation_table(self):
        if self.input_table is None:
            columns = {}
        else:
            columns = self.input_table.collect_schema()
        self.column_agg_table.blockSignals(True)
        self.column_agg_table.setRowCount(len(columns))

        settings_aggs = self.node[COLUMNS_AGGREGATIONS] or {}
        for i, (column, datatype) in enumerate(columns.items()):
            # Add column name
            column_item = QtWidgets.QTableWidgetItem(column)
            column_item.setFlags(Qt.ItemIsEnabled)
            self.column_agg_table.setItem(i, 0, column_item)

            # Add aggregation function dropdown
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
            agg_function = None
            if combo:
                agg_function = combo.currentText()
            columns_aggregations[column_name] = agg_function

        self.node[COLUMNS_AGGREGATIONS] = columns_aggregations
        self.emit_changed()
