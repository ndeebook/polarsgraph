from PySide6 import QtWidgets, QtCore

from polarsgraph.attrs import ColorAttr, IntAttr, TextAttr
from polarsgraph.nodes import LIGHT_GRAY
from polarsgraph.graph import BACKDROP_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


WIDTH = 'width'
HEIGHT = 'height'
COLOR = 'color'
TEXT = 'text'
TEXT_SIZE = 'text_size'


class BackdropNode(BaseNode):
    type = 'backdrop'
    category = BACKDROP_CATEGORY
    default_color = LIGHT_GRAY
    attrs = [
        ColorAttr(COLOR, default=LIGHT_GRAY),
        TextAttr(TEXT, label='Text'),
        IntAttr(TEXT_SIZE, default=20, label='Font size', maximum=999),
        # width/height are set by wrap_around_nodes, not shown in the form
        # but we still want sensible defaults applied at construction.
        IntAttr(WIDTH, default=200),
        IntAttr(HEIGHT, default=100),
    ]

    def wrap_around_nodes(self, nodes: list[BaseNode]):
        nodes = [n for n in nodes if not n.type == 'backdrop']
        positions = [n['position'] for n in nodes]
        if not positions:
            return

        margin = 60
        min_x = min(p.x() for p in positions) - margin
        max_x = max(p.x() for p in positions) + 128 + margin
        min_y = min(p.y() for p in positions) - margin * 2
        max_y = max(p.y() for p in positions) + 128 + margin / 2

        self['position'] = QtCore.QPointF(min_x, min_y)
        self[WIDTH] = max_x - min_x
        self[HEIGHT] = max_y - min_y

    def _build_query(self, tables):
        return


# The width/height attrs are not shown in the settings form.
_FORM_ATTRS = BackdropNode.attrs[:3]


class BackdropSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(self.build_attr_form(_FORM_ATTRS))

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.load_attrs(node, input_tables)
        self.blockSignals(False)
