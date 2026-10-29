"""JSON backed storage for mods and user defined characters."""

from __future__ import annotations

import contextlib
import json
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from . import paths
from .models import Mod

SCHEMA_VERSION = 4


class Store:
    """Loads and persists the application database.

    Writes are atomic (temp file plus ``os.replace``) so a crash can never leave
    a truncated database behind.  Unknown keys are preserved so a database
    written by a newer version is not silently downgraded.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or paths.DATA_FILE
        self.mods: list[Mod] = []
        self.characters: list[dict[str, Any]] = []
        self.extra: dict[str, Any] = {}
        self.dirty = False

    # ---------------------------------------------------------------- loading
    def load(self) -> Store:
        if not self.path.exists():
            return self
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            with contextlib.suppress(OSError):
                shutil.copy2(self.path, self.path.with_suffix(".corrupt.json"))
            return self
        if isinstance(raw, list):  # a legacy projects.json dropped in place
            raw = {"mods": raw}
        self.mods = [Mod.from_dict(item) for item in raw.get("mods") or []]
        self.characters = list(raw.get("characters") or [])
        self.extra = {
            key: value
            for key, value in raw.items()
            if key not in {"schema", "mods", "presets", "characters"}
        }
        return self

    # ---------------------------------------------------------------- saving
    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = dict(self.extra)
        data.update(
            {
                "schema": SCHEMA_VERSION,
                "mods": [mod.to_dict() for mod in self.mods],
                "characters": self.characters,
            }
        )
        return data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        self.dirty = False

    # ------------------------------------------------------------------ mods
    def get_mod(self, mod_id: str) -> Mod | None:
        for mod in self.mods:
            if mod.id == mod_id:
                return mod
        return None

    def get_mods(self, mod_ids: Iterable[str]) -> list[Mod]:
        wanted = set(mod_ids)
        return [mod for mod in self.mods if mod.id in wanted]

    def add_mod(self, mod: Mod) -> Mod:
        self.mods.append(mod)
        self.dirty = True
        return mod

    def add_mods(self, mods: Iterable[Mod]) -> list[Mod]:
        added = list(mods)
        self.mods.extend(added)
        if added:
            self.dirty = True
        return added

    def remove_mods(self, mods: Iterable[Mod]) -> None:
        doomed = {mod.id for mod in mods}
        if not doomed:
            return
        self.mods = [mod for mod in self.mods if mod.id not in doomed]
        self.dirty = True

    def find_mod_by_file(self, file_path: str) -> Mod | None:
        key = str(Path(file_path)).lower().replace(".disabled", "")
        for mod in self.mods:
            if str(mod.enabled_path).lower() == key:
                return mod
        return None

    def mods_of(self, character: str) -> list[Mod]:
        return [mod for mod in self.mods if mod.character == character]

    def characters_with_mods(self) -> list[str]:
        seen: dict[str, None] = {}
        for mod in self.mods:
            if mod.character:
                seen.setdefault(mod.character, None)
        return list(seen)

    # ------------------------------------------------------ custom characters
    def upsert_character(self, payload: dict[str, Any]) -> None:
        name = str(payload.get("name") or "")
        for index, item in enumerate(self.characters):
            if str(item.get("name")) == name:
                self.characters[index] = payload
                self.dirty = True
                return
        self.characters.append(payload)
        self.dirty = True
