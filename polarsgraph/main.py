import os
import uuid
import json
import traceback
from datetime import datetime as Datetime
from functools import partial

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
from polarsgraph.display import DisplayWidget, get_displays_by_index

from polarsgraph.nodes.dot import DotNode, DotSettingsWidget
from polarsgraph.nodes.load import LoadNode, LoadSettingsWidget
from polarsgraph.nodes.sort import SortNode, SortSettingsWidget
from polarsgraph.nodes.join import JoinNode, JoinSettingsWidget
from polarsgraph.nodes.group import GroupNode, GroupSettingsWidget
from polarsgraph.nodes.pivot import PivotNode, PivotSettingsWidget
from polarsgraph.nodes.derive import DeriveNode, DeriveSettingsWidget
from polarsgraph.nodes.filter import FilterNode, FilterSettingsWidget
from polarsgraph.nodes.format import FormatNode, FormatSettingsWidget
from polarsgraph.nodes.rename import RenameNode, RenameSettingsWidget
from polarsgraph.nodes.switch import SwitchNode, SwitchSettingsWidget
from polarsgraph.nodes.reorder import ReorderNode, ReorderSettingsWidget
from polarsgraph.nodes.backdrop import BackdropNode, BackdropSettingsWidget
from polarsgraph.nodes.constant import (
    ConstantNode, ConstantSettingsWidget)
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
from polarsgraph.nodes.label import (
    LabelNode, LabelSettingsWidget)
from polarsgraph.nodes.dashboard import (
    DashboardNode, DashboardSettingsWidget)


types = {
    LoadNode.type: {'type': LoadNode, 'widget': LoadSettingsWidget},
    # Manipulators
    SortNode.type: {'type': SortNode, 'widget': SortSettingsWidget},
    JoinNode.type: {'type': JoinNode, 'widget': JoinSettingsWidget},
    PivotNode.type: {'type': PivotNode, 'widget': PivotSettingsWidget},
    GroupNode.type: {'type': GroupNode, 'widget': GroupSettingsWidget},
    DeriveNode.type: {'type': DeriveNode, 'widget': DeriveSettingsWidget},
    FilterNode.type: {'type': FilterNode, 'widget': FilterSettingsWidget},
    FormatNode.type: {'type': FormatNode, 'widget': FormatSettingsWidget},
    RenameNode.type: {'type': RenameNode, 'widget': RenameSettingsWidget},
    ReorderNode.type: {'type': ReorderNode, 'widget': ReorderSettingsWidget},
    SwitchNode.type: {'type': SwitchNode, 'widget': SwitchSettingsWidget},
    ConcatenateNode.type: {
        'type': ConcatenateNode, 'widget': ConcatenateSettingsWidget},
    ConstantNode.type: {
        'type': ConstantNode, 'widget': ConstantSettingsWidget},
    # Displays
    PieNode.type: {'type': PieNode, 'widget': PieSettingsWidget},
    BarsNode.type: {'type': BarsNode, 'widget': BarsSettingsWidget},
    LabelNode.type: {'type': LabelNode, 'widget': LabelSettingsWidget},
    LinesNode.type: {'type': LinesNode, 'widget': LinesSettingsWidget},
    TableNode.type: {'type': TableNode, 'widget': TableSettingsWidget},
    # Dashboard
    DashboardNode.type: {
        'type': DashboardNode, 'widget': DashboardSettingsWidget},
    # Backdrop
    BackdropNode.type: {
        'type': BackdropNode, 'widget': BackdropSettingsWidget},
    # Dot
    DotNode.type: {'type': DotNode, 'widget': DotSettingsWidget},
}


LOCAL_DIR = os.path.expanduser('~/.polarsgraph')
os.makedirs(LOCAL_DIR, exist_ok=True)
DEFAULT_AUTOSAVE_PATH = f'{LOCAL_DIR}/.autosave.pg'
PREFS_PATH = f'{LOCAL_DIR}/.prefs'
RECENTS_PREF = 'recents'

GRAPH_SETTINGS_KEY = '_graph_settings'
TITLE = 'PolarsGraph'
CLIPBOARD_PREFIX = '# PolarsGraph clipboard\n'


