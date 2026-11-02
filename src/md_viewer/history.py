"""Back/forward history of documents shown in one window. Pure (no GTK)."""

from __future__ import annotations


class History:
    """Browser-style history: visiting a new entry drops anything ahead of the cursor."""

    def __init__(self) -> None:
        self._entries: list[str] = []
        self._index = -1

    @property
    def current(self) -> str | None:
        return self._entries[self._index] if self._index >= 0 else None

    def visit(self, uri: str) -> None:
        if uri == self.current:
            return
        del self._entries[self._index + 1 :]
        self._entries.append(uri)
        self._index += 1

    def can_go_back(self) -> bool:
        return self._index > 0

    def can_go_forward(self) -> bool:
        return self._index < len(self._entries) - 1

    def back(self) -> str | None:
        if not self.can_go_back():
            return None
        self._index -= 1
        return self.current

    def forward(self) -> str | None:
        if not self.can_go_forward():
            return None
        self._index += 1
        return self.current
