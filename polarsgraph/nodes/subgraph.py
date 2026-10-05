from PySide6 import QtGui, QtWidgets

from polarsgraph.graph import (
    BaseNode, MANIPULATE_CATEGORY, LOAD_CATEGORY, DYNAMIC_PLUG_COUNT)
from polarsgraph.nodes.base import BaseSettingsWidget


SUBGRAPH_COLOR = QtGui.QColor(80, 40, 120)
INPUT_COLOR = QtGui.QColor(77, 77, 77)
OUTPUT_COLOR = QtGui.QColor(77, 77, 77)


class InputNode(BaseNode):
    type = 'input'
    category = LOAD_CATEGORY
    inputs = None
    outputs = ('table',)
    default_color = INPUT_COLOR

    def _build_query(self, tables):
        pass


class OutputNode(BaseNode):
    type = 'output'
    category = MANIPULATE_CATEGORY
    inputs = ('table',)
    outputs = None
    default_color = OUTPUT_COLOR

    def _build_query(self, tables):
        pass


class SubgraphNode(BaseNode):
    type = 'subgraph'
    category = MANIPULATE_CATEGORY
    default_color = SUBGRAPH_COLOR
    inputs_prefix = 'input'
    outputs_prefix = 'output'

    def _build_query(self, tables):
        pass

    def input_plug_name(self, i):
        return f'{self.inputs_prefix}{i + 1}'

    def output_plug_name(self, i):
        return f'{self.outputs_prefix}{i + 1}'


class _NameOnlySettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        self.needs_built_query = False
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.name_edit)
        layout.addStretch()

    def set_node(self, node, input_tables):
        self.node = node
        self.name_edit.setText(node['name'])


class SubgraphSettingsWidget(_NameOnlySettingsWidget):
    pass


class InputSettingsWidget(_NameOnlySettingsWidget):
    pass


class OutputSettingsWidget(_NameOnlySettingsWidget):
    pass
