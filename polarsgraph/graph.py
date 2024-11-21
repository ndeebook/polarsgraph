import re
import traceback
from collections import defaultdict

import polars as pl
from PySide6 import QtCore, QtGui

from polarsgraph.log import logger
from polarsgraph.serialize import serialize_node


MANIPULATE_CATEGORY = 'manipulate'
DISPLAY_CATEGORY = 'display'
LOAD_CATEGORY = 'load'
DASHBOARD_CATEGORY = 'dashboard'

DYNAMIC_PLUG_COUNT = 'dynamic'

CATEGORY_INPUT_TYPE = {
    LOAD_CATEGORY: None,
    MANIPULATE_CATEGORY: 'table',
    DISPLAY_CATEGORY: 'table',
    DASHBOARD_CATEGORY: 'display',
}

CATEGORY_OUTPUT_TYPE = {
    LOAD_CATEGORY: 'table',
    MANIPULATE_CATEGORY: 'table',
    DISPLAY_CATEGORY: 'display',
    DASHBOARD_CATEGORY: 'display',
}


class BaseNode:
    type: str = None
    category: str = None
    inputs: tuple[str] = None
    outputs: tuple[str] = None
    default_color: QtGui.QColor = None

    def __init__(self, settings=None):
        self.error = None
        self.settings = settings or dict()
        self.settings['type'] = self.type

        self.dirty = True
        self.tables: dict[str, pl.LazyFrame] = {}

        # Graph settings
        if not self.settings.get('position'):
            self.settings['position'] = QtCore.QPointF(0, 0)
        if 'color' in self.settings:
            self.settings['color'] = QtGui.QColor(self.settings['color'])
        else:
            self.settings['color'] = self.default_color

    def __getitem__(self, key):
        return self.settings.get(key)

    def __setitem__(self, key, value):
        self.settings[key] = value

    def __eq__(self, other_node):
        return self.settings['name'] == other_node['name']

    def _build_query(self, tables):
        """
        Build `self.tables` here.
        Set `self.dirty` to False when done.
        """
        raise NotImplementedError

    def build_query(self, tables=None):
        if not self.dirty:
            return
        try:
            logger.debug(f'Building query for "{self["name"]}"')
            self._build_query(tables)
            self.dirty = False
            return None
        except BaseException:
            error = traceback.format_exc()
            print_build_error(error)
            return error

    def serialize(self):
        return serialize_node(self.settings)


def print_build_error(error):
    prefix = '    [build error] '
    logger.warning(prefix + f'\n{prefix}'.join(error.split('\n')))


def create_node(
        graph,
        types,
        node_type,
        name=None,
        settings=None,
        auto_increment=True):

    # Handle name
    if name is None:
        name = node_type.title()
    settings = settings or dict()
    while name in graph:
        if not auto_increment:
            raise ValueError(f'Node "{name}" already exists')
        name = increment_name(name)
    settings['name'] = name

    # Create node
    NodeClass = types[node_type]['type']
    node: BaseNode = NodeClass(settings)

    # Create default empty inputs
    if node.inputs and not node['inputs']:
        node['inputs'] = [None for _ in node.inputs]
    graph[name] = node
    return node


def get_input_node_names(graph, node_name):
    return [plug[0] for plug in graph[node_name]['inputs'] if plug]


def get_input_nodes(graph, node_name):
    return [graph[name] for name in get_input_node_names(graph, node_name)]


def get_upstream_node_names(graph, node_name):
    names = []
    for plug in graph[node_name]['inputs'] or []:
        if not plug:
            continue
        source_node_name = plug[0]
        if source_node_name == node_name:
            raise ValueError(f'Cyclic graph around {node_name}')
        names.append(source_node_name)
    return names


def get_all_upstream_node_names(graph, initial_node_name):
    upstream_names = []
    to_parse = [initial_node_name]
    while to_parse:
        node_name = to_parse.pop()
        upstream_nodes = get_upstream_node_names(graph, node_name)
        to_parse.extend(upstream_nodes)
        for node_name in upstream_nodes:
            if node_name not in upstream_names:
                upstream_names.append(node_name)
    return upstream_names


def get_all_nodes_output_nodes(graph):
    downstreams = defaultdict(list)
    for node_name in graph:
        for upstream_name in get_upstream_node_names(graph, node_name):
            downstreams[upstream_name].append(node_name)
    return downstreams


