"""Verify the exact portrait bytes inside every release archive and its hashes."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "dist" / "release"


def check_assets(bundle: zipfile.ZipFile, prefix: str):
    manifest = json.loads(bundle.read(prefix + "catalog/artwork.json"))
    assert len(manifest["portraits"]) == 54
    for entry in manifest["portraits"]:
        assert hashlib.sha256(bundle.read(prefix + entry["file"])).hexdigest() == entry["sha256"]
    names = json.loads(bundle.read(prefix + "catalog/characters.json"))
    assert len(names) == 54 and all(item.get("name_en") for item in names)
    assert prefix + "icons/app.ico" in bundle.namelist()
    assert prefix + "licenses/LGPL-3.0.txt" in bundle.namelist()


def main():
    for line in (OUTPUT / "SHA256SUMS.txt").read_text().splitlines():
        expected, name = line.split("  ", 1)
        assert hashlib.sha256((OUTPUT / name).read_bytes()).hexdigest() == expected, name
    for target in sorted([*OUTPUT.glob("*.zip"), *OUTPUT.glob("*.whl")]):
        with zipfile.ZipFile(target) as bundle:
            manifest = next(name for name in bundle.namelist() if name.endswith("catalog/artwork.json"))
            prefix = manifest.removesuffix("catalog/artwork.json")
            check_assets(bundle, prefix)
            assert not any(part in {".work", ".build-deps", "__pycache__"}
                           for name in bundle.namelist() for part in name.split("/"))
        print(f"verified {target.name}: 54 image hashes, names, icons, licenses")
    report = json.loads((ROOT / "dist" / "release-self-test.json").read_text(encoding="utf-8"))
    assert report.get("ok"), report
    print("All release archives and frozen application verified.")


if __name__ == "__main__":
    main()
