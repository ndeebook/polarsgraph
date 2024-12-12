import os
from datetime import datetime as Datetime

from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt

from polarsgraph.log import logger
from polarsgraph.graph import (
    DISPLAY_CATEGORY, DASHBOARD_CATEGORY,
    create_node, build_node_query, connect_nodes, rename_node,
    set_dirty_recursive, disconnect_plug, get_input_tables)
from polarsgraph.undo import UndoStack
from polarsgraph.qtutils import set_shortcut
from polarsgraph.serialize import serialize_graph, deserialize_graph

from polarsgraph.nodes.base import BaseNode
from polarsgraph.nodeview import NodeView, IN, OUT
from polarsgraph.panel import SettingsWidget
from polarsgraph.display import DisplayWidget

from polarsgraph.nodes.load import LoadNode, LoadSettingsWidget
from polarsgraph.nodes.sort import SortNode, SortSettingsWidget
from polarsgraph.nodes.join import JoinNode, JoinSettingsWidget
from polarsgraph.nodes.group import GroupNode, GroupSettingsWidget
from polarsgraph.nodes.derive import DeriveNode, DeriveSettingsWidget
from polarsgraph.nodes.filter import FilterNode, FilterSettingsWidget
from polarsgraph.nodes.rename import RenameNode, RenameSettingsWidget
from polarsgraph.nodes.reorder import ReorderNode, ReorderSettingsWidget
from polarsgraph.nodes.concatenate import (
    ConcatenateNode, ConcatenateSettingsWidget)

from polarsgraph.nodes.table import (
    TableNode, TableSettingsWidget)
from polarsgraph.nodes.bars import (
    BarsNode, BarsSettingsWidget)
from polarsgraph.nodes.pie import (
    PieNode, PieSettingsWidget)
from polarsgraph.nodes.lines import (
    LinesNode, LinesSettingsWidget)
from polarsgraph.nodes.dashboard import (
    DashboardNode, DashboardSettingsWidget)


types = {
    # Manipulators
    LoadNode.type: {'type': LoadNode, 'widget': LoadSettingsWidget},
    JoinNode.type: {'type': JoinNode, 'widget': JoinSettingsWidget},
    DeriveNode.type: {'type': DeriveNode, 'widget': DeriveSettingsWidget},
    GroupNode.type: {'type': GroupNode, 'widget': GroupSettingsWidget},
    SortNode.type: {'type': SortNode, 'widget': SortSettingsWidget},
    FilterNode.type: {'type': FilterNode, 'widget': FilterSettingsWidget},
    RenameNode.type: {'type': RenameNode, 'widget': RenameSettingsWidget},
    ReorderNode.type: {'type': ReorderNode, 'widget': ReorderSettingsWidget},
    ConcatenateNode.type: {
        'type': ConcatenateNode, 'widget': ConcatenateSettingsWidget},
    # Displays
    BarsNode.type: {'type': BarsNode, 'widget': BarsSettingsWidget},
    PieNode.type: {'type': PieNode, 'widget': PieSettingsWidget},
    LinesNode.type: {'type': LinesNode, 'widget': LinesSettingsWidget},
    TableNode.type: {'type': TableNode, 'widget': TableSettingsWidget},
    # Dashboard
    DashboardNode.type: {
        'type': DashboardNode, 'widget': DashboardSettingsWidget},
}


LOCAL_DIR = os.path.expanduser('~/.polarsgraph')
os.makedirs(LOCAL_DIR, exist_ok=True)
AUTOSAVE_PATH = f'{LOCAL_DIR}/.autosave'

GRAPH_SETTINGS_KEY = '_graph_settings'


