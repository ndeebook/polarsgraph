from functools import partial

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.graph import (
    LOAD_CATEGORY, MANIPULATE_CATEGORY, DISPLAY_CATEGORY, DASHBOARD_CATEGORY,
    BACKDROP_CATEGORY,
    CATEGORY_INPUT_TYPE, CATEGORY_OUTPUT_TYPE, DYNAMIC_PLUG_COUNT)
from polarsgraph.nodes.base import BaseNode
from polarsgraph.viewportmapper import ViewportMapper
from polarsgraph.display import get_displays_by_index


BACKGROUND_COLOR = QtGui.QColor('#1E1E1E')
NODE_COLOR = QtGui.QColor(16, 16, 16)
NODE_TITLE_BG_COLOR = QtGui.QColor(5, 5, 5)
PLUG_COLOR = QtGui.QColor(22, 162, 232)
SELECTION_PEN = QtGui.QPen(
    Qt.white, .5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
SELECTION_BACKGROUND_COLOR = QtGui.QColor(255, 255, 255, 20)
DEFAULT_PLUG_NAMES = 'table', 'widget'

IN = 0
OUT = 1


class NodeView(QtWidgets.QWidget):
    nodes_selected = QtCore.Signal(list)
    nodes_position_changed = QtCore.Signal(list)
    node_double_clicked = QtCore.Signal(str)
    plug_changes_requested = QtCore.Signal(dict, dict)
    create_requested = QtCore.Signal(str)
    delete_requested = QtCore.Signal(list)

    def __init__(
            self,
            types,
            graph=None,
            zoom=1.0,
            origin=(0, 0)):

        super().__init__()

        self.types = types
        self.graph: dict[str, BaseNode] = graph
        self.viewportmapper = ViewportMapper(zoom, origin)

        self.nodes_bboxes: dict[str, QtCore.QRect] = dict()
        self.backdrop_bboxes: dict[str, tuple] = dict()
        self.plugs_bboxes: dict[str, tuple] = dict()

        self.selected_names = []

        self.clicked_button = None
        self.previous_pan_pos = None
        self.dragged_object = None
        self.drag_position = None
        self.select_position: QtCore.QPointF = None
        self.move_start_positions = dict()

        self.add_menu = QtWidgets.QMenu()
        for node_type in get_sorted_node_types(types):
            if node_type == '_separator':
                self.add_menu.addSeparator()
                continue
            action = QtGui.QAction(node_type, self)
            action.triggered.connect(
                partial(self.create_requested.emit, node_type))
            self.add_menu.addAction(action)

    def clear(self):
        self.nodes_bboxes.clear()
        self.plugs_bboxes.clear()
        self.backdrop_bboxes.clear()
        self.selected_names.clear()

    def set_graph(self, graph):
        self.graph = graph
        self.clear()
        self.update()

    def rename_node(self, old_name, new_name):
        # node already renamed in the Graph itself

        # rename in dicts:
        dicts_to_rename = (
            self.nodes_bboxes,
            self.plugs_bboxes,
            self.backdrop_bboxes,
            self.move_start_positions)
        for dict_ in dicts_to_rename:
            if old_name not in dict_:
                continue
            dict_[new_name] = dict_.pop(old_name)

        # Rename in selection:
        if old_name in self.selected_names:
            self.selected_names.remove(old_name)
            self.selected_names.append(new_name)

        self.update()

    def frame_all(self):
        if self.selected_names:
            rects = [
                rect for name, rect in self.nodes_bboxes.items()
                if name in self.selected_names]
        else:
            rects = list(self.nodes_bboxes.values())
        if not rects:
            return
        rect = rects[0]
        for other_rect in rects[1:]:
            rect = rect.united(other_rect)
        self.viewportmapper.focus(self.viewportmapper.to_units_rect(rect))
        self.update()

    def paintEvent(self, _):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Draw background
        painter.setBrush(BACKGROUND_COLOR)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

        # Draw backdrops first
        for name in sorted(list(self.graph)):
            node = self.graph[name]
            if node.category != BACKDROP_CATEGORY:
                continue
            self.backdrop_bboxes[name] = paint_backdrop(
                painter, self.viewportmapper, node,
                selected=name in self.selected_names)

        # Draw nodes
        display_indexes = {
            i: d for d, i in get_displays_by_index(self.graph).items()}
        for name in sorted(list(self.graph)):
            node = self.graph[name]
            if node.category == BACKDROP_CATEGORY:
                continue
            index = display_indexes.get(name, '')
            self.plugs_bboxes[name], self.nodes_bboxes[name] = paint_node(
                painter, self.viewportmapper, node, index,
                name in self.selected_names)

        # Draw connections
        painter.setBrush(Qt.BrushStyle.NoBrush)
        thickness = self.viewportmapper.to_viewport(2)
        zoom = self.viewportmapper.zoom
        for node in self.graph.values():
            inputs = node['inputs'] or []
            for i, plug in enumerate(inputs):
                if plug is None:
                    continue
                name, output_plug_index = plug
                p1 = self.plugs_bboxes[name][1][output_plug_index].center()
                p2 = self.plugs_bboxes[node['name']][0][i].center()
                painter.setPen(get_connection_pen(
                    CATEGORY_INPUT_TYPE[node.category], thickness))
                paint_connection(painter, p1, p2, OUT, zoom)

        # Draw selection rectangle
        if self.drag_position:
            if not self.dragged_object:
                paint_selection_rectangle(
                    painter, self.select_position, self.drag_position)

            # Draw dragged cable
            if self.dragged_object and self.dragged_object['type'] == 'plug':
                name, side, index = [
                    self.dragged_object[a] for a in ('name', 'side', 'index')]
                try:
                    plug_pos = self.plugs_bboxes[name][side][index].center()
                except IndexError:
                    return
                painter.setPen(get_connection_pen(
                    self.dragged_object['plug_type'], thickness))
                paint_connection(
                    painter, plug_pos, self.drag_position, side, zoom)

    def resizeEvent(self, event):
        self.viewportmapper.viewsize = event.size()
        size = (event.size() - event.oldSize()) / 2
        offset = QtCore.QPointF(size.width(), size.height())
        self.viewportmapper.origin -= offset
        self.repaint()

    def wheelEvent(self, event):
        factor = .25 if event.angleDelta().y() > 0 else -.25
        set_zoom(self.viewportmapper, factor, event.position())
        self.repaint()

    def mouseMoveEvent(self, event):
        if event.buttons() in (Qt.RightButton, Qt.MiddleButton):
            return self.pan(event)
        else:
            return self.drag(event)

    def mouseReleaseEvent(self, event):
        self.release_pan()
        self.release_drag(event.modifiers())
        self.repaint()
        return super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        under_cursor = self.get_object_under_cursor(event.position())
        if under_cursor and under_cursor['type'] == 'node':
            self.node_double_clicked.emit(under_cursor['name'])
        return super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        self.setFocus()
        self.clicked_button = event.button()
        if event.buttons() == Qt.LeftButton:
            self.select(event.position(), event.modifiers())
        return super().mousePressEvent(event)

    @property
    def zoom(self):
        return self.viewportmapper.zoom

    @zoom.setter
    def zoom(self, zoom):
        self.viewportmapper.zoom = zoom

    @property
    def origin(self):
        # Compute origin relative to graph widget size
        origin = QtCore.QPointF(self.viewportmapper.origin)
        rect = self.geometry()
        origin.setX(origin.x() + rect.width() / 2)
        origin.setY(origin.y() + rect.height() / 2)
        return origin

    @origin.setter
    def origin(self, origin):
        self.viewportmapper.origin = origin

    # PAN
    def pan(self, event):
        point = event.position()
        if not self.previous_pan_pos:
            self.previous_pan_pos = point
            return
        offset = self.previous_pan_pos - point
        self.previous_pan_pos = point
        self.viewportmapper.origin = self.viewportmapper.origin + offset
        self.repaint()

    def release_pan(self):
        self.previous_pan_pos = None

    # SELECT
    def get_object_under_cursor(self, position):
        # Check nodes
        for name, rect in self.nodes_bboxes.items():
            if rect.contains(position):
                category = self.graph[name].category
                # Check if a plug is under cursor:
                inplugs, outplugs = self.plugs_bboxes[name]
                for i, rect in enumerate(inplugs):
                    if rect.contains(position):
                        return dict(
                            type='plug',
                            plug_type=CATEGORY_INPUT_TYPE[category],
                            name=name,
                            side=IN,
                            index=i)
                for i, rect in enumerate(outplugs):
                    if rect.contains(position):
                        return dict(
                            type='plug',
                            plug_type=CATEGORY_OUTPUT_TYPE[category],
                            name=name,
                            side=OUT,
                            index=i)
                return dict(type='node', name=name)

        # Check backdrops
        for name, (_, title_rect, corner_rect) in self.backdrop_bboxes.items():
            if corner_rect.contains(position):
                return dict(type='backdrop_corner', name=name)
            if title_rect.contains(position):
                return dict(type='backdrop', name=name)

    def select(self, position, modifiers):
        under_cursor = self.get_object_under_cursor(position)
        self.select_position = position
        shift = modifiers & Qt.KeyboardModifier.ShiftModifier
        ctrl = modifiers & Qt.KeyboardModifier.ControlModifier
        alt = modifiers & Qt.KeyboardModifier.AltModifier
        if under_cursor is None:
            if not shift:
                self.selected_names = []
            return
        name = under_cursor['name']
        if under_cursor['type'] in ('node', 'backdrop'):
            # Select nodes underbackdrop
            if under_cursor['type'] == 'backdrop':
                backdrop_bbox: QtCore.QRectF = self.backdrop_bboxes[name][0]
                if alt:  # Only move backdrop
                    self.selected_names = [name]
                else:
                    self.selected_names = [
                        n for n, bbox in self.nodes_bboxes.items() if
                        backdrop_bbox.contains(bbox)]
                    self.selected_names.append(name)
                self.dragged_object = under_cursor
                self.nodes_selected.emit(self.selected_names)

            # Node selection
            elif name not in self.selected_names:  # dont unselect other nodes
                if shift or ctrl:
                    self.selected_names.append(name)
                else:
                    self.selected_names = [name]
                self.nodes_selected.emit(self.selected_names)
            elif ctrl:
                self.selected_names.remove(name)
                self.nodes_selected.emit(self.selected_names)

            # Record start positions
            for name in self.selected_names:
                self.move_start_positions[name] = self.graph[name]['position']

        self.dragged_object = under_cursor

    def drag(self, event):
        self.drag_position = event.position()
        if not self.dragged_object:
            return self.repaint()
        pos_offset = self.select_position - self.drag_position
        pos_offset /= self.viewportmapper.zoom
        if self.dragged_object['type'] in ('node', 'backdrop'):
            # Move nodes (not connecting plug, not dragging selection rect)
            for name in self.selected_names or [self.dragged_object['name']]:
                self.graph[name]['position'] = (
                    self.move_start_positions[name] - pos_offset)
        elif self.dragged_object['type'] == 'backdrop_corner':
            backdrop = self.graph[self.dragged_object['name']]
            p = backdrop['position']
            p2 = self.viewportmapper.to_units_coords(self.drag_position)
            backdrop['width'] = max(p2.x() - p.x(), 100)
            backdrop['height'] = max(p2.y() - p.y(), 50)
        self.repaint()

    def release_drag(self, modifiers):
        if self.dragged_object:
            if self.dragged_object['type'] == 'plug' and self.drag_position:
                # Emit plug change
                under_cursor = self.get_object_under_cursor(self.drag_position)
                self.plug_changes_requested.emit(
                    self.dragged_object, under_cursor)
            else:
                # Emit moved node name
                if self.drag_position:
                    self.nodes_position_changed.emit(self.selected_names)
        elif (
                self.drag_position and
                self.clicked_button == Qt.MouseButton.LeftButton):
            # Select what's under selection rectangle
            sel_rect = QtCore.QRectF(self.select_position, self.drag_position)
            shift = modifiers & Qt.KeyboardModifier.ShiftModifier
            nodes = [
                name for name, rect in self.nodes_bboxes.items()
                if sel_rect.intersects(rect)]
            nodes.extend([
                n for n, (_, title_rect, _) in self.backdrop_bboxes.items()
                if sel_rect.intersects(title_rect)])
            if shift:
                nodes = list(set(self.selected_names or []) | set(nodes))
            self.selected_names = nodes
            self.nodes_selected.emit(self.selected_names)
            for name in self.selected_names:
                self.move_start_positions[name] = self.graph[name]['position']
        self.drag_position = None
        self.dragged_object = None

    def delete_nodes(self, nodes):
        self.selected_names = [
            n for n in self.selected_names if n not in nodes]
        dicts_to_clean = (
            self.nodes_bboxes,
            self.plugs_bboxes,
            self.backdrop_bboxes,
            self.move_start_positions)
        for dict_ in dicts_to_clean:
            for name in nodes:
                if name in dict_:
                    dict_.pop(name)
        self.update()

    def show_add_node_menu(self, position=None):
        self.add_menu.popup(position or QtGui.QCursor.pos())

    def delete_selected_nodes(self):
        self.delete_requested.emit(self.selected_names)

    def get_create_position(self):
        if len(self.selected_names) == 1:
            pos = QtCore.QPointF(
                self.graph[self.selected_names[0]]['position'])
            pos.setX(pos.x() + 200)
            return pos
        if self.select_position is None:
            return
        return self.viewportmapper.to_units_coords(self.select_position)


def paint_node(
        painter: QtGui.QPainter,
        viewportmapper: ViewportMapper,
        node: BaseNode,
        display_index: int,
        selected: bool):
    name = node['name']
    pos = node['position']
    if node.inputs == DYNAMIC_PLUG_COUNT:
        inputs = [n for n in node['inputs'] if n]
        inputs = [f'{node.plug_name(i)}' for i in range(len(inputs) + 1)]
    else:
        inputs = node.inputs or []
    outputs = node.outputs or []

    pos = viewportmapper.to_viewport_coords(pos)
    x = pos.x()
    y = pos.y()
    title_height = viewportmapper.to_viewport(20)
    node_width = viewportmapper.to_viewport(128)
    plug_height = viewportmapper.to_viewport(24)
    round_size = viewportmapper.to_viewport(3)
    plug_radius = viewportmapper.to_viewport(7)
    font_size = viewportmapper.to_viewport(10)
    font_margin = viewportmapper.to_viewport(4)
    thickness = viewportmapper.to_viewport(1)

    plugs_vertical_count = max(len(inputs), len(outputs))
    plugs_height = plugs_vertical_count * plug_height
    node_height = plugs_height + title_height

    if node.type == 'dot':
        node_width /= 3.5
        title_height /= 5
        node_height /= 1.5

    # Draw node rectangle
    rect = QtCore.QRectF(x, y, node_width, node_height)
    painter.setBrush(NODE_COLOR)
    if selected:
        painter.setPen(QtGui.QPen(Qt.white, thickness))
    else:
        painter.setPen(QtGui.QPen(Qt.black, thickness))
    painter.drawRoundedRect(rect, round_size, round_size)

    # Draw the title at the top
    if node.type != 'dot':
        painter.setFont(QtGui.QFont('Verdana', font_size))
        title_rect = QtCore.QRectF(x, y, node_width, title_height)
        painter.setBrush(node['color'])
        painter.drawRoundedRect(title_rect, round_size, round_size)
    if node.error:
        painter.setPen(QtGui.QPen(Qt.red, thickness))
    else:
        painter.setPen(QtGui.QPen(Qt.white, thickness))
    if node.type != 'dot':
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, name)

    # Draw inputs and plugs
    if node.category == DASHBOARD_CATEGORY:
        painter.setBrush(Qt.black)
    else:
        painter.setBrush(PLUG_COLOR)

    input_coords = []
    for i, input_text in enumerate(inputs):
        if len(inputs) == 1:
            input_text = '' if input_text in DEFAULT_PLUG_NAMES else input_text
        py = y + title_height + plug_height / 2 + title_height * i
        bbox = QtCore.QRectF(
            x - plug_radius, py - plug_radius,
            plug_radius * 2, plug_radius * 2)
        input_coords.append(bbox.adjusted(-4, -3, 4, 3))
        painter.drawEllipse(bbox)
        painter.setPen(QtGui.QPen(Qt.white, thickness))
        painter.drawText(
            x + plug_radius + font_margin,
            py - font_size,
            node_width,
            title_height,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            input_text)

    # Right outputs and plugs
    if node.category in (DISPLAY_CATEGORY, DASHBOARD_CATEGORY):
        # Draw display index
        painter.setPen(QtGui.QPen(BACKGROUND_COLOR, thickness))
        painter.drawText(
            # title_rect.translated(0, -viewportmapper.to_viewport(18)),
            # Qt.AlignmentFlag.AlignCenter,
            title_rect.translated(-viewportmapper.to_viewport(4), 0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            str(display_index))
        painter.setBrush(Qt.black)
    else:
        painter.setBrush(PLUG_COLOR)
    output_coords = []
    for i, output_text in enumerate(node.outputs):
        output_text = '' if output_text in DEFAULT_PLUG_NAMES else output_text
        px = x + node_width
        py = y + title_height + plug_height / 2 + title_height * i
        bbox = QtCore.QRectF(
            px - plug_radius, py - plug_radius,
            plug_radius * 2, plug_radius * 2)
        output_coords.append(bbox.adjusted(-4, -3, 4, 3))
        painter.drawEllipse(bbox)
        painter.setPen(QtGui.QPen(Qt.white, thickness))
        painter.drawText(
            x,
            py - font_size,
            node_width - plug_radius - font_margin,
            title_height,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            output_text)

    # Draw disabled
    if node['disabled']:
        painter.setPen(QtGui.QPen(Qt.red, thickness * 4))
        painter.drawLine(rect.bottomLeft(), rect.topRight())

    rect.adjust(-plug_radius, 0, plug_radius, 0)  # BBOX including plugs
    return (input_coords, output_coords), rect


def paint_backdrop(
        painter: QtGui.QPainter,
        viewportmapper: ViewportMapper,
        node: BaseNode,
        selected: bool):
    pos = node['position']
    pos = viewportmapper.to_viewport_coords(pos)
    x = pos.x()
    y = pos.y()
    w = viewportmapper.to_viewport(node['width'])
    h = viewportmapper.to_viewport(node['height'])
    title_height = viewportmapper.to_viewport(30)
    font_size = viewportmapper.to_viewport(10)
    thickness = viewportmapper.to_viewport(1)
    margin = viewportmapper.to_viewport(2)

    # Main rect
    color: QtGui.QColor = node['color']
    painter.setBrush(color)
    if selected:
        painter.setPen(QtGui.QPen(Qt.white, 1))
    else:
        painter.setPen(Qt.PenStyle.NoPen)
    main_rect = QtCore.QRectF(x, y, w, h)
    painter.drawRect(main_rect)
    if selected:
        painter.setPen(Qt.PenStyle.NoPen)

    # Title
    title_rect = main_rect.adjusted(margin, margin, -margin, -margin)
    title_rect.setHeight(title_height - margin)
    painter.setBrush(color.lighter())
    painter.drawRect(title_rect)

    painter.setPen(QtGui.QPen(Qt.black, thickness))
    painter.setFont(QtGui.QFont('Verdana', font_size))
    painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, node['name'])

    # Text
    # TODO: QtGui.QStaticText(node['text'])
    font_size = viewportmapper.to_viewport(node['text_size'])
    painter.setFont(QtGui.QFont('Verdana', font_size))
    painter.drawText(
        x + margin,
        y + title_height,
        w - margin * 2,
        h - title_height - margin,
        Qt.AlignmentFlag.AlignLeft,
        node['text'])

    # Lower right size manipulation hint
    corner_size = viewportmapper.to_viewport(12)
    corner_rect = QtCore.QRectF(
        x + w - corner_size,
        y + h - corner_size,
        corner_size,
        corner_size)
    painter.setPen(Qt.PenStyle.NoPen)
    # Draw triangle
    path = QtGui.QPainterPath()
    path.moveTo(corner_rect.bottomLeft())
    path.lineTo(corner_rect.bottomRight())
    path.lineTo(corner_rect.topRight())
    path.lineTo(corner_rect.bottomLeft())
    painter.drawPath(path)

    return main_rect, title_rect, corner_rect


