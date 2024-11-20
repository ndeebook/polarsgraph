from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt


GRID_COLOR = QtGui.QColor('#333333')

INACTIVE_COLOR = QtGui.QColor('#666666')
INACTIVE_COLOR_TRANSPARENT = QtGui.QColor('#666666')
INACTIVE_COLOR_TRANSPARENT.setAlpha(100)

ACTIVE_COLOR = QtGui.QColor(5, 175, 75)
ACTIVE_COLOR_TRANSPARENT = QtGui.QColor(5, 175, 75)
ACTIVE_COLOR_TRANSPARENT.setAlpha(100)


class DashboardLayoutWidget(QtWidgets.QWidget):
    layout_changed = QtCore.Signal(dict)

    def __init__(self, settings=None):
        super().__init__()

        # Widgets
        settings = settings or {}
        grid_width = settings.get('grid_width', 16)
        grid_height = settings.get('grid_height', 16)
        positions = settings.get('positions')
        if positions:
            positions = {
                get_widget_label(i): rect for i, rect in enumerate(positions)}

        self.grid_widget = GridWidget(
            grid_width, grid_height, )
        self.grid_widget.layout_changed.connect(self.emit_layout_updated)

        self.grid_width_spinbox = QtWidgets.QSpinBox()
        self.grid_width_spinbox.setRange(1, 100)
        self.grid_width_spinbox.setValue(grid_width)
        self.grid_width_spinbox.setPrefix('Width: ')

        self.grid_height_spinbox = QtWidgets.QSpinBox()
        self.grid_height_spinbox.setRange(1, 100)
        self.grid_height_spinbox.setValue(grid_height)
        self.grid_height_spinbox.setPrefix('Height: ')

        self.rect_selector = QtWidgets.QComboBox()
        self.rect_selector.currentIndexChanged.connect(
            self.grid_widget.change_current_rect)

        add_rect_button = QtWidgets.QPushButton('Add Widget')
        add_rect_button.clicked.connect(self.add_rectangle)

        remove_rect_button = QtWidgets.QPushButton('Remove Widget')
        remove_rect_button.clicked.connect(self.remove_rectangle)

        # Layout
        self.grid_width_spinbox.valueChanged.connect(self.set_grid_width)
        self.grid_height_spinbox.valueChanged.connect(self.set_grid_height)

        # Layout
        grid_size_layout = QtWidgets.QHBoxLayout()
        grid_size_layout.setContentsMargins(0, 0, 0, 0)
        grid_size_layout.setSpacing(2)
        grid_size_layout.addWidget(self.grid_width_spinbox)
        grid_size_layout.addWidget(self.grid_height_spinbox)

        add_remove_layout = QtWidgets.QHBoxLayout()
        add_remove_layout.setContentsMargins(0, 0, 0, 0)
        add_remove_layout.setSpacing(2)
        add_remove_layout.addWidget(add_rect_button)
        add_remove_layout.addWidget(remove_rect_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(2)
        layout.addLayout(grid_size_layout)
        layout.addWidget(self.rect_selector)
        layout.addLayout(add_remove_layout)
        layout.addWidget(self.grid_widget)
        layout.addStretch()

    def emit_layout_updated(self):
        data = dict(
            grid_width=self.grid_widget.grid_width,
            grid_height=self.grid_widget.grid_height,
            widgets_rectangles=self.grid_widget.rectangles)
        self.layout_changed.emit(data)

    def clear(self):
        self.rect_selector.clear()
        self.grid_widget.rectangles.clear()

    def add_rectangle(self, rect: list = None):
        index = len(self.grid_widget.rectangles)
        rect = rect or (0, 0, 1, 1)
        self.grid_widget.rectangles[index] = QtCore.QRect(*rect)
        self.rect_selector.addItem(get_widget_label(index))
        self.rect_selector.setCurrentIndex(index)
        self.grid_widget.update()

    def remove_rectangle(self):
        widget_index = self.rect_selector.currentIndex()
        self.grid_widget.rectangles.pop(widget_index)
        # Dont allow non-continuous indexes:
        self.grid_widget.rectangles = {
            i: rect for i, rect in
            enumerate(self.grid_widget.rectangles.values())}

        # Update widget
        self.grid_widget.update()

        # Fill combo
        self.rect_selector.clear()
        self.rect_selector.addItems([
            get_widget_label(i) for i in
            range(len(self.grid_widget.rectangles))])

        # Emit update
        self.emit_layout_updated()

    def set_grid_width(self, size):
        self.grid_widget.grid_width = size
        self.emit_layout_updated()
        self.grid_widget.update_grid_size()

    def set_grid_height(self, size):
        self.grid_widget.grid_height = size
        self.emit_layout_updated()
        self.grid_widget.update_grid_size()


class GridWidget(QtWidgets.QWidget):
    layout_changed = QtCore.Signal()

    def __init__(self, grid_width=16, grid_height=16, rectangles=None):
        super().__init__()

        self.setMinimumSize(300, 200)

        self.current_rect_index = None

        self.grid_width = grid_width
        self.grid_height = grid_height
        self.rectangles = rectangles or {}

        self.moved = False
        self.selection_start = None
        self.selection_rect = QtCore.QRect()

        self.update_grid_size()

    def update_grid_size(self):
        self.cell_width = self.width() / self.grid_width
        self.cell_height = self.height() / self.grid_height
        self.update()

    def resizeEvent(self, event):
        self.update_grid_size()
        return super().resizeEvent(event)

    def change_current_rect(self, index):
        self.current_rect_index = index
        self.selection_rect = self.rectangles.get(
            self.current_rect_index, QtCore.QRect())
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)

        # Draw the grid
        painter.setPen(QtGui.QPen(GRID_COLOR, 1))
        for x in range(self.grid_width):
            x *= self.cell_width
            painter.drawLine(x, 0, x, self.height())
        for y in range(self.grid_height):
            y *= self.cell_height
            painter.drawLine(0, y, self.width(), y)
        painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

        # Draw all rects
        font = painter.font()
        font.setPointSize(font.pointSize() * 2)
        painter.setFont(font)
        for index, rect in self.rectangles.items():
            if index == self.current_rect_index:
                painter.setPen(QtGui.QPen(ACTIVE_COLOR, 1))
                painter.setBrush(
                    QtGui.QBrush(ACTIVE_COLOR_TRANSPARENT))
            else:
                painter.setPen(QtGui.QPen(INACTIVE_COLOR, 1))
                painter.setBrush(QtGui.QBrush(INACTIVE_COLOR_TRANSPARENT))
            rect = scale_rect(rect, self.cell_width, self.cell_height)
            painter.drawRect(rect)
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter, str(index + 1))

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton:
            return
        self.moved = False
        self.selection_start = QtCore.QPoint(
            *self.coord_to_cell(event.pos()))
        # if self.current_rect_index in self.rectangles:
        #     self.rectangles[self.current_rect_index] = QtCore.QRect(
        #         self.selection_start, self.selection_start)
        # elif self.current_rect_index is not None:
        #     self.rectangles[self.current_rect_index] = QtCore.QRect(
        #         self.selection_start, QtCore.QPoint(
        #             self.cell_width, self.cell_height))
        if self.current_rect_index is not None:
            self.selection_rect = self.rectangles[self.current_rect_index]
        self.update()

    def mouseMoveEvent(self, event):
        if self.selection_start is None:
            return
        if self.current_rect_index is None:
            return
        pos = self.coord_to_cell(event.pos())
        grid_rect = points_to_rect(self.selection_start, QtCore.QPoint(*pos))
        self.rectangles[self.current_rect_index] = grid_rect
        self.moved = True
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.layout_changed.emit()
            self.selection_start = None
            if not self.moved:
                # Select rect under cursor
                pos = event.pos()
                for index, rect in self.rectangles.items():
                    rect = scale_rect(rect, self.cell_width, self.cell_height)
                    if rect.contains(pos):
                        self.current_rect_index = index
                        return self.update()

    def coord_to_cell(self, pos):
        return int(pos.x() / self.cell_width), int(pos.y() / self.cell_height)


def get_widget_label(index):
    return f'Widget {index + 1}'


def points_to_rect(p1, p2):
    x1, x2 = p1.x(), p2.x()
    if x1 > x2:
        x2, x1 = x1, x2
    y1, y2 = p1.y(), p2.y()
    if y1 > y2:
        y2, y1 = y1, y2
    return QtCore.QRect(x1, y1, x2 - x1 + 1, y2 - y1 + 1)


def scale_rect(rect: QtCore.QRect, x_scale, y_scale) -> QtCore.QRect:
    return QtCore.QRect(
        rect.x() * x_scale,
        rect.y() * y_scale,
        rect.width() * x_scale,
        rect.height() * y_scale)


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    widget = DashboardLayoutWidget()
    widget.show()
    app.exec()