class PolarsGraph(QtWidgets.QMainWindow):
    def __init__(self, graph=None, extra_types=None, zoom=1.0, origin=(0, 0)):
        super().__init__()

        icon = QtGui.QIcon(f'{os.path.dirname(__file__)}/polarsgraph.png')
        self.setWindowIcon(icon)

        if extra_types:
            types.update(extra_types)

        self.graph = dict()
        self.undo_stack = UndoStack()
        self.save_path = None
        self.clipboard = None

        self.setMinimumWidth(1000)
        self.setMinimumHeight(500)
        self.setWindowTitle('PolarsGraph')

        # Widgets
        self.display_widget = DisplayWidget(self.graph)
        self.node_view = NodeView(types, self.graph, zoom, origin)
        self.settings_widget = SettingsWidget(types)

        toolbar = QtWidgets.QWidget()
        size = 24
        toolbar.setMaximumHeight(size)
        toolbar_layout = QtWidgets.QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(0)
        self.add_button = QtWidgets.QPushButton(
            '+', clicked=self.show_add_node_menu)
        buttons = self.add_button,
        for button in buttons:
            button.setMaximumWidth(size)
            button.setMaximumHeight(size)
            toolbar_layout.addWidget(button)
        # toolbar_layout.addStretch() would disable node view interactivity
        toolbar.setMaximumWidth(size * len(buttons) + 2)

        # Connections
        self.node_view.nodes_selected.connect(self.set_panel_node)
        self.node_view.plug_changes_requested.connect(self.change_plug)
        self.node_view.create_requested.connect(self.create_node_at)
        self.node_view.delete_requested.connect(self.delete_nodes)
        self.node_view.node_double_clicked.connect(
            self.settings_widget.show_error)

        self.settings_widget.settings_changed.connect(self.set_dirty_recursive)
        self.settings_widget.settings_changed.connect(self.node_view.update)
        self.settings_widget.settings_changed.connect(self.build_node_query)
        self.settings_widget.rename_asked.connect(self.rename_node)

        self.settings_widget.settings_changed.connect(self.autosave)

        # Layout
        graph_widget = QtWidgets.QWidget()
        graph_widget_layout = QtWidgets.QStackedLayout(graph_widget)
        graph_widget_layout.setStackingMode(QtWidgets.QStackedLayout.StackAll)
        graph_widget_layout.setContentsMargins(0, 0, 0, 0)
        graph_widget_layout.addWidget(toolbar)
        graph_widget_layout.addWidget(self.node_view)

        horizontal_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        horizontal_splitter.addWidget(self.display_widget)
        horizontal_splitter.addWidget(graph_widget)
        horizontal_splitter.setSizes([300, 300])
        horizontal_splitter.setHandleWidth(2)
        palette = horizontal_splitter.palette()
        palette.setColor(
            QtGui.QPalette.ColorRole.Window, palette.mid().color())
        horizontal_splitter.setPalette(palette)

        vertical_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        vertical_splitter.addWidget(horizontal_splitter)
        vertical_splitter.addWidget(self.settings_widget)
        vertical_splitter.setSizes([900, 200])
        vertical_splitter.setHandleWidth(2)
        vertical_splitter.setPalette(palette)

        central_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(vertical_splitter)

        self.setCentralWidget(central_widget)

        # Create menu options
        menubar = self.menuBar()
        file_menu = QtWidgets.QMenu('File', self)
        menubar.addMenu(file_menu)
        edit_menu = QtWidgets.QMenu('Edit', self)
        menubar.addMenu(edit_menu)
        menu_cfg = (
            (file_menu, 'Open...', self.prompt_open, 'ctrl+o'),
            (
                file_menu,
                'Import...',
                lambda: self.prompt_open(import_=True),
                None),
            (file_menu, '-----', None, None),
            (file_menu, 'Save', self.save, 'ctrl+s'),
            (file_menu, 'Save as...', self.prompt_save, 'shift+ctrl+s'),
            (
                file_menu,
                'Export selected...',
                lambda: self.prompt_save(selected=True),
                None),
            (edit_menu, 'Copy', self.copy, 'ctrl+c'),
            (edit_menu, 'Paste', self.paste, 'ctrl+v'),
            (file_menu, '-----', None, None),
            (edit_menu, 'Undo', self.undo, 'ctrl+z'),
            (edit_menu, 'Redo', self.redo, 'ctrl+y'),
        )
        for menu, label, func, shortcut_key in menu_cfg:
            if func is None:
                menu.addSeparator()
                continue
            action = QtGui.QAction(label, self)
            action.triggered.connect(func)
            if shortcut_key:
                action.setShortcut(shortcut_key)
            menu.addAction(action)

        # Shortcuts
        set_shortcut('n', self, self.node_view.show_add_node_menu)
        set_shortcut('f', self, self.node_view.frame_all)
        # FIXME: only enable tab shortcut for nodeview
        # set_shortcut('tab', self, self.node_view.show_add_node_menu)
        set_shortcut('delete', self, self.node_view.delete_selected_nodes)
        # set_shortcut('ctrl+z', self, self.undo)
        # set_shortcut('ctrl+y', self, self.redo)
        # set_shortcut('ctrl+shift+z', self, self.redo)
        set_shortcut('1', self, self.connect_to_display)
        set_shortcut('2', self, lambda: self.connect_to_display(1))
        set_shortcut('3', self, lambda: self.connect_to_display(2))
        set_shortcut('4', self, lambda: self.connect_to_display(3))
        set_shortcut('5', self, lambda: self.connect_to_display(4))

        # Load graph
        if graph:
            self.load_graph(graph)
            self.add_undo()
        else:
            self.open_autosave()

    def load_graph(self, graph, add=False, record_undo=True):
        # Remove and handle graph settings stored as dummy node
        if GRAPH_SETTINGS_KEY in graph:
            graph_settings = graph.pop(GRAPH_SETTINGS_KEY)
            self.node_view.zoom = graph_settings.get('zoom')
            self.node_view.origin = graph_settings.get('origin')
            display_node_name = graph_settings.get('current_display')
            if display_node_name:
                self.display_widget.set_display_node(display_node_name)

        # Build graph
        if not add:
            self.graph = dict()
        for name, settings in (graph or dict()).items():
            nodetype = settings['type']
            if nodetype not in types:
                continue
            if add:
                # offset position slightly for paste/import
                p = settings['position']
                p.setX(p.x() + 50)
                p.setY(p.y() + 50)
            self.create_node(
                nodetype, name, settings, auto_increment=add, update=False)

        # Autosave
        self.autosave(record_undo=record_undo)

        # Refresh UI
        self.node_view.set_graph(self.graph)
        self.display_widget.set_graph(self.graph)
        # SettingsWidget:
        if self.settings_widget.node:
            node_name = self.settings_widget.node['name']
            node = self.graph[node_name] if node_name in self.graph else None
            if node:
                self.build_node_query(node_name)  # enable access to schema
            self.set_settings_node(node)
        # Force refresh node view + frame all
        self.node_view.repaint()
        self.node_view.frame_all()

    def set_settings_node(self, node: BaseNode):
        input_tables = []
        if (
            node and
            self.settings_widget.types_widgets[node.type].needs_built_query
        ):
            self.build_node_query(node['name'])
            input_tables = get_input_tables(self.graph, node)
        self.settings_widget.set_node(node, input_tables)

    def set_dirty_recursive(self, node_name: BaseNode):
        set_dirty_recursive(self.graph, node_name)

    def build_node_query(self, node_name):
        build_node_query(self.graph, node_name)
        self.update_view_widget()

    def update_view_widget(self):
        self.display_widget.update_content()

    def create_node(
            self,
            node_type,
            name=None,
            settings=None,
            auto_increment=True,
            update=True):

        node = create_node(
            self.graph,
            types,
            node_type,
            name=name,
            settings=settings,
            auto_increment=auto_increment)

        # Repaint graph
        if update:
            self.node_view.update()
            self.display_widget.update_content()
        # Fill Displays combo
        if node.category in DISPLAY_CATEGORY:
            self.display_widget.fill_combo()

    def create_node_at(self, node_type, position):
        self.create_node(node_type, settings=dict(position=position))
        self.update_view_widget()
        self.autosave()

    def delete_nodes(self, node_names_to_delete):
        # Delete nodes
        for node_name in node_names_to_delete:
            self.graph.pop(node_name)
        # Delete inputs pointing to deleted nodes
        for node in self.graph.values():
            for i, inputs in enumerate(node['inputs'] or []):
                if not inputs:
                    continue
                name = inputs[0]
                if name in node_names_to_delete:
                    node['inputs'][i] = None
        self.node_view.delete_nodes(node_names_to_delete)
        self.update_view_widget()
        self.autosave()

    def change_plug(self, plug1, plug2):
        # Ignore meaningless cases
        if plug1.get('type') == 'node' or plug2.get('type') == 'node':
            return  # Ignore trying to connect to a node
        if plug1.get('side') == plug2.get('side'):
            return  # Ignore trying to connect to same side

        # Define which is plug in which is plug out
        try:
            plug_out = [p for p in (plug1, plug2) if p.get('side') == OUT][0]
        except IndexError:
            plug_out = None
        try:
            plug_in = [p for p in (plug1, plug2) if p.get('side') == IN][0]
        except IndexError:
            plug_in = None

        # Handle cases
        if not plug_out:  # disconnecting plug in
            disconnect_plug(self.graph[plug_in['name']], plug_in['index'])
        elif plug_in:  # connecting two plugs
            target_node_name = plug_in['name']
            target_node = self.graph[target_node_name]
            source_node_name = plug_out['name']
            source_node = self.graph[source_node_name]
            success = connect_nodes(
                self.graph,
                source_node, plug_out['index'],
                target_node, plug_in['index'])
            if not success:
                return
            self.set_dirty_recursive(target_node_name)
        else:
            return

        self.node_view.repaint()
        self.update_view_widget()
        self.set_settings_node(self.settings_widget.node)
        self.autosave()

    def set_panel_node(self, node_names):
        if len(node_names) == 1:
            self.set_settings_node(self.graph[node_names[0]])
        else:
            self.settings_widget.clear()

    # Save/Load
    def serialize_graph(self, selected=False):
        if selected:
            selected_graph = {
                n: self.graph[n] for n in self.node_view.selected_names}
            return serialize_graph(selected_graph)
        # Save graph settings
        settings_node = GraphSettings(settings=dict(
            name=GRAPH_SETTINGS_KEY,
            zoom=round(self.node_view.zoom, 2),
            origin=self.node_view.origin,
            display_node_name=self.display_widget.node_name,
            datetime=Datetime.now().isoformat()))
        return serialize_graph(self.graph, settings_node)

    def save_to_file(self, path, selected=False, set_current=True):
        content = self.serialize_graph(selected=selected)
        with open(path, 'w') as f:
            f.write(content)
        if set_current:
            self.save_path = path

    def save(self):
        self.save_to_file(self.save_path)

    def open_file(self, path, import_=False):
        self.save_path = path
        with open(path, 'r') as f:
            graph = deserialize_graph(f.read())
        self.load_graph(graph, add=import_)

    def prompt_open(self, import_=False):
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open Graph', '', '*.pg')
        if not filepath:
            return
        self.open_file(filepath, import_=import_)

    def prompt_save(self, selected=False):
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Open Graph', '', '*.pg')
        if not filepath:
            return
        self.save_to_file(
            filepath, selected=selected, set_current=not selected)

    # Copy/Paste
    def copy(self):
        self.clipboard = self.serialize_graph(selected=True)

    def paste(self):
        if not self.clipboard:
            return
        self.load_graph(deserialize_graph(self.clipboard), add=True)

    # Autosave
    def autosave(self, record_undo=True):
        logger.debug('autosave')
        self.save_to_file(AUTOSAVE_PATH)
        if record_undo:
            self.add_undo()

    def open_autosave(self):
        if os.path.exists(AUTOSAVE_PATH):
            self.open_file(AUTOSAVE_PATH)

    def closeEvent(self, event):
        self.autosave()
        return super().closeEvent(event)

    # Undo/Redo
    def _undo_redo(self, action='undo'):
        if action == 'undo':
            graph = deserialize_graph(self.undo_stack.undo())
        else:
            graph = deserialize_graph(self.undo_stack.redo())
        if graph:
            self.load_graph(graph, record_undo=False)

    def add_undo(self):
        logger.debug('record undo')
        self.undo_stack.add(self.serialize_graph())

    def undo(self):
        logger.debug('undo')
        self._undo_redo()

    def redo(self):
        logger.debug('redo')
        self._undo_redo('redo')

    # Rename/Add
    def rename_node(self, old_name, new_name):
        rename_node(self.graph, old_name, new_name)
        self.node_view.rename_node(old_name, new_name)
        self.set_settings_node(self.graph[new_name])
        self.display_widget.fill_combo()

    def show_add_node_menu(self):
        position = self.add_button.rect().bottomLeft()
        self.node_view.show_add_node_menu(
            self.node_view.mapToGlobal(position))

    # Connect shortcut
    def connect_to_display(self, display_index=0):
        """Display index is based on their names alphabetical order"""
        display_nodes = [
            n for n in self.graph if
            self.graph[n].category in (DISPLAY_CATEGORY, DASHBOARD_CATEGORY)]
        if len(display_nodes) < display_index + 1:
            return
        display_nodes.sort()  # alphabetical order
        display_node_name = display_nodes[display_index]
        if len(self.node_view.selected_names) == 1:
            selected_node = self.graph[self.node_view.selected_names[0]]
            self.change_plug(
                dict(side=1, name=selected_node['name'], index=0),
                dict(side=0, name=display_node_name, index=0))
        self.display_widget.set_display_node(display_node_name)


class GraphSettings(BaseNode):
    default_color = QtGui.QColor()
    type = 'graph_settings'

    def __init__(self, settings=None):
        super().__init__(settings)
