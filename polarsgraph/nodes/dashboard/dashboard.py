from PySide6 import QtWidgets, QtGui, QtCore

from polarsgraph.graph import (
    DASHBOARD_CATEGORY, DYNAMIC_PLUG_COUNT, get_input_nodes,
    build_node_query)
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget, BaseDisplay

from polarsgraph.nodes.dashboard.layoutwidget import DashboardLayoutWidget


TABLE_HANDLE_CSS = 'QScrollBar::handle:vertical {min-height: 30px;}'


class ATTR:
    NAME = 'name'
    GRID_WIDTH = 'grid_width'
    GRID_HEIGHT = 'grid_height'
    SPACING = 'spacing'
    MARGINS = 'margins'
    WIDGETS_RECTANGLES = 'widgets_rectangles'


class DashboardNode(BaseNode):
    type = 'dashboard'
    category = DASHBOARD_CATEGORY
    inputs = DYNAMIC_PLUG_COUNT
    inputs_prefix = 'widget'
    outputs = ()
    default_color = QtGui.QColor(5, 175, 75)

    def __init__(self, settings=None):
        super().__init__(settings)

        self._display_widget = None
        self._trash_layout = QtWidgets.QVBoxLayout()

    def _build_query(self, tables):
        for i, table in enumerate(tables):
            self.tables[f'{self.plug_name(i)}'] = table

    def plug_name(self, i):
        return f'{self.inputs_prefix}{i + 1}'

    def update_board(self, graph):
        layout = self.display_widget.grid

        # Spacing & margins
        layout.setSpacing(self[ATTR.SPACING])
        m = self[ATTR.MARGINS]
        layout.setContentsMargins(m, m, m, m)
        layout.grid_width = self[ATTR.GRID_WIDTH]
        layout.grid_height = self[ATTR.GRID_HEIGHT]

        # Widgets
        layout.clear()
        for node in get_input_nodes(graph, self['name']):
            display_widget: BaseDisplay = node.display_widget
            layout.addWidget(display_widget)
            display_widget.setVisible(True)
            build_node_query(graph, node['name'])
        layout.rects = self[ATTR.WIDGETS_RECTANGLES]

    @property
    def widgets(self):
        return [i.widget() for i in self.display_widget.grid.items]

    @property
    def display_widget(self):
        if not self._display_widget:
            self._display_widget = DashboardDisplay()
        return self._display_widget


class DashboardSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.spacing_edit = QtWidgets.QSpinBox()
        self.spacing_edit.valueChanged.connect(
            lambda: self.spinbox_to_settings(self.spacing_edit, ATTR.SPACING))
        self.margins_edit = QtWidgets.QSpinBox()
        self.margins_edit.valueChanged.connect(
            lambda: self.spinbox_to_settings(self.margins_edit, ATTR.MARGINS))
        self.dashboard_layout_widget = DashboardLayoutWidget()
        self.dashboard_layout_widget.layout_changed.connect(
            self.update_dashboard_layout)

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(0)
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        form_layout.addRow(ATTR.SPACING.title(), self.spacing_edit)
        form_layout.addRow(ATTR.MARGINS.title(), self.margins_edit)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(self.dashboard_layout_widget)

    def update_dashboard_layout(self, data):
        self.node[ATTR.GRID_WIDTH] = data['grid_width']
        self.node[ATTR.GRID_HEIGHT] = data['grid_height']
        self.node[ATTR.WIDGETS_RECTANGLES] = [
            qrect_to_rect(r) for r in data['widgets_rectangles'].values()]
        self.emit_changed()

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.dashboard_layout_widget.blockSignals(True)

        self.node = node

        self.name_edit.setText(node[ATTR.NAME])
        self.margins_edit.setValue(node[ATTR.MARGINS] or 2)
        self.spacing_edit.setValue(node[ATTR.SPACING] or 2)

        self.dashboard_layout_widget.grid_width_spinbox.setValue(
            int(node[ATTR.GRID_WIDTH] or 16))
        self.dashboard_layout_widget.grid_height_spinbox.setValue(
            int(node[ATTR.GRID_HEIGHT] or 16))
        self.dashboard_layout_widget.clear()
        for rect in node[ATTR.WIDGETS_RECTANGLES]:
            self.dashboard_layout_widget.add_rectangle(rect)

        self.blockSignals(False)
        self.dashboard_layout_widget.blockSignals(False)


class DashboardDisplay(BaseDisplay):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.node_name = None
        self.grid = FixedGridLayout(self)

    def showEvent(self, event):
        self.shown.emit()
        return super().showEvent(event)


class FixedGridLayout(QtWidgets.QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.items = []
        self.rects = []

        self.grid_width = 1
        self.grid_height = 1

    def addItem(self, item):
        self.items.append(item)

    def sizeHint(self):
        return QtCore.QSize(300, 200)

    def itemAt(self, index):
        if 0 <= index < len(self.items):
            return self.items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self.items):
            return self.items.pop(index)
        return None

    def count(self):
        return len(self.items)

    def setGeometry(self, outer_rect: QtCore.QRect):
        super().setGeometry(outer_rect)

        total_width = outer_rect.width()
        total_height = outer_rect.height()
        outer_rect = outer_rect.marginsRemoved(self.contentsMargins())
        spacing = self.spacing()

        for item, (x, y, w, h) in zip(self.items, self.rects):
            x = int(x / self.grid_width * total_width)
            y = int(y / self.grid_height * total_height)
            w = int(w / self.grid_width * total_width)
            h = int(h / self.grid_height * total_height)
            if spacing:
                if x + w != total_width:
                    w -= spacing
                if y + h != total_height:
                    h -= spacing
                if x != 0:
                    x += int(spacing / 2)
                if y != 0:
                    y += int(spacing / 2)
            rect = QtCore.QRect(x, y, w, h)
            item.setGeometry(rect & outer_rect)  # remove margin

    def clear(self):
        for i in range(len(self.items)):
            self.takeAt(i)
            # # Not working:
            # item = self.takeAt(i)
            # if item:
            #     item.widget().setParent(None)
            #     item.widget().setVisible(False)
        self.items.clear()


def qrect_to_rect(qrect):
    return qrect.x(), qrect.y(), qrect.width(), qrect.height()
