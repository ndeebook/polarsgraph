import polars as pl
from PySide6 import QtWidgets

from polarsgraph.nodes import PURPLE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY, DYNAMIC_PLUG_COUNT
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class ATTR:
    NAME = 'name'
    WHICH = 'which'


class SwitchNode(BaseNode):
    type = 'switch'
    category = MANIPULATE_CATEGORY
    inputs = DYNAMIC_PLUG_COUNT
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        settings[ATTR.WHICH] = settings.get(ATTR.WHICH) or 1
        super().__init__(settings)

    def plug_name(self, i):
        return f'{i + 1}'

    def _build_query(self, tables):
        self.tables['table'] = tables[self[ATTR.WHICH] - 1]


class SwitchSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.value_edit = QtWidgets.QSpinBox()
        self.value_edit.setMinimum(1)
        self.value_edit.valueChanged.connect(
            lambda: self.spinbox_to_settings(self.value_edit, ATTR.WHICH))

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow(ATTR.WHICH.title(), self.value_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]

        self.name_edit.setText(node[ATTR.NAME])
        self.value_edit.setValue(node[ATTR.WHICH] or 1)
        self.value_edit.setMaximum(len(node['inputs']))

        self.blockSignals(False)
