"""A responsive grid that reflows its children when the window is resized."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QGridLayout, QScrollArea, QSizePolicy, QWidget


class FlowGrid(QWidget):
    """Places cards in as many columns as fit, sizing them to fill the row.

    The card width follows the available space between ``min_card_width`` and
    ``max_card_width`` so the grid looks deliberate on a narrow window and on a
    wide one, instead of leaving a ragged strip of empty space on the right.
    """

    def __init__(
        self,
        card_width: int = 180,
        spacing: int = 14,
        min_card_width: int = 128,
        max_card_width: int = 208,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.card_width = card_width
        self.spacing = spacing
        self.min_card_width = min(min_card_width, card_width)
        self.max_card_width = max(max_card_width, card_width)
        self._items: list[QWidget] = []
        self._columns = 0
        self._cell_size = 0
        self._reflowing = False
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(spacing)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    # ----------------------------------------------------------------- public
    @property
    def items(self) -> list[QWidget]:
        return list(self._items)

    def set_items(self, widgets: list[QWidget]) -> None:
        incoming = {id(widget) for widget in widgets}
        for widget in self._items:
            self._grid.removeWidget(widget)
            if id(widget) in incoming:
                continue
            # Never orphan a visible widget: ``setParent(None)`` would promote it
            # to a top level window, which is exactly the bug where every rebuilt
            # card popped up in a window of its own.
            widget.hide()
            # Filters retain cached cards under this grid; showing them again
            # must not reconstruct widgets or create native windows.
        self._items = list(widgets)
        self._columns = 0
        self._cell_size = 0
        self._reflow(force=True)

    def clear(self) -> None:
        self.set_items([])

    # ------------------------------------------------------------- internals
    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt naming
        """Never let the placed cards drive the widget's width.

        Inside a resizable scroll area a minimum width that grows with the
        number of columns makes the viewport wider on every relayout, which adds
        more columns - the grid used to run from 600px to over 11000px before the
        stack blew up.  Only the height may follow the content.
        """
        return QSize(self.min_card_width, super().minimumSizeHint().height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow()

    def _scroll_area(self) -> QScrollArea | None:
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                return parent
            parent = parent.parentWidget()
        return None

    def _available_width(self) -> int:
        area = self._scroll_area()
        if area is not None:
            # Measure the viewport and always reserve the vertical scrollbar,
            # even while it is hidden: otherwise showing it narrows the viewport,
            # which can drop a column and hide it again - an endless resize loop.
            bar = area.verticalScrollBar()
            reserved = 0 if bar.isVisible() else bar.sizeHint().width()
            return max(self.min_card_width, min(self.width(), area.viewport().width() - reserved))
        width = self.width()
        if width > 0:
            return width
        parent = self.parentWidget()
        return max(200, parent.width() - 48) if parent is not None else 800

    def _column_count(self, width: int) -> int:
        return max(1, int((width + self.spacing) // (self.card_width + self.spacing)))

    def _cell_width(self, width: int, columns: int) -> int:
        usable = width - self.spacing * (columns - 1)
        return max(self.min_card_width, min(self.max_card_width, usable // columns))

    def _reflow(self, force: bool = False) -> None:
        if self._reflowing:
            # Resizing a card can deliver a nested resize event before the outer
            # pass has finished; re-entering would recurse until the C stack ran
            # out.
            return
        self._reflowing = True
        try:
            self._reflow_once(force)
        finally:
            self._reflowing = False

    def _reflow_once(self, force: bool = False) -> None:
        width = self._available_width()
        columns = self._column_count(width)
        cell = self._cell_width(width, columns)
        if columns == self._columns and cell == self._cell_size and not force:
            return
        self._columns = columns
        self._cell_size = cell
        while self._grid.count():
            self._grid.takeAt(0)
        for index in range(self._grid.columnCount()):
            self._grid.setColumnStretch(index, 0)
        for index in range(self._grid.rowCount()):
            self._grid.setRowStretch(index, 0)
        for index, widget in enumerate(self._items):
            resize = getattr(widget, "set_card_size", None)
            if callable(resize):
                resize(cell)
            self._grid.addWidget(
                widget, index // columns, index % columns,
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            )
            # Cards are created hidden and only revealed once the layout owns
            # them; a fresh card would otherwise paint as a small empty box in
            # the page corner for a frame on every refresh.
            widget.show()
        self._grid.setColumnStretch(columns, 1)
        rows = (len(self._items) + columns - 1) // columns if self._items else 1
        for index in range(rows, rows + 4):
            self._grid.setRowStretch(index, 0)
        self._grid.setRowStretch(rows, 1)
