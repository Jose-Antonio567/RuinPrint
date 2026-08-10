"""Bounded undo/redo history for processing-settings snapshots."""

from copy import deepcopy


class EditHistory:
    def __init__(self, limit: int = 100) -> None:
        self.limit = limit
        self.undo_stack: list[dict] = []
        self.redo_stack: list[dict] = []

    def record(self, before: dict, after: dict) -> None:
        if before == after:
            return
        self.undo_stack.append(deepcopy(before))
        self.undo_stack = self.undo_stack[-self.limit:]
        self.redo_stack.clear()

    def undo(self, current: dict) -> dict | None:
        if not self.undo_stack:
            return None
        self.redo_stack.append(deepcopy(current))
        return self.undo_stack.pop()

    def redo(self, current: dict) -> dict | None:
        if not self.redo_stack:
            return None
        self.undo_stack.append(deepcopy(current))
        return self.redo_stack.pop()

    def clear(self) -> None:
        self.undo_stack.clear(); self.redo_stack.clear()