class PolarsGraph(QtWidgets.QMainWindow):
    def __init__(self, graph=None, extra_types=None, zoom=1.0, origin=(0, 0)):
        super().__init__()

        icon = QtGui.QIcon(f'{os.path.dirname(__file__)}/polarsgraph.png')
        self.setWindowIcon(icon)

        if extra_types:
            types.update(extra_types)

        self.graph = dict()
        self.undo_stack = UndoStack()
        self._save_path = None
        self.autosave_path = DEFAULT_AUTOSAVE_PATH

        self.shortcuts_list = []

        self.setMinimumWidth(1000)
        self.setMinimumHeight(500)
        self.setWindowTitle(TITLE)

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
        self.align_horizontal_button = QtWidgets.QPushButton(
            '―', clicked=lambda: self.align(axis='horizontal'))
        self.align_vertical_button = QtWidgets.QPushButton(
            '|', clicked=lambda: self.align(axis='vertical'))
        buttons = (
            self.add_button,
            self.align_horizontal_button,
            self.align_vertical_button,
        )
        for button in buttons:
            button.setMaximumWidth(size)
            button.setMaximumHeight(size)
            toolbar_layout.addWidget(button)
        # toolbar_layout.addStretch() would disable node view interactivity
        toolbar.setMaximumWidth(size * len(buttons) + 2)

        # Connections
        self.node_view.nodes_selected.connect(self.set_panel_node)
        self.node_view.plug_changes_requested.connect(self.change_plug)
        self.node_view.create_requested.connect(self.create_node)
        self.node_view.create_load_requested.connect(self.create_load)
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

        self.horizontal_splitter = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        self.horizontal_splitter.addWidget(self.display_widget)
        self.horizontal_splitter.addWidget(graph_widget)
        self.horizontal_splitter.setSizes([300, 300])
        self.horizontal_splitter.setHandleWidth(2)
        palette = self.horizontal_splitter.palette()
        palette.setColor(
            QtGui.QPalette.ColorRole.Window, palette.mid().color())
        self.horizontal_splitter.setPalette(palette)

        self.vertical_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        self.vertical_splitter.addWidget(self.horizontal_splitter)
        self.vertical_splitter.addWidget(self.settings_widget)
        self.vertical_splitter.setSizes([900, 200])
        self.vertical_splitter.setHandleWidth(2)
        self.vertical_splitter.setPalette(palette)

        central_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.vertical_splitter)

        self.setCentralWidget(central_widget)

        # Create menu options
        menubar = self.menuBar()

        file_menu = QtWidgets.QMenu('File', self)
        menubar.addMenu(file_menu)
        edit_menu = QtWidgets.QMenu('Edit', self)
        menubar.addMenu(edit_menu)
        help_menu = QtWidgets.QMenu('Help', self)
        menubar.addMenu(help_menu)

        open_recent_label = 'Open recent'
        menu_cfg = (
            (file_menu, 'New', self.prompt_new, 'ctrl+n'),
            (file_menu, 'Open...', self.prompt_open, 'ctrl+o'),
            (file_menu, open_recent_label, None, None),
            (
                file_menu,
                'Import...',
                lambda: self.prompt_open(import_=True),
                None),
            (file_menu, None, None, '-------'),
            (file_menu, 'Save', self.save, 'ctrl+s'),
            (file_menu, 'Save as...', self.prompt_save, 'shift+ctrl+s'),
            (
                file_menu,
                'Incremental save',
                self.incremental_save,
                'shift+alt+s'),
            (
                file_menu,
                'Export selected...',
                lambda: self.prompt_save(selected=True),
                None),
            (edit_menu, 'Copy', self.copy, 'ctrl+c'),
            (edit_menu, 'Paste', self.paste, 'ctrl+v'),
            (edit_menu, None, None, '-------'),
            (edit_menu, 'Undo', self.undo, 'ctrl+z'),
            (edit_menu, 'Redo', self.redo, 'ctrl+y'),
            (help_menu, 'Shortcuts', self.show_shortcuts, None),
        )
        for menu, label, func, shortcut_key in menu_cfg:
            if label is None:
                menu.addSeparator()
                continue
            if label == open_recent_label:
                self.open_recent_menu = QtWidgets.QMenu(
                    open_recent_label, self)
                menu.addMenu(self.open_recent_menu)
                self.open_recent_menu.aboutToShow.connect(self.fill_recent)
                continue
            action = QtGui.QAction(label, self)
            action.triggered.connect(func)
            if shortcut_key:
                action.setShortcut(shortcut_key)
            menu.addAction(action)
            if shortcut_key:
                self.shortcuts_list.append((shortcut_key, label))

        # Shortcuts
        shortcuts = [
            ('f', self.node_view.frame_all, 'Frame node view'),

            ('delete', self.node_view.delete_selected_nodes, 'Delete selected nodes'),
            ('d', self.toggle_disable_selected, 'Toggle disable selected nodes'),

            ('y', self.connect_selected_nodes, 'Connect selected nodes'),

            ('space', self.connect_to_display, 'Show 1st display'),
            ('1', self.connect_to_display, 'Show 1st display'),
            ('2', lambda: self.connect_to_display(2), 'Show 2nd display'),
            ('3', lambda: self.connect_to_display(3), 'Show 3rd display'),
            ('4', lambda: self.connect_to_display(4), 'Show 4th display'),
            ('5', lambda: self.connect_to_display(5), 'Show 5th display'),
            ('6', lambda: self.connect_to_display(6), 'Show 6th display'),
            ('7', lambda: self.connect_to_display(7), 'Show 7th display'),
            ('8', lambda: self.connect_to_display(8), 'Show 8th display'),
            ('9', lambda: self.connect_to_display(9), 'Show 9th display'),

            ('`', self.node_view.show_add_node_menu, 'New node menu'),
            ('²', self.node_view.show_add_node_menu, 'New node menu'),  # FR
            ('n', self.node_view.show_add_node_menu, 'New node menu'),

            ('c', lambda: self.create_node('concatenate'), 'Create Concatenate'),
            ('x', lambda: self.create_node('derive'), 'Create Derive'),
            ('v', lambda: self.create_node('filter'), 'Create Filter'),
            ('p', lambda: self.create_node('format'), 'Create Format'),
            ('g', lambda: self.create_node('group'), 'Create Group'),
            ('j', lambda: self.create_node('join'), 'Create Join'),
            ('r', lambda: self.create_node('rename'), 'Create Rename'),
            ('o', lambda: self.create_node('reorder'), 'Create Reorder'),
            ('s', lambda: self.create_node('sort'), 'Create Sort'),
            ('t', lambda: self.create_node('table'), 'Create Table'),
            ('.', lambda: self.create_node('dot'), 'Create Dot'),

            ('b', lambda: self.create_node('backdrop'), 'Create Backdrop'),
            ('-', lambda: self.align('horizontal'), 'Align horizontally'),
            ('|', lambda: self.align('vertical'), 'Align vertically'),
        ]
        for key, cmd, label in shortcuts:
            set_shortcut(key, self, cmd)
            self.shortcuts_list.append((key, label))

        # Load graph
        if graph:
            self.load_graph(graph)
            self.add_undo()

    @property
    def save_path(self):
        return self._save_path

    @save_path.setter
    def save_path(self, path):
        self._save_path = path
        self.setWindowTitle(f'{TITLE} - {path}')

    def load_graph(self, graph, add=False, record_undo=True):
        try:
            self._load_graph(graph, add, record_undo)
        except BaseException:
            self.load_graph({})
            self.save_path = None
            self.undo_stack.clear()
            return QtWidgets.QMessageBox.warning(
                self, 'Error', traceback.format_exc())

    def _load_graph(self, graph, add=False, record_undo=True):
        # Remove and handle graph settings stored as dummy node
        if GRAPH_SETTINGS_KEY in graph:
            graph_settings = graph.pop(GRAPH_SETTINGS_KEY)
            self.node_view.zoom = graph_settings.get('zoom')
            self.node_view.origin = graph_settings.get('origin')
            display_node_name = graph_settings.get('current_display')
            if display_node_name:
                self.display_widget.set_display_node(display_node_name)

        if not add:
            self.graph = dict()
            self.node_view.clear()
        else:
            """
            Pasting node: we need to rename everything to avoid clashes
            We want new nodes to be connected together but remove connections
            to the other nodes
            """
            # Rename nodes to avoid clashes and preserve connections
            graph = graph or dict()
            suffix = str(uuid.uuid1())
            graph = {
                f'{name}{suffix}': settings
                for name, settings in graph.items()}
            # Rename connections but remove connections not part of clipboard
            for name, settings in graph.items():
                inputs = settings.get('inputs') or []
                for i, input_ in enumerate(inputs or []):
                    if not input_:
                        continue
                    node_name, conn_index = input_
                    new_name = f'{node_name}{suffix}'
                    if new_name in graph:
                        inputs[i] = [new_name, conn_index]
                    else:
                        inputs[i] = None

        # Build graph
        new_nodes: list[BaseNode] = []
        for name, settings in graph.items():
            nodetype = settings['type']
            if nodetype not in types:
                continue
            if add:
                # offset position slightly for paste/import
                p = settings['position']
                p.setX(p.x() + 50)
                p.setY(p.y() + 50)
            new_nodes.append(self.create_node(
                nodetype, name, settings, auto_increment=add, update=False))

        # Rename pasted nodes
        if add:
            for node in new_nodes:
                self.rename_node(node['name'], node['name'][:-len(suffix)])

        # Autosave
        self.autosave(record_undo=record_undo)

        # Select new nodes
        if add:
            self.node_view.selected_names = [n['name'] for n in new_nodes]
        else:
            self.node_view.selected_names.clear()

        # Refresh UI
        if not add:
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
        if not add:
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

        # Define create position
        inject_position = (
            self.node_view.select_position and
            (not settings or not settings.get('position')))
        if inject_position:
            if settings is None:
                settings = {}
            settings['position'] = self.node_view.get_create_position()

        # Create node
        node = create_node(
            self.graph,
            types,
            node_type,
            name=name,
            settings=settings,
            auto_increment=auto_increment)

        if node_type == 'backdrop':
            # Size backdrop based on selection
            nodes = [self.graph[n] for n in self.node_view.selected_names]
            node.wrap_around_nodes(nodes)
        else:
            # Connect to selected node
            if len(self.node_view.selected_names) == 1:
                source_node = self.graph[self.node_view.selected_names[0]]
                connect_nodes(self.graph, source_node, 0, node, 0)

        # Repaint graph
        if update:
            self.node_view.selected_names = [node['name']]
            self.set_settings_node(node)
            self.node_view.update()
            self.display_widget.update_content()
        # Fill Displays combo
        if node.category in (DISPLAY_CATEGORY, DASHBOARD_CATEGORY):
            self.display_widget.fill_combo()

        return node

    def create_load(self, path):
        self.create_node('load', settings=dict(path=path))

    def toggle_disable_selected(self):
        if not self.node_view.selected_names:
            return
        first_node = self.graph[self.node_view.selected_names[0]]
        new_state = not first_node['disabled']
        for node_name in self.node_view.selected_names:
            self.graph[node_name].settings['disabled'] = new_state
            self.set_dirty_recursive(node_name)
        self.node_view.update()
        self.display_widget.update_content()
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

    def connect_selected_nodes(self):
        if len(self.node_view.selected_names) != 2:
            return
        connect_nodes(
            self.graph,
            self.graph[self.node_view.selected_names[0]], 0,
            self.graph[self.node_view.selected_names[1]], 0)
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

    def _add_to_recents(self, filepath):
        recents = get_preference(RECENTS_PREF) or []
        filepath = filepath.replace('\\', '/')
        if filepath in recents:
            recents.remove(filepath)
        recents.insert(0, filepath)
        set_preference(RECENTS_PREF, recents[:16])

    def save_to_file(self, path, selected=False, set_current=True):
        content = self.serialize_graph(selected=selected)
        with open(path, 'w') as f:
            f.write(content)
        if set_current:
            self.save_path = path
            self.autosave_path = f'{path}~'
            self._add_to_recents(self.save_path)

    def save(self):
        if not self.save_path:
            return self.prompt_save()
        self.save_to_file(self.save_path)

    def incremental_save(self):
        if not self.save_path:
            return self.prompt_save()
        self.save_path = increment_path(self.save_path)
        self.save_to_file(self.save_path)
        self._add_to_recents(self.save_path)

    def open_file(self, filepath, import_=False):
        self._add_to_recents(filepath)
        # Open
        with open(filepath, 'r') as f:
            graph = deserialize_graph(f.read())
        self.load_graph(graph, add=import_)
        self.save_path = filepath

    def prompt_open(self, import_=False):
        filepath, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Open Graph', '', '*.pg')
        if not filepath:
            return
        self.open_file(filepath, import_=import_)

    def fill_recent(self):
        self.open_recent_menu.clear()
        recents = get_preference(RECENTS_PREF) or []
        for path in recents:
            action = QtGui.QAction(path, self)
            action.triggered.connect(partial(self.open_file, path))
            self.open_recent_menu.addAction(action)

    def prompt_new(self):
        prompt = QtWidgets.QMessageBox(
            windowTitle='New',
            text='New graph ?\nAll unsaved changes will be lost',
            parent=self,
            standardButtons=(
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel))
        prompt.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        if prompt.exec_() == QtWidgets.QMessageBox.Cancel:
            return False
        self.load_graph({})
        self.save_path = None
        self.autosave_path = DEFAULT_AUTOSAVE_PATH
        self.undo_stack.clear()

    def prompt_save(self, selected=False):
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Open Graph', '', '*.pg')
        if not filepath:
            return
        self.save_to_file(
            filepath, selected=selected, set_current=not selected)

    # Copy/Paste
    def copy(self):
        QtWidgets.QApplication.clipboard().setText(
            f'{CLIPBOARD_PREFIX}{self.serialize_graph(selected=True)}')

    def paste(self):
        clipboard = QtWidgets.QApplication.clipboard().text().strip()
        if clipboard.startswith(CLIPBOARD_PREFIX):
            self.load_graph(deserialize_graph(clipboard), add=True)

    # Autosave
    def autosave(self, record_undo=True):
        logger.debug('autosave')
        self.save_to_file(self.autosave_path, set_current=False)
        if record_undo:
            self.add_undo()

    def closeEvent(self, event):
        self.autosave()
        return super().closeEvent(event)

    # Undo/Redo
    def _undo_redo(self, action='undo'):
        if action == 'undo':
            graph = self.undo_stack.undo()
        else:
            graph = self.undo_stack.redo()
        if graph:
            self.load_graph(deserialize_graph(graph), record_undo=False)

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
        new_name = rename_node(self.graph, old_name, new_name)
        self.node_view.rename_node(old_name, new_name)
        self.set_settings_node(self.graph[new_name])
        self.display_widget.fill_combo()

    def show_add_node_menu(self):
        position = self.add_button.rect().bottomLeft()
        self.node_view.show_add_node_menu(
            self.node_view.mapToGlobal(position))

    # Connect shortcut
    def connect_to_display(self, display_index=1):
        """Display index is based on their names alphabetical order"""
        display_node_name = get_displays_by_index(self.graph).get(
            display_index)
        if not display_node_name:
            return
        if len(self.node_view.selected_names) == 1:
            selected_node = self.graph[self.node_view.selected_names[0]]
            self.change_plug(
                dict(side=1, name=selected_node['name'], index=0),
                dict(side=0, name=display_node_name, index=0))
        self.display_widget.set_display_node(display_node_name)

    def align(self, axis='horizontal'):
        if len(self.node_view.selected_names) < 2:
            return
        pos = self.graph[self.node_view.selected_names[0]]['position']
        value = pos.y() if axis == 'horizontal' else pos.x()
        for name in self.node_view.selected_names[1:]:
            if axis == 'horizontal':
                self.graph[name]['position'].setY(value)
            else:
                self.graph[name]['position'].setX(value)
        self.node_view.repaint()

    def show_shortcuts(self):
        text = '<table style="font-family: monospace;">'
        for key, label in self.shortcuts_list:
            text += f'<tr><th align="right">{key.upper()}: </th>'
            text += f'<th align="left"> {label}</th></tr>'
        text += '</table>'
        QtWidgets.QMessageBox.information(self, 'Shortcuts', text)


class GraphSettings(BaseNode):
    default_color = QtGui.QColor()
    type = 'graph_settings'

    def __init__(self, settings=None):
        super().__init__(settings)


def get_preferences():
    try:
        with open(PREFS_PATH, 'r') as f:
            return json.load(f)
    except BaseException:
        return {}


def get_preference(key):
    return get_preferences().get(key)


def set_preference(key, value):
    prefs = get_preferences()
    prefs[key] = value
    with open(PREFS_PATH, 'w') as f:
        json.dump(prefs, f)


def increment_path(path):
    path, ext = os.path.splitext(path)
    version = ''
    for char in reversed(path):
        if not char.isdigit():
            break
        version = f'{char}{version}'
    if not version:
        return increment_path(f'{path}.000{ext}')
    size = len(version)
    next_version = int(version) + 1
    # Increment until file does not exist
    path = f'{path[:-size]}{str(next_version).zfill(size)}{ext}'
    while os.path.exists(path):
        next_version += 1
        path = f'{path[:-size]}{str(next_version).zfill(size)}{ext}'
    return path
