"""
see graph.py > create_node()

Subgraph node uses input_plugs and output_plugs attributes
It also has input_nodes and output_nodes to recall input and output nodes
and in which order they are.
"""

from PySide6 import QtGui, QtWidgets

from polarsgraph.graph import (
    BaseNode, MANIPULATE_CATEGORY, LOAD_CATEGORY)
from polarsgraph.nodes.base import BaseSettingsWidget


SUBGRAPH_COLOR = QtGui.QColor(80, 40, 120)
INPUT_COLOR = QtGui.QColor(77, 77, 77)
OUTPUT_COLOR = QtGui.QColor(77, 77, 77)


class InputNode(BaseNode):
    type = 'input'
    category = LOAD_CATEGORY
    input_plugs = None
    output_plugs = ('table',)
    default_color = INPUT_COLOR

    def _build_query(self, tables):
        pass


class OutputNode(BaseNode):
    type = 'output'
    category = MANIPULATE_CATEGORY
    input_plugs = ('table',)
    output_plugs = None
    default_color = OUTPUT_COLOR

    def _build_query(self, tables):
        pass


class SubgraphNode(BaseNode):
    type = 'subgraph'
    category = MANIPULATE_CATEGORY
    default_color = SUBGRAPH_COLOR

    def _build_query(self, tables):
        pass

    def record_new_plug(self, plug_node_type, node_name):
        """
        When an output/input node is created, record it on the parent subgraph
        => used by create_node()
        """
        attribute_name = f'{plug_node_type}_nodes'
        try:
            self[attribute_name].append(node_name)
        except AttributeError:
            self[attribute_name] = [node_name]

        # Also create the empty input slot
        if plug_node_type == 'input':
            self['inputs'] = (self['inputs'] or []) + [None]

    def remove_plug(self, plug_node_type, node_name):
        plug_nodes = self[f'{plug_node_type}_nodes']
        index = plug_nodes.index(node_name)
        plug_nodes.remove(node_name)
        if plug_node_type == 'input':
            self['inputs'].pop(index)

    def rename_plug(self, plug_node_type, old_name, new_name):
        plug_nodes = self[f'{plug_node_type}_nodes']
        index = plug_nodes.index(old_name)
        plug_nodes[index] = new_name

    def _get_plugs(self, side):
        """side: input or output"""
        # return [
        #     f'{side}{i + 1}'
        #     for i, _ in enumerate(self[f'{side}_nodes'] or [])]
        return self[f'{side}_nodes'] or []

    def get_input_plugs(self):
        return self._get_plugs('input')

    def get_outpout_plugs(self):
        return self._get_plugs('output')


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
