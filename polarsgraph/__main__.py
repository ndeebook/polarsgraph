import logging
import argparse

from PySide6 import QtCore, QtWidgets

from polarsgraph.main import GRAPH_SETTINGS_KEY, PolarsGraph
from polarsgraph.log import logger


example_graph = {
    'Load1': dict(
        type='load',
        inputs=None,
        position=QtCore.QPointF(100, 50),
    ),
    'Join1': dict(
        type='join',
        inputs=[['Load1', 0], None],
        position=QtCore.QPointF(400, 200),
    ),
    'Derive1': dict(
        type='derive',
        inputs=[['Join1', 0]],
        position=QtCore.QPointF(300, 300),
    ),
    GRAPH_SETTINGS_KEY: dict(origin=(300, 200))
}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--example', action='store_true', default=False)
    parser.add_argument(
        '--log-level', default='WARNING', type=str.lower,
        choices=['debug', 'info', 'warning', 'error', 'critical'])
    args = parser.parse_args()

    graph = example_graph if args.example else None
    logger.setLevel(getattr(logging, args.log_level.upper()))

    app = QtWidgets.QApplication([])
    viewport = PolarsGraph(graph)
    viewport.show()
    app.exec()
