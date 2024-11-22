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
            clicked=lambda: self.populate_columns_text(reset=True))
        self.column_order_edit = QtWidgets.QPlainTextEdit()
        self.column_order_edit.textChanged.connect(self.handle_columns_change)
        self.missing_columns_edit = QtWidgets.QPlainTextEdit()
        self.missing_columns_edit.setReadOnly(True)

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)
        layout.addWidget(reset_button)
        layout.addWidget(QtWidgets.QLabel('New Columns Order:'))
        layout.addWidget(self.column_order_edit)
        layout.addWidget(QtWidgets.QLabel('Deleted Columns:'))
        layout.addWidget(self.missing_columns_edit)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.input_table: pl.LazyFrame = input_tables[0]

        self.name_edit.setText(node[ATTR.NAME])

        self.populate_columns_text()
        self.update_missing_columns()

        self.blockSignals(False)

    def populate_columns_text(self, reset=False):
        if self.input_table is None:
            return self.column_order_edit.clear()

        columns = self.node[ATTR.COLUMNS_ORDER]
        if reset or not columns:
            columns = self.input_table.collect_schema().names()
        self.column_order_edit.setPlainText('\n'.join(columns))

    def handle_columns_change(self):
        columns_order = [
            col.strip() for col
            in self.column_order_edit.toPlainText().splitlines()
            if col.strip()]
        self.node[ATTR.COLUMNS_ORDER] = columns_order
        self.update_missing_columns()
        self.emit_changed()

    def update_missing_columns(self):
        if self.input_table is None:
            return self.column_order_edit.clear()

        existing_columns = self.input_table.collect_schema().names()
        input_columns = self.column_order_edit.toPlainText().splitlines()
        missing_columns = [
            col for col in existing_columns if col not in input_columns]
        self.missing_columns_edit.setPlainText('\n'.join(missing_columns))


# TODO: use this:
class ReorderableListWidget(QtWidgets.QWidget):
    def __init__(self, items, parent=None):
        super().__init__(parent)

        # Widgets
        self.list_widget = DragDropListWidget()
        self.list_widget.addItems(items)

        self.up_button = QtWidgets.QPushButton('Move Up')
        self.up_button.clicked.connect(self.move_up)
        self.down_button = QtWidgets.QPushButton('Move Down')
        self.down_button.clicked.connect(self.move_down)
        self.delete_button = QtWidgets.QPushButton('Delete')
        self.delete_button.clicked.connect(self.delete_item)

        # Layouts
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.up_button)
        button_layout.addWidget(self.down_button)
        button_layout.addWidget(self.delete_button)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.list_widget)
        main_layout.addLayout(button_layout)

    def move_up(self):
        current_row = self.list_widget.currentRow()
        if current_row > 0:
            item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row - 1, item)
            self.list_widget.setCurrentRow(current_row - 1)

    def move_down(self):
        current_row = self.list_widget.currentRow()
        if current_row < self.list_widget.count() - 1:
            item = self.list_widget.takeItem(current_row)
            self.list_widget.insertItem(current_row + 1, item)
            self.list_widget.setCurrentRow(current_row + 1)

    def delete_item(self):
        current_row = self.list_widget.currentRow()
        if current_row != -1:
            self.list_widget.takeItem(current_row)


class DragDropListWidget(QtWidgets.QListWidget):
    item_deleted = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSelectionMode(QtWidgets.QListWidget.SingleSelection)
        self.setDragDropMode(QtWidgets.QListWidget.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)

    def dropEvent(self, event):
        if event.source() != self:
            row = self.currentRow()
            self.takeItem(row)
        else:
            super().dropEvent(event)
