"""Shared application state handed to every page."""

from __future__ import annotations

from dataclasses import dataclass

from ..core.catalog import Catalog
from ..core.manager import Issue, ModManager
from ..core.models import Mod
from ..core.settings import Settings
from ..core.store import Store
from .imaging import ImageCache
from .theme import Theme


@dataclass
class AppContext:
    """Everything a page needs: data, services and the active theme."""

    settings: Settings
    store: Store
    manager: ModManager
    catalog: Catalog
    images: ImageCache
    theme: Theme
    toast: object | None = None

    def save(self) -> None:
        self.store.save()
        self.settings.save()

    # ------------------------------------------------------------- character
    def characters(self) -> list[str]:
        """The characters that ship with the app - never one invented on the fly.

        A stray folder or an unknown pak must not grow the roster, so the art
        library is the only source.  Records pointing somewhere else are
        surfaced by :meth:`issues` instead.
        """
        return self.catalog.names()

    def known_characters(self) -> set[str]:
        """Names accepted as a character (used to validate folders on disk)."""
        return set(self.catalog.names())

    def character_mods(self, name: str) -> list[Mod]:
        return [mod for mod in self.store.mods if mod.character == name]

    def character_counts(self, name: str) -> tuple[int, int]:
        mods = self.character_mods(name)
        return len(mods), sum(1 for mod in mods if mod.enabled)

    def elements(self) -> list[str]:
        """Damage types that actually have characters, in game order."""
        return self.catalog.elements()

    # ----------------------------------------------------------------- stats
    def stats(self) -> dict[str, int]:
        return self.manager.stats()

    def issues(self) -> list[Issue]:
        return self.manager.issues(self.known_characters())
