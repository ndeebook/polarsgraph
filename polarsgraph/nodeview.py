from functools import partial

from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtCore import Qt

from polarsgraph.graph import (
    LOAD_CATEGORY, MANIPULATE_CATEGORY, DISPLAY_CATEGORY, DASHBOARD_CATEGORY,
    CATEGORY_INPUT_TYPE, CATEGORY_OUTPUT_TYPE, DYNAMIC_PLUG_COUNT)
from polarsgraph.nodes.base import BaseNode
from polarsgraph.viewportmapper import ViewportMapper


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

    def set_graph(self, graph):
        self.graph = graph
        self.nodes_bboxes.clear()
        self.plugs_bboxes.clear()
        self.selected_names.clear()
        self.update()

    def rename_node(self, old_name, new_name):
        # node already renamed in the Graph itself

        # rename in bboxes:
        for dict_ in (self.nodes_bboxes, self.plugs_bboxes):
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

        # Draw nodes
        for name, node in self.graph.items():
            self.plugs_bboxes[name], self.nodes_bboxes[name] = paint_node(
                painter, self.viewportmapper, node,
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

    def select(self, position, modifiers):
        under_cursor = self.get_object_under_cursor(position)
        self.select_position = position
        shift = modifiers & Qt.KeyboardModifier.ShiftModifier
        ctrl = modifiers & Qt.KeyboardModifier.ControlModifier
        if under_cursor is None:
            if not shift:
                self.selected_names = []
            return
        name = under_cursor['name']
        if under_cursor['type'] == 'node':
            if name not in self.selected_names:  # dont unselect other nodes
                if shift or ctrl:
                    self.selected_names.append(name)
                else:
                    self.selected_names = [name]
                self.nodes_selected.emit(self.selected_names)
            elif ctrl:
                self.selected_names.remove(name)
                self.nodes_selected.emit(self.selected_names)
            for name in self.selected_names:
                self.move_start_positions[name] = self.graph[name]['position']
        self.dragged_object = under_cursor

    def drag(self, event):
        self.drag_position = event.position()
        if self.dragged_object and self.dragged_object['type'] == 'node':
            # Move nodes (not connecting plug, not dragging selection rect)
            pos_offset = self.select_position - self.drag_position
            pos_offset /= self.viewportmapper.zoom
            for name in self.selected_names or [self.dragged_object['name']]:
                self.graph[name]['position'] = (
                    self.move_start_positions[name] - pos_offset)
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
            sel_rect = QtCore.QRectF(self.select_position, self.drag_position)
            shift = modifiers & Qt.KeyboardModifier.ShiftModifier
            nodes = [
                name for name, rect in self.nodes_bboxes.items()
                if sel_rect.intersects(rect)]
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
        for name in nodes:
            self.nodes_bboxes.pop(name)
            self.plugs_bboxes.pop(name)
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

    # Draw node rectangle
    rect = QtCore.QRectF(x, y, node_width, node_height)
    painter.setBrush(NODE_COLOR)
    if selected:
        painter.setPen(QtGui.QPen(Qt.white, thickness))
    else:
        painter.setPen(QtGui.QPen(Qt.black, thickness))
    painter.drawRoundedRect(rect, round_size, round_size)

    # Draw the title at the top
    painter.setFont(QtGui.QFont('Verdana', font_size))
    title_rect = QtCore.QRectF(x, y, node_width, title_height)
    painter.setBrush(node['color'])
    painter.drawRoundedRect(title_rect, round_size, round_size)
    if node.error:
        painter.setPen(QtGui.QPen(Qt.red, thickness))
    else:
        painter.setPen(QtGui.QPen(Qt.white, thickness))
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
        DASHBOARD_CATEGORY)
    categories_types = {c: [] for c in category_order}
    for name, cfg in types.items():
        categories_types[cfg['type'].category].append(name)
    types_list = []
    for types in categories_types.values():
        types_list.extend(sorted(types))
        types_list.append('_separator')
    types_list.pop()
    return types_list
