"""Colour tokens and the generated Qt stylesheet for both themes."""

from __future__ import annotations

from dataclasses import dataclass
from string import Template


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    surface: str
    surface_alt: str
    surface_hover: str
    border: str
    border_strong: str
    text: str
    text_dim: str
    text_faint: str
    accent: str
    accent_hover: str
    accent_soft: str
    accent_text: str
    success: str
    success_soft: str
    warning: str
    warning_soft: str
    danger: str
    danger_soft: str
    shadow: str
    radius: int = 12

    def path(self) -> dict[str, str]:
        data = self.__dict__.copy()
        data["radius"] = f"{self.radius}px"
        data["radius_sm"] = f"{max(6, self.radius - 4)}px"
        data["radius_lg"] = f"{self.radius + 6}px"
        return data


DARK = Theme(
    name="dark",
    bg="#0f1117",
    surface="#171a21",
    surface_alt="#1d2129",
    surface_hover="#232833",
    border="#262b36",
    border_strong="#333a48",
    text="#e7eaf0",
    text_dim="#98a1b3",
    text_faint="#6b7385",
    accent="#4f8cff",
    accent_hover="#6ea3ff",
    accent_soft="rgba(79, 140, 255, 0.18)",
    accent_text="#0b1220",
    success="#35c48a",
    success_soft="rgba(53, 196, 138, 0.16)",
    warning="#f0b429",
    warning_soft="rgba(240, 180, 41, 0.16)",
    danger="#ef5350",
    danger_soft="rgba(239, 83, 80, 0.16)",
    shadow="rgba(0, 0, 0, 0.45)",
)

LIGHT = Theme(
    name="light",
    bg="#f2f4f9",
    surface="#ffffff",
    surface_alt="#f7f9fc",
    surface_hover="#eef2f9",
    border="#e3e7ef",
    border_strong="#cdd5e3",
    text="#16202e",
    text_dim="#64718a",
    text_faint="#8a94a8",
    accent="#2563eb",
    accent_hover="#1d4ed8",
    accent_soft="rgba(37, 99, 235, 0.12)",
    accent_text="#ffffff",
    success="#15a06a",
    success_soft="rgba(21, 160, 106, 0.12)",
    warning="#c47f00",
    warning_soft="rgba(196, 127, 0, 0.12)",
    danger="#dc2626",
    danger_soft="rgba(220, 38, 38, 0.12)",
    shadow="rgba(15, 23, 42, 0.10)",
)

THEMES = {"dark": DARK, "light": LIGHT}

