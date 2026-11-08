"""Library service compatible with the upstream character pages and galleries."""

from __future__ import annotations

import copy
import os
import shutil
import tempfile
import uuid
from pathlib import Path

from ..core.manager import ImportResult, Issue, ModManager
from ..core.models import new_id
from ..core.skins import skins_for
from .deployment import Deployment, game_running
from .storage import (
    RUNTIME_EXTENSIONS,
    LibraryMod,
    LibraryStore,
    component,
    digest,
    folder_name,
    inside,
    linked,
)


class LibraryManager(ModManager):
    def __init__(self, store: LibraryStore, settings):
        super().__init__(store, settings)
        self.store = store
        self.compatibility_errors = list(store.errors)
        self.running_check = lambda: game_running(settings)
        self.store.before_save = self.sync_folders

    @property
    def deployment(self):
        return Deployment(
            Path(self.settings.deploy_path)
            if self.settings.deploy_path
            else self.settings._home / "unconfigured-deployment"
        )

    def _validate_roots(self):
        if not self.settings.deploy_path:
            raise ValueError("请先在增强设置选择游戏应用目录")
        self.deployment.validate(self.store.root)

    def character_dir(self, character):
        if character in {"基地", "杂项"}:
            return self.store.root / character
        person, _, armor = character.partition("-")
        return self.store.root / "角色" / component(person) / component(armor or "其他")

    def category_for(self, character, skin="default"):
        if character in {"基地", "杂项"}:
            return [character]
        person, _, armor = character.partition("-")
        label = "原皮"
        if skin != "default":
            label = next((s.name for s in skins_for(character) if s.id == skin), skin)
        return ["角色", person or "待归类", armor or "待归类", label]

    def siblings(self, mod):
        return mod.files()

    def is_enabled(self, mod):
        return mod.id in self.deployment.enabled_ids()

    def refresh_states(self):
        try:
            ids = self.deployment.enabled_ids()
            self.compatibility_errors = list(self.store.errors) + self.deployment.errors()
        except (OSError, ValueError, KeyError) as error:
            ids = set()
            self.compatibility_errors = [str(error)]
        for mod in self.mods:
            mod.enabled = mod.id in ids
        return len(ids)

    def repair_legacy_layout(self, known_characters):
        # Deliberately no filesystem conversion on scan/F5/startup.
        return 0, list(self.store.errors)

    def normalize_layout(self, known_characters):
        return 0, ["不自动转换原目录。请使用资源库的导入预览。"]

    def scan_storage(self, progress=None, known_characters=None):
        self.store.load()
        self.refresh_states()
        return []

    def desired_ids(self):
        return set(self.settings.pending_ids) if self.settings.has_pending else self.deployment.enabled_ids()

    def _apply_ids(self, ids):
        self._validate_roots()
        mods = [m for m in self.mods if m.id in ids]
        if len(mods) != len(ids):
            raise ValueError("启用方案含已不存在的模组")
        groups = [m.conflict_group for m in mods if m.conflict_group]
        if len(groups) != len(set(groups)):
            raise ValueError("同一互斥组不能同时启用多个模组")
        self.deployment.apply(mods, self.settings.deploy_mode)
        self.refresh_states()

    def set_enabled(self, mods, enabled):
        selected = list(mods)
        wanted = self.desired_ids()
        for mod in selected:
            if enabled:
                if mod.conflict_group:
                    wanted -= {m.id for m in self.mods if m.conflict_group == mod.conflict_group}
                wanted.add(mod.id)
            else:
                wanted.discard(mod.id)
        try:
            if self.running_check():
                self.settings.pending_ids = sorted(wanted)
                self.settings.has_pending = True
                self.settings.save()
                return 0, ["游戏运行中：已保存待应用方案，退出游戏后点击‘应用待办’。"]
            if self.settings.has_pending:
                self.settings.pending_ids = sorted(wanted)
                self.apply_pending()
            else:
                self._apply_ids(wanted)
            self.settings.pending_ids = []
            self.settings.has_pending = False
            self.settings.save()
            return len(selected), []
        except (OSError, ValueError, KeyError, StopIteration) as error:
            self.refresh_states()
            return 0, [str(error)]

    def apply_pending(self):
        if self.running_check():
            raise ValueError("请先退出游戏，截图和编辑信息仍可使用")
        old_versions = {}
        try:
            for mod in self.mods:
                revision = self.settings.pending_revisions.get(mod.id)
                if revision:
                    old_versions[mod.id] = mod.current_version
                    mod.version(revision)
                    mod.current_version = revision
                    mod.hydrate()
            self._apply_ids(self.desired_ids())
        except BaseException:
            for mod in self.mods:
                if mod.id in old_versions:
                    mod.current_version = old_versions[mod.id]
                    mod.hydrate()
            raise
        self.settings.has_pending = False
        self.settings.pending_ids = []
        self.settings.pending_revisions = {}
        self.settings.save()
        self.store.save()

    def select_version(self, mod, revision):
        mod.version(revision)
        if self.running_check():
            if not self.settings.has_pending:
                self.settings.pending_ids = sorted(self.deployment.enabled_ids())
            self.settings.pending_revisions[mod.id] = revision
            self.settings.has_pending = True
            self.settings.save()
            return "游戏运行中，版本切换已加入待办"
        old = mod.current_version
        wanted = self.deployment.enabled_ids()
        mod.current_version = revision
        mod.hydrate()
        try:
            self._apply_ids(wanted)
            self.store.save()
        except BaseException:
            mod.current_version = old
            mod.hydrate()
            raise
        return "当前版本已切换；请重新启动游戏查看效果"

    def sync_folders(self):
        moves = []
        for mod in self.mods:
            for part in mod.category_parts:
                component(part)
            signature = (mod.name, tuple(mod.category_parts))
            if not hasattr(mod, "_layout_signature"):
                mod._layout_signature = signature
            if mod._layout_signature == signature:
                continue
            expected = inside(
                self.store.root, self.store.root.joinpath(*mod.category_parts) / folder_name(mod.name, mod.id)
            )
            if Path(mod.folder) != expected:
                if os.path.lexists(expected):
                    raise FileExistsError(f"目标模组目录已存在：{expected}")
                moves.append((mod, Path(mod.folder), expected))
        if not moves:
            return
        if self.running_check():
            for mod, source, _ in moves:
                previous = LibraryMod.read(source)
                mod.name = previous.name
                mod.category_parts = previous.category_parts
            raise ValueError("游戏运行时暂不移动或改名模组目录，请退出后操作")
        wanted = self.deployment.enabled_ids()
        moving_ids = {m.id for m, _, _ in moves}
        snapshots = {mod.id: LibraryMod.read(source) for mod, source, _ in moves}
        self._apply_ids(wanted - moving_ids)
        completed = []
        try:
            for mod, source, destination in moves:
                inside(self.store.root, source)
                if linked(source):
                    raise ValueError("拒绝移动链接目录")
                destination.parent.mkdir(parents=True, exist_ok=True)
                source.rename(destination)
                mod.folder = str(destination)
                mod.hydrate()
                completed.append((mod, source, destination))
                mod.save()
            self._apply_ids(wanted)
            for mod, _, _ in completed:
                mod._layout_signature = (mod.name, tuple(mod.category_parts))
        except BaseException:
            for mod, source, destination in reversed(completed):
                destination.rename(source)
                mod.folder = str(source)
                original = snapshots[mod.id]
                mod.__dict__.update(original.__dict__)
                mod._layout_signature = (mod.name, tuple(mod.category_parts))
                mod.hydrate()
                mod.save()
            self._apply_ids(wanted)
            raise

    def _groups(self, sources):
        groups = {}
        for source in sources:
            if source.is_dir():
                candidates = []
                for root, dirs, files in os.walk(source, followlinks=False):
                    dirs[:] = [d for d in dirs if not linked(Path(root) / d)]
                    candidates.extend(Path(root) / f for f in files)
            else:
                candidates = [source]
            for candidate in sorted(candidates):
                if not candidate.is_file() or linked(candidate):
                    continue
                bare = candidate.name.removesuffix(".disabled")
                suffix = Path(bare).suffix.lower()
                if suffix not in {".pak", ".utoc"}:
                    continue
                if source.is_dir():
                    inside(source, candidate)
                stem = Path(bare).stem
                key = (str(candidate.parent.resolve()), stem)
                if key in groups:
                    continue
                files = [
                    p
                    for p in candidate.parent.iterdir()
                    if p.is_file()
                    and not linked(p)
                    and Path(p.name.removesuffix(".disabled")).stem == stem
                    and Path(p.name.removesuffix(".disabled")).suffix.lower() in RUNTIME_EXTENSIONS
                ]
                if any(p.name.removesuffix(".disabled").endswith(".utoc") for p in files) and not any(
                    p.name.removesuffix(".disabled").endswith(".ucas") for p in files
                ):
                    raise ValueError(f"配套 UCAS 缺失：{stem}")
                groups[key] = files
        return list(groups.values())

    def preview_import(self, sources):
        result = []
        from ..core.archives import extract_packages

        for source in sources:
            if source.is_dir() and (source / "mod.json").is_file():
                mod = LibraryMod.read(source)
                result.append(
                    {
                        "source": str(source),
                        "files": [p.name for p in mod.files()],
                        "bytes": sum(p.stat().st_size for p in mod.files()),
                        "versions": len(mod.versions),
                    }
                )
                continue
            if source.suffix.lower() in {".zip", ".7z", ".rar"}:
                with tempfile.TemporaryDirectory(prefix="snowmm-inspect-") as temporary:
                    extract_packages(source, Path(temporary))
                    groups = self._groups([Path(temporary)])
                    result.extend(
                        {
                            "source": str(source),
                            "files": [f.name for f in group],
                            "bytes": sum(f.stat().st_size for f in group),
                        }
                        for group in groups
                    )
            else:
                result.extend(
                    {
                        "source": str(source),
                        "files": [f.name for f in group],
                        "bytes": sum(f.stat().st_size for f in group),
                    }
                    for group in self._groups([source])
                )
        return result

    def import_paths(
        self,
        sources,
        *,
        character="杂项",
        skin="default",
        name="",
        author="",
        source_url="",
        note="",
        preview="",
        progress=None,
        category=None,
    ):
        result = ImportResult()
        category = list(category or self.category_for(character, skin))
        for part in category:
            component(part)
        from ..core.archives import extract_packages

        for source in map(Path, sources):
            try:
                if source.is_dir() and self.store.root.resolve().is_relative_to(source.resolve()):
                    raise ValueError("不能把资源库自身或其上级目录再次导入自身")
                # Already organized packages retain their history and metadata.
                if source.is_dir() and (source / "mod.json").is_file():
                    original = LibraryMod.read(source)
                    mod = copy.deepcopy(original)
                    if self.store.get_mod(mod.id):
                        raise ValueError("同一稳定ID的模组已存在；请使用导入更新版")
                    mod.category_parts = category
                    destination = self.store.root.joinpath(*category) / folder_name(mod.name, mod.id)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    for path in source.rglob("*"):
                        if linked(path):
                            raise ValueError("已整理模组含链接，拒绝复制")
                    shutil.copytree(source, destination)
                    mod.folder = str(destination)
                    mod.hydrate()
                    mod.save()
                    self.store.add_mod(mod)
                    result.added.append(mod)
                    continue
                with tempfile.TemporaryDirectory(prefix="snowmm-import-") as temporary:
                    archive = source.suffix.lower() in {".zip", ".7z", ".rar"}
                    if archive:
                        extract_packages(source, Path(temporary))
                    groups = self._groups([Path(temporary) if archive else source])
                    for index, group in enumerate(groups):
                        if progress:
                            progress(index + 1, len(groups), group[0].name)
                        primary = next(
                            (p for p in group if p.name.removesuffix(".disabled").endswith(".pak")), group[0]
                        )
                        title = name or Path(primary.name.removesuffix(".disabled")).stem
                        if name and len(groups) > 1:
                            title += " · " + Path(primary.name.removesuffix(".disabled")).stem
                        identity = new_id("mod_")
                        folder = inside(
                            self.store.root, self.store.root.joinpath(*category) / folder_name(title, identity)
                        )
                        payload = folder / "版本/v001_原始"
                        payload.mkdir(parents=True)
                        try:
                            information = []
                            for file in group:
                                target = payload / component(file.name.removesuffix(".disabled"))
                                if target.exists():
                                    raise FileExistsError("同一包内有同名启用/禁用文件，请先选择正确版本")
                                shutil.copy2(file, target)
                                information.append(
                                    {"name": target.name, "sha256": digest(target), "size": target.stat().st_size}
                                )
                            for sub in ("原始压缩包", "预览", "报告"):
                                (folder / sub).mkdir()
                            if archive:
                                shutil.copy2(source, folder / "原始压缩包" / source.name)
                            mod = LibraryMod(
                                id=identity,
                                folder=str(folder),
                                name=title,
                                character=character,
                                skin=skin,
                                author=author,
                                source_url=source_url,
                                note=note,
                                category_parts=category,
                                original_names=[f.name for f in group],
                                provenance=[str(source)],
                                versions=[{"id": "v001_原始", "label": "原始导入", "files": information}],
                            )
                            mod.save()
                            if preview:
                                self.set_preview(mod, Path(preview))
                            self.store.add_mod(mod)
                            result.added.append(mod)
                        except BaseException:
                            inside(self.store.root, folder)
                            shutil.rmtree(folder)
                            raise
            except (OSError, ValueError, KeyError, StopIteration) as error:
                result.errors.append(f"{source.name}: {error}")
        if result.added:
            if category not in self.store.categories:
                self.store.categories.append(category)
            self.store.save()
        return result

    def set_preview(self, mod, source, cover=True):
        source = Path(source)
        if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            raise ValueError("请选择图片文件")
        destination = Path(mod.folder) / "预览" / (uuid.uuid4().hex[:12] + source.suffix.lower())
        destination.parent.mkdir(exist_ok=True)
        shutil.copy2(source, destination)
        relative = destination.relative_to(Path(mod.folder)).as_posix()
        mod.previews.append(relative)
        if cover or not mod.cover:
            mod.cover = relative
        mod.save()
        return str(destination)

    def add_revision(self, mod, sources, label="更新版本"):
        """Preserve an update without selecting or deploying it."""
        from ..core.archives import extract_packages

        information = []
        archives = []
        version_id = f"v{len(mod.versions) + 1:03d}_更新_{uuid.uuid4().hex[:8]}"
        destination = inside(Path(mod.folder), Path(mod.folder) / "版本" / version_id)
        destination.mkdir()
        try:
            with tempfile.TemporaryDirectory(prefix="snowmm-update-") as temporary:
                expanded = []
                for index, source in enumerate(map(Path, sources)):
                    if source.suffix.lower() in {".zip", ".7z", ".rar"}:
                        target = Path(temporary) / str(index)
                        target.mkdir()
                        extract_packages(source, target)
                        expanded.append(target)
                        archives.append(source)
                    else:
                        expanded.append(source)
                for group in self._groups(expanded):
                    for source in group:
                        target = destination / component(source.name.removesuffix(".disabled"))
                        if target.exists():
                            raise ValueError("更新版本中有重名运行文件")
                        shutil.copy2(source, target)
                        information.append(
                            {"name": target.name, "sha256": digest(target), "size": target.stat().st_size}
                        )
                if not information:
                    raise ValueError("没有找到可导入的运行文件")
            for archive in archives:
                shutil.copy2(archive, Path(mod.folder) / "原始压缩包" / (version_id + "_" + archive.name))
            mod.versions.append(
                {"id": version_id, "label": label, "files": information, "game_versions": "待确认", "tested": "未实测"}
            )
            mod.provenance.extend(str(p) for p in sources)
            mod.save()
        except BaseException:
            mod.versions = [v for v in mod.versions if v["id"] != version_id]
            shutil.rmtree(destination)
            raise
        return version_id

    def move_mod(self, mod, character, skin="default"):
        previous = mod.character, mod.skin, mod.category_parts[:]
        mod.character, mod.skin = character, skin
        mod.category_parts = self.category_for(character, skin)
        try:
            self.store.save()
            return None
        except (OSError, ValueError) as error:
            mod.character, mod.skin, mod.category_parts = previous
            return str(error)

    def rename_stem(self, mod, new_stem):
        # The upstream UI action now renames the display/folder, never a PAK priority suffix.
        previous = mod.name
        mod.name = new_stem
        try:
            self.store.save()
            return None
        except (OSError, ValueError) as error:
            mod.name = previous
            return str(error)

    def change_category(self, old_parts, new_parts):
        for part in new_parts:
            component(part)
        previous_categories = copy.deepcopy(self.store.categories)
        snapshots = {m.id: m.category_parts[:] for m in self.mods}

        def replace(parts):
            return list(new_parts) + parts[len(old_parts) :] if parts[: len(old_parts)] == list(old_parts) else parts

        self.store.categories = [replace(parts) for parts in self.store.categories]
        for mod in self.mods:
            mod.category_parts = replace(mod.category_parts)
        try:
            destination = inside(self.store.root, self.store.root.joinpath(*new_parts))
            destination.mkdir(parents=True, exist_ok=True)
            self.store.save()
            source = inside(self.store.root, self.store.root.joinpath(*old_parts))
            if source != destination and source.exists():
                self._prune_empty(source)
        except BaseException:
            self.store.categories = previous_categories
            for mod in self.mods:
                mod.category_parts = snapshots[mod.id]
            raise

    def delete(self, mods, remove_files=True):
        selected = list(mods)
        if self.running_check():
            return 0, ["请退出游戏后再移至回收目录"]
        try:
            self._apply_ids(self.deployment.enabled_ids() - {m.id for m in selected})
            trash = self.store.root / ".回收站"
            trash.mkdir(exist_ok=True)
            for mod in selected:
                folder = inside(self.store.root, Path(mod.folder))
                folder.rename(trash / (folder.name + "_" + uuid.uuid4().hex[:8]))
                self.store.mods.remove(mod)
            self.store.save()
            return len(selected), []
        except (OSError, ValueError) as error:
            return 0, [str(error)]

    def issues(self, known_characters=None):
        found = [Issue("missing_file", "error", {"file": e}, []) for e in self.compatibility_errors]
        for mod in self.mods:
            if not all(p.exists() for p in mod.files()):
                found.append(Issue("missing_file", "error", {"file": mod.name}, [mod.id]))
        return found

    def save_preset(self, name):
        component(name)
        self.store.presets[name] = {
            "ids": sorted(self.desired_ids()),
            "versions": {m.id: m.current_version for m in self.mods if m.id in self.desired_ids()},
        }
        self.store.save()

    def load_preset(self, name):
        preset = self.store.presets[name]
        for identity, revision in preset["versions"].items():
            mod = self.store.get_mod(identity)
            if mod is None:
                raise ValueError("方案引用的模组已不存在")
            mod.version(revision)
        self.settings.pending_ids = list(preset["ids"])
        self.settings.pending_revisions = dict(preset["versions"])
        self.settings.has_pending = True
        self.settings.save()

    def stats(self):
        return {
            "mods": len(self.mods),
            "missing": sum(not m.exists for m in self.mods),
            "total": len(self.mods),
            "enabled": sum(m.enabled for m in self.mods),
            "disabled": sum(not m.enabled for m in self.mods),
            "size": sum(m.size for m in self.mods),
        }
