"""Owned-file deployment with write-ahead recovery and conservative identity checks."""

from __future__ import annotations

import contextlib
import os
import shutil
import uuid
from pathlib import Path

from .storage import atomic_json, component, digest, inside, linked, read_json


class LinkPermissionError(OSError):
    pass


def _link_target_key(target: str, parent: Path) -> str:
    """Compare lexical targets, including dangling links, without following other links.

    Windows readlink returns substitution names (e.g. \\?\\ drive/UNC paths),
    whereas our manifest stores ordinary absolute paths. Only translate those
    two known DOS spellings; do not guess aliases for arbitrary device paths.
    """
    if os.name == "nt":
        if target[:8].casefold() == "\\\\?\\unc\\":
            target = "\\\\" + target[8:]
        elif (
            target.startswith("\\\\?\\")
            and len(target) >= 7
            and target[4].isascii()
            and target[4].isalpha()
            and target[5:7] == ":\\"
        ):
            target = target[4:]
    if not os.path.isabs(target):
        target = os.path.join(parent, target)
    return os.path.normcase(os.path.abspath(target))


def game_running(settings) -> bool:
    import psutil

    executable = Path(settings.game_exe)
    for process in psutil.process_iter(["name", "exe"]):
        try:
            if (process.info["name"] or "").casefold() != executable.name.casefold():
                continue
            if not process.info["exe"] or Path(process.info["exe"]).resolve() == executable.resolve():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


