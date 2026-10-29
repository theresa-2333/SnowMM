"""Card style widgets: character tiles, element badges, issue rows, stat tiles."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...core import paths
from ...core.catalog import Character
from ...i18n import character_name, element_name, get_language, tr
from .. import icons
from ..imaging import ImageCache
from ..theme import Theme
from .common import Tag


def repolish(widget: QWidget) -> None:
    """Force a stylesheet re-evaluation after a dynamic property changed."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


#: Role values stored in the catalog that need translating before display.
ROLE_KEYS = frozenset({"dps", "buffer", "support"})


def icon_button(name: str, theme: Theme, tooltip: str = "", size: int = 18, object_name: str = "Ghost") -> QPushButton:
    button = QPushButton()
    button.setObjectName(object_name)
    button.setIcon(icons.icon(name, theme.text_dim, size))
    button.setIconSize(QSize(size, size))
    button.setFixedSize(QSize(30, 30))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if tooltip:
        button.setToolTip(tooltip)
    return button


def role_label(role: str) -> str:
    """Translate a stored role key such as ``dps`` for display."""
    return tr(f"role_{role}") if role else ""


class StatTile(QWidget):
    """Compact ``value`` over ``label`` readout used in page headers."""

    def __init__(self, value: str = "0", label: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")
        self.caption_label = QLabel(label)
        self.caption_label.setObjectName("StatLabel")
        layout.addWidget(self.value_label)
        layout.addWidget(self.caption_label)

    def set_value(self, value: str, accent: str = "") -> None:
        self.value_label.setText(value)
        self.value_label.setProperty("accent", accent)
        self.value_label.setStyleSheet(f"color: {accent};" if accent else "")


class ElementBadge(QFrame):
    """Damage-type pill: the bundled element icon plus its name."""

    def __init__(self, element: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ElementBadge")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.element = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 8, 2)
        layout.setSpacing(4)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(QSize(14, 14))
        self.text_label = QLabel()
        self.text_label.setObjectName("ElementBadgeText")
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)
        self.set_element(element)

    def set_element(self, element: str) -> None:
        self.element = element
        self.setVisible(bool(element))
        self.text_label.setText(element_name(element))
        icon = paths.element_icon(element) if element else None
        self.icon_label.setVisible(icon is not None)
        if icon is None:
            self.icon_label.clear()
            return
        self.icon_label.setPixmap(
            QPixmap(str(icon)).scaled(
                QSize(14, 14), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        )


class CharacterCard(QFrame):
    """Portrait tile for the character grid."""

    clicked = Signal(str)
    favorite_toggled = Signal(str)

    def __init__(
        self,
        character: Character,
        images: ImageCache,
        theme: Theme,
        parent: QWidget | None = None,
        card_size: int = 150,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("CharacterCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.character = character
        self.images = images
        self.theme = theme
        self.card_size = card_size

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addStretch(1)
        self.favorite_button = QPushButton()
        self.favorite_button.setObjectName("Ghost")
        self.favorite_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.favorite_button.setFixedSize(QSize(26, 26))
        self.favorite_button.clicked.connect(lambda: self.favorite_toggled.emit(self.character.name))
        header.addWidget(self.favorite_button)
        layout.addLayout(header)

        self.portrait = QLabel()
        self.portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        portrait_size = max(1, card_size - 22)
        self.portrait.setFixedSize(QSize(portrait_size, portrait_size))
        self.portrait.setPixmap(images.portrait(character, QSize(portrait_size, portrait_size), 12))
        self.portrait.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.portrait, alignment=Qt.AlignmentFlag.AlignHCenter)

        display_name = character_name(character.name, character.name_en)
        if get_language() == "en_US":
            display_name = display_name.replace(" · ", "\n", 1)
        self.name_label = QLabel(display_name)
        self.name_label.setObjectName("CardTitle")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(False)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.name_label.setToolTip(character_name(character.name, character.name_en))
        self.name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.name_label)

        subtitle = character.subtitle
        self.meta_label = QLabel(role_label(subtitle) if subtitle in ROLE_KEYS else subtitle, self)
        self.meta_label.setObjectName("Faint")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.meta_label.setVisible(bool(self.meta_label.text()))
        self.meta_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.meta_label)

        self.tags_row = QHBoxLayout()
        self.tags_row.setContentsMargins(0, 0, 0, 0)
        self.tags_row.setSpacing(6)
        self.tags_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mod_tag = Tag("")
        # ElementBadge sets its visibility during construction. Give it an owner
        # immediately so it can never flash as a standalone native window.
        self.element_badge = ElementBadge(character.element, self)
        self.mod_tag.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.element_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.tags_row.addWidget(self.mod_tag)
        self.tags_row.addWidget(self.element_badge)
        layout.addLayout(self.tags_row)

        self.setFixedWidth(card_size)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.update_state(mods=0, enabled=0, favorite=False)
        # Cards are revealed by ``FlowGrid`` once it has placed them, so a newly
        # built card never paints in the corner of a visible page for a frame.
        self.hide()

    # ------------------------------------------------------------------ state
    def set_character(self, character: Character) -> None:
        self.character = character
        self.portrait.setPixmap(self.images.portrait(character, self.portrait.size(), 12))

    def update_state(self, *, mods: int, enabled: int, favorite: bool) -> None:
        self.mod_tag.setText(f"{enabled}/{mods}" if mods else "0")
        if mods and enabled:
            variant = "success"
        elif mods:
            variant = "accent"
        else:
            variant = ""
        self.mod_tag.setObjectName(Tag.VARIANTS[variant])
        repolish(self.mod_tag)

        self.favorite_button.setIcon(
            icons.icon("star", self.theme.warning if favorite else self.theme.text_faint, 16, filled=favorite)
        )
        self.favorite_button.setToolTip(character_name(self.character.name, self.character.name_en))

        self.setProperty("hasEnabledMods", bool(enabled))
        repolish(self)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        repolish(self)

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.portrait.setPixmap(self.images.portrait(self.character, self.portrait.size(), 12))
        self.favorite_button.setIcon(icons.icon("star", theme.text_faint, 16))

    def set_card_size(self, card_size: int) -> None:
        """Resize the tile (``FlowGrid`` calls this while reflowing)."""
        if card_size == self.card_size or card_size <= 0:
            return
        self.card_size = card_size
        portrait_size = max(1, card_size - 22)
        self.portrait.setFixedSize(QSize(portrait_size, portrait_size))
        self.setFixedWidth(card_size)
        self.portrait.setPixmap(self.images.portrait(self.character, self.portrait.size(), 12))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.character.name)
        super().mousePressEvent(event)


class IssueRow(QFrame):
    """One detected problem with its quick fixes."""

    action_requested = Signal(str, str, list)  # kind, action, mod ids

    def __init__(
        self,
        kind: str,
        severity: str,
        title: str,
        description: str,
        mod_ids: list[str],
        actions: list[tuple[str, str]],
        theme: Theme,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("IssueRow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("severity", severity)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        color = {"error": theme.danger, "warning": theme.warning, "info": theme.accent}.get(severity, theme.warning)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("warning" if severity != "info" else "info", color, 20))
        glyph.setFixedWidth(24)

        text_column = QVBoxLayout()
        text_column.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        title_label.setWordWrap(True)
        description_label = QLabel(description)
        description_label.setObjectName("Dim")
        description_label.setWordWrap(True)
        text_column.addWidget(title_label)
        text_column.addWidget(description_label)

        layout.addWidget(glyph, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addLayout(text_column, 1)
        for label, action in actions:
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, a=action: self.action_requested.emit(kind, a, mod_ids))
            layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignVCenter)
