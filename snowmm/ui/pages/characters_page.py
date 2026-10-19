"""Character overview: the portrait grid that is the heart of the app."""

from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...core import paths
from ...core.models import Mod
from ...i18n import character_name, element_name, tr
from ..widgets.cards import CharacterCard, StatTile
from ..widgets.common import ChipButton, EmptyState, FlowLayout
from ..widgets.grid import FlowGrid
from .base import Page


class CharactersPage(Page):
    """The fixed roster: one card per character in the art library."""

    title_key = "nav_characters"
    subtitle_key = "page_characters_sub"

    open_character = Signal(str)
    changed = Signal()

    def __init__(self, ctx, parent: QWidget | None = None) -> None:
        super().__init__(ctx, parent)
        self._search = ""
        self._favorites_only = False
        self._with_mods_only = False
        self._element = ""
        self._cards: dict[str, CharacterCard] = {}
        self._element_chips: dict[str, ChipButton] = {}

        self.root.addWidget(self._build_header())

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("ScrollHost")
        inner = QVBoxLayout(container)
        inner.setContentsMargins(0, 0, 6, 0)
        inner.setSpacing(12)
        self.grid = FlowGrid(card_width=172, spacing=14)
        self.empty = EmptyState()
        inner.addWidget(self.grid)
        inner.addWidget(self.empty)
        self.scroll.setWidget(container)
        self.root.addWidget(self.scroll, 1)

    # ------------------------------------------------------------------ build
    def _build_header(self) -> QWidget:
        header = QWidget()
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(26)
        self.stat_mods = StatTile("0", tr("stat_mods"))
        self.stat_enabled = StatTile("0", tr("stat_enabled"))
        self.stat_characters = StatTile("0", tr("stat_characters"))
        self.stat_missing = StatTile("0", tr("stat_missing"))
        for tile in (self.stat_mods, self.stat_enabled, self.stat_characters, self.stat_missing):
            stats_row.addWidget(tile)
        stats_row.addStretch(1)
        layout.addLayout(stats_row)

        self.favorite_chip = ChipButton(tr("filter_favorites"))
        self.favorite_chip.toggled.connect(self._on_favorites_toggled)
        self.with_mods_chip = ChipButton(tr("filter_with_mods"))
        self.with_mods_chip.toggled.connect(self._on_with_mods_toggled)
        self.show_all_chip = ChipButton(tr("filter_show_all"))
        self.show_all_chip.setToolTip(tr("filter_show_all_hint"))
        self.show_all_chip.setChecked(not self.ctx.settings.hide_empty_characters)
        self.show_all_chip.toggled.connect(self._on_show_all_toggled)

        self.element_label = QLabel(tr("filter_element"))
        self.element_label.setObjectName("Faint")

        # A flow layout keeps the chips usable on a narrow window: they simply
        # wrap onto a second line instead of being squeezed out of view.
        filters = FlowLayout(spacing=8)
        filters.addWidget(self.favorite_chip)
        filters.addWidget(self.with_mods_chip)
        filters.addWidget(self.show_all_chip)
        filters.addWidget(self.element_label)
        self._filters = filters
        layout.addLayout(filters)
        return header

    # ----------------------------------------------------------------- events
    def _on_favorites_toggled(self, checked: bool) -> None:
        self._favorites_only = checked
        self._rebuild()

    def _on_with_mods_toggled(self, checked: bool) -> None:
        self._with_mods_only = checked
        self._rebuild()

    def _on_show_all_toggled(self, checked: bool) -> None:
        self.ctx.settings.hide_empty_characters = not checked
        self.ctx.settings.save()
        self._rebuild()

    def _on_card_clicked(self, name: str) -> None:
        self.open_character.emit(name)

    def _on_favorite(self, name: str) -> None:
        self.ctx.settings.toggle_favorite(name)
        self.ctx.settings.save()
        self._rebuild()

    def _select_element(self, element: str) -> None:
        self._element = element
        for key, chip in self._element_chips.items():
            chip.setChecked(key == element)
        self._rebuild()

    # ----------------------------------------------------------------- public
    def set_search(self, text: str) -> None:
        self._search = text.strip().lower()
        self._rebuild()

    def refresh(self) -> None:
        stats = self.ctx.stats()
        self.stat_mods.set_value(str(stats["mods"]))
        self.stat_enabled.set_value(str(stats["enabled"]), self.ctx.theme.success)
        self.stat_missing.set_value(str(stats["missing"]), self.ctx.theme.danger if stats["missing"] else "")
        self._rebuild_element_chips()
        self._rebuild()

    def apply_theme(self, ctx) -> None:
        super().apply_theme(ctx)
        # Portraits and star icons are rendered pixmaps, so the existing cards
        # have to be re-rendered when the theme changes.
        for card in self._cards.values():
            card.set_theme(ctx.theme)

    # -------------------------------------------------------------- rebuilding
    def _rebuild_element_chips(self) -> None:
        """One chip per damage type the art library actually provides."""
        elements = self.ctx.elements()
        if set(elements) == set(self._element_chips) - {""}:
            return
        if self._element not in ["", *elements]:
            self._element = ""
        for chip in self._element_chips.values():
            self._filters.removeWidget(chip)
            chip.deleteLater()
        self._element_chips.clear()
        for element in ["", *elements]:
            chip = ChipButton(element_name(element) if element else tr("filter_all"))
            icon = paths.element_icon(element) if element else None
            if icon is not None:
                chip.setIcon(QIcon(str(icon)))
                chip.setIconSize(QSize(16, 16))
            chip.setChecked(element == self._element)
            chip.clicked.connect(lambda _checked=False, value=element: self._select_element(value))
            self._filters.addWidget(chip)
            self._element_chips[element] = chip

    def _rebuild(self) -> None:
        entries = self._collect()
        # Cards are reused across refreshes: rebuilding 54 tiles (and re-decoding
        # their portraits) on every navigation made the page stutter.
        cards: list[QWidget] = []
        for character, mods, enabled in entries:
            card = self._cards.get(character.name)
            if card is None:
                card = CharacterCard(character, self.ctx.images, self.ctx.theme, self.grid)
                card.clicked.connect(self._on_card_clicked)
                card.favorite_toggled.connect(self._on_favorite)
                self._cards[character.name] = card
            card.update_state(
                mods=mods,
                enabled=enabled,
                favorite=self.ctx.settings.is_favorite(character.name),
            )
            cards.append(card)
        self.grid.set_items(cards)
        self.grid.setVisible(bool(cards))
        self.empty.setVisible(not cards)
        # The headline count is what the grid shows, so it always matches the
        # character art that ships with the app.
        self.stat_characters.set_value(str(len(entries)))
        if not cards:
            self.empty.show_state(
                tr("empty_results_title"), tr("empty_results_desc"), icon="search", theme=self.ctx.theme
            )

    def _collect(self) -> list[tuple]:
        """Characters to show, in art-library order (grouped by element)."""
        grouped: dict[str, list[Mod]] = {}
        for mod in self.ctx.store.mods:
            grouped.setdefault(mod.character, []).append(mod)

        show_empty = not self.ctx.settings.hide_empty_characters
        query = self._search
        entries = []
        for name in self.ctx.characters():
            character = self.ctx.catalog.get(name)
            if character is None:
                # Never invent a card for something that is not on the roster.
                continue
            mods = grouped.get(name, [])
            if not mods and not show_empty:
                continue
            if self._favorites_only and not self.ctx.settings.is_favorite(name):
                continue
            if self._with_mods_only and not mods:
                continue
            if self._element and character.element != self._element:
                continue
            if (
                query and query not in name.lower()
                and query not in character_name(name, character.name_en).lower()
                and not any(query in mod.name.lower() for mod in mods)
            ):
                continue
            entries.append((character, len(mods), sum(1 for mod in mods if mod.enabled)))
        return entries
