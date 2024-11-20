from PySide6 import QtCore


class ViewportMapper():
    """
    Used to translate/map between:
        - abstract/data/units coordinates
        - viewport/display/pixels coordinates
    """
    def __init__(self, zoom=1, origin=None, viewsize=None):
        self.zoom = zoom
        self.origin = (
            QtCore.QPointF(*origin) if origin else QtCore.QPointF(0, 0))
        # We need the viewport size to be able to center the view or to
        # automatically set zoom from selection:
        self.viewsize = viewsize or QtCore.QSize(300, 300)

    def to_viewport(self, value):
        return value * self.zoom

    def to_units(self, pixels):
        return pixels / self.zoom

    def to_viewport_coords(self, units_point):
        return QtCore.QPointF(
            self.to_viewport(units_point.x()) - self.origin.x(),
            self.to_viewport(units_point.y()) - self.origin.y())

    def to_units_coords(self, pixels_point):
        return QtCore.QPointF(
            self.to_units(pixels_point.x() + self.origin.x()),
            self.to_units(pixels_point.y() + self.origin.y()))

    def to_viewport_rect(self, units_rect):
        return QtCore.QRectF(
            (units_rect.left() * self.zoom) - self.origin.x(),
            (units_rect.top() * self.zoom) - self.origin.y(),
            units_rect.width() * self.zoom,
            units_rect.height() * self.zoom)

    def to_units_rect(self, pixels_rect):
        top_left = self.to_units_coords(pixels_rect.topLeft())
        width = self.to_units(pixels_rect.width())
        height = self.to_units(pixels_rect.height())
        return QtCore.QRectF(top_left.x(), top_left.y(), width, height)

    def zoomin(self, factor=10.0):
        self.zoom += self.zoom * factor
        self.zoom = min(self.zoom, 5.0)

    def zoomout(self, factor=10.0):
        self.zoom -= self.zoom * factor
        self.zoom = max(self.zoom, .025)

    def center_on_point(self, units_center):
        """Given current zoom and viewport size, set the origin point."""
        self.origin = QtCore.QPointF(
            units_center.x() * self.zoom - self.viewsize.width() / 2,
            units_center.y() * self.zoom - self.viewsize.height() / 2)

    def focus(self, units_rect):
        self.zoom = min([
            float(self.viewsize.width()) / units_rect.width(),
            float(self.viewsize.height()) / units_rect.height()])
        self.zoom *= 0.8
        self.zoom = max(self.zoom, .1)
        self.center_on_point(units_rect.center())