def get_connection_pen(category, thickness):
    display = category == 'display'
    if display:
        return QtGui.QPen(
            Qt.black, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    return QtGui.QPen(
        PLUG_COLOR, thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)


def paint_connection(
        painter: QtGui.QPainter,
        p1: QtCore.QPoint,
        p4: QtCore.QPoint,
        side=OUT,
        zoom: float = 1.0):
    path = QtGui.QPainterPath()
    x1, y1 = p1.x(), p1.y()
    x2, y2 = p4.x(), p4.y()
    p1 = QtCore.QPoint(x1, y1)
    p4 = QtCore.QPoint(x2, y2)
    if (side == OUT) == (x1 > x2):
        x_offset = min(x1 - x2, 150) * zoom
        p2 = QtCore.QPoint(x1 + x_offset, y1)
        p3 = QtCore.QPoint(x2 - x_offset, y2)
    else:
        middle_x = (x2 + x1) / 2
        p2 = QtCore.QPoint(middle_x, y1)
        p3 = QtCore.QPoint(middle_x, y2)
    path.moveTo(p1)
    path.cubicTo(p2, p3, p4)
    painter.drawPath(path)


def paint_selection_rectangle(
        painter: QtGui.QPainter,
        p1: QtCore.QPoint,
        p2: QtCore.QPoint):
    rect = QtCore.QRectF(p1, p2)
    painter.setPen(SELECTION_PEN)
    painter.setBrush(SELECTION_BACKGROUND_COLOR)
    painter.drawRect(rect)


def set_zoom(viewportmapper: ViewportMapper, factor, reference):
    abspoint = viewportmapper.to_units_coords(reference)
    if factor > 0:
        viewportmapper.zoomin(abs(factor))
    else:
        viewportmapper.zoomout(abs(factor))
    relcursor = viewportmapper.to_viewport_coords(abspoint)
    vector = relcursor - reference
    viewportmapper.origin = viewportmapper.origin + vector


def get_sorted_node_types(types):
    """
    Sort by categories, then alphabetically. Insert separators in list.
    """
    category_order = (
        LOAD_CATEGORY, MANIPULATE_CATEGORY, DISPLAY_CATEGORY,
        DASHBOARD_CATEGORY, BACKDROP_CATEGORY)
    categories_types = {c: [] for c in category_order}
    for name, cfg in types.items():
        categories_types[cfg['type'].category].append(name)
    types_list = []
    for types in categories_types.values():
        types_list.extend(sorted(types))
        types_list.append('_separator')
    types_list.pop()
    return types_list
