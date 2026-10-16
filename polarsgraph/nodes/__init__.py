from PySide6 import QtGui

BLACK = QtGui.QColor(5, 5, 5)
GREEN = QtGui.QColor(5, 175, 75)
BLUE = QtGui.QColor(44, 112, 201)
PINK = QtGui.QColor(166, 75, 132)
ORANGE = QtGui.QColor(207, 110, 50)
PURPLE = QtGui.QColor(41, 20, 199)
GRAY = QtGui.QColor(63, 63, 63)
LIGHT_GRAY = QtGui.QColor(111, 111, 111)


OPERATOR_MAGIC_METHODS = {
    '+': '__add__',
    '-': '__sub__',
    '*': '__mul__',
    '/': '__truediv__',
    '//': '__floordiv__',
    '%': '__mod__',
    '**': '__pow__',
    '&': '__and__',
    '|': '__or__',
    '^': '__xor__',
    '~': '__invert__',
    '==': '__eq__',
    # '!=': '__ne__',
    '!=': 'ne_missing',  # dont always drop null values
    '<': '__lt__',
    '<=': '__le__',
    '>': '__gt__',
    '>=': '__ge__',
    'in': '__contains__',
    '+=': '__iadd__',
    '-=': '__isub__',
    '*=': '__imul__',
    '/=': '__itruediv__',
    '//=': '__ifloordiv__',
    '%=': '__imod__',
    '**=': '__ipow__',
    '&=': '__iand__',
    '|=': '__ior__',
    '^=': '__ixor__',
}
