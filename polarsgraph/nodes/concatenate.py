import polars as pl
from PySide6 import QtWidgets

from polarsgraph.nodes import GRAY as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class ATTR:
    NAME = 'name'
    HOW = 'how'


class ConcatenateNode(BaseNode):
    type = 'concatenate'
    category = MANIPULATE_CATEGORY
    inputs = 'table1', 'table2'
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)
        settings[ATTR.HOW] = settings.get(ATTR.HOW) or 'vertical'

    def _build_query(self, tables):
        df1: pl.LazyFrame = tables[0]
        df2: pl.LazyFrame = tables[1]
        self.tables['table'] = pl.concat([df1, df2], how=self['how'])


class ConcatenateSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.how_combo = QtWidgets.QComboBox()
        self.how_combo.addItems(['vertical', 'horizontal'])
        self.how_combo.currentTextChanged.connect(
            lambda: self.combobox_to_settings(
                self.how_combo, ATTR.HOW))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow('how', self.how_combo)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node

        self.name_edit.setText(node[ATTR.NAME])

        self.how_combo.setCurrentText(node[ATTR.HOW] or 'vertical')

        self.blockSignals(False)
