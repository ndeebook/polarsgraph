"""
see graph.py > create_node()

Subgraph node uses input_plugs and output_plugs attributes
It also has input_nodes and output_nodes to recall input and output nodes
and in which order they are.

The subgraph can also expose selected child-node attributes on its own
settings panel via `settings['exposed_attrs']` — see ExposedAttrsEditor.
"""

from PySide6 import QtGui, QtWidgets

from polarsgraph.attrs import CompoundAttr, ExposedAttr
from polarsgraph.graph import (
    BaseNode, MANIPULATE_CATEGORY, LOAD_CATEGORY)
from polarsgraph.nodes.base import BaseSettingsWidget


SUBGRAPH_COLOR = QtGui.QColor(80, 40, 120)
INPUT_COLOR = QtGui.QColor(255, 10, 180)
OUTPUT_COLOR = INPUT_COLOR

EXPOSED_ATTRS = 'exposed_attrs'


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
        return self[f'{side}_nodes'] or []

    @property
    def input_plugs(self):
        return self._get_plugs('input')

    @property
    def output_plugs(self):
        return self._get_plugs('output')


def get_subgraph_children(subgraph_node) -> list[BaseNode]:
    """Nodes in the same graph whose parent is this subgraph."""
    return [
        n for n in subgraph_node.graph.values()
        if n['parent'] == subgraph_node['name']]


def is_exposable_attr(attr) -> bool:
    """Compound attrs are not exposable (they own multiple keys)."""
    return (
        not isinstance(attr, CompoundAttr)
        and attr.keys == (attr.key,))


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


class InputSettingsWidget(_NameOnlySettingsWidget):
    pass


class OutputSettingsWidget(_NameOnlySettingsWidget):
    pass


class SubgraphSettingsWidget(BaseSettingsWidget):
    """
    The subgraph settings panel is one shared widget instance (per
    `panel.py`), but each subgraph instance can expose a different set of
    child attributes — so the dynamic form is torn down and rebuilt on
    every `set_node` from `node['exposed_attrs']`.
    """

    def __init__(self):
        super().__init__()
        self.needs_built_query = False

        self.edit_button = QtWidgets.QPushButton('Edit exposed attributes…')
        self.edit_button.clicked.connect(self._open_editor)

        self.dynamic_container = QtWidgets.QWidget()
        self.dynamic_form = QtWidgets.QFormLayout(self.dynamic_container)
        self.dynamic_form.setContentsMargins(0, 0, 0, 0)

        name_form = QtWidgets.QFormLayout()
        name_form.addRow('Name', self.name_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(name_form)
        layout.addWidget(self.dynamic_container)
        layout.addWidget(self.edit_button)
        layout.addStretch()

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node['name'])
        self._rebuild_form()
        self.load_attrs(node, input_tables)
        self.blockSignals(False)

    def _rebuild_form(self):
        # Qt deletes row widgets when removeRow is called.
        while self.dynamic_form.rowCount() > 0:
            self.dynamic_form.removeRow(0)
        self._attrs = []

        if self.node is None or self.node.graph is None:
            return

        for spec in self.node[EXPOSED_ATTRS] or []:
            child_name = spec.get('child')
            attr_key = spec.get('key')
            child = self.node.graph.get(child_name) if child_name else None
            if child is None:
                continue
            inner = next(
                (a for a in child.attrs
                 if a.key == attr_key and is_exposable_attr(a)),
                None)
            if inner is None:
                continue
            exposed = ExposedAttr(child_name, inner)
            label, widget = self.register_attr(exposed)
            self.dynamic_form.addRow(label, widget)

    def _open_editor(self):
        if self.node is None:
            return
        dialog = ExposedAttrsEditor(self.node, parent=self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self.node[EXPOSED_ATTRS] = dialog.selected()
        self._rebuild_form()
        self.load_attrs(self.node, [])
        self.emit_changed(make_dirty=False)


class ExposedAttrsEditor(QtWidgets.QDialog):
    """
    Checkbox-per-attr-per-child picker. Selection is persisted on the
    subgraph as `settings['exposed_attrs'] = [{'child': name, 'key': attr_key}, …]`.
    """

    def __init__(self, subgraph_node, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Expose child attributes')
        self.resize(420, 520)
        self.subgraph = subgraph_node

        current = {
            (s.get('child'), s.get('key'))
            for s in (subgraph_node[EXPOSED_ATTRS] or [])}

        # Preserve insertion order (dict); also drives output order.
        self.checkboxes: dict = {}

        content = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content)

        children = get_subgraph_children(subgraph_node)
        rendered = 0
        for child in children:
            attrs = [a for a in child.attrs if is_exposable_attr(a)]
            if not attrs:
                continue
            rendered += 1
            group = QtWidgets.QGroupBox(f'{child["name"]} ({child.type})')
            group_layout = QtWidgets.QVBoxLayout(group)
            for attr in attrs:
                cb = QtWidgets.QCheckBox(attr.label)
                if (child['name'], attr.key) in current:
                    cb.setChecked(True)
                self.checkboxes[(child['name'], attr.key)] = cb
                group_layout.addWidget(cb)
            content_layout.addWidget(group)

        if rendered == 0:
            content_layout.addWidget(QtWidgets.QLabel(
                '(No child nodes with exposable attributes.)'))

        content_layout.addStretch()

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addWidget(buttons)

    def selected(self):
        return [
            {'child': child, 'key': key}
            for (child, key), cb in self.checkboxes.items()
            if cb.isChecked()]
