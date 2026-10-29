"""Detect and repair known old layouts without touching unrelated folders."""
from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from .models import DISABLED_SUFFIX, Mod
from .naming import character_for
from .skins import skins_for, valid_skin


def _skin(character: str, label: str) -> str:
    return next((skin.id for skin in skins_for(character)
                 if label.casefold() in {skin.id.casefold(), skin.name.casefold(), skin.name_en.casefold()}), "default")


def infer_category(folders: tuple[str, ...], known: set[str]) -> tuple[str, str] | None:
    if not folders:
        return None
    character = character_for(folders[0].replace("·", "-"))
    consumed = 1
    if character not in known and len(folders) > 1:
        character = f"{folders[0]}-{folders[1]}"
        consumed = 2
    if character not in known:
        return None
    return character, _skin(character, folders[consumed]) if len(folders) > consumed else "default"


def repair_layout(manager, known_characters) -> tuple[int, list[str]]:
    """Back up only when needed; move each complete package with rollback.

    Supports v0.2 character/armor/outfit, v1.0 Chinese flat folders, Chinese
    outfit subfolders and old records already moved manually into English paths.
    Existing records keep their identity, names, notes, previews and enable state.
    """
    from .manager import PRIMARY_EXTENSIONS, _strip_disabled
    from .naming import ascii_stem

    base = manager.storage_dir
    if base is None or not base.is_dir():
        return 0, []
    known = set(known_characters)
    records = {str(mod.enabled_path.resolve()).casefold(): mod for mod in manager.mods}
    jobs = []
    seen = set()
    errors = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [name for name in dirs if not (Path(root) / name).is_symlink()]
        for filename in sorted(files):
            source = Path(root) / filename
            bare = Path(_strip_disabled(filename))
            if (bare.suffix.lower() not in PRIMARY_EXTENSIONS or source.is_symlink()
                    or not source.resolve().is_relative_to(base.resolve())):
                continue
            key = (source.parent.resolve(), bare.stem.casefold())
            if key in seen:
                continue
            seen.add(key)
            probe = Mod(file=str(source))
            package = manager.siblings(probe)
            primary = manager._pick_primary(package)
            if primary is None:
                continue
            matching = [records[str(Path(_strip_disabled(str(path))).resolve()).casefold()]
                        for path in package if str(Path(_strip_disabled(str(path))).resolve()).casefold() in records]
            category = infer_category(primary.relative_to(base).parts[:-1], known)
            if category is None:
                tracked = next((mod for mod in matching if mod.character in known), None)
                if tracked is None:
                    continue
                category = tracked.character, tracked.skin if valid_skin(tracked.character, tracked.skin) else "default"
            character, skin = category
            target = manager.skin_dir(character, skin)
            needs_move = primary.parent != target or not Path(_strip_disabled(primary.name)).stem.isascii()
            needs_record = not matching or any((mod.character, mod.skin) != category for mod in matching)
            if needs_move or needs_record:
                jobs.append((primary, package, matching, character, skin, needs_move))
    # Repair records left pointing at a Chinese path after an external folder rename.
    relinks = []
    for mod in manager.mods:
        if mod.exists:
            continue
        try:
            relative = mod.enabled_path.relative_to(base)
        except ValueError:
            continue
        category = infer_category(relative.parts[:-1], known)
        if category is None:
            continue
        character, skin = category
        candidate = manager.skin_dir(character, skin) / f"{ascii_stem(mod.stem)}{mod.extension}"
        if candidate.is_file() or Path(str(candidate) + DISABLED_SUFFIX).is_file():
            relinks.append((mod, candidate, character, skin))
            # Prefer the existing record over adopting a duplicate at its new path.
            for job in jobs:
                if str(Path(_strip_disabled(str(job[0])))).casefold() == str(candidate).casefold():
                    job[2].append(mod)
    if not jobs and not relinks:
        return 0, []
    try:
        manager.store.save()
        backup = manager.store.path.with_name(f"data-before-compatibility-{datetime.now():%Y%m%d-%H%M%S-%f}.json")
        shutil.copy2(manager.store.path, backup)
    except OSError as error:
        return 0, [f"Compatibility backup: {error}"]
    changed = 0
    for mod, candidate, character, skin in relinks:
        mod.file, mod.character, mod.skin = str(candidate), character, skin
        changed += 1
    for primary, _package, matching, character, skin, needs_move in jobs:
        mod = matching[0] if matching else Mod(
            name=Path(_strip_disabled(primary.name)).stem, file=str(primary), character=character, skin=skin)
        old_values = mod.file, mod.character, mod.skin
        mod.file = _strip_disabled(str(primary))
        try:
            if needs_move:
                target = manager.skin_dir(character, skin)
                if primary.parent == target:
                    stem = manager._package_stem(target, ascii_stem(mod.stem))
                    error = manager.rename_stem(mod, stem)
                else:
                    error = manager.move_mod(mod, character, skin)
                if error:
                    mod.file, mod.character, mod.skin = old_values
                    errors.append(f"{primary.name}: {error}")
                    continue
            mod.character, mod.skin = character, skin
            if not matching:
                manager.store.add_mod(mod)
            for duplicate in matching[1:]:
                duplicate.file, duplicate.character, duplicate.skin = mod.file, character, skin
            changed += 1
        except (OSError, ValueError, RuntimeError) as error:
            # The manager owns filesystem rollback; keep the latest valid path
            # if saving fails after a successful move.
            errors.append(f"{primary.name}: {error}")
    manager.refresh_states()
    try:
        manager.store.save()
    except OSError as error:
        errors.append(f"Compatibility save: {error}")
    return changed, errors
