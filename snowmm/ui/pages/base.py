"""Base class shared by all pages."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..context import AppContext


class Page(QWidget):
    """A navigation destination shown inside the main window's stack."""

    title_key = ""
    subtitle_key = ""

    def __init__(self, ctx: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(24, 18, 24, 22)
        self.root.setSpacing(14)

    # -------------------------------------------------------------- lifecycle
    def refresh(self) -> None:
        """Rebuild the page from the current data."""

    def set_search(self, text: str) -> None:
        """Apply the global search box content to this page."""

    def apply_theme(self, ctx: AppContext) -> None:
        self.ctx = ctx
