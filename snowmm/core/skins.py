"""Offline, source-attributed skin catalog for each character armor."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from . import paths
from .naming import SPECIAL_CATEGORIES


@dataclass(frozen=True)
class Skin:
    id: str
    name: str
    name_en: str


@lru_cache(maxsize=1)
def _catalog() -> dict[str, list[Skin]]:
    payload = json.loads(paths.asset("catalog", "skins.json").read_text(encoding="utf-8"))
    result: dict[str, list[Skin]] = {}
    for item in payload["skins"]:
        result.setdefault(item["character"], []).append(Skin(item["id"], item["name"], item["name_en"]))
    return result


def skins_for(character: str) -> list[Skin]:
    default = Skin("default", "默认皮肤", "Default")
    return [default] if character in SPECIAL_CATEGORIES else [default, *_catalog().get(character, [])]


def valid_skin(character: str, skin: str) -> bool:
    return any(item.id == skin for item in skins_for(character))
