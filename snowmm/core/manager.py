"""Filesystem operations: importing, enabling, disabling, scanning, auditing.

Snowbreak loads every ``*.pak`` file inside ``Game/Content/Paks/mods`` (or a user
supplied folder).  A mod is therefore "enabled" when its files keep their real
extension and "disabled" when they are renamed to ``*.disabled`` - which is
exactly what the previous 0.x manager did, so existing collections keep working.

Files live in ``<mods>/<english-character-id>/[<english-skin-id>/]``. The
default skin stays at the character root. Database character keys remain
compatible with earlier releases; naming.py handles the directory mapping.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .models import ARCHIVE_EXTENSIONS, DISABLED_SUFFIX, Mod, unique_in_order
from .naming import SPECIAL_CATEGORIES, ascii_stem, character_for, folder_for
from .settings import Settings
from .skins import valid_skin
from .store import Store

PRIMARY_EXTENSIONS = (".pak", ".utoc")
PACKAGE_EXTENSIONS = (".pak", ".utoc", ".ucas", ".sig")

def _strip_disabled(name: str) -> str:
    """Return the file name without the trailing ``.disabled`` marker."""
    return name[: -len(DISABLED_SUFFIX)] if name.endswith(DISABLED_SUFFIX) else name


@dataclass
class Issue:
    """A problem detected in the current collection, rendered by the UI."""

    kind: str
    severity: str = "warning"  # "error" | "warning" | "info"
    data: dict[str, str] = field(default_factory=dict)
    mod_ids: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.kind}:{sorted(self.data.items())}:{sorted(self.mod_ids)}"


@dataclass
class ImportResult:
    added: list[Mod] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.added) and not self.errors


class ModManager:
    """All mutating operations against the mods directory."""

    def __init__(self, store: Store, settings: Settings) -> None:
        self.store = store
        self.settings = settings

    # ------------------------------------------------------------- basic info
    @property
    def mods(self) -> list[Mod]:
        return self.store.mods

    @property
    def storage_dir(self) -> Path | None:
        return self.settings.storage_dir

    def character_dir(self, character: str) -> Path | None:
        base = self.storage_dir
        if base is None:
            return None
        name = character.strip()
        if name in {".", ".."} or any(c in name for c in '/\\:<>"|?*'):
            raise ValueError("invalid character folder")
        return base / folder_for(name) if name else base

    def skin_dir(self, character: str, skin: str = "default") -> Path:
        if not valid_skin(character, skin):
            raise ValueError("invalid skin")
        directory = self.character_dir(character)
        if directory is None:
            raise RuntimeError("mods directory is not configured")
        # Default stays at the character root, preserving older flat collections.
        return directory if skin == "default" else directory / skin

    def ensure_character_dir(self, character: str) -> Path:
        directory = self.character_dir(character)
        if directory is None:
            raise RuntimeError("mods directory is not configured")
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def siblings(self, mod: Mod) -> list[Path]:
        """Every file that belongs to ``mod`` (``.pak`` plus ``.utoc``/``.ucas``)."""
        directory = mod.enabled_path.parent
        stem = mod.enabled_path.stem
        found: list[Path] = []
        try:
            entries = list(directory.iterdir())
        except OSError:
            return found
        for entry in entries:
            name = _strip_disabled(entry.name)
            if entry.is_file() and Path(name).stem == stem and Path(name).suffix.lower() in PACKAGE_EXTENSIONS:
                found.append(entry)
        return found

    def _prune_empty(self, directory: Path) -> None:
        """Remove a folder that just became empty, up to the mods root."""
        base = self.storage_dir
        if base is None:
            return
        current = directory
        while current != base and current.is_relative_to(base):
            try:
                current.rmdir()
            except OSError:
                return
            current = current.parent

    # ----------------------------------------------------------- state sync
    def is_enabled(self, mod: Mod) -> bool:
        return mod.enabled_path.exists()

    def refresh_states(self) -> int:
        """Re-read enable state and size from disk; returns how many changed."""
        changed = 0
        for mod in self.store.mods:
            was = mod.enabled
            mod.enabled = self.is_enabled(mod)
            mod.refresh_size()
            if was != mod.enabled:
                changed += 1
        return changed

    # ------------------------------------------------------- enable / disable
    def set_enabled(self, mods: Iterable[Mod], enabled: bool) -> tuple[int, list[str]]:
        changed = 0
        errors: list[str] = []
        for mod in mods:
            was_enabled = self.is_enabled(mod)
            error = self._set_enabled_one(mod, enabled)
            if error:
                errors.append(error)
            elif was_enabled != enabled:
                changed += 1
            mod.enabled = self.is_enabled(mod)
        self.store.dirty = True
        return changed, errors

    def _set_enabled_one(self, mod: Mod, enabled: bool) -> str | None:
        targets = self.siblings(mod)
        if not targets:
            return mod.filename
        moves = []
        for path in targets:
            text = str(path)
            if enabled and text.endswith(DISABLED_SUFFIX):
                new_path = Path(text[: -len(DISABLED_SUFFIX)])
            elif not enabled and not text.endswith(DISABLED_SUFFIX):
                new_path = Path(text + DISABLED_SUFFIX)
            else:
                continue
            moves.append((path, new_path))
        return self._relocate(moves)

    @staticmethod
    def _relocate(moves: Sequence[tuple[Path, Path]]) -> str | None:
        """Preflight a package operation and roll back if a file fails."""
        for _source, target in moves:
            if target.exists():
                return f"{target.name}: exists"
        completed = []
        try:
            for source, target in moves:
                shutil.move(str(source), str(target))
                completed.append((source, target))
        except OSError as error:
            failures = []
            for source, target in reversed(completed):
                try:
                    shutil.move(str(target), str(source))
                except OSError as rollback_error:
                    failures.append(str(rollback_error))
            return str(error) + (f"; rollback: {'; '.join(failures)}" if failures else "")
        return None

    def set_character_enabled(self, character: str, enabled: bool) -> tuple[int, list[str]]:
        return self.set_enabled(self.store.mods_of(character), enabled)

    def set_all_enabled(self, enabled: bool) -> tuple[int, list[str]]:
        return self.set_enabled(list(self.store.mods), enabled)

    # ---------------------------------------------------------------- import
    def import_paths(
        self,
        sources: Sequence[Path],
        *,
        character: str,
        skin: str = "default",
        name: str = "",
        author: str = "",
        source_url: str = "",
        note: str = "",
        preview: str = "",
        progress: Callable[[int, int, str], None] | None = None,
    ) -> ImportResult:
        """Copy files/folders/archives into the mods directory and track them."""
        result = ImportResult()
        # Keep staging alive until all discovered packages have been copied.
        with tempfile.TemporaryDirectory(prefix="snowmm-import-") as staging:
            from .archives import extract_packages

            expanded = []
            for index, source in enumerate(sources):
                if source.suffix.lower() not in ARCHIVE_EXTENSIONS:
                    expanded.append(source)
                    continue
                target = Path(staging) / str(index)
                target.mkdir()
                try:
                    extract_packages(source, target)
                    if not any(Path(_strip_disabled(p.name)).suffix.lower() in PRIMARY_EXTENSIONS
                               for p in target.rglob("*") if p.is_file()):
                        result.skipped.append(source.name)
                    expanded.append(target)
                except Exception as error:
                    result.errors.append(f"{source.name}: {error}")
            imported = self._import_files(
                expanded, character=character, skin=skin, name=name, author=author,
                source_url=source_url, note=note, preview=preview, progress=progress,
            )
            result.added.extend(imported.added)
            result.errors.extend(imported.errors)
            result.skipped.extend(imported.skipped)
        return result

    def _import_files(
        self, sources: Sequence[Path], *, character: str, skin: str, name: str,
        author: str, source_url: str, note: str, preview: str,
        progress: Callable[[int, int, str], None] | None,
    ) -> ImportResult:
        result = ImportResult()
        if self.storage_dir is None:
            result.errors.append("storage-path-missing")
            return result
        character = character.strip()
        if not character:
            result.errors.append("character-missing")
            return result
        try:
            target_dir = self.skin_dir(character, skin)
            target_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, RuntimeError, ValueError) as error:
            result.errors.append(str(error))
            return result
        # Discover each package once, even when both its pak and utoc were selected.
        groups: dict[tuple[Path, str], list[Path]] = {}
        for source in sources:
            candidates = sorted(source.rglob("*")) if source.is_dir() else [source]
            for candidate in candidates:
                bare = Path(_strip_disabled(candidate.name))
                if not candidate.is_file() or bare.suffix.lower() not in PRIMARY_EXTENSIONS:
                    continue
                if source.is_dir() and not candidate.resolve().is_relative_to(source.resolve()):
                    continue
                key = (candidate.parent.resolve(), bare.stem)
                if key in groups:
                    continue
                companions = [
                    item for item in candidate.parent.iterdir()
                    if item.is_file() and Path(_strip_disabled(item.name)).stem == bare.stem
                    and Path(_strip_disabled(item.name)).suffix.lower() in PACKAGE_EXTENSIONS
                    and item.resolve().parent == candidate.resolve().parent
                ]
                groups[key] = companions
            if not any(key[0] == source.parent.resolve() for key in groups) and not source.is_dir():
                result.skipped.append(source.name)
        total = len(groups)
        for index, files in enumerate(groups.values(), start=1):
            primary = self._pick_primary(files)
            if primary is None:
                continue
            if progress:
                progress(index, total, primary.name)
            copied: list[Path] = []
            try:
                stem = self._package_stem(target_dir, ascii_stem(Path(_strip_disabled(primary.name)).stem))
                for source in files:
                    bare = Path(_strip_disabled(source.name))
                    suffix = bare.suffix + (DISABLED_SUFFIX if source.name.endswith(DISABLED_SUFFIX) else "")
                    destination = target_dir / f"{stem}{suffix}"
                    # Exclusive creation protects an existing package from being overwritten.
                    with source.open("rb") as reader, destination.open("xb") as writer:
                        copied.append(destination)
                        shutil.copyfileobj(reader, writer)
                destination_primary = self._pick_primary(copied)
                mod = Mod(
                    name=(f"{name} · {Path(_strip_disabled(primary.name)).stem}" if name and total > 1
                          else name or Path(_strip_disabled(primary.name)).stem),
                    file=str(destination_primary), character=character, author=author,
                    skin=skin,
                    source_url=source_url, note=note, preview=preview,
                )
                mod.file = str(mod.enabled_path)
                mod.refresh_size()
                mod.enabled = mod.enabled_path.exists()
                self.store.add_mod(mod)
                result.added.append(mod)
            except OSError as error:
                for path in copied:
                    path.unlink(missing_ok=True)
                result.errors.append(f"{primary.name}: {error}")
        if result.added:
            self.store.save()
        else:
            self._prune_empty(target_dir)
        return result

    @staticmethod
    def _pick_primary(files: Sequence[Path]) -> Path | None:
        for extension in PRIMARY_EXTENSIONS:
            for path in files:
                if Path(_strip_disabled(path.name)).suffix.lower() == extension:
                    return path
        return None

    @staticmethod
    def _package_stem(directory: Path, stem: str) -> str:
        occupied = {Path(_strip_disabled(path.name)).stem.casefold() for path in directory.iterdir()}
        if stem.casefold() not in occupied:
            return stem
        marker = "_100_p"
        base = stem[:-len(marker)] if stem.lower().endswith(marker) else stem
        tail = stem[len(base):]
        index = 2
        while f"{base} ({index}){tail}".casefold() in occupied:
            index += 1
        return f"{base} ({index}){tail}"

    @staticmethod
    def _unique_path(path: Path) -> Path:
        if not path.exists() and not Path(str(path) + DISABLED_SUFFIX).exists():
            return path
        stem, suffix = path.stem, path.suffix
        # Keep the trailing "_100_P" marker in place, otherwise the game would
        # stop mounting the renamed copy.
        marker = "_100_p"
        base = stem[: -len(marker)] if stem.lower().endswith(marker) else stem
        tail = stem[len(base) :]
        for index in range(2, 1000):
            candidate = path.with_name(f"{base} ({index}){tail}{suffix}")
            if not candidate.exists() and not Path(str(candidate) + DISABLED_SUFFIX).exists():
                return candidate
        raise OSError(f"No free filename: {path.name}")

    # ---------------------------------------------------------------- delete
    def delete(self, mods: Iterable[Mod], remove_files: bool = True) -> tuple[int, list[str]]:
        doomed = list(mods)
        errors: list[str] = []
        removed = 0
        deleted = []
        for mod in doomed:
            failed = False
            if remove_files:
                for path in self.siblings(mod):
                    try:
                        path.unlink()
                    except OSError as error:
                        errors.append(f"{path.name}: {error}")
                        failed = True
            if failed:
                continue
            self._prune_empty(mod.enabled_path.parent)
            deleted.append(mod)
            removed += 1
        if removed:
            self.store.remove_mods(deleted)
            self.store.save()
        return removed, errors

    def rename_stem(self, mod: Mod, new_stem: str) -> str | None:
        """Rename a complete package, keeping the record unchanged on failure."""
        new_stem = ascii_stem(new_stem.strip())
        if not new_stem or new_stem == mod.enabled_path.stem:
            return None
        if new_stem in {".", ".."} or any(c in new_stem for c in '/\\:<>"|?*'):
            return "invalid filename"
        files = self.siblings(mod)
        if not files:
            return f"{mod.filename}: missing"
        for extension in PACKAGE_EXTENSIONS:
            target = mod.directory / f"{new_stem}{extension}"
            if target.exists() or Path(str(target) + DISABLED_SUFFIX).exists():
                return f"{target.name}: exists"
        moves = []
        for path in files:
            bare = Path(_strip_disabled(path.name))
            suffix = bare.suffix + (DISABLED_SUFFIX if path.name.endswith(DISABLED_SUFFIX) else "")
            moves.append((path, path.with_name(f"{new_stem}{suffix}")))
        error = self._relocate(moves)
        if error:
            return error
        mod.file = str(self.path_for(mod, new_stem))
        self.store.save()
        return None

    def path_for(self, mod: Mod, stem: str) -> Path:
        """Where the mod's files end up once they are renamed to ``stem``."""
        return mod.enabled_path.with_name(f"{stem}{mod.enabled_path.suffix}")

    def move_mod(self, mod: Mod, character: str, skin: str = "default") -> str | None:
        """Move a mod's files into another character's folder."""
        character = character.strip()
        if not character:
            return None
        try:
            target_dir = self.skin_dir(character, skin)
            if mod.directory == target_dir:
                mod.character, mod.skin = character, skin
                self.store.save()
                return None
            target_dir.mkdir(parents=True, exist_ok=True)
            files = self.siblings(mod)
            if not files:
                return f"{mod.filename}: missing"
            stem = self._package_stem(target_dir, ascii_stem(mod.stem))
            moves = []
            for path in files:
                bare = Path(_strip_disabled(path.name))
                suffix = bare.suffix + (DISABLED_SUFFIX if path.name.endswith(DISABLED_SUFFIX) else "")
                moves.append((path, target_dir / f"{stem}{suffix}"))
            error = self._relocate(moves)
            if error:
                self._prune_empty(target_dir)
                return error
        except (OSError, RuntimeError, ValueError) as error:
            return str(error)
        source_dir = mod.directory
        mod.file = str(target_dir / f"{stem}{mod.extension}")
        mod.character = character
        mod.skin = skin
        self._prune_empty(source_dir)
        self.store.save()
        return None

    # ---------------------------------------------------------------- preview
    def set_preview(self, mod: Mod, source: Path) -> str:
        from . import paths as _paths

        _paths.PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
        destination = _paths.PREVIEW_DIR / f"{mod.id}{source.suffix.lower()}"
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        mod.preview = str(destination)
        self.store.dirty = True
        return mod.preview

    # ----------------------------------------------------------------- scan
    def repair_legacy_layout(self, known_characters: Collection[str]) -> tuple[int, list[str]]:
        from .compatibility import repair_layout

        return repair_layout(self, known_characters)

    def normalize_layout(self, known_characters: Collection[str]) -> tuple[int, list[str]]:
        """Migrate managed packages to English paths; leave unrelated files alone.

        A database snapshot is written first. Each package move is transactional
        and collisions receive a fresh stem. Re-running only retries remaining work.
        """
        base = self.storage_dir
        if base is None or not base.exists():
            return 0, []
        from datetime import datetime

        self.store.save()
        backup = self.store.path.with_name(f"data-before-english-{datetime.now():%Y%m%d-%H%M%S-%f}.json")
        shutil.copy2(self.store.path, backup)
        self.scan_storage(known_characters=known_characters)
        changed, errors = 0, []
        for mod in list(self.mods):
            if mod.character not in known_characters or not mod.exists:
                continue
            if not mod.disk_path.resolve().is_relative_to(base.resolve()):
                continue
            try:
                target = self.skin_dir(mod.character, mod.skin)
                if mod.directory == target and mod.stem.isascii():
                    continue
                if mod.directory == target:
                    stem = self._package_stem(target, ascii_stem(mod.stem))
                    error = self.rename_stem(mod, stem)
                else:
                    error = self.move_mod(mod, mod.character, mod.skin)
                if error:
                    errors.append(f"{mod.filename}: {error}")
                else:
                    changed += 1
            except (OSError, ValueError, RuntimeError) as error:
                errors.append(str(error))
        return changed, errors

    def scan_storage(
        self,
        progress: Callable[[int, int, str], None] | None = None,
        known_characters: Collection[str] | None = None,
    ) -> list[Mod]:
        """Adopt mod files that exist on disk but are not tracked yet.

        ``known_characters`` restricts adoption to folders that really are
        characters; anything else is left alone instead of silently turning into
        a brand new character card.
        """
        base = self.storage_dir
        if base is None or not base.exists():
            return []
        candidates: list[Path] = []
        for root, dirs, files in os.walk(base):
            dirs[:] = [name for name in dirs if not (Path(root) / name).is_symlink()]
            for name in files:
                stripped = _strip_disabled(name)
                if Path(stripped).suffix.lower() in PRIMARY_EXTENSIONS and not (Path(root) / name).is_symlink():
                    candidates.append(Path(root) / name)
        known = {str(mod.enabled_path).lower() for mod in self.store.mods}
        adopted: list[Mod] = []
        total = len(candidates)
        for index, path in enumerate(candidates, start=1):
            if progress:
                progress(index, total, path.name)
            if str(path).removesuffix(DISABLED_SUFFIX).lower() in known:
                continue
            bare = Path(_strip_disabled(path.name))
            if bare.suffix.lower() == ".utoc":
                pak = path.with_name(bare.stem + ".pak")
                if pak.exists() or Path(str(pak) + DISABLED_SUFFIX).exists():
                    continue
            relative = path.relative_to(base)
            folders = list(relative.parts)[:-1]
            if not folders:
                continue
            character = character_for(folders[0])
            if known_characters is not None and character not in known_characters:
                continue
            mod = Mod(
                name=Path(_strip_disabled(path.name)).stem,
                file=str(path),
                character=character,
                skin=folders[1] if len(folders) > 1 and valid_skin(character, folders[1]) else "default",
            )
            mod.enabled = not str(path).endswith(DISABLED_SUFFIX)
            mod.refresh_size()
            self.store.add_mod(mod)
            adopted.append(mod)
            known.add(str(mod.enabled_path).lower())
        if adopted:
            self.store.save()
        return adopted

    # ---------------------------------------------------------------- audit
    def issues(self, known_characters: Collection[str] | None = None) -> list[Issue]:
        """Audit the collection.

        When ``known_characters`` is given, any tracked mod whose character is
        not part of it is reported so the user can tidy it up - the app never
        invents a character of its own.
        """
        found: list[Issue] = []
        groups: dict[tuple[str, str], list[Mod]] = {}
        paths_seen: dict[str, Mod] = {}
        unknown: dict[str, list[Mod]] = {}

        for mod in self.store.mods:
            if not mod.exists:
                found.append(Issue("missing_file", "error", {"file": mod.filename}, [mod.id]))
                continue
            key = str(mod.enabled_path).lower()
            if key in paths_seen and mod.character not in SPECIAL_CATEGORIES:
                found.append(
                    Issue("duplicate_path", "warning", {"file": mod.filename}, [paths_seen[key].id, mod.id])
                )
            else:
                paths_seen[key] = mod
            if known_characters is not None and mod.character not in known_characters:
                unknown.setdefault(mod.character, []).append(mod)
            if mod.enabled and mod.character and mod.character not in SPECIAL_CATEGORIES:
                groups.setdefault((mod.character, mod.skin), []).append(mod)

        for character, mods in sorted(unknown.items()):
            found.append(
                Issue(
                    "unknown_character",
                    "warning",
                    {"character": character or "-", "count": str(len(mods))},
                    [mod.id for mod in mods],
                )
            )

        for (character, _skin), mods in groups.items():
            if len(mods) > 1:
                found.append(
                    Issue(
                        "multi_enabled",
                        "warning",
                        {"character": character, "count": str(len(mods))},
                        [mod.id for mod in mods],
                    )
                )
        return found

    # ----------------------------------------------------------------- stats
    def stats(self) -> dict[str, int]:
        enabled = [mod for mod in self.store.mods if mod.enabled]
        return {
            "mods": len(self.store.mods),
            "enabled": len(enabled),
            "characters": len(unique_in_order(mod.character for mod in self.store.mods)),
            "missing": sum(1 for mod in self.store.mods if not mod.exists),
        }
