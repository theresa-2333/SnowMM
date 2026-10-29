"""Refresh the offline skin catalog from BWIKI's outfit index.

Usage: python tools/fetch_skins.py [--from-file saved.html]
Only names and their source are stored; no network is used by the app.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.fetch_catalog import fetch

SOURCE = "https://wiki.biligame.com/sonw/%E6%97%B6%E8%A3%85%E4%B8%80%E8%A7%88"


def parse_skins(page: str, names: set[str]) -> tuple[list[dict], list[str]]:
    records: dict[tuple[str, str], dict] = {}
    unmatched = set()
    for heading in re.findall(r"<h3\b[^>]*>(.*?)</h3>", page, re.S):
        text = html.unescape(re.sub(r"<[^>]+>", "", heading)).strip()
        match = re.fullmatch(r"(.+?)[|丨](.+?)「(.+?)」", text)
        if not match:
            continue
        character, name, english = (part.strip() for part in match.groups())
        character = character.replace("·", "-")
        if character not in names:
            unmatched.add(character)
            continue
        skin_id = re.sub(r"[^a-z0-9]+", "-", english.lower()).strip("-")
        if not skin_id:
            raise ValueError(f"Missing English skin name: {text}")
        records[(character, name)] = {
            "character": character, "id": skin_id, "name": name,
            "name_en": english, "source": SOURCE,
        }
    return list(records.values()), sorted(unmatched)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-file", type=Path)
    args = parser.parse_args()
    page = args.from_file.read_text(encoding="utf-8") if args.from_file else fetch(SOURCE).decode("utf-8")
    roster = json.loads((ROOT / "snowmm/assets/catalog/characters.json").read_text(encoding="utf-8"))
    skins, unmatched = parse_skins(page, {item["name"] for item in roster})
    if not skins:
        raise ValueError("No skins found; catalog left unchanged")
    payload = {"source": SOURCE, "retrieved": date.today().isoformat(),
               "scope": "BWIKI outfit index, existing bundled roster only",
               "unmatched_characters": unmatched, "skins": skins}
    (ROOT / "snowmm/assets/catalog/skins.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(skins)} skins; {len(unmatched)} characters outside bundled roster")


if __name__ == "__main__":
    main()
