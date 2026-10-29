"""Stable ASCII storage names, independent of UI language and user annotations."""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache

from . import paths

SPECIAL_CATEGORIES = {"基地": "Base", "杂项": "Miscellaneous"}
ELEMENT_IDS = {"高热": "thermal", "低温": "frost", "电击": "electrical", "动能": "kinetic", "特异": "chaos"}


def ascii_stem(value: str, fallback: str = "mod") -> str:
    """Preserve existing ASCII names and Unreal's trailing mount marker."""
    if value.isascii():
        return value
    marker = "_100_P" if value.lower().endswith("_100_p") else ""
    head = value[:-6] if marker else value
    readable = re.sub(r"[^a-zA-Z0-9_-]+", "-", head).strip("-")[:48]
    digest = hashlib.sha256(value.encode()).hexdigest()[:10]
    return f"{readable or fallback}-{digest}{marker}"


@lru_cache(maxsize=1)
def character_folders() -> dict[str, str]:
    roster = json.loads(paths.asset("catalog", "characters.json").read_text(encoding="utf-8"))
    return {**{item["name"]: item["folder"] for item in roster}, **SPECIAL_CATEGORIES}


def folder_for(character: str) -> str:
    return character_folders().get(character, ascii_stem(character, "character"))


def character_for(folder: str) -> str:
    return next((name for name, value in character_folders().items() if value.casefold() == folder.casefold()), folder)
