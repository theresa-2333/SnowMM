"""Fetch the Snowbreak character roster and portraits for SnowMM's art library.

The wiki is the reference for the roster, but it is not reachable from every
network (and it rate limits hard), so this helper is completely optional: the app
ships with all 54 portraits and works offline.

This is a developer tool - it only ever refreshes the *source* portraits inside
the package, so it is meant to be run from a checkout, not from an installed
build.  The roster is exactly what lives in the art library, so a portrait that
is not moved into the right element folder shows up as a character without a
damage type.

Usage
-----
    python tools/fetch_catalog.py                  # fetch the wiki page + portraits
    python tools/fetch_catalog.py --no-images      # roster only (fast, text only)
    python tools/fetch_catalog.py --from-file page.html
    python tools/fetch_catalog.py --page 角色 --limit 200

Portraits are written into the **art library** the app reads
(``snowmm/assets/characters/``, see ``snowmm/core/paths.py``); move a downloaded
file into ``<属性>/`` to give it an element.  ``--out`` picks another directory.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from snowmm.core import paths  # noqa: E402
from snowmm.core.naming import folder_for  # noqa: E402

WIKI_BASE = "https://wiki.biligame.com/sonw/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
SKIP_TITLES = {"角色", "首页", "编辑", "模板", "分类", "文件", "讨论", "帮助", "特殊"}


class RosterParser(HTMLParser):
    """Collects ``/sonw/<character>`` links and the image next to each one."""

    def __init__(self) -> None:
        super().__init__()
        self.entries: dict[str, str] = {}
        self._current: str | None = None
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: (value or "") for key, value in attrs}
        if tag == "a":
            href = attributes.get("href", "")
            title = attributes.get("title", "").strip()
            match = re.search(r"/sonw/([^#?]+)", href)
            if match:
                name = urllib.parse.unquote(title or match.group(1)).strip()
                if name and name not in SKIP_TITLES and not name.startswith(("T:", "模板:")):
                    self._current = name
                    self._depth = 0
                    self.entries.setdefault(name, "")
        elif tag == "img" and self._current is not None and self._depth < 3:
            source = attributes.get("src") or attributes.get("data-src") or ""
            if source and not self.entries.get(self._current):
                self.entries[self._current] = source
        if self._current is not None:
            self._depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._current is not None:
            self._depth -= 1
            if tag == "a" or self._depth <= 0:
                self._current = None


def fetch(url: str, timeout: int = 30) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Referer": WIKI_BASE},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def download_page(page: str) -> str:
    api = (
        f"{WIKI_BASE}api.php?action=parse&prop=text&format=json&formatversion=2"
        f"&page={urllib.parse.quote(page)}"
    )
    payload = json.loads(fetch(api).decode("utf-8", errors="replace"))
    return payload.get("parse", {}).get("text", "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", default="角色", help="wiki page name (default: 角色)")
    parser.add_argument("--from-file", help="parse a locally saved HTML file instead of the network")
    parser.add_argument("--no-images", action="store_true", help="skip portrait downloads")
    parser.add_argument("--limit", type=int, default=0, help="stop after N characters")
    parser.add_argument("--out", help="download portraits here instead of the art library")
    arguments = parser.parse_args()

    if arguments.from_file:
        html = Path(arguments.from_file).read_text(encoding="utf-8", errors="replace")
    else:
        try:
            html = download_page(arguments.page)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            print(f"! could not reach the wiki ({error}).")
            print("  Save the page manually and rerun with --from-file page.html,")
            print("  or keep using the portraits that ship inside snowmm/assets/characters/.")
            return 2

    roster = RosterParser()
    roster.feed(html)
    names = list(roster.entries)
    if arguments.limit:
        names = names[: arguments.limit]
    if not names:
        print("! no character links found - the wiki markup may have changed.")
        return 1

    art_root = Path(arguments.out) if arguments.out else paths.resolve_art_dir()
    art_root.mkdir(parents=True, exist_ok=True)
    saved_count = 0
    for index, name in enumerate(names, start=1):
        portrait = roster.entries.get(name, "")
        if portrait and not arguments.no_images:
            target = art_root / f"{folder_for(name.replace('·', '-'))}.png"
            if not target.exists():
                try:
                    target.write_bytes(fetch(portrait))
                    saved_count += 1
                except (urllib.error.URLError, TimeoutError, OSError) as error:
                    print(f"  ! {name}: {error}")
        print(f"[{index}/{len(names)}] {name}")

    print(f"\n{len(names)} characters found, {saved_count} new portraits in {art_root}")
    print("restart SnowMM (or press 刷新) to pick them up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
