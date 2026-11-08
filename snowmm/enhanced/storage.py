"""Portable records and guarded paths. JSON beside each mod is authoritative."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, fields
from pathlib import Path

from ..core.models import Mod, now_iso
from ..core.settings import Settings
from ..core.store import Store

DEFAULT_LIBRARY = str(Path.home() / "SnowMM" / "Library")
DEFAULT_GAME = ""
DEFAULT_DEPLOY = ""
DEFAULT_SERVER = ""
DEFAULT_TOOL = ""
DEFAULT_CATEGORIES = [[x] for x in ("角色", "插画", "Boss", "NPC", "基地", "反和谐", "杂项")]
RUNTIME_EXTENSIONS = {".pak", ".utoc", ".ucas", ".sig"}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        checksum = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
        return checksum.hexdigest()


def linked(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def component(text: str) -> str:
    if not isinstance(text, str) or not text or len(text) > 240:
        raise ValueError("目录名不能为空或超过240字符")
    if re.search(r'[<>:"/\\|?*\x00-\x1f]', text) or text.rstrip(" .") != text or text in {".", ".."}:
        raise ValueError(f"不安全的目录或文件名：{text}")
    if text.split(".")[0].upper() in {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        raise ValueError("Windows 保留名称不可用")
    return text


def folder_name(text: str, identity: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text).strip(" .")[:65] or "未命名"
    return component(f"{safe}__{identity[-8:]}")


def inside(root: Path, path: Path) -> Path:
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"路径越出允许目录：{path}")
    return path


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and linked(path):
        raise ValueError(f"拒绝写入链接元数据：{path}")
    content = json.dumps(value, ensure_ascii=False, indent=2)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    temporary = path.with_name(path.name + ".tmp")
    if os.path.lexists(temporary) and linked(temporary):
        raise ValueError("临时文件是链接，已停止")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def read_json(path: Path, default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


@dataclass
class EnhancedSettings(Settings):
    deploy_path: str = DEFAULT_DEPLOY
    deploy_mode: str = "symlink"
    hotkey: str = "Ctrl+Alt+S"
    launch_mode: str = "direct"
    server_exe: str = DEFAULT_SERVER
    custom_exe: str = ""
    custom_args: str = ""
    launch_cwd: str = ""
    repair_tool: str = DEFAULT_TOOL
    repair_python: str = ""
    bundled_repair: bool = False
    pending_ids: list[str] = field(default_factory=list)
    pending_revisions: dict[str, str] = field(default_factory=dict)
    has_pending: bool = False

    @classmethod
    def load_portable(cls, home: Path):
        raw = read_json(home / "settings.json", {})
        settings = cls(**{k: v for k, v in raw.items() if k in {f.name for f in fields(cls)}})
        if not settings.storage_path:
            settings.storage_path = DEFAULT_LIBRARY
        if not settings.game_exe:
            settings.game_exe = DEFAULT_GAME
        settings._home = home
        return settings

    def save(self, path=None):
        atomic_json(path or self._home / "settings.json", self.to_dict())


@dataclass
class LibraryMod(Mod):
    folder: str = ""
    category_parts: list[str] = field(default_factory=list)
    versions: list[dict] = field(default_factory=list)
    current_version: str = "v001_原始"
    original_names: list[str] = field(default_factory=list)
    previews: list[str] = field(default_factory=list)
    cover: str = ""
    conflict_group: str = ""
    target: str = "待确认"
    game_versions: str = "待确认"
    tested: str = "未实测"
    repair_history: list[dict] = field(default_factory=list)
    provenance: list[str] = field(default_factory=list)

    def version(self, version_id=None):
        return next(v for v in self.versions if v["id"] == (version_id or self.current_version))

    def files(self, version_id=None) -> list[Path]:
        version = self.version(version_id)
        base = inside(Path(self.folder), Path(self.folder) / "版本" / component(version["id"]))
        result = []
        for info in version["files"]:
            filename = component(info["name"])
            if Path(filename).suffix.lower() not in RUNTIME_EXTENSIONS:
                raise ValueError("非运行文件不能部署")
            result.append(inside(Path(self.folder), base / filename))
        return result

    def hydrate(self):
        files = self.files()
        primary = next((p for p in files if p.suffix.lower() == ".pak"), files[0] if files else None)
        self.file = str(primary) if primary else ""
        self.preview = str(inside(Path(self.folder), Path(self.folder) / self.cover)) if self.cover else ""
        self.size = sum(int(f.get("size", 0)) for f in self.version()["files"])
        self.game_versions = self.version().get("game_versions", self.game_versions)
        self.tested = self.version().get("tested", self.tested)
        return self

    def to_dict(self):
        data = super().to_dict()
        for name in (
            "category_parts",
            "versions",
            "current_version",
            "original_names",
            "previews",
            "cover",
            "conflict_group",
            "target",
            "game_versions",
            "tested",
            "repair_history",
            "provenance",
        ):
            data[name] = getattr(self, name)
        data.update(schema=1, file="", preview="", folder="")
        return data

    @classmethod
    def read(cls, folder: Path):
        raw = read_json(folder / "mod.json")
        if raw.get("schema") != 1:
            raise ValueError("未知 mod.json 版本")
        value = cls(**{k: v for k, v in raw.items() if k in {f.name for f in fields(cls)}})
        component(value.id)
        if value.source_url and not value.source_url.startswith(("https://", "http://")):
            raise ValueError("来源链接只接受 http/https")
        if not isinstance(value.versions, list) or not value.versions:
            raise ValueError("模组版本清单不能为空")
        seen = set()
        for version in value.versions:
            component(version["id"])
            if version["id"] in seen or not version.get("files"):
                raise ValueError("重复版本或空的版本文件清单")
            seen.add(version["id"])
            for info in version["files"]:
                component(info["name"])
                if not re.fullmatch(r"[0-9a-fA-F]{64}", info["sha256"]) or int(info["size"]) < 0:
                    raise ValueError("无效的版本文件校验信息")
        if value.current_version not in seen:
            raise ValueError("当前版本不在版本清单中")
        value.folder = str(folder)
        for preview in [*value.previews, value.cover]:
            if preview:
                inside(folder, folder / preview)
        return value.hydrate()

    def save(self):
        if self.source_url and not self.source_url.startswith(("https://", "http://")):
            raise ValueError("来源链接只接受 http/https")
        self.version()["game_versions"] = self.game_versions
        self.version()["tested"] = self.tested
        self.hydrate()
        root = Path(self.folder)
        atomic_json(root / "mod.json", self.to_dict())
        version_text = "\n".join(
            f"- {'【当前】' if v['id'] == self.current_version else ''}{v['id']}："
            + "、".join(f["name"] for f in v["files"])
            for v in self.versions
        )
        text = (
            f"# {self.name}\n\n分类：{' / '.join(self.category_parts)}\n\n稳定ID：{self.id}\n\n"
            f"原名：{'、'.join(self.original_names)}\n\n作者：{self.author or '待确认'}\n\n"
            f"来源：{self.source_url or '待确认'}\n\n作用对象：{self.target}\n\n游戏版本：{self.game_versions}\n\n"
            f"实测状态：{self.tested}\n\n互斥组：{self.conflict_group or '未设置（允许叠加）'}\n\n"
            f"## 版本\n\n{version_text}\n\n## 备注\n\n{self.note}\n\n"
            "此文件由管理器生成。编辑信息以 mod.json 为准；原始压缩包、各版本和预览均在本文件夹内。\n"
        )
        summary = root / "说明.md"
        if summary.exists() and linked(summary):
            raise ValueError("说明.md 不能是链接")
        if not summary.exists() or summary.read_text(encoding="utf-8") != text:
            temporary = summary.with_name("说明.md.tmp")
            if temporary.exists() and linked(temporary):
                raise ValueError("说明的临时文件不能是链接")
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(summary)


class LibraryStore(Store):
    def __init__(self, root: Path, home: Path):
        super().__init__(home / "index.json")
        self.root, self.home = root, home
        self.categories = [p[:] for p in DEFAULT_CATEGORIES]
        self.presets = {}
        self.errors = []
        self.before_save = None
        self._saving = False

    @property
    def manifest_path(self):
        return self.root / ".snowmm-library.json"

    def load(self):
        self.mods, self.errors = [], []
        if self.root.exists() and linked(self.root):
            raise ValueError("资源库根目录不能是链接或联接点")
        meta = read_json(self.manifest_path, {})
        self.categories = meta.get("categories", [p[:] for p in DEFAULT_CATEGORIES])
        self.presets = meta.get("presets", {})
        self.characters = meta.get("characters", [])
        if not self.root.exists():
            return self
        for root, dirs, files in os.walk(self.root, followlinks=False):
            dirs[:] = [d for d in dirs if not d.startswith(".") and not linked(Path(root) / d)]
            if "mod.json" not in files:
                continue
            dirs[:] = []
            try:
                folder = inside(self.root, Path(root))
                if linked(folder / "mod.json"):
                    raise ValueError("链接元数据不收录")
                mod = LibraryMod.read(folder)
                mod.category_parts = list(folder.relative_to(self.root).parts[:-1])
                mod._layout_signature = (mod.name, tuple(mod.category_parts))
                if any(m.id == mod.id for m in self.mods):
                    raise ValueError(f"重复模组ID：{mod.id}")
                self.mods.append(mod)
                if mod.category_parts not in self.categories:
                    self.categories.append(mod.category_parts)
            except (OSError, ValueError, KeyError, StopIteration, TypeError) as error:
                self.errors.append(f"{root}: {error}")
        return self

    def save(self):
        if self._saving:
            return
        if not self.root.exists() and not self.mods:
            return  # A suggested drive may not exist on a new computer.
        self._saving = True
        try:
            if self.before_save:
                self.before_save()
            for mod in self.mods:
                inside(self.root, Path(mod.folder))
                mod.save()
            atomic_json(
                self.manifest_path,
                {"schema": 1, "categories": self.categories, "presets": self.presets, "characters": self.characters},
            )
            atomic_json(
                self.path,
                {
                    "schema": 1,
                    "root": str(self.root),
                    "mods": [{"id": m.id, "folder": m.folder} for m in self.mods],
                    "rebuilt_at": now_iso(),
                },
            )
        finally:
            self._saving = False
