from PySide6 import QtWidgets, QtCore

from polarsgraph.graph import (
    DISPLAY_CATEGORY, DASHBOARD_CATEGORY, build_node_query)
from polarsgraph.nodes.base import BaseNode


DISPLAY_CATEGORIES = DISPLAY_CATEGORY, DASHBOARD_CATEGORY


class DisplayWidget(QtWidgets.QWidget):
    build_requested = QtCore.Signal(str)

    def __init__(self, graph):
        super().__init__()

        self.graph = graph
        self.node: BaseNode = None

        # Widgets
        self.node_combo = QtWidgets.QComboBox(minimumWidth=100)
        self.node_combo.currentTextChanged.connect(self.set_display_node)

        # Layout
        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.addWidget(self.node_combo)
        toolbar.addStretch()

        self.content_layout = QtWidgets.QVBoxLayout()

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(toolbar)
        main_layout.addLayout(self.content_layout)

        self.stretch = QtWidgets.QSpacerItem(
            10, 10,
            QtWidgets.QSizePolicy.Minimum,
            QtWidgets.QSizePolicy.Expanding)
        self.content_layout.addItem(self.stretch)

    def update_content(self):
        if not self.node:
            return
        if self.node['name'] not in self.graph:  # display was deleted
            self.node = None
            return
        success = build_node_query(self.graph, self.node['name'])
        if self.node.type == 'dashboard':
            # First, make sur we remove all Widgets, otherwise they will
            # still be visible avec disconnecting them from Dashboard
            for widget in self.node.widgets:
                self.content_layout.addWidget(widget)
                widget.setVisible(False)
            # Now, update layout & visible widgets:
            self.node.update_board(self.graph)
        elif not success:
            self.node.clear()

    def set_display_node(self, node_name: str):
        # Update settings
        self.node_combo.blockSignals(True)
        self.node_combo.setCurrentText(node_name)
        self.node_combo.blockSignals(False)

        # Clear display layout
        if self.node:
            self.node.display_widget.setVisible(False)
        if not node_name:
            self.content_layout.addItem(self.stretch)
            return
        self.content_layout.removeItem(self.stretch)

        # Display (Unhide or add) Node's Display Widget
        self.node = self.graph[node_name]
        display_widget: DisplayWidget = self.node.display_widget
        display_widget.setVisible(True)
        display_widget.set_board_mode(False)
        self.content_layout.addWidget(display_widget)

        # Update content
        self.update_content()

    @property
    def node_name(self):
        return self.node['name'] if self.node else None

    def fill_combo(self):
        self.node_combo.blockSignals(True)
        current_name = self.node_name
        self.node_combo.clear()
        display_nodes = [
            n for n in self.graph if
            self.graph[n].category in DISPLAY_CATEGORIES]
        self.node_combo.addItems(['', *sorted(display_nodes)])
        if current_name and current_name in display_nodes:
            self.node_combo.setCurrentText(current_name)
        self.node_combo.blockSignals(False)

    def set_graph(self, graph):
        self.graph = graph
        self.fill_combo()
        if self.node:
            node_name = self.node['name']
            if node_name in self.graph:
                self.set_display_node(node_name)
            else:
                self.set_display_node(None)