class Deployment:
    def __init__(self, root: Path):
        self.root = root.absolute()
        self.manifest = self.root / ".snowmm-deployment.json"

    def validate(self, library: Path | None = None):
        if self.root.exists() and linked(self.root):
            raise ValueError("部署根目录不能是链接或联接点")
        # Never allow a library/version folder to become the game deployment root.
        if library and (
            self.root.resolve().is_relative_to(library.resolve())
            or library.resolve().is_relative_to(self.root.resolve())
        ):
            raise ValueError("资源库与部署目录不能相同或互相包含")
        if self.root.name in {"Paks", "Content", "Game", "Win64", ""} or self.root.parent == self.root:
            raise ValueError("请选择游戏 Paks 下单独的 ~SnowMM 文件夹")
        if self.manifest.exists() and linked(self.manifest):
            raise ValueError("部署清单不能是链接")

    def state(self):
        raw = read_json(self.manifest, {"schema": 1, "files": []})
        if raw.get("schema") != 1 or not isinstance(raw.get("files"), list):
            raise ValueError("部署清单损坏，已停止操作")
        for item in raw["files"]:
            component(item["name"])
            if item["mode"] not in {"copy", "symlink"}:
                raise ValueError("部署清单模式不合法")
        return raw

    @staticmethod
    def matches(path: Path, item: dict):
        if not os.path.lexists(path):
            return False
        if item["mode"] == "symlink":
            return path.is_symlink() and _link_target_key(os.readlink(path), path.parent) == _link_target_key(
                item["source"], path.parent
            )
        return not linked(path) and path.is_file() and digest(path) == item["sha256"]

    def enabled_ids(self):
        grouped = {}
        for item in self.state()["files"]:
            grouped.setdefault(item["mod_id"], []).append(self.matches(self.root / item["name"], item))
        return {key for key, checks in grouped.items() if all(checks)}

    def errors(self):
        return [
            f"受管理文件缺失或身份不符：{item['name']}"
            for item in self.state()["files"]
            if not self.matches(self.root / item["name"], item)
        ]

    def _clean(self, folder: Path):
        if folder.parent != self.root or not folder.name.startswith(".snowmm-txn-") or linked(folder):
            raise ValueError("不安全的事务目录")
        inside(self.root, folder)
        if not self._owned_transaction(folder):
            raise ValueError("未确认归属的事务目录不会清理")
        shutil.rmtree(folder)

    @staticmethod
    def _owned_transaction(folder):
        try:
            marker = folder / "owner.json"
            if linked(marker):
                return False
            record = read_json(marker, {})
            return record.get("owner") == "SnowMMEnhanced" and record.get("id") == folder.name.removeprefix(
                ".snowmm-txn-"
            )
        except (OSError, ValueError):
            return False

    def recover(self):
        """On an interrupted transaction, restore the prior manifest and owned files."""
        if not self.root.exists():
            return
        self.validate()
        for folder in self.root.glob(".snowmm-txn-*"):
            if linked(folder):
                raise ValueError("事务目录是链接，需人工检查")
            if not self._owned_transaction(folder):
                continue
            journal = folder / "journal.json"
            if not journal.exists():
                self._clean(folder)
                continue
            if linked(journal):
                raise ValueError("恢复日志是链接")
            plan = read_json(journal)
            if self.state().get("transaction") == plan["id"]:
                self._clean(folder)
                continue
            for item in plan["new"]["files"]:
                destination = self.root / component(item["name"])
                staged = folder / "new" / item["name"]
                if not os.path.lexists(staged) and os.path.lexists(destination):
                    if not self.matches(destination, item):
                        raise ValueError(f"恢复时发现外部改动：{destination.name}")
                    destination.unlink()
            for item in plan["old"]["files"]:
                destination = self.root / component(item["name"])
                backup = folder / "old" / item["name"]
                if os.path.lexists(backup):
                    if not self.matches(backup, item):
                        raise ValueError(f"恢复备份被修改：{backup.name}")
                    if os.path.lexists(destination):
                        raise ValueError(f"恢复目标被占用：{destination.name}")
                    backup.replace(destination)
            atomic_json(self.manifest, plan["old"])
            self._clean(folder)

    def apply(self, mods, mode: str):
        if mode not in {"copy", "symlink"}:
            raise ValueError("只支持链接或复制模式")
        self.validate()
        self.root.mkdir(parents=True, exist_ok=True)
        self.recover()
        old = self.state()
        old_names = {i["name"].casefold(): i for i in old["files"]}
        for item in old["files"]:
            path = self.root / item["name"]
            if os.path.lexists(path) and not self.matches(path, item):
                raise ValueError(f"拒绝改动已被外部修改的文件：{path.name}")
        new, seen = [], set()
        for mod in mods:
            version = mod.version()
            for source, info in zip(mod.files(), version["files"], strict=True):
                if not source.is_file() or linked(source) or digest(source) != info["sha256"]:
                    raise ValueError(f"资源库文件缺失、是链接或校验失败：{source.name}")
                key = source.name.casefold()
                if key in seen:
                    raise ValueError(f"同名部署冲突：{source.name}；请停用其中一项")
                seen.add(key)
                destination = self.root / source.name
                if os.path.lexists(destination) and key not in old_names:
                    raise ValueError(f"拒绝覆盖未知游戏文件：{source.name}")
                new.append(
                    {
                        "name": source.name,
                        "source": str(source.absolute()),
                        "sha256": info["sha256"],
                        "size": info["size"],
                        "mod_id": mod.id,
                        "version": mod.current_version,
                        "mode": mode,
                    }
                )
        if old["files"] == new and not self.errors():
            return
        transaction = uuid.uuid4().hex
        folder = self.root / (".snowmm-txn-" + transaction)
        (folder / "new").mkdir(parents=True)
        (folder / "old").mkdir()
        atomic_json(folder / "owner.json", {"owner": "SnowMMEnhanced", "id": transaction})
        new_state = {"schema": 1, "files": new, "transaction": transaction}
        # All outputs are staged before any live file is removed.
        try:
            for item in new:
                staged = folder / "new" / item["name"]
                try:
                    if mode == "symlink":
                        os.symlink(item["source"], staged)
                    else:
                        shutil.copy2(item["source"], staged)
                except OSError as error:
                    if mode == "symlink" and (
                        getattr(error, "winerror", None) == 1314 or isinstance(error, PermissionError)
                    ):
                        raise LinkPermissionError(
                            "Windows不允许建立符号链接：可手动请求管理员重启、开启开发者模式，或选择复制。"
                        ) from error
                    raise
                if not self.matches(staged, item):
                    raise OSError("暂存文件校验失败")
            atomic_json(folder / "journal.json", {"id": transaction, "old": old, "new": new_state})
            for item in old["files"]:
                destination = self.root / item["name"]
                if os.path.lexists(destination):
                    destination.replace(folder / "old" / item["name"])
            for item in new:
                destination = self.root / item["name"]
                if os.path.lexists(destination):
                    raise FileExistsError(f"目标被其他程序占用：{destination.name}")
                (folder / "new" / item["name"]).replace(destination)
            atomic_json(self.manifest, new_state)
        except BaseException:
            if (folder / "journal.json").exists():
                self.recover()
            elif folder.exists():
                self._clean(folder)
            raise
        # A committed transaction remains valid even if cleanup cannot finish.
        with contextlib.suppress(OSError):
            self._clean(folder)
