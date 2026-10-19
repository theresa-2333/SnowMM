"""Health check page: conflicts, missing files and orphaned records."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ...core import shell
from ...core.manager import Issue
from ...i18n import character_name, tr
from ..widgets.cards import IssueRow
from ..widgets.common import EmptyState
from .base import Page

ACTION_KEYS = {
    "multi_enabled": ["disable_others", "reveal"],
    "missing_file": ["remove_record"],
    "duplicate_path": ["remove_record", "reveal"],
    "unknown_character": ["remove_record", "reveal"],
}


class IssuesPage(Page):
    title_key = "nav_issues"
    subtitle_key = "page_issues_sub"

    changed = Signal()

    def __init__(self, ctx, parent: QWidget | None = None) -> None:
        super().__init__(ctx, parent)
        header = QHBoxLayout()
        self.summary = QLabel()
        self.summary.setObjectName("Dim")
        self.refresh_button = QPushButton(tr("button_refresh"))
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.summary)
        header.addStretch(1)
        header.addWidget(self.refresh_button)
        self.root.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("ScrollHost")
        self.list_layout = QVBoxLayout(container)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(10)
        self.list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.empty = EmptyState()
        self.list_layout.addWidget(self.empty)
        self.scroll.setWidget(container)
        self.root.addWidget(self.scroll, 1)

    # ------------------------------------------------------------------ build
    def refresh(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self.empty:
                widget.deleteLater()
        issues = self.ctx.issues()
        self.summary.setText(tr("issue_count", count=len(issues)))
        for issue in issues:
            self.list_layout.addWidget(self._build_row(issue))
        self.list_layout.addWidget(self.empty)
        self.empty.setVisible(not issues)
        if not issues:
            self.empty.show_state(
                tr("empty_issues_title"), tr("empty_issues_desc"), icon="shield", theme=self.ctx.theme
            )

    def _build_row(self, issue: Issue) -> IssueRow:
        actions = [(self._action_label(key), key) for key in ACTION_KEYS.get(issue.kind, [])]
        row = IssueRow(
            issue.kind,
            issue.severity,
            self._title(issue),
            tr(f"issue_{issue.kind}_desc", **self._display_data(issue)),
            issue.mod_ids,
            actions,
            self.ctx.theme,
        )
        row.action_requested.connect(self._on_action)
        return row

    def _title(self, issue: Issue) -> str:
        return tr(f"issue_{issue.kind}", **self._display_data(issue))

    @staticmethod
    def _display_data(issue: Issue) -> dict:
        data = dict(issue.data)
        if data.get("character"):
            data["character"] = character_name(data["character"])
        return data

    @staticmethod
    def _action_label(key: str) -> str:
        return {
            "disable_others": tr("issue_disable_others"),
            "remove_record": tr("issue_remove_record"),
            "reveal": tr("issue_reveal"),
        }.get(key, key)

    # ----------------------------------------------------------------- actions
    def _on_action(self, kind: str, action: str, mod_ids: list) -> None:
        mods = self.ctx.store.get_mods(mod_ids)
        if action == "disable_others":
            if len(mods) > 1:
                changed, _ = self.ctx.manager.set_enabled(mods[1:], False)
                self.changed.emit()
                self.refresh()
                self.ctx.toast and self.ctx.toast.show_message(tr("toast_changed", count=changed))
        elif action == "remove_record":
            removed, _ = self.ctx.manager.delete(mods, remove_files=False)
            self.changed.emit()
            self.refresh()
            self.ctx.toast and self.ctx.toast.show_message(tr("toast_changed", count=removed))
        elif action == "reveal" and mods:
            shell.reveal(mods[0].disk_path if mods[0].exists else mods[0].enabled_path.parent)
