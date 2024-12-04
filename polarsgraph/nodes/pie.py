import polars as pl
from PySide6 import QtWidgets, QtGui, QtCharts
from PySide6.QtCore import Qt

from polarsgraph.nodes import GREEN as DEFAULT_COLOR
from polarsgraph.graph import DISPLAY_CATEGORY
from polarsgraph.nodes.base import BaseNode, BaseSettingsWidget, BaseDisplay


TABLE_HANDLE_CSS = 'QScrollBar::handle:vertical {min-height: 30px;}'


class ATTR:
    NAME = 'name'


class PieNode(BaseNode):
    type = 'pie'
    category = DISPLAY_CATEGORY
    inputs = 'table',
    outputs = 'widget',
    default_color = DEFAULT_COLOR

    def __init__(self, settings=None):
        super().__init__(settings)

        self._display_widget = None

    def _build_query(self, tables):
        self.tables['table'] = tables[0]
        # Update display
        if not self.display_widget:
            return
        self.display_widget.set_table(tables[0])

    def clear(self):
        pass

    @property
    def display_widget(self):
        if not self._display_widget:
            self._display_widget = PieDisplay()
        return self._display_widget


class PieSettingsWidget(BaseSettingsWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        ...

        # Layout
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow(ATTR.NAME.title(), self.name_edit)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form_layout)

    def set_node(self, node, input_tables):
        self.blockSignals(True)
        self.node = node
        self.name_edit.setText(node[ATTR.NAME])
        self.blockSignals(False)


class PieDisplay(BaseDisplay):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.node: PieNode = None
        self._resizing = False

        # Widgets
        self.chart_view = QtCharts.QChartView()

        # Layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.chart_view)

    def set_table(self, table: pl.LazyFrame):
        if table is None:
            return
        table = table.collect(stream=True)
        make_chart(self.chart_view, table, self)

    def get_pixmap(self):
        pixmap = QtGui.QPixmap(self.chart_view.size())
        self.chart_view.render(pixmap)
        return pixmap

    def save_image(self):
        filepath, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, 'Save spreadsheet', '', '*.png')
        if not filepath:
            return
        self.get_pixmap().save(filepath)

    def image_to_clipboard(self):
        QtWidgets.QApplication.clipboard().setPixmap(self.get_pixmap())


def make_chart(
        chart_view: QtCharts.QChartView, dataframe: pl.DataFrame, parent):
    # Create the chart
    chart = QtCharts.QChart()
    chart_view.setChart(chart)
    chart_view.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

    # Create the Pie Series
    series = QtCharts.QPieSeries()

    # Sum data for each column to calculate their share in the pie
    value_column = dataframe.select(dataframe.columns[1])
    total = value_column.sum()[0, 0]

    for values in dataframe.iter_rows():
        label, value, *_ = values
        ratio = value / total
        slice_ = series.append(label, ratio)
        slice_.setLabelVisible(True)

    chart.addSeries(series)

    # Set the legend position and style
    chart.legend().setVisible(True)
    chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)

    # Set the chart title
    chart.setTitle('Pie Chart Example')

    # Apply the parent widget's palette to chart styles
    palette = parent.palette()
    background_color = palette.color(QtGui.QPalette.Window)
    chart.setBackgroundBrush(QtGui.QBrush(background_color))
    text_color = palette.color(QtGui.QPalette.WindowText)
    chart.setTitleBrush(QtGui.QBrush(text_color))

    # Customize the legend font color
    legend = chart.legend()
    # legend.setLabelColor(text_color)
    legend.hide()
