import json
from copy import deepcopy

from PySide6 import QtGui, QtCore

from polarsgraph.log import logger
from polarsgraph.version import VERSION


HEADER_PREFIX = '# PolarsGraph'
HEADER = f'{HEADER_PREFIX} v{".".join([str(v) for v in VERSION])}'


def dump(data, depth=0, indent=' ' * 4):
    """
    json dump but only indent first 2 levels of dict
    """
    next_level = depth + 1
    if depth < 2 and isinstance(data, dict):
        serialized = ',\n'.join(
            f'{indent * next_level}"{k}": {dump(v, next_level)}'
            for k, v in data.items())
        return f'{{\n{serialized}\n{indent * depth}}}'
    return json.dumps(data)


def _reorder_keys(node_settings):
    # Put some keys first:
    settings = {
        k: node_settings[k] for k in ('name', 'type', 'disabled', 'inputs')
        if k in node_settings}
    # Recover other keys:
    settings.update(node_settings)
    # Put some keys last:
    for key in ('color', 'position', 'columns_widths'):
        if key in settings:
            settings[key] = settings.pop(key)
    return settings


def serialize_node(settings: dict, ignore_attributes=None):
    settings = deepcopy(settings)
    for k, v in settings.items():
        # if isinstance(v, QtGui.QColor):
        if k == 'color':
            v = [v.red(), v.green(), v.blue()]
        # elif isinstance(v, QtCore.QPointF):
        elif k in ('position', 'origin'):
            v = [round(v.x(), 3), round(v.y(), 3)]
        elif isinstance(v, tuple):
            v = list(v)
        if v is not None:
            settings[k] = v
    for attribute in ignore_attributes or []:
        settings.pop(attribute, None)
    return dump(_reorder_keys(settings))


def deserialize_node(text):
    try:
        settings = json.loads(text)
    except json.decoder.JSONDecodeError:
        logger.debug(f'Deserialize error with following:\n{text}')
        raise
    for k, v in settings.items():
        if k == 'color':
            settings[k] = QtGui.QColor(*v)
        elif k in ('position', 'origin'):
            settings[k] = QtCore.QPointF(*v)
    return settings


def serialize_graph(graph, settings=None):
    content = f'{HEADER}\n'
    nodes = list(graph.values())
    if settings:
        nodes.append(settings)
    for node in graph.values():
        content += f'{node["name"]}\n'
        content += node.serialize()
        content += '\n'
    return content


def _extract_version(serialized_graph_lines):
    if not serialized_graph_lines[0].startswith(HEADER_PREFIX):
        return 0, 7
    header = serialized_graph_lines.pop(0)
    if ' v' not in header:
        return 0, 7
    file_version = header.split(' v')[-1].split('.')
    return tuple(int(v) for v in file_version)


def deserialize_graph(text):
    lines = text.split('\n')
    file_version = _extract_version(lines)

    # Parse nodes
    nodes = []
    in_node = False
    current_node = ''
    for line in lines:
        if line == '{':
            in_node = True
        elif line == '}':
            in_node = False
            nodes.append(f'{{{current_node}}}')
            current_node = ''
        elif in_node:
            current_node += line

    # Deserialize nodes
    nodes = [deserialize_node(n) for n in nodes]
    if file_version < VERSION:
        _conform_old_nodes(nodes, file_version)
    return {n['name']: n for n in nodes}


def _conform_old_nodes(nodes, file_version):
    for node in nodes:
        if file_version < (0, 8) and node['type'] == 'group':
            node['type'] = 'groupby'
        if file_version < (0, 9) and node['type'] == 'filter':
            node['type'] = 'filter2'
            node['conditions'] = [[
                node.pop('column'),
                node.pop('condition'),
                node.pop('value', None)]]


if __name__ == '__main__':
    # Test 1
    expected = '''{
    "x": 1,
    "y": [1, 2, 3]
}'''
    assert dump(dict(x=1, y=[1, 2, 3])) == expected

    # Test 2
    text = '''test
{
    "type": "test",
    "name": "test",
    "x": [["a", "b", "c"]]
}'''
    deserialize_graph(text) == {
        'test': {'type': 'test', 'name': 'test', 'x': [['a', 'b', 'c']]}}

    # Test 3
    text = '''Derive1
{
    "type": "derive",
    "inputs": [["Join1", 0]],
    "position": [487.1, 159.7],
    "name": "Derive1",
    "color": [255, 111, 0]
}

Load1
{
    "type": "load",
    "inputs": null,
    "position": [9.8, 165.3],
    "name": "Load1",
    "color": [255, 0, 111]
}'''
    expected = {
        'Derive1': {
            'color': QtGui.QColor.fromRgbF(1, 0.435294, 0, 1),
            'inputs': [['Join1', 0]],
            'name': 'Derive1',
            'position': QtCore.QPointF(487.1, 159.7),
            'type': 'derive',
        },
        'Load1': {
            'color': QtGui.QColor.fromRgbF(1, 0, 0.435294, 1),
            'inputs': None,
            'name': 'Load1',
            'position': QtCore.QPointF(9.8, 165.3),
            'type': 'load',
        }
    }
    assert deserialize_graph(text) == expected
