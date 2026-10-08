import re
import traceback
from copy import deepcopy
from collections import defaultdict

import polars as pl
from PySide6 import QtCore, QtGui

from polarsgraph.log import logger
from polarsgraph.serialize import serialize_node


MANIPULATE_CATEGORY = 'manipulate'
DISPLAY_CATEGORY = 'display'
LOAD_CATEGORY = 'load'
DASHBOARD_CATEGORY = 'dashboard'
BACKDROP_CATEGORY = 'backdrop'

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
    input_plugs: tuple[str] = None
    output_plugs: tuple[str] = None
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
            if self['disabled']:
                self.tables['table'] = tables[0]
            else:
                self._build_query(tables)
            self.error = None
            self.dirty = False
            return None
        except BaseException:
            error = traceback.format_exc()
            prefix = f'    [query error "{self["name"]}"] '
            logger.warning(prefix + f'\n{prefix}'.join(error.split('\n')))
            return error

    def serialize(self):
        return serialize_node(self.settings)

    def __deepcopy__(self, memo):
        """
        Enable deepcopy on nodes by ignoring self._display_widget which cannot
        be pickled.
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        for k, v in self.__dict__.items():
            if k == '_display_widget':
                setattr(result, k, None)
            else:
                setattr(result, k, deepcopy(v, memo))
        return result


def create_node(
        graph,
        types,
        node_type,
        name=None,
        settings=None,
        parent=None,
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
    if node.input_plugs and not node['inputs']:
        node['inputs'] = [None for _ in node.input_plugs]
    graph[name] = node

    # Subgraph
    if parent:
        node['parent'] = parent
        graph[parent].record_new_plug(node_type, name)

    return node


def get_input_node_names(graph, node_name):
    return [cnx[0] for cnx in graph[node_name]['inputs'] or [] if cnx]


def get_logical_input_nodes(graph, initial_node_name):
    nodes = []
    for node_name in get_input_node_names(graph, initial_node_name):
        if node_name == initial_node_name:
            raise ValueError(f'Cyclic graph around {node_name}')
        node: BaseNode = graph[node_name]
        if node.type not in ('subgraph', 'input', 'output'):
            nodes.append(node)
        # Output: just skip the node
        elif node.type == 'output':
            nodes.extend(get_logical_input_nodes(graph, node_name))
        # Input: return the subgraph input
        elif node.type == 'input':
            parent_subgraph = graph[node['parent']]
            input_index = parent_subgraph['input_nodes'].index(node_name)
            cnx = parent_subgraph['inputs'][input_index]
            if not cnx:
                continue
            nodes.append(graph[cnx[0]])
        # Subgraph: return the subgraph output nodes' inputs
        elif node.type == 'subgraph':
            for output_node_name in node['output_nodes'] or []:
                nodes.extend(get_logical_input_nodes(graph, output_node_name))
    return nodes


def get_logical_input_node_names(graph, node_name):
    return [n['name'] for n in get_logical_input_nodes(graph, node_name)]


def get_all_upstream_node_names(graph, initial_node_name):
    """
    Return nodes in an order they can be computed (with their inputs computed).
    """
    upstream_names = []
    to_parse = [initial_node_name]
    while to_parse:
        node_name = to_parse.pop()
        upstream_node_names = get_logical_input_node_names(graph, node_name)
        to_parse.extend(upstream_node_names)
        for node_name in upstream_node_names:
            if node_name in upstream_names:
                # position needs to be updated
                upstream_names.remove(node_name)
            upstream_names.append(node_name)
    return upstream_names


def get_all_nodes_output_nodes(graph):
    downstreams = defaultdict(list)
    for node_name in graph:
        for upstream_name in get_input_node_names(graph, node_name):
            downstreams[upstream_name].append(node_name)
    return downstreams


def get_downstream_node_names(graph, initial_node_name):
    return get_all_nodes_output_nodes(graph)[initial_node_name]


def set_dirty_recursive(graph: dict, node_name: str, visited=None):
    visited = set() if visited is None else visited
    if node_name in visited:
        return
    visited.add(node_name)
    node: BaseNode = graph[node_name]
    node.dirty = True
    if node.type == 'output':
        set_dirty_recursive(graph, node['parent'], visited)
    elif node.type == 'subgraph':
        for input_node_name in node['input_nodes'] or []:
            set_dirty_recursive(graph, input_node_name, visited)
    for downstream_name in get_downstream_node_names(graph, node_name):
        set_dirty_recursive(graph, downstream_name, visited)


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

    # Resolve Subgraph nodes
    if input_node.type == 'output':
        return _get_input_table(graph, input_node_name, 0)
    if input_node.type == 'input':
        idx = graph[input_node['parent']]['input_nodes'].index(input_node_name)
        return _get_input_table(graph, input_node['parent'], idx)
    if input_node.type == 'subgraph':
        output_node_name = input_node['output_nodes'][input_node_plug_index]
        return _get_input_table(graph, output_node_name, 0)

    input_table_name = input_node.output_plugs[input_node_plug_index]
    return input_node.tables.get(input_table_name)


def get_input_tables(graph, node: BaseNode):
    input_tables = []
    for input_plug_index in range(len(node.input_plugs or [])):
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
            error = upstream_node.build_query(
                get_input_tables(graph, upstream_node))
            if error:
                error_node = None
                if upstream_node.category == DISPLAY_CATEGORY:
                    input_nodes = get_logical_input_nodes(
                        graph, upstream_node['name'])
                    if not input_nodes:
                        upstream_node.error = error
                        return False
                    error_node = input_nodes[0]
                else:
                    error_node = upstream_node
                if error_node:
                    error_node.error = error
                logger.debug(f'Build aborted because of {upstream_node_name}')
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
    if target_node.input_plugs == DYNAMIC_PLUG_COUNT:
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
    if node.input_plugs == DYNAMIC_PLUG_COUNT:
        remove_unused_dynamic_plugs(node)


def _increment_string(s):
    match = re.search(r'(\d+)$', s)
    if match:
        num = match.group(1)
        incremented_num = str(int(num) + 1).zfill(len(num))
        return s[:match.start()] + incremented_num
    else:
        return s + '1'


def rename_node(graph, old_name, new_name):
    # Ensure name is unique
    while new_name in graph:
        new_name = _increment_string(new_name)

    # Rename node
    node = graph.pop(old_name)
    node['name'] = new_name
    graph[new_name] = node

    # Rename Subgraph plug
    if node.type in ('input', 'output'):
        subgraph = graph[node['parent']]
        subgraph.rename_plug(node.type, old_name, new_name)
    elif node.type == 'subgraph':
        for n in graph.values():
            if n['parent'] == old_name:
                n['parent'] = new_name

    # Rename plugs
    for node in graph.values():
        for input in node['inputs'] or []:
            if not input:
                continue
            plug_node_name = input[0]
            if plug_node_name == old_name:
                input[0] = new_name

    return new_name


def increment_name(name):
    match = re.search(r'(\d+)$', name)
    if not match:
        return name + '1'
    number = match.group(1)  # Get the number part
    return name[:match.start()] + str(int(number) + 1)
