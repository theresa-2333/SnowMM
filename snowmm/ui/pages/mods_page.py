"""All mods in one filterable table."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...core import shell
from ...core.models import Mod
from ...i18n import character_name, tr
from ..widgets.common import EmptyState
from ..widgets.inspector import ModInspector
from ..widgets.table import ModTable
from .base import Page

STATUS_FILTERS = ("all", "enabled", "disabled", "missing")


class ModsPage(Page):
    title_key = "nav_mods"
    subtitle_key = "page_mods_sub"

    changed = Signal()

    def __init__(self, ctx, parent: QWidget | None = None) -> None:
        super().__init__(ctx, parent)
        self._search = ""
        self._character = ""
        self._status = "all"
        self.root.addLayout(self._build_toolbar())

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter = self.splitter
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(18)

        table_host = QWidget()
        table_layout = QVBoxLayout(table_host)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(8)
        self.table = ModTable(
            self.ctx.theme,
            ["enabled", "name", "character", "author", "added", "size"],
        )
        self.table.selection_changed.connect(self._on_selection)
        self.table.toggle_requested.connect(self._on_toggle)
        self.table.action_requested.connect(self._on_action)
        self.table.open_requested.connect(lambda mod: self.inspector.set_selection([mod]))
        self.empty = EmptyState()
        table_layout.addWidget(self.table, 1)
        table_layout.addWidget(self.empty)

        self.inspector = ModInspector(self.ctx.theme, self.ctx.images, self.ctx.catalog, show_character=True)
        self.inspector.changed.connect(lambda mod: self.ctx.store.save())
        self.inspector.enable_toggled.connect(self._on_toggle)
        self.inspector.delete_requested.connect(self._on_delete)
        self.inspector.reveal_requested.connect(lambda mod: shell.reveal(mod.disk_path))
        self.inspector.preview_requested.connect(self._choose_preview)
        self.inspector.preview_dropped.connect(self._on_preview)
        self.inspector.category_changed.connect(self._on_category_changed)

        splitter.addWidget(table_host)
        splitter.addWidget(self.inspector)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        self.root.addWidget(splitter, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_split()

    def _apply_split(self) -> None:
        """Keep the table usable: the inspector takes a share, not a fixed slice."""
        total = self.splitter.width()
        if total <= 0:
            return
        inspector = max(260, min(380, int(total * 0.32)))
        table = max(320, total - inspector - self.splitter.handleWidth())
        self.splitter.setSizes([table, inspector])

    def _build_toolbar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(8)
        self.count_label = QLabel()
        self.count_label.setObjectName("Dim")
        layout.addWidget(self.count_label)
        layout.addStretch(1)

        self.character_combo = QComboBox()
        self.character_combo.setMinimumWidth(160)
        self.character_combo.currentIndexChanged.connect(self._on_character_changed)
        self.status_combo = QComboBox()
        for key in STATUS_FILTERS:
            self.status_combo.addItem(tr(f"status_{key}"), key)
        self.status_combo.currentIndexChanged.connect(self._on_status_changed)

        layout.addWidget(self.character_combo)
        layout.addWidget(self.status_combo)
        layout.addStretch(1)
        return layout

    # ------------------------------------------------------------------ events
    def _on_character_changed(self, _index: int) -> None:
        self._character = self.character_combo.currentData() or ""
        self.refresh()

    def _on_status_changed(self, _index: int) -> None:
        self._status = self.status_combo.currentData()
        self.refresh()

    def _on_selection(self, mods: list) -> None:
        if mods:
            self.inspector.set_selection(mods)
        else:
            self.inspector.clear()

    def _on_toggle(self, mods: list, enabled: bool) -> None:
        changed, errors = self.ctx.manager.set_enabled(mods, enabled)
        self.changed.emit()
        self.refresh()
        if errors:
            self.ctx.toast and self.ctx.toast.show_message(errors[0], "warning")
        elif changed:
            self.ctx.toast and self.ctx.toast.show_message(tr("toast_changed", count=changed))

    def _on_delete(self, mods: list) -> None:
        if not mods:
            return
        if self.ctx.settings.confirm_delete:
            answer = QMessageBox.question(
                self,
                tr("warning_confirm_delete_title"),
                tr("warning_confirm_delete_body", count=len(mods)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        removed, errors = self.ctx.manager.delete(mods)
        self.changed.emit()
        self.refresh()
        self.ctx.toast and self.ctx.toast.show_message(
            errors[0] if errors else tr("toast_changed", count=removed), "warning" if errors else "check"
        )

    def _on_action(self, action: str, mods: list) -> None:
        if action == "enable":
            self._on_toggle(mods, True)
        elif action == "disable":
            self._on_toggle(mods, False)
        elif action == "delete":
            self._on_delete(mods)
        elif action == "reveal":
            shell.reveal(mods[0].disk_path)
        elif action == "copy":
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText(str(mods[0].enabled_path))
            self.ctx.toast and self.ctx.toast.show_message(tr("toast_copied"))

    def _choose_preview(self, mod: Mod) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("button_choose_image"), "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self._on_preview(mod, path)

    def _on_preview(self, mod: Mod, path: str) -> None:
        try:
            self.ctx.manager.set_preview(mod, Path(path))
        except OSError as error:
            self.ctx.toast and self.ctx.toast.show_message(str(error), "warning")
            return
        self.ctx.store.save()
        self.refresh()

    def _on_category_changed(self, mod: Mod, character: str) -> None:
        error = self.ctx.manager.move_mod(mod, character)
        if error:
            self.ctx.toast and self.ctx.toast.show_message(error, "warning")
            return
        self.changed.emit()
        self.refresh()

    # ------------------------------------------------------------------ public
    def set_search(self, text: str) -> None:
        self._search = text.strip().lower()
        self.refresh()

    def refresh(self) -> None:
        names = self.ctx.characters()
        self.character_combo.blockSignals(True)
        current = self.character_combo.currentData()
        self.character_combo.clear()
        self.character_combo.addItem(tr("label_character"), "")
        for name in names:
            self.character_combo.addItem(character_name(name), name)
        index = self.character_combo.findData(current or self._character)
        self.character_combo.setCurrentIndex(max(0, index))
        self.character_combo.blockSignals(False)

        mods = self._filtered()
        self.table.set_mods(mods)
        self.count_label.setText(tr("settings_stats", mods=len(mods), characters=len(names)))
        self.table.setVisible(bool(mods))
        self.empty.setVisible(not mods)
        if not mods:
            self.inspector.clear()
            self.empty.show_state(
                tr("empty_results_title"), tr("empty_results_desc"), icon="search", theme=self.ctx.theme
            )
        elif self.table.selected_mods():
            self.inspector.set_selection(self.table.selected_mods())
        else:
            self.inspector.set_selection([mods[0]])

    def _filtered(self) -> list[Mod]:
        mods = list(self.ctx.store.mods)
        if self._character:
            mods = [mod for mod in mods if mod.character == self._character]
        if self._status == "enabled":
            mods = [mod for mod in mods if mod.enabled]
        elif self._status == "disabled":
            mods = [mod for mod in mods if not mod.enabled]
        elif self._status == "missing":
            mods = [mod for mod in mods if not mod.exists]
        if self._search:
            query = self._search
            mods = [
                mod
                for mod in mods
                if query in mod.name.lower()
                or query in mod.character.lower()
                or query in character_name(mod.character).lower()
                or query in mod.author.lower()
                or query in mod.note.lower()
            ]
        return sorted(mods, key=lambda mod: (mod.character, mod.name))

    def apply_theme(self, ctx) -> None:
        super().apply_theme(ctx)
        self.table.theme = ctx.theme
        self.inspector.set_theme(ctx.theme)
        self.refresh()
