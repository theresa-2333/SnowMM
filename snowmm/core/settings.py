"""User preferences persisted to ``settings.json``."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import paths

THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEMES = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)

LANGUAGES = ("zh_CN", "en_US")


@dataclass
class Settings:
    """Everything the user can tweak, with sane defaults for a fresh install."""

    storage_path: str = ""
    game_exe: str = ""
    game_args: str = ""
    theme: str = THEME_DARK
    language: str = "zh_CN"
    hide_empty_characters: bool = False
    favorites: list[str] = field(default_factory=list)
    window_geometry: str = ""
    last_page: str = "characters"
    confirm_delete: bool = True

    # ---------------------------------------------------------------- helpers
    @property
    def storage_dir(self) -> Path | None:
        return Path(self.storage_path) if self.storage_path else None

    def is_favorite(self, character: str) -> bool:
        return character in self.favorites

    def toggle_favorite(self, character: str) -> bool:
        if character in self.favorites:
            self.favorites.remove(character)
            return False
        self.favorites.append(character)
        return True

    # ------------------------------------------------------------ (de)serial
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Settings:
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        data = {key: value for key, value in (raw or {}).items() if key in known}
        settings = cls(**data)
        if settings.theme not in THEMES:
            settings.theme = THEME_DARK
        if settings.language not in LANGUAGES:
            settings.language = "zh_CN"
        return settings

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        target = path or paths.SETTINGS_FILE
        if not target.exists():
            return cls()
        try:
            return cls.from_dict(json.loads(target.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError):
            return cls()

    def save(self, path: Path | None = None) -> None:
        target = path or paths.SETTINGS_FILE
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(target)
