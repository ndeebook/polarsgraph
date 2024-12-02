import polars as pl
from PySide6 import QtWidgets, QtCore

from polarsgraph.nodes import BLUE as DEFAULT_COLOR
from polarsgraph.graph import MANIPULATE_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget


class ATTR:
    NAME = 'name'
    COLUMNS_ORDER = 'columns_order'


class ReorderNode(BaseNode):
    type = 'reorder'
    category = MANIPULATE_CATEGORY
    inputs = 'table',
    outputs = 'table',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

    def _build_query(self, tables):
        df: pl.LazyFrame = tables[0]

        column_order = self[ATTR.COLUMNS_ORDER]
        if column_order:
            df = df.select(column_order)

        self.tables['table'] = df


class ReorderSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        self.input_table = None

        reset_button = QtWidgets.QPushButton(
            'Reset list',
            clicked=lambda: self.populate_lists(reset=True))
        self.column_order_widget = ReorderableListWidget()
        self.column_order_widget.order_changed.connect(
            self.handle_columns_change)

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(reset_button)
        layout.addWidget(self.column_order_widget)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]

        self.name_edit.setText(node[ATTR.NAME])

        self.populate_lists()

        self.blockSignals(False)

    def populate_lists(self, reset=False):
        if self.input_table is None:
            return self.column_order_widget.clear()

        columns = self.node[ATTR.COLUMNS_ORDER]
        all_columns = self.input_table.collect_schema().names()

        if reset or not columns:
            columns = all_columns
        self.column_order_widget.set_items(columns)

        missing_columns = [c for c in all_columns if c not in columns]
        self.column_order_widget.set_deleted_items(missing_columns)
        if reset:
            self.node[ATTR.COLUMNS_ORDER] = all_columns
            self.emit_changed()

    def handle_columns_change(self, items):
        self.node[ATTR.COLUMNS_ORDER] = items
        self.emit_changed()


class ReorderableListWidget(QtWidgets.QWidget):
    order_changed = QtCore.Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Widgets
        self.order_list_widget = DragDropListWidget()
        self.order_list_widget.order_changed.connect(self.emit_order)
        self.order_list_widget.item_double_clicked.connect(self.delete_item)
        self.delete_list_widget = DragDropListWidget()
        self.delete_list_widget.order_changed.connect(self.emit_order)
        self.delete_list_widget.item_double_clicked.connect(self.undelete_item)

        self.up_button = QtWidgets.QPushButton('Move Up')
        self.up_button.clicked.connect(self.move_up)
        self.down_button = QtWidgets.QPushButton('Move Down')
        self.down_button.clicked.connect(self.move_down)
        self.delete_button = QtWidgets.QPushButton('Delete')
        self.delete_button.clicked.connect(self.delete_item)
        self.undelete_button = QtWidgets.QPushButton('Restore')
        self.undelete_button.clicked.connect(self.undelete_item)

        # Layouts
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.up_button)
        button_layout.addWidget(self.down_button)
        button_layout.addWidget(self.delete_button)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(QtWidgets.QLabel('New Columns Order:'))
        main_layout.addWidget(self.order_list_widget)
        main_layout.addLayout(button_layout)
        main_layout.addWidget(QtWidgets.QLabel('Deleted Columns:'))
        main_layout.addWidget(self.delete_list_widget)
        main_layout.addWidget(self.undelete_button)

    def set_items(self, items):
        self.order_list_widget.clear()
        self.order_list_widget.addItems(items)

    def set_deleted_items(self, items):
        self.delete_list_widget.clear()
        self.delete_list_widget.addItems(sorted(items))

    def items(self):
        return [
            self.order_list_widget.item(i).text()
            for i in range(self.order_list_widget.count())]

    def emit_order(self):
        items = self.items()
        self.order_changed.emit(items)

    def move_up(self):
        current_row = self.order_list_widget.currentRow()
        if current_row > 0:
            item = self.order_list_widget.takeItem(current_row)
            self.order_list_widget.insertItem(current_row - 1, item)
            self.order_list_widget.setCurrentRow(current_row - 1)
        self.emit_order()

    def move_down(self):
        current_row = self.order_list_widget.currentRow()
        if current_row < self.order_list_widget.count() - 1:
            item = self.order_list_widget.takeItem(current_row)
            self.order_list_widget.insertItem(current_row + 1, item)
            self.order_list_widget.setCurrentRow(current_row + 1)
        self.emit_order()

    def delete_item(self):
        current_row = self.order_list_widget.currentRow()
        if current_row != -1:
            item = self.order_list_widget.takeItem(current_row)
            self.delete_list_widget.addItem(item)
        self.emit_order()

    def undelete_item(self):
        current_row = self.delete_list_widget.currentRow()
        if current_row != -1:
            item = self.delete_list_widget.takeItem(current_row)
            self.order_list_widget.addItem(item)
        self.emit_order()


class DragDropListWidget(QtWidgets.QListWidget):
    order_changed = QtCore.Signal()
    item_double_clicked = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)

    def dropEvent(self, event):
        if event.source() == self:
            super().dropEvent(event)
        else:
            self.addItem(event.source().currentItem().text())
            event.accept()
        # QTimer.singleShot => make sure List widget is updated and that
        # .items() will return the updated list
        QtCore.QTimer.singleShot(0, self.order_changed.emit)

    def mouseDoubleClickEvent(self, event):
        self.item_double_clicked.emit()
        return super().mouseDoubleClickEvent(event)
