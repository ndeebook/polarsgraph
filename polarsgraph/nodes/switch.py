from PySide6 import QtWidgets

from polarsgraph.attrs import IntAttr
from polarsgraph.nodes import PURPLE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY, DYNAMIC_PLUG_COUNT
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


WHICH = 'which'


class SwitchNode(BaseNode):
    type = 'switch'
    category = MANIPULATE_CATEGORY
    inputs = DYNAMIC_PLUG_COUNT
    output_plugs = 'table',
    default_color = DEFAULT_COLOR
    attrs = [IntAttr(WHICH, default=1, label='Which', minimum=1)]

    def input_plug_name(self, i):
        return f'{i + 1}'

    def _build_query(self, tables):
        self.tables['table'] = tables[self[WHICH] - 1]


class SwitchSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.build_attr_form(SwitchNode.attrs))

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        # Dynamic max: WHICH is bounded by current input count.
        SwitchNode.attrs[0].widget.setMaximum(len(node['inputs']))
        self.blockSignals(False)
