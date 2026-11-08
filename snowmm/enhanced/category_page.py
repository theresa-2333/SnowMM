"""Sidebar categories drill down through the same portrait-card grid as the roster."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ..core.catalog import Character
from ..ui.pages.base import Page
from ..ui.pages.characters_page import CharactersPage
from ..ui.widgets.cards import CharacterCard
from ..ui.widgets.grid import FlowGrid


def category_paths(ctx):
    result = []
    for parts in ctx.store.categories + [m.category_parts for m in ctx.manager.mods]:
        for depth in range(1, len(parts) + 1):
            path = parts[:depth]
            if path not in result:
                result.append(path)
    return result


class RosterPage(CharactersPage):
    def _collect(self):
        return [entry for entry in super()._collect() if not entry[0].special]


class CategoryCard(CharacterCard):
    def __init__(self, ctx, label, identity, mods, subtitle, parent):
        super().__init__(Character(label), ctx.images, ctx.theme, parent)
        self.label, self.sample = label, next((m for m in mods if m.preview), None)
        self.favorite_button.hide()
        self.element_badge.hide()
        self.name_label.setText(label)
        self.name_label.setToolTip(label)
        self.meta_label.setText(subtitle)
        self.meta_label.show()
        self.update_state(mods=len(mods), enabled=sum(m.enabled for m in mods), favorite=False)
        self._paint_preview()

    def _paint_preview(self):
        if self.sample:
            self.portrait.setPixmap(self.images.preview(self.sample, self.portrait.size(), 12))

    def set_card_size(self, size):
        super().set_card_size(size)
        self._paint_preview()


class CategoryPage(Page):
    def __init__(self, ctx, owner):
        super().__init__(ctx)
        self.owner, self.path, self.query = owner, ["杂项"], ""
        self.cards = {}
        self.heading = QLabel()
        self.heading.setObjectName("PageSubtitle")
        self.root.addWidget(self.heading)
        actions = QHBoxLayout()
        for label, callback in [
            ("返回上级", self.up),
            ("本分类全部模组", self.show_all),
            ("导入模组", self.import_mods),
            ("新增分类", lambda: self.edit_category("add_category")),
            ("改名/移动", lambda: self.edit_category("rename_category")),
            ("上移", lambda: self.edit_category("order_category", -1)),
            ("下移", lambda: self.edit_category("order_category", 1)),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        self.root.addLayout(actions)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.root.addWidget(self.summary)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.grid = FlowGrid(card_width=172, spacing=14)
        layout.addWidget(self.grid)
        scroll.setWidget(container)
        self.root.addWidget(scroll, 1)

    def show_path(self, path):
        self.path = path[:]
        self.refresh()

    def set_search(self, value):
        self.query = value.casefold().strip()
        self.refresh()

    def refresh(self):
        self.heading.setText(" / ".join(self.path))
        depth = len(self.path)
        children = [p for p in category_paths(self.ctx) if len(p) == depth + 1 and p[:depth] == self.path]
        mods = [m for m in self.ctx.manager.mods if m.category_parts[:depth] == self.path]
        direct = [m for m in mods if m.category_parts == self.path]
        old = list(self.cards.values())
        self.cards = {}
        for path in children:
            contained = [m for m in mods if m.category_parts[: len(path)] == path]
            if (
                self.query
                and self.query not in "/".join(path).casefold()
                and not any(self.query in m.name.casefold() for m in contained)
            ):
                continue
            identity = "/".join(path)
            card = CategoryCard(self.ctx, path[-1], identity, contained, "子分类 · 点击进入", self.grid)
            card.clicked.connect(lambda _=None, p=path: self.owner.open_category(p))
            card.setToolTip(" / ".join(path))
            self.cards[identity] = card
        for mod in direct:
            if self.query and self.query not in f"{mod.name} {mod.author} {mod.note}".casefold():
                continue
            card = CategoryCard(self.ctx, mod.name, mod.id, [mod], mod.tested, self.grid)
            card.clicked.connect(lambda _=None, m=mod: self.owner.open_library_category(self.path, m))
            self.cards[mod.id] = card
        self.grid.set_items(list(self.cards.values()))
        for card in old:
            card.deleteLater()
        self.summary.setText(
            f"{len(children)} 个小分类 · {len(mods)} 个模组（其中本层 {len(direct)} 个）\n"
            + (
                "点击卡片逐级浏览；模组卡片打开版本、部署与预览操作。"
                if self.cards
                else "此分类暂为空，可新增子分类或导入模组。"
            )
        )

    def apply_theme(self, ctx):
        super().apply_theme(ctx)
        self.refresh()

    def up(self):
        if len(self.path) > 1:
            self.owner.open_category(self.path[:-1])
        else:
            self.owner._navigate("characters")

    def show_all(self):
        self.owner.open_library_category(self.path)

    def edit_category(self, method, *args):
        page = self.owner.library_page
        if not page.commit_metadata():
            return
        page.category = self.path[:]
        getattr(page, method)(*args)
        self.owner.refresh_all()
        self.owner.open_category(page.category)

    def import_mods(self):
        page = self.owner.library_page
        page.category = self.path[:]
        page.import_files()
