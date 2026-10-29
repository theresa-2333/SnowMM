"""Extract only Unreal package files into a private staging directory."""
from __future__ import annotations

import os
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

MAX_FILES = 20000
MAX_BYTES = 8 * 1024**3
PACKAGE_SUFFIXES = {".pak", ".utoc", ".ucas", ".sig"}


def _safe_name(name: str) -> str:
    normalized = name.replace("\\", "/").rstrip("/")
    parts = PurePosixPath(normalized).parts
    windows = PureWindowsPath(normalized)
    if (not parts or normalized.startswith("/") or windows.drive
            or any(part in {".", ".."} or ":" in part or part.endswith((".", " "))
                   or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)
                   for part in parts)):
        raise ValueError(f"unsafe archive path: {name}")
    return normalized


def _validate(entries: list[tuple[str, int, bool]]) -> list[str]:
    if len(entries) > MAX_FILES or sum(size for _, size, _ in entries) > MAX_BYTES:
        raise ValueError("archive exceeds extraction limit (20000 entries / 8 GiB)")
    selected = []
    seen = set()
    for name, _size, link in entries:
        normalized = _safe_name(name)
        if link:
            raise ValueError(f"archive links are not supported: {name}")
        bare = normalized.removesuffix(".disabled")
        if not name.endswith(("/", "\\")) and Path(bare).suffix.lower() in PACKAGE_SUFFIXES:
            if normalized.casefold() in seen:
                raise ValueError(f"duplicate archive path: {name}")
            seen.add(normalized.casefold())
            selected.append(name)
    return selected


def _copy(reader, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as writer:
        shutil.copyfileobj(reader, writer)


def extract_packages(source: Path, target: Path) -> None:
    """Validate before extraction; callers own cleanup on every outcome."""
    extension = source.suffix.lower()
    if extension == ".zip":
        with zipfile.ZipFile(source) as archive:
            entries = archive.infolist()
            selected = _validate([(item.filename, item.file_size,
                                   stat.S_ISLNK(item.external_attr >> 16)) for item in entries])
            for name in selected:
                with archive.open(name) as reader:
                    _copy(reader, target / _safe_name(name))
    elif extension == ".7z":
        import py7zr

        with py7zr.SevenZipFile(source, "r") as archive:
            entries = archive.list()
            selected = _validate([
                (item.filename + ("/" if item.is_directory else ""), item.uncompressed,
                 not (item.is_file or item.is_directory)) for item in entries
            ])
            if selected:
                archive.extract(path=target, targets=selected)
    elif extension == ".rar":
        import rarfile

        if os.name == "nt":
            for variable in ("ProgramFiles", "ProgramFiles(x86)"):
                root = Path(os.environ.get(variable, "C:/Program Files"))
                unrar, sevenzip = root / "WinRAR/UnRAR.exe", root / "7-Zip/7z.exe"
                if unrar.is_file():
                    rarfile.UNRAR_TOOL = str(unrar)
                if sevenzip.is_file():
                    rarfile.SEVENZIP_TOOL = str(sevenzip)
            rarfile.BSDTAR_TOOL = shutil.which("tar.exe") or "bsdtar"
        with rarfile.RarFile(source) as archive:
            entries = archive.infolist()
            selected = _validate([(item.filename, item.file_size, item.is_symlink() or bool(item.file_redir))
                                  for item in entries])
            try:
                if any(item.filename in selected and item.compress_type != rarfile.RAR_M0 for item in entries):
                    rarfile.tool_setup(force=True)
                for name in selected:
                    with archive.open(name) as reader:
                        _copy(reader, target / _safe_name(name))
            except rarfile.Error as error:
                hint = "RAR extraction failed; install WinRAR or 7-Zip for solid RAR support"
                raise ValueError(f"{hint}: {error}") from error
    else:
        raise ValueError(f"unsupported archive: {extension}")
