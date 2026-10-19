"""Refresh bundled, text-free portraits from the public GameKee character index.

Developer-only network tool. Runtime remains completely offline. Run from the
repository root with Pillow installed: python tools/refresh_artwork.py
"""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".work" / "release-assets"
ASSETS = ROOT / "snowmm" / "assets"
INDEX = "https://www.gamekee.com/v1/wiki/entry"
SPARKDRIVE = "https://patchwiki.biligame.com/images/sonw/3/36/953m3n3883y9o1sjaxh6gdaq0v8q6n0.png"


def download(url: str, target: Path, *, api: bool = False) -> bytes:
    if target.exists() and target.stat().st_size:
        return target.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    command = ["curl.exe", "-L", "--fail", "--silent", "--show-error", "--retry", "2",
               "--max-time", "60", "-A", "Mozilla/5.0", "-e", "https://www.gamekee.com/"]
    if api:
        command += ["-H", "game-alias: snow", "-H", "X-Requested-With: XMLHttpRequest"]
    temporary = target.with_suffix(target.suffix + ".download")
    subprocess.run([*command, url, "-o", str(temporary)], check=True)
    temporary.replace(target)
    return target.read_bytes()


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def refresh(character, entries):
    name = character["name"]
    armor = name.split("-", 1)[1]
    if name == "芙提雅-炬芯":
        image_url = SPARKDRIVE
        source = "https://wiki.biligame.com/sonw/芙提雅·炬芯"
    else:
        entry = next(item for item in entries if item["name"].strip("[]") == armor)
        source = f"https://www.gamekee.com/snow/{entry['content_id']}.html"
        # The roster card is the deliberate, text-free portrait crop. Some
        # profile images are in-game screenshots with name plates baked in.
        image_url = entry["icon"]
        if image_url.startswith("//"):
            image_url = "https:" + image_url
    payload = download(image_url, CACHE / f"{name}-card.image")
    image = Image.open(io.BytesIO(payload)).convert("RGBA")
    image.load()
    if min(image.size) < 100:
        raise ValueError(f"{name}: invalid portrait dimensions {image.size}")
    target = ASSETS / "characters" / character["element"] / f"{name}.png"
    image.save(target, optimize=True)
    return {"name": name, "file": target.relative_to(ASSETS).as_posix(),
            "source_page": source, "image_url": image_url,
            "width": image.width, "height": image.height,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def main():
    CACHE.mkdir(parents=True, exist_ok=True)
    data = json.loads(download(INDEX, CACHE / "gamekee-entries.json", api=True))
    entries = next(node["child"] for node in walk(data) if node.get("id") == 121233)
    catalog = json.loads((ASSETS / "catalog" / "characters.json").read_text(encoding="utf-8"))
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(refresh, item, entries): item["name"] for item in catalog}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(f"[{len(results)}/{len(catalog)}] {result['name']} {result['width']}x{result['height']}", flush=True)
    manifest = {
        "retrieved": "2026-10-19",
        "rights": "Game artwork belongs to Amazing Seasun Games; see third-party notices.",
        "portraits": sorted(results, key=lambda item: item["name"]),
    }
    (ASSETS / "catalog" / "artwork.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


if __name__ == "__main__":
    main()
