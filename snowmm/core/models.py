"""Core data structures shared by the storage, catalog and UI layers."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

DISABLED_SUFFIX = ".disabled"

# Extensions treated as part of a mod when importing folders or archives.
MOD_EXTENSIONS = (".pak", ".utoc", ".ucas", ".sig", ".ini", ".txt", ".json", ".png", ".jpg")
ARCHIVE_EXTENSIONS = (".zip", ".7z", ".rar")


def new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


@dataclass
class Mod:
    """A single mod file tracked by the manager.

    ``file`` always stores the *enabled* path.  Whether a mod is currently
    active is derived from the filesystem (the game only mounts ``*.pak`` files
    that are not renamed to ``*.pak.disabled``), so the flag is never persisted.
    """

    name: str = ""
    file: str = ""
    id: str = field(default_factory=lambda: new_id("mod_"))
    #: Stable character key such as ``凯茜娅-狂诗``; naming.py maps it to disk.
    character: str = ""
    skin: str = "default"
    author: str = ""
    source_url: str = ""
    note: str = ""
    preview: str = ""
    added_at: str = field(default_factory=now_iso)
    tags: list[str] = field(default_factory=list)
    size: int = 0
    enabled: bool = False  # transient, refreshed from disk

    # ------------------------------------------------------------------ paths
    @property
    def enabled_path(self) -> Path:
        text = str(self.file)
        if text.endswith(DISABLED_SUFFIX):
            text = text[: -len(DISABLED_SUFFIX)]
        return Path(text)

    @property
    def disabled_path(self) -> Path:
        return Path(str(self.enabled_path) + DISABLED_SUFFIX)

    @property
    def exists(self) -> bool:
        return self.enabled_path.exists() or self.disabled_path.exists()

    @property
    def disk_path(self) -> Path:
        """The path that currently exists on disk (enabled or not)."""
        return self.enabled_path if self.enabled_path.exists() else self.disabled_path

    @property
    def filename(self) -> str:
        return self.enabled_path.name

    @property
    def stem(self) -> str:
        return self.enabled_path.stem

    @property
    def extension(self) -> str:
        return self.enabled_path.suffix.lower()

    @property
    def directory(self) -> Path:
        return self.enabled_path.parent

    @property
    def base_name(self) -> str:
        """The character without the armor, e.g. ``凯茜娅``."""
        head, _, _tail = self.character.partition("-")
        return head or self.character

    @property
    def armor_name(self) -> str:
        """The armor part of the name, e.g. ``狂诗`` (may be empty)."""
        _head, _, tail = self.character.partition("-")
        return tail

    @property
    def pretty_name(self) -> str:
        """Display form of the full name, e.g. ``凯茜娅 · 狂诗``."""
        return self.character.replace("-", " · ")

    @property
    def category(self) -> tuple[str, ...]:
        return (self.character,)

    def refresh_size(self) -> int:
        for candidate in (self.enabled_path, self.disabled_path):
            try:
                self.size = candidate.stat().st_size
                return self.size
            except OSError:
                continue
        self.size = 0
        return 0

    # ------------------------------------------------------------- (de)serial
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "file": self.file,
            "character": self.character,
            "skin": self.skin,
            "author": self.author,
            "source_url": self.source_url,
            "note": self.note,
            "preview": self.preview,
            "added_at": self.added_at,
            "tags": list(self.tags),
            "size": self.size,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Mod:
        """Build a mod from stored JSON, accepting the legacy v0.2.x schema."""
        raw_file = str(raw.get("file") or raw.get("path") or "")
        character = str(raw.get("character") or raw.get("category1") or "")
        # 0.2.x kept the character and the armor in two fields; the new layout
        # keys everything off one "character-armor" name.
        armor = str(raw.get("armor") or raw.get("category2") or "")
        if armor and "-" not in character:
            character = f"{character}-{armor}"
        return cls(
            id=str(raw.get("id") or new_id("mod_")),
            name=str(raw.get("name") or Path(raw_file).stem),
            file=raw_file,
            character=character,
            skin=str(raw.get("skin") or "default"),
            author=str(raw.get("author") or ""),
            source_url=str(raw.get("source_url") or raw.get("url") or ""),
            note=str(raw.get("note") or ""),
            preview=str(raw.get("preview") or raw.get("image_path") or ""),
            added_at=str(raw.get("added_at") or now_iso()),
            tags=[str(tag) for tag in raw.get("tags") or []],
            size=int(raw.get("size") or 0),
        )


def unique_in_order(items: Iterable[str]) -> list[str]:
    """Return ``items`` with duplicates and empty values removed."""
    seen: dict[str, None] = {}
    for item in items:
        if item and item not in seen:
            seen[item] = None
    return list(seen)


def human_size(num_bytes: int) -> str:
    size = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"