_SHEET = Template(
    """
* {
    font-family: "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "PingFang SC",
        "Noto Sans CJK SC", "Source Han Sans SC", Arial, sans-serif;
    font-size: 10.5pt;
    color: $text;
    outline: none;
}

QWidget#Root, QMainWindow, QDialog {
    background-color: $bg;
}

QWidget#Sidebar {
    background-color: $surface;
    border-right: 1px solid $border;
}

QFrame#Card, QFrame#Panel {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: $radius;
}

QFrame#SubtleCard {
    background-color: $surface_alt;
    border: 1px solid $border;
    border-radius: $radius;
}
QFrame#CharacterCard, QFrame#ModCard {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: $radius;
}
QFrame#CharacterCard:hover, QFrame#ModCard:hover {
    border-color: $accent;
    background-color: $surface_hover;
}
QFrame#ElementBadge {
    background-color: $surface_alt;
    border: 1px solid $border;
    border-radius: 9px;
}
QLabel#ElementBadgeText { color: $text_dim; font-size: 9pt; }
QFrame#CharacterCard[selected="true"], QFrame#ModCard[selected="true"] {
    border-color: $accent;
    background-color: $accent_soft;
}
QFrame#CharacterCard[hasEnabledMods="true"] { border-color: $success; }

QFrame#IssueRow {
    background-color: $surface;
    border: 1px solid $border;
    border-left: 3px solid $warning;
    border-radius: $radius;
}
QFrame#IssueRow[severity="error"] { border-left-color: $danger; }
QFrame#IssueRow[severity="info"] { border-left-color: $accent; }

QWidget#SidebarHeader { background: transparent; }
QLabel#AppName { font-size: 13pt; font-weight: 700; }
QLabel#AppTagline { color: $text_faint; font-size: 9pt; }

QLabel#InspectorPreview {
    background-color: $surface_alt;
    border: 1px dashed $border_strong;
    border-radius: $radius;
}
QLabel#PortraitLarge {
    background-color: $surface_alt;
    border: 1px solid $border;
    border-radius: $radius;
}

QLabel#PageTitle { font-size: 20pt; font-weight: 700; }
QLabel#PageSubtitle, QLabel#Dim { color: $text_dim; }
QLabel#Faint { color: $text_faint; font-size: 9.5pt; }
QLabel#SectionTitle { font-size: 12pt; font-weight: 700; }
QLabel#CardTitle { font-size: 11pt; font-weight: 600; }
QLabel#StatValue { font-size: 16pt; font-weight: 700; }
QLabel#StatLabel { color: $text_dim; font-size: 9pt; }
QLabel#Tag {
    background-color: $surface_alt;
    border: 1px solid $border;
    border-radius: 9px;
    padding: 2px 8px;
    color: $text_dim;
    font-size: 9pt;
}
QLabel#TagAccent {
    background-color: $accent_soft;
    border: 1px solid $accent;
    border-radius: 9px;
    padding: 2px 8px;
    color: $accent;
    font-size: 9pt;
}
QLabel#TagSuccess {
    background-color: $success_soft;
    border: 1px solid $success;
    border-radius: 9px;
    padding: 2px 8px;
    color: $success;
    font-size: 9pt;
}
QLabel#TagDanger {
    background-color: $danger_soft;
    border: 1px solid $danger;
    border-radius: 9px;
    padding: 2px 8px;
    color: $danger;
    font-size: 9pt;
}
QLabel#TagWarning {
    background-color: $warning_soft;
    border: 1px solid $warning;
    border-radius: 9px;
    padding: 2px 8px;
    color: $warning;
    font-size: 9pt;
}

QPushButton {
    background-color: $surface_alt;
    border: 1px solid $border_strong;
    border-radius: $radius_sm;
    padding: 6px 14px;
    min-height: 20px;
}
QPushButton:hover { background-color: $surface_hover; }
QPushButton:pressed { background-color: $border; }
QPushButton:disabled { color: $text_faint; border-color: $border; }

QPushButton#Primary {
    background-color: $accent;
    border: 1px solid $accent;
    color: $accent_text;
    font-weight: 600;
}
QPushButton#Primary:hover { background-color: $accent_hover; border-color: $accent_hover; }
QPushButton#Primary:disabled { background-color: $border; border-color: $border; color: $text_faint; }

QPushButton#Danger {
    background-color: transparent;
    border: 1px solid $danger;
    color: $danger;
}
QPushButton#Danger:hover { background-color: $danger_soft; }

QPushButton#Ghost {
    background-color: transparent;
    border: 1px solid transparent;
    color: $text_dim;
}
QPushButton#Ghost:hover { background-color: $surface_hover; color: $text; }

QPushButton#NavItem {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: $radius_sm;
    padding: 8px 12px;
    text-align: left;
    color: $text_dim;
}
QPushButton#NavItem:hover { background-color: $surface_hover; color: $text; }
QPushButton#NavItem:checked {
    background-color: $accent_soft;
    color: $accent;
    font-weight: 600;
    border: 1px solid $accent;
}

QPushButton#Chip {
    background-color: transparent;
    border: 1px solid $border_strong;
    border-radius: 12px;
    padding: 4px 12px;
    color: $text_dim;
}
QPushButton#Chip:hover { background-color: $surface_hover; color: $text; }
QPushButton#Chip:checked {
    background-color: $accent_soft;
    border-color: $accent;
    color: $accent;
    font-weight: 600;
}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: $surface_alt;
    border: 1px solid $border_strong;
    border-radius: $radius_sm;
    padding: 6px 10px;
    selection-background-color: $accent;
    selection-color: $accent_text;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: $accent;
    background-color: $surface;
}
QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled { color: $text_faint; }

QLineEdit#Search {
    padding-left: 30px;
    border-radius: 14px;
}

QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background-color: $surface;
    border: 1px solid $border_strong;
    border-radius: $radius_sm;
    selection-background-color: $accent_soft;
    selection-color: $text;
    padding: 4px;
}

QCheckBox, QRadioButton { spacing: 8px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 16px; height: 16px;
    border: 1px solid $border_strong;
    border-radius: 4px;
    background-color: $surface_alt;
}
QCheckBox::indicator:checked {
    background-color: $accent;
    border-color: $accent;
    image: url($checkbox);
}
QRadioButton::indicator { border-radius: 8px; }
QRadioButton::indicator:checked { background-color: $accent; border-color: $accent; }

QTableWidget, QTableView, QTreeWidget, QListWidget {
    background-color: $surface;
    border: 1px solid $border;
    border-radius: $radius;
    gridline-color: $border;
    alternate-background-color: $surface_alt;
}
QTableWidget::item, QTreeWidget::item, QListWidget::item { padding: 6px; border: none; }
QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: $accent_soft;
    color: $text;
}
QListWidget::item:hover, QTreeWidget::item:hover { background-color: $surface_hover; }
QHeaderView::section {
    background-color: $surface_alt;
    border: none;
    border-bottom: 1px solid $border;
    border-right: 1px solid $border;
    padding: 8px;
    color: $text_dim;
    font-weight: 600;
}
QTableCornerButton::section { background-color: $surface_alt; border: none; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border_strong; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $text_faint; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: $border_strong; border-radius: 5px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {
    background: none; border: none; height: 0; width: 0;
}

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }

QTabBar::tab {
    background: transparent;
    color: $text_dim;
    padding: 7px 14px;
    margin-right: 4px;
    border: 1px solid transparent;
    border-radius: $radius_sm;
}
QTabBar::tab:hover { color: $text; background: $surface_hover; }
QTabBar::tab:selected {
    color: $accent;
    background: $accent_soft;
    border-color: $accent;
    font-weight: 600;
}

QMenu {
    background-color: $surface;
    border: 1px solid $border_strong;
    border-radius: $radius_sm;
    padding: 6px;
}
QMenu::item { padding: 6px 18px; border-radius: 6px; }
QMenu::item:selected { background-color: $accent_soft; color: $text; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }

QToolTip {
    background-color: $surface;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 6px;
    padding: 6px 8px;
}

/* The splitter gap is what separates the three detail panels, so keep it wide
   enough to read as spacing (the code sets the same handle width). */
QSplitter::handle { background: transparent; width: 18px; }

QProgressBar {
    background-color: $surface_alt;
    border: 1px solid $border;
    border-radius: 6px;
    height: 8px;
    text-align: center;
}
QProgressBar::chunk { background-color: $accent; border-radius: 6px; }

QFrame#Separator { background-color: $border; max-height: 1px; border: none; }
QFrame#VSeparator { background-color: $border; max-width: 1px; border: none; }

QWidget#Toast {
    background-color: $surface;
    border: 1px solid $border_strong;
    border-radius: $radius_sm;
}
QLabel#ToastText { font-weight: 600; }

QWidget#DropOverlay {
    background-color: $accent_soft;
    border: 2px dashed $accent;
    border-radius: $radius_lg;
}
QLabel#DropText { font-size: 14pt; font-weight: 700; color: $accent; }

QLabel#Portrait {
    background-color: $surface_alt;
    border: 1px solid $border;
    border-radius: $radius;
}

QWidget#ScrollHost { background: transparent; }
"""
)


def stylesheet(theme: Theme, checkbox: str = "") -> str:
    """Return the full application stylesheet for ``theme``.

    ``checkbox`` is the absolute path of a check-mark image used for checked
    checkboxes; an empty string simply leaves the box filled with the accent
    colour, which is a perfectly usable fallback.
    """
    values = theme.path()
    values["checkbox"] = checkbox.replace("\\", "/")
    return _SHEET.substitute(values)


def resolve(name: str, system_dark: bool) -> Theme:
    """Resolve a settings value (``system``/``light``/``dark``) into a theme."""
    if name == "system":
        return DARK if system_dark else LIGHT
    return THEMES.get(name, DARK)
