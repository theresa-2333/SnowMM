"""An enabled-mod snapshot with immediate, reversible package toggles."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core.models import Mod
from ...core.skins import skins_for
from ...i18n import character_name, get_language, tr
from .common import Card
from .grid import FlowGrid
from .image_preview import ImagePreviewDialog


class GalleryCard(Card):
    selected = Signal(object)
    toggle_requested = Signal(object)

    def __init__(self, mod: Mod, ctx, parent=None) -> None:
        super().__init__(parent)
        self.mod = mod
        self.ctx = ctx
        self._preview_dialog = None
        self.setFixedWidth(290)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        self.preview = QPushButton()
        self.preview.setFixedHeight(180)
        self.preview.setIconSize(QSize(256, 170))
        self.preview.setIcon(QIcon(ctx.images.preview(mod, QSize(256, 170))))
        self.preview.setToolTip(tr("preview_click_hint"))
        self.preview.clicked.connect(lambda: self.selected.emit(self))
        layout.addWidget(self.preview)
        title = QLabel(mod.name)
        title.setWordWrap(True)
        title.setObjectName("CardTitle")
        layout.addWidget(title)
        skin = next((skin for skin in skins_for(mod.character) if skin.id == mod.skin), None)
        skin_name = (skin.name_en if get_language() == "en_US" else skin.name) if skin else mod.skin
        subtitle = QLabel(f"{character_name(mod.character)} · {skin_name}")
        subtitle.setObjectName("Dim")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        actions = QHBoxLayout()
        self.toggle = QPushButton()
        self.toggle.setCheckable(True)
        self.toggle.setObjectName("Primary")
        self.toggle.clicked.connect(lambda: self.toggle_requested.emit(self))
        self.open_button = QPushButton(tr("label_preview"))
        self.open_button.clicked.connect(self.open_image)
        actions.addWidget(self.toggle)
        actions.addWidget(self.open_button)
        layout.addLayout(actions)
        self.update_state()

    def set_card_size(self, width: int) -> None:
        self.setFixedWidth(width)
        self.preview.setIconSize(QSize(min(256, max(1, width - 32)), 170))

    def update_state(self) -> None:
        self.toggle.setChecked(self.mod.enabled)
        self.toggle.setText(tr("button_disable") if self.mod.enabled else tr("button_enable"))
        self.toggle.setEnabled(self.mod.exists)

    def set_selected(self, selected: bool) -> None:
        border = self.ctx.theme.accent if selected else self.ctx.theme.border
        self.setStyleSheet(f"QFrame#Card {{ border: 2px solid {border}; border-radius: 12px; }}")

    def open_image(self) -> None:
        self.selected.emit(self)
        pixmap = QPixmap(self.mod.preview) if self.mod.preview else QPixmap()
        if pixmap.isNull():
            pixmap = self.ctx.images.preview(self.mod, QSize(800, 600))
        if self._preview_dialog is not None:
            self._preview_dialog.close()
        dialog = ImagePreviewDialog(pixmap, self.mod.name, self)
        self._preview_dialog = dialog
        dialog.finished.connect(lambda _: setattr(self, "_preview_dialog", None))
        dialog.show()


class ModGalleryWidget(QWidget):
    changed = Signal()
    back_requested = Signal()

    def __init__(self, ctx, parent=None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.cards: list[GalleryCard] = []
        self.selected_index = 0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.count = QLabel()
        toolbar.addWidget(self.count, 1)
        self.refresh_button = QPushButton(tr("button_refresh"))
        self.refresh_button.clicked.connect(self.reload)
        toolbar.addWidget(self.refresh_button)
        self.back_button = QPushButton(tr("button_back"))
        self.back_button.clicked.connect(self.back_requested.emit)
        toolbar.addWidget(self.back_button)
        layout.addLayout(toolbar)
        hint = QLabel(tr("gallery_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"color: {ctx.theme.danger};")
        layout.addWidget(self.error)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid = FlowGrid(card_width=290, min_card_width=260, max_card_width=340)
        self.scroll.setWidget(self.grid)
        layout.addWidget(self.scroll, 1)
        self.empty = QLabel(tr("gallery_empty"))
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty)
        self.shortcuts = []
        for key, action in (("Left", lambda: self.select_offset(-1)),
                            ("Right", lambda: self.select_offset(1)), ("Space", self.toggle_selected)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(action)
            self.shortcuts.append(shortcut)
        self.sync()

    def refresh(self) -> None:
        # Keep disabled cards in the active snapshot until explicit reload.
        self.sync()

    def reload(self) -> None:
        self.ctx.manager.refresh_states()
        previous = self.cards
        self.grid.clear()
        self.cards = []
        for mod in self.ctx.store.mods:
            if not mod.enabled:
                continue
            card = GalleryCard(mod, self.ctx, self.grid)
            card.selected.connect(self.select_card)
            card.toggle_requested.connect(self.toggle_card)
            self.cards.append(card)
        self.grid.set_items(self.cards)
        for card in previous:
            card.deleteLater()
        self.selected_index = 0
        self.error.clear()
        self.scroll.setVisible(bool(self.cards))
        self.empty.setVisible(not self.cards)
        self.sync()
        self.changed.emit()

    def sync(self) -> None:
        for index, card in enumerate(self.cards):
            card.update_state()
            card.set_selected(index == self.selected_index)
        self.count.setText(tr("gallery_count", total=len(self.cards),
                              enabled=sum(card.mod.enabled for card in self.cards)))

    def select_card(self, card: GalleryCard) -> None:
        self.selected_index = self.cards.index(card)
        self.sync()

    def select_offset(self, offset: int) -> None:
        if self.cards:
            self.selected_index = (self.selected_index + offset) % len(self.cards)
            self.sync()
            self.scroll.ensureWidgetVisible(self.cards[self.selected_index])

    def toggle_selected(self) -> None:
        if self.cards:
            self.toggle_card(self.cards[self.selected_index])

    def toggle_card(self, card: GalleryCard) -> None:
        self.select_card(card)
        # Always read the actual file state, including changes made outside the app.
        self.ctx.manager.refresh_states()
        _changed, errors = self.ctx.manager.set_enabled([card.mod], not card.mod.enabled)
        self.ctx.store.save()
        self.error.setText(errors[0] if errors else "")
        self.sync()
        self.changed.emit()
