"""
Brute force Undo stack holding the entire state of the document, not the
modification steps.
"""


class UndoStack():
    def __init__(self, max_size=300):
        self.max_size = max_size
        self._stack = []
        self.index = 0

    @property
    def size(self):
        return len(self._stack)

    def add(self, item):
        # Remove whatever was re-done
        while self.index:
            self._stack.pop(0)
            self.index -= 1

        # Add item
        self._stack.insert(0, item)

        # Remove old items
        while self.size > self.max_size:
            self._stack.pop()

    def undo(self):
        if not self._stack:
            return
        self.index = min(self.size - 1, self.index + 1)
        return self._stack[self.index]

    def redo(self):
        if not self._stack:
            return
        self.index = max(0, self.index - 1)
        return self._stack[self.index]


if __name__ == '__main__':
    stack = UndoStack()
    stack.undo()
    stack.redo()
    stack.add(1)
    assert stack.undo() == 1
    stack.add(2)
    assert stack.index == 0
    stack.add(3)
    stack.add(4)
    assert stack._stack == [4, 3, 2, 1]
    assert stack.undo() == 3
    assert stack.undo() == 2
    assert stack.redo() == 3
    assert stack.redo() == 4
    assert stack.redo() == 4
    assert stack.redo() == 4
    assert stack.undo() == 3
    assert stack.undo() == 2
    assert stack.undo() == 1
    assert stack.undo() == 1
    stack.add('a')
    assert stack._stack == ['a', 1]
