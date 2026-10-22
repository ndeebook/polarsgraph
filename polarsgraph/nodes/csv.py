import io

from PySide6 import QtWidgets
import polars as pl

from polarsgraph.attrs import StrAttr, TextAttr
from polarsgraph.nodes import BLACK as DEFAULT_COLOR
from polarsgraph.graph import LOAD_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


DATA = 'data'
CSV_SEPARATOR = 'csv_separator'
PREFIX = 'columns_prefix'


class CsvNode(BaseNode):
    type = 'csv'
    category = LOAD_CATEGORY
    inputs = None
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [
        StrAttr(CSV_SEPARATOR, default=',', label='CSV Separator'),
        StrAttr(PREFIX, label='Columns prefix'),
        TextAttr(DATA, label='CSV Data', placeholder='Paste CSV data here...'),
    ]

    def _build_query(self, _):
        data = self[DATA]
        if not data:
            raise ValueError('Please enter some CSV data')

        table: pl.DataFrame = pl.read_csv(
            io.StringIO(data),
            separator=self[CSV_SEPARATOR] or ',',
        )

        prefix = self[PREFIX]
        if prefix:
            table = table.rename({c: f'{prefix}{c}' for c in table.columns})

        self.tables[self.output_plugs[0]] = table.lazy()


class CsvSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        separator_attr, prefix_attr, data_attr = CsvNode.attrs

        form = QtWidgets.QFormLayout()
        form.addRow('Name', self.name_edit)
        for attr in (separator_attr, prefix_attr):
            label, widget = self.register_attr(attr)
            form.addRow(label, widget)

        _, data_widget = self.register_attr(data_attr)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(QtWidgets.QLabel('CSV Data'))
        layout.addWidget(data_widget)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.blockSignals(False)