def get_downstream_node_names(graph, initial_node_name):
    return get_all_nodes_output_nodes(graph)[initial_node_name]


def set_dirty_recursive(graph: dict, node_name: str):
    graph[node_name].dirty = True
    for node_name in get_downstream_node_names(graph, node_name):
        set_dirty_recursive(graph, node_name)


def _get_input_table(graph, node_name, input_plug_index=0):
    node: BaseNode = graph[node_name]
    inputs = node['inputs']
    if not inputs:
        return
    try:
        plug_target = inputs[input_plug_index]
    except IndexError:
        return
    if not plug_target:
        return
    input_node_name, input_node_plug_index = plug_target
    input_node: BaseNode = graph[input_node_name]
    input_table_name = input_node.outputs[input_node_plug_index]
    return input_node.tables.get(input_table_name)


def get_input_tables(graph, node):
    input_tables = []
    for input_plug_index in range(len(node.inputs or [])):
        input_tables.append(
            _get_input_table(graph, node['name'], input_plug_index))
    return input_tables


def build_node_query(graph: dict, node_name: str):
    """
    Build the LazyFrame query
    LazyFrame.collect() is only called when displaying the data, not here.
    """
    node: BaseNode = graph[node_name]
    if not node.dirty:
        return True
    nodes_to_build = [
        node_name, *get_all_upstream_node_names(graph, node_name)]
    for upstream_node_name in reversed(nodes_to_build):
        upstream_node: BaseNode = graph[upstream_node_name]
        if upstream_node.dirty:
            upstream_node.error = upstream_node.build_query(
                get_input_tables(graph, upstream_node))
            if upstream_node.error:
                logger.debug(
                    f'Build aborted because of {upstream_node_name}')
                return False
    return True


def connect_nodes(graph, source_node, source_index, target_node, target_index):
    # Check plugs compatibility
    if source_node == target_node:
        return False
    target_name = target_node['name']

    out_type = CATEGORY_OUTPUT_TYPE[source_node.category]
    in_type = CATEGORY_INPUT_TYPE[target_node.category]
    if out_type != in_type:
        logger.warning(f'Incompatible plugs {out_type} and {in_type}')
        return False

    upstream_nodes = get_all_upstream_node_names(graph, source_node['name'])
    if target_name in upstream_nodes:
        logger.warning('Cannot connect, would create a cyclic graph')
        return False

    dashboard_already_contains_display = (
        target_node.category == 'dashboard' and
        source_node['name'] in get_input_node_names(graph, target_name))
    if dashboard_already_contains_display:
        logger.warning('Cannot connect same Display twice in a Dashboard')
        return False

    # Connect
    if target_node.inputs == DYNAMIC_PLUG_COUNT:
        remove_unused_dynamic_plugs(target_node)
        try:
            target_node['inputs'][target_index]
        except IndexError:
            target_node['inputs'].append(None)
    target_node['inputs'][target_index] = [source_node['name'], source_index]
    return True


def remove_unused_dynamic_plugs(node):
    """
    Only remove the last empty ones.
        => if we have plug 1, 2, 3 plugged, we dont want #3 to become #2 if we
        disconnect #2
    """
    to_disconnect = 0
    for plug in reversed(node['inputs']):
        if plug:
            break
        to_disconnect += 1
    if not to_disconnect:
        return
    node['inputs'] = node['inputs'][:-to_disconnect]


def disconnect_plug(node, index):
    try:
        if not node['inputs'][index]:
            return
    except IndexError:
        pass
    node['inputs'][index] = None
    if node.inputs == DYNAMIC_PLUG_COUNT:
        remove_unused_dynamic_plugs(node)


def rename_node(graph, old_name, new_name):
    node = graph.pop(old_name)
    node['name'] = new_name
    graph[new_name] = node
    for node in graph.values():
        for input in node['inputs'] or []:
            if not input:
                continue
            plug_node_name = input[0]
            if plug_node_name == old_name:
                input[0] = new_name


def increment_name(name):
    match = re.search(r'(\d+)$', name)
    if not match:
        return name + '1'
    number = match.group(1)  # Get the number part
    return name[:match.start()] + str(int(number) + 1)
