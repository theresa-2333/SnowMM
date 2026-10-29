"""Character catalog: one entry per character wearing one armor.

The catalog is assembled from three sources, in increasing priority:

1. the art library (``<art>/<element>/<name>.png``) - it decides *which*
   characters exist and where each portrait lives,
2. the bundled annotations in ``assets/catalog/characters.json`` (english name
   and combat role), which only ever annotate characters the art library knows
   about and never invent new ones,
3. the records the user edited inside the app, which annotate an existing entry
   but can never introduce a character of their own.

A character's ``name`` remains a stable display/database key. The bundled
``folder`` annotation maps English asset and mod directories to this key.
Two explicit utility categories are included alongside the portrait roster.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import paths
from .naming import ELEMENT_IDS, SPECIAL_CATEGORIES, character_for

ELEMENT_ORDER = paths.ELEMENTS


def slugify(name: str) -> str:
    """Filesystem safe, stable identifier for a (possibly Chinese) name."""
    ascii_name = re.sub(r"[^0-9a-zA-Z]+", "-", name).strip("-").lower()
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"{ascii_name[:32]}-{digest}" if ascii_name else digest


@dataclass
class Character:
    """A single album: one character wearing one armor."""

    name: str
    name_en: str = ""
    element: str = ""
    role: str = ""
    portrait: str = ""
    user_defined: bool = False

    @property
    def special(self) -> bool:
        return self.name in SPECIAL_CATEGORIES

    # ----------------------------------------------------------------- naming
    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def base_name(self) -> str:
        """The character without the armor, e.g. ``凯茜娅``."""
        head, _sep, _tail = self.name.partition("-")
        return head or self.name

    @property
    def armor_name(self) -> str:
        """The armor part, e.g. ``狂诗`` (empty for a plain character name)."""
        _head, _sep, tail = self.name.partition("-")
        return tail

    @property
    def pretty_name(self) -> str:
        """Display form, e.g. ``凯茜娅 · 狂诗``."""
        return self.name.replace("-", " · ")

    @property
    def subtitle(self) -> str:
        return self.role

    # ------------------------------------------------------------- (de)serial
    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, user_defined: bool = False) -> Character:
        return cls(
            name=str(raw.get("name") or ""),
            name_en=str(raw.get("name_en") or ""),
            element=str(raw.get("element") or ""),
            role=str(raw.get("role") or ""),
            portrait=str(raw.get("portrait") or ""),
            user_defined=user_defined,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "name_en": self.name_en,
            "element": self.element,
            "role": self.role,
            "portrait": self.portrait,
        }


def _read_json(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, dict):
        raw = raw.get("characters") or []
    return [item for item in raw if isinstance(item, dict) and item.get("name")]


def _element_rank(element: str) -> int:
    try:
        return ELEMENT_ORDER.index(element)
    except ValueError:
        return len(ELEMENT_ORDER)


def scan_art(root: Path) -> list[Character]:
    """Turn ``<root>/<element>/<character>.png`` into character entries.

    The 40x40 element icons that sit next to the portraits are skipped, along
    with anything that is not an image.
    """
    found: list[Character] = []
    if not root.exists():
        return found
    folders = sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: _element_rank(item.name))
    for folder in folders:
        for image in sorted(folder.iterdir()):
            if image.suffix.lower() not in paths.IMAGE_SUFFIXES or image.stem == folder.name:
                continue
            element = next((cn for cn, en in ELEMENT_IDS.items() if en == folder.name), folder.name)
            found.append(Character(name=character_for(image.stem), element=element, portrait=str(image)))
    for image in sorted(item for item in root.iterdir() if item.is_file()):
        if image.suffix.lower() in paths.IMAGE_SUFFIXES:
            found.append(Character(name=image.stem, portrait=str(image)))
    return found


class Catalog:
    """Merged, queryable view over every character source."""

    def __init__(self, characters: Iterable[Character] = ()) -> None:
        self._characters: dict[str, Character] = {}
        for character in characters:
            self.merge(character)

    # ---------------------------------------------------------------- loading
    @classmethod
    def load(
        cls,
        user_characters: Iterable[dict[str, Any]] = (),
        art_dir: Path | None = None,
    ) -> Catalog:
        catalog = cls(scan_art(art_dir or paths.ART_DIR))
        for item in _read_json(paths.asset("catalog", "characters.json")):
            annotation = Character.from_dict(item)
            if annotation.name in catalog:
                catalog.merge(annotation)
        for item in user_characters or ():
            character = Character.from_dict(item, user_defined=True)
            # A stored record may only annotate a character the art library
            # already knows about: the roster is fixed, so a stale or renamed
            # record must never grow it.
            if character.name in catalog:
                catalog.merge(character)
        if art_dir is None or art_dir == paths.ART_DIR:
            for name, english in SPECIAL_CATEGORIES.items():
                catalog.merge(Character(name=name, name_en=english))
        return catalog

    def merge(self, character: Character) -> Character:
        """Add ``character`` or merge it into an existing entry by name."""
        existing = self._characters.get(character.name)
        if existing is None:
            self._characters[character.name] = character
            return character
        for field_name in ("name_en", "element", "role", "portrait"):
            value = getattr(character, field_name)
            if field_name == "portrait" and value and not Path(value).is_file():
                continue
            if value:
                setattr(existing, field_name, value)
        existing.user_defined = existing.user_defined or character.user_defined
        return existing

    def reload(
        self,
        user_characters: Iterable[dict[str, Any]] = (),
        art_dir: Path | None = None,
    ) -> None:
        """Refresh in place, keeping every existing reference to this catalog valid."""
        fresh = type(self).load(user_characters, art_dir)
        self._characters = fresh._characters

    # ---------------------------------------------------------------- queries
    def get(self, name: str) -> Character | None:
        return self._characters.get(name)

    def ensure(self, name: str) -> Character:
        """Return the character, creating a placeholder entry when unknown."""
        if not name:
            name = "-"
        found = self._characters.get(name)
        if found is None:
            found = Character(name=name, user_defined=True)
            self._characters[name] = found
        return found

    def all(self) -> list[Character]:
        """Every character, grouped by element and then by name."""
        return sorted(self._characters.values(), key=lambda item: (_element_rank(item.element), item.name))

    def names(self) -> list[str]:
        return [character.name for character in self.all()]

    def of_element(self, element: str) -> list[Character]:
        return [character for character in self.all() if character.element == element]

    def elements(self) -> list[str]:
        """Every element that actually has characters, in game order."""
        present = {character.element for character in self._characters.values() if character.element}
        return sorted(present, key=_element_rank)

    def siblings(self, name: str) -> list[Character]:
        """The other armors of the same character."""
        base = self.ensure(name).base_name
        return [item for item in self.all() if item.base_name == base and item.name != name]

    def __contains__(self, name: object) -> bool:
        return name in self._characters

    def __iter__(self):
        return iter(self.all())

    def __len__(self) -> int:
        return len(self._characters)
