"""Character detail: portrait panel, mod table and the inspector, side by side."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core import shell
from ...core.catalog import Character
from ...core.models import Mod, human_size
from ...i18n import armor_name, character_name, tr
from .. import icons
from ..widgets.cards import ROLE_KEYS, StatTile, icon_button, role_label
from ..widgets.common import Card, EmptyState, FlowLayout
from ..widgets.inspector import ModInspector
from ..widgets.table import ModTable
from .base import Page


class CharacterDetailPage(Page):
    title_key = "nav_characters"
    subtitle_key = ""

    back_requested = Signal()
    changed = Signal()
    add_mod_requested = Signal(str)
    add_folder_requested = Signal(str)
    navigate_requested = Signal(str)

    def __init__(self, ctx, parent: QWidget | None = None) -> None:
        super().__init__(ctx, parent)
        self.character_name = ""
        self._portrait_width = 0
        self.root.setContentsMargins(18, 14, 18, 18)
        self.root.addWidget(self._build_header())

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        # A visible handle keeps the three panels from visually touching.
        self.splitter.setHandleWidth(18)
        self.splitter.addWidget(self._build_left_panel())
        self.splitter.addWidget(self._build_center())
        self.splitter.addWidget(self._build_right())
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.root.addWidget(self.splitter, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_split()
        self._render_portrait()

    def _render_portrait(self) -> None:
        """Re-render the portrait for the current panel width.

        A pixmap rendered for the widest panel would be clipped in a narrow one,
        so the portrait follows the panel (measured from the panel, not from the
        scrolled host, which changes width when its scrollbar appears).
        """
        if not self.character_name:
            return
        character = self.ctx.catalog.get(self.character_name)
        width = max(120, min(300, self.left_panel.width() - 32))
        if character is None or width == self._portrait_width:
            return
        self._portrait_width = width
        self.portrait.setPixmap(self.ctx.images.portrait(character, QSize(width, int(width * 1.15)), 12))

    def _apply_split(self) -> None:
        """Give the three panels a proportional share so nothing gets squeezed."""
        total = self.splitter.width()
        if total <= 0:
            return
        handle = self.splitter.handleWidth()
        self.left_panel.setVisible(total >= 850)
        left = max(180, min(260, int(total * 0.20)))
        right = max(260, min(360, int(total * 0.28)))
        center = max(260, total - left - right - 2 * handle)
        self.splitter.setSizes([left, center, right])

    # ------------------------------------------------------------------ build
    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        self.back_button = icon_button("chevron-left", self.ctx.theme, tr("button_back"))
        self.back_button.clicked.connect(self.back_requested.emit)
        self.title_label = QLabel()
        self.title_label.setObjectName("PageTitle")
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("Dim")

        title_row.addWidget(self.back_button)
        title_row.addWidget(self.title_label)
        title_row.addWidget(self.subtitle_label)
        title_row.addStretch(1)
        layout.addLayout(title_row)

        self.add_button = QPushButton(tr("button_add_mod"))
        self.add_button.setObjectName("Primary")
        self.add_button.clicked.connect(lambda: self.add_mod_requested.emit(self.character_name))
        self.folder_import_button = QPushButton(tr("button_import_folder"))
        self.folder_import_button.clicked.connect(lambda: self.add_folder_requested.emit(self.character_name))
        self.enable_button = QPushButton(tr("button_enable_all"))
        self.enable_button.clicked.connect(lambda: self._set_all(True))
        self.disable_button = QPushButton(tr("button_disable_all"))
        self.disable_button.clicked.connect(lambda: self._set_all(False))
        self.reveal_button = icon_button("folder", self.ctx.theme, tr("button_open_folder"))
        self.reveal_button.clicked.connect(self._reveal_character_folder)
        self.edit_button = QPushButton(tr("button_edit"))
        self.edit_button.clicked.connect(self._edit_character)

        # The action buttons wrap instead of being squeezed out on a narrow
        # window.
        actions = FlowLayout(spacing=8)
        for button in (
            self.edit_button,
            self.add_button,
            self.folder_import_button,
            self.enable_button,
            self.disable_button,
            self.reveal_button,
        ):
            actions.addWidget(button)
        layout.addLayout(actions)
        return header

    def _build_left_panel(self) -> QWidget:
        panel = Card()
        self.left_panel = panel
        panel.setMinimumWidth(180)
        panel.setMaximumWidth(320)
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        # Scrolls like the inspector, so a short window clips nothing.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        host.setObjectName("ScrollHost")
        layout = QVBoxLayout(host)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.portrait = QLabel()
        self.portrait.setObjectName("PortraitLarge")
        self.portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.portrait.setMinimumHeight(140)
        self.portrait.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.portrait)

        self.name_label = QLabel()
        self.name_label.setObjectName("PageTitle")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.subtitle_label_left = QLabel()
        self.subtitle_label_left.setObjectName("Faint")
        self.subtitle_label_left.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_label)
        layout.addWidget(self.subtitle_label_left)

        stats = QHBoxLayout()
        stats.setSpacing(18)
        self.tile_mods = StatTile("0", tr("label_mods"))
        self.tile_enabled = StatTile("0", tr("stat_enabled"))
        self.tile_armors = StatTile("0", tr("label_armors"))
        for tile in (self.tile_mods, self.tile_enabled, self.tile_armors):
            stats.addWidget(tile)
        stats.addStretch(1)
        layout.addLayout(stats)

        layout.addWidget(self._divider())
        self.skin_label = QLabel(tr("label_switch_armor"))
        self.skin_label.setObjectName("Faint")
        layout.addWidget(self.skin_label)

        self.skin_combo = QComboBox()
        self.skin_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.skin_combo.setMinimumContentsLength(8)
        self.skin_combo.activated.connect(self._on_armor_selected)
        layout.addWidget(self.skin_combo)
        self.skin_button = QPushButton(tr("button_enable_only"))
        self.skin_button.clicked.connect(self._enable_only_selection)
        layout.addWidget(self.skin_button)

        self.disable_character_button = QPushButton(tr("button_disable_character"))
        self.disable_character_button.setObjectName("Danger")
        self.disable_character_button.clicked.connect(lambda: self._set_all(False))
        layout.addWidget(self.disable_character_button)
        layout.addStretch(1)
        scroll.setWidget(host)
        outer.addWidget(scroll)
        return panel

    @staticmethod
    def _divider() -> QWidget:
        from ..widgets.common import Divider

        return Divider()

    def _build_center(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        mods_tab = QWidget()
        mods_layout = QVBoxLayout(mods_tab)
        mods_layout.setContentsMargins(0, 8, 0, 0)
        mods_layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.count_label = QLabel()
        self.count_label.setObjectName("Dim")
        toolbar.addWidget(self.count_label)
        toolbar.addStretch(1)
        self.empty_hint = QLabel(tr("empty_mods_desc"))
        self.empty_hint.setObjectName("Faint")
        self.empty_hint.setWordWrap(True)
        toolbar.addWidget(self.empty_hint)
        mods_layout.addLayout(toolbar)

        self.table = ModTable(self.ctx.theme, ["enabled", "name", "author", "added", "size", "note"])
        self.table.selection_changed.connect(self._on_selection_changed)
        self.table.toggle_requested.connect(self._on_toggle_requested)
        self.table.action_requested.connect(self._on_table_action)
        self.table.open_requested.connect(self._on_open_mod)
        mods_layout.addWidget(self.table, 1)

        self.empty_state = EmptyState()
        self.empty_state.action_button.clicked.connect(
            lambda: self.add_mod_requested.emit(self.character_name)
        )
        mods_layout.addWidget(self.empty_state, 1)

        folders_tab = QWidget()
        folders_layout = QVBoxLayout(folders_tab)
        folders_layout.setContentsMargins(0, 8, 0, 0)
        self.folder_tree = QTreeWidget()
        self.folder_tree.setHeaderLabels([tr("label_files"), tr("label_size")])
        self.folder_tree.itemDoubleClicked.connect(self._on_folder_double_clicked)
        folders_layout.addWidget(self.folder_tree, 1)

        self.tabs.addTab(mods_tab, tr("tab_mods"))
        self.tabs.addTab(folders_tab, tr("tab_folders"))
        layout.addWidget(self.tabs, 1)
        return container

    def _build_right(self) -> QWidget:
        self.inspector = ModInspector(self.ctx.theme, self.ctx.images, self.ctx.catalog)
        self.inspector.changed.connect(self._on_mod_changed)
        self.inspector.enable_toggled.connect(self._on_toggle_requested)
        self.inspector.delete_requested.connect(self._on_delete_requested)
        self.inspector.reveal_requested.connect(lambda mod: shell.reveal(mod.disk_path))
        self.inspector.preview_requested.connect(self._on_preview_requested)
        self.inspector.preview_dropped.connect(self._on_preview_dropped)
        self.inspector.paste_failed.connect(
            lambda: self.ctx.toast and self.ctx.toast.show_message(tr("toast_paste_empty"), "warning")
        )
        return self.inspector

    # ------------------------------------------------------------------- data
    def show_character(self, name: str) -> None:
        self.character_name = name
        self.refresh()

    def refresh(self) -> None:
        if not self.character_name:
            return
        character = self.ctx.catalog.get(self.character_name) or self.ctx.catalog.ensure(self.character_name)
        mods = self.ctx.character_mods(self.character_name)
        enabled = [mod for mod in mods if mod.enabled]

        subtitle = role_label(character.subtitle) if character.subtitle in ROLE_KEYS else character.subtitle
        self.title_label.setText(character_name(character.name, character.name_en))
        self.subtitle_label.setText(subtitle)
        self.name_label.setText(character_name(character.name, character.name_en))
        self.subtitle_label_left.setText(subtitle or tr("label_unknown"))
        self._portrait_width = 0
        self._render_portrait()
        self.tile_mods.set_value(str(len(mods)))
        self.tile_enabled.set_value(str(len(enabled)), self.ctx.theme.success if enabled else "")
        self.tile_armors.set_value(str(len(self.ctx.catalog.siblings(self.character_name)) + 1))
        self.count_label.setText(tr("label_enabled_of", enabled=len(enabled), total=len(mods)))

        self._fill_armor_combo(character)
        self.table.set_mods(mods)
        self.empty_state.setVisible(not mods)
        self.table.setVisible(bool(mods))
        self.empty_hint.setVisible(bool(mods))
        if not mods:
            self.empty_state.show_state(
                tr("empty_mods_title"),
                tr("empty_mods_desc"),
                icon="package",
                theme=self.ctx.theme,
                action=tr("button_add_mod"),
            )
        self._fill_folder_tree()
        if mods:
            current = self.table.selected_mods()
            self.inspector.set_selection(current or [mods[0]])
        else:
            self.inspector.clear()

    def _fill_armor_combo(self, character: Character) -> None:
        """Let the user jump between the armors of the same character."""
        self.skin_combo.blockSignals(True)
        self.skin_combo.clear()
        for item in [character, *self.ctx.catalog.siblings(character.name)]:
            self.skin_combo.addItem(armor_name(item.name, item.name_en), item.name)
        index = self.skin_combo.findData(character.name)
        self.skin_combo.setCurrentIndex(max(0, index))
        self.skin_combo.blockSignals(False)

    def _on_armor_selected(self, index: int) -> None:
        name = self.skin_combo.itemData(index)
        if name and name != self.character_name:
            self.navigate_requested.emit(str(name))

    def _fill_folder_tree(self) -> None:
        self.folder_tree.clear()
        directory = self.ctx.manager.character_dir(self.character_name)
        if directory is None or not directory.exists():
            return
        for child in sorted(directory.rglob("*")):
            if child.is_dir():
                continue
            relative = child.relative_to(directory)
            parent_item = None
            for part in relative.parts[:-1]:
                found = None
                if parent_item is None:
                    for i in range(self.folder_tree.topLevelItemCount()):
                        candidate = self.folder_tree.topLevelItem(i)
                        if candidate.text(0) == part:
                            found = candidate
                            break
                else:
                    for i in range(parent_item.childCount()):
                        candidate = parent_item.child(i)
                        if candidate.text(0) == part:
                            found = candidate
                            break
                if found is None:
                    item = QTreeWidgetItem([part, ""])
                    if parent_item is None:
                        self.folder_tree.addTopLevelItem(item)
                    else:
                        parent_item.addChild(item)
                    found = item
                parent_item = found
            try:
                size = child.stat().st_size
            except OSError:
                size = 0

            leaf = QTreeWidgetItem([child.name, human_size(size)])
            leaf.setData(0, Qt.ItemDataRole.UserRole, str(child))
            leaf.setToolTip(0, str(child))
            if parent_item is None:
                self.folder_tree.addTopLevelItem(leaf)
            else:
                parent_item.addChild(leaf)
        self.folder_tree.expandAll()

    # ---------------------------------------------------------------- actions
    def _current_mods(self) -> list[Mod]:
        return self.ctx.character_mods(self.character_name)

    def _set_all(self, enabled: bool) -> None:
        changed, errors = self.ctx.manager.set_character_enabled(self.character_name, enabled)
        self.changed.emit()
        self.refresh()
        self.ctx.toast and self.ctx.toast.show_message(
            errors[0] if errors else tr("toast_changed", count=changed), "warning" if errors else "check"
        )

    def _enable_only_selection(self) -> None:
        """Enable the selected mods and turn every other mod of this character off."""
        mods = self._current_mods()
        wanted = self.table.selected_mods() or mods[:1]
        changed, errors = self.ctx.manager.set_enabled(wanted, True)
        others = [mod for mod in mods if mod not in wanted]
        if not errors:
            more, errors = self.ctx.manager.set_enabled(others, False)
            changed += more
        self.changed.emit()
        self.refresh()
        self.ctx.toast and self.ctx.toast.show_message(
            errors[0] if errors else tr("toast_changed", count=changed), "warning" if errors else "check"
        )

    def _reveal_character_folder(self) -> None:
        directory = self.ctx.manager.character_dir(self.character_name)
        if directory is not None and directory.exists():
            shell.reveal(directory)

    def _edit_character(self) -> None:
        from ..dialogs import CharacterEditorDialog

        character = self.ctx.catalog.get(self.character_name)
        if character is None:
            return
        dialog = CharacterEditorDialog(self.ctx, character, self)
        if dialog.exec() != CharacterEditorDialog.DialogCode.Accepted:
            return
        payload = dialog.payload()
        if not payload["name"]:
            return
        self.ctx.store.upsert_character(payload)
        self.ctx.store.save()
        self.ctx.catalog.merge(Character.from_dict(payload, user_defined=True))
        self.character_name = payload["name"]
        self.changed.emit()
        self.refresh()

    def _on_toggle_requested(self, mods: list, enabled: bool) -> None:
        changed, errors = self.ctx.manager.set_enabled(mods, enabled)
        self.changed.emit()
        self.refresh()
        if changed and not errors:
            self.ctx.toast and self.ctx.toast.show_message(tr("toast_changed", count=changed))
        elif errors:
            self.ctx.toast and self.ctx.toast.show_message(errors[0], "warning")

    def _on_selection_changed(self, mods: list) -> None:
        if mods:
            self.inspector.set_selection(mods)

    def _on_open_mod(self, mod: Mod) -> None:
        self.inspector.set_selection([mod])

    def _on_mod_changed(self, mod: Mod) -> None:
        self.ctx.store.save()

    def _on_preview_requested(self, mod: Mod) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("button_choose_image"), "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self._on_preview_dropped(mod, path)

    def _on_preview_dropped(self, mod: Mod, path: str) -> None:
        try:
            self.ctx.manager.set_preview(mod, Path(path))
        except OSError as error:
            self.ctx.toast and self.ctx.toast.show_message(str(error), "warning")
            return
        self.ctx.store.save()
        self.refresh()

    def _on_delete_requested(self, mods: list) -> None:
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
        message = errors[0] if errors else tr("toast_changed", count=removed)
        self.ctx.toast and self.ctx.toast.show_message(message, "warning" if errors else "check")

    def _on_table_action(self, action: str, mods: list) -> None:
        if action == "enable":
            self._on_toggle_requested(mods, True)
        elif action == "disable":
            self._on_toggle_requested(mods, False)
        elif action == "reveal":
            shell.reveal(mods[0].disk_path)
        elif action == "copy":
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText(str(mods[0].enabled_path))
            self.ctx.toast and self.ctx.toast.show_message(tr("toast_copied"))
        elif action == "delete":
            self._on_delete_requested(mods)

    def _on_folder_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path:
            shell.open_path(path)

    def apply_theme(self, ctx) -> None:
        super().apply_theme(ctx)
        self.back_button.setIcon(icons.icon("chevron-left", ctx.theme.text_dim, 18))
        self.reveal_button.setIcon(icons.icon("folder", ctx.theme.text_dim, 18))
        self.table.theme = ctx.theme
        self.inspector.set_theme(ctx.theme)
