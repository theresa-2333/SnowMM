"""Pages shown in the main window navigation."""

from .base import Page
from .character_detail_page import CharacterDetailPage
from .characters_page import CharactersPage
from .issues_page import IssuesPage
from .mods_page import ModsPage
from .settings_page import SettingsPage

__all__ = [
    "CharacterDetailPage",
    "CharactersPage",
    "IssuesPage",
    "ModsPage",
    "Page",
    "SettingsPage",
]
