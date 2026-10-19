"""Import data from the previous ``~/.snowbreak_mod_manager`` layout."""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

from . import paths
from .models import DISABLED_SUFFIX, MOD_EXTENSIONS, Mod
from .settings import Settings
from .store import Store


def legacy_available() -> bool:
    return paths.LEGACY_PROJECTS_FILE.exists()


def _load_legacy_config() -> dict:
    try:
        return json.loads(paths.LEGACY_CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def migrate(store: Store, settings: Settings, copy_images: bool = True) -> tuple[int, list[str]]:
    """Merge legacy mod records and settings into the new database.

    Returns the number of imported mods plus a list of warnings.  Existing
    entries (matched by file path) are left untouched, so running the migration
    twice is safe.
    """
    warnings: list[str] = []
    if not legacy_available():
        return 0, warnings
    try:
        raw = json.loads(paths.LEGACY_PROJECTS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return 0, [str(error)]

    existing = {str(mod.enabled_path).lower() for mod in store.mods}
    imported = 0
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        mod = Mod.from_dict(item)
        if not mod.file or str(mod.enabled_path).lower() in existing:
            continue
        if copy_images and mod.preview:
            mod.preview = _copy_legacy_image(mod.preview, mod.id)
        store.add_mod(mod)
        existing.add(str(mod.enabled_path).lower())
        imported += 1

    config = _load_legacy_config()
    if not settings.storage_path and config.get("storage_path"):
        settings.storage_path = str(config["storage_path"])
    if config.get("theme") in {"light", "dark"}:
        settings.theme = str(config["theme"])
    if config.get("language") in {"zh_CN", "en_US"}:
        settings.language = str(config["language"])

    if imported:
        store.save()
    settings.save()
    return imported, warnings


def _copy_legacy_image(source: str, mod_id: str) -> str:
    """Copy a preview image out of the legacy folder so it survives an upgrade."""
    path = Path(source)
    if not path.exists():
        return source
    try:
        paths.PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        destination = paths.PREVIEW_DIR / f"{mod_id}{path.suffix.lower()}"
        shutil.copy2(path, destination)
        return str(destination)
    except OSError:
        return source


# ------------------------------------------------------- folder layout upgrade
def _mod_files(folder: Path) -> list[Path]:
    try:
        return [
            item for item in folder.iterdir()
            if item.is_file() and Path(item.name.removesuffix(DISABLED_SUFFIX)).suffix.lower() in MOD_EXTENSIONS
        ]
    except OSError:
        return []


def _subfolders(folder: Path) -> list[Path]:
    try:
        return sorted(item for item in folder.iterdir() if item.is_dir())
    except OSError:
        return []


def legacy_layout_count(base: Path | None) -> int:
    """How many folders still use the old ``<character>/<armor>/[<outfit>]`` tree."""
    if base is None or not base.exists():
        return 0
    total = 0
    for character in _subfolders(base):
        if _mod_files(character):
            continue
        for armor in _subfolders(character):
            if _mod_files(armor) or _subfolders(armor):
                total += 1
    return total


def _prune(folder: Path, stop: Path) -> None:
    """Remove ``folder`` and any parent that became empty, stopping at ``stop``."""
    current = folder
    while current != stop:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def flatten_layout(
    base: Path | None,
    progress: Callable[[int, int, str], None] | None = None,
    *,
    store: Store | None = None,
) -> tuple[int, list[str]]:
    """Rewrite ``<character>/<armor>/<outfit>`` into ``<character>-<armor>``.

    File names are preserved so the game keeps mounting them; the outfit level
    is folded into the armor name because the new layout keys everything off the
    full character name.  Returns the number of moved files plus warnings.
    """
    from .manager import ModManager

    warnings: list[str] = []
    moved = 0
    if base is None or not base.exists():
        return moved, warnings

    jobs: list[tuple[Path, Path, list[tuple[str, list[Path], Path | None]]]] = []
    for character in _subfolders(base):
        if _mod_files(character):
            continue  # already the flat layout
        for armor in _subfolders(character):
            groups: list[tuple[str, list[Path], Path | None]] = [("", _mod_files(armor), None)]
            groups.extend((outfit.name, _mod_files(outfit), outfit) for outfit in _subfolders(armor))
            if any(files for _name, files, _folder in groups):
                jobs.append((armor, base / f"{character.name}-{armor.name}", groups))

    total = len(jobs)
    for index, (armor, target, groups) in enumerate(jobs, start=1):
        if progress:
            progress(index, total, target.name)
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            warnings.append(f"{target.name}: {error}")
            continue
        for outfit_name, files, folder in groups:
            packages: dict[str, list[Path]] = {}
            for source in files:
                stem = Path(source.name.removesuffix(DISABLED_SUFFIX)).stem
                packages.setdefault(stem, []).append(source)
            for stem, package in packages.items():
                new_stem = ModManager._package_stem(target, stem)
                moves = []
                for source in package:
                    bare = Path(source.name.removesuffix(DISABLED_SUFFIX))
                    suffix = bare.suffix + (DISABLED_SUFFIX if source.name.endswith(DISABLED_SUFFIX) else "")
                    moves.append((source, target / f"{new_stem}{suffix}"))
                error = ModManager._relocate(moves)
                if error:
                    warnings.append(f"{stem}: {error}")
                    continue
                if new_stem != stem:
                    label = f" [{outfit_name}]" if outfit_name else ""
                    warnings.append(f"{stem}{label} -> {new_stem}")
                moved += len(moves)
                if store is not None:
                    for source, destination in moves:
                        key = str(source).removesuffix(DISABLED_SUFFIX).casefold()
                        for mod in store.mods:
                            if str(mod.enabled_path).casefold() == key:
                                mod.file = str(destination).removesuffix(DISABLED_SUFFIX)
                                mod.character = target.name
            if folder is not None:
                _prune(folder, base)
        _prune(armor, base)
    if moved and store is not None:
        store.save()
    return moved, warnings
