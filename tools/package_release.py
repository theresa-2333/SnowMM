"""Create curated release archives; never include user data or build caches."""

from __future__ import annotations

import hashlib
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from snowmm import __version__

OUTPUT = ROOT / "dist" / "release"


def archive(target: Path, files):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for source, name in sorted(files, key=lambda pair: pair[1]):
            bundle.write(source, name)
    with zipfile.ZipFile(target) as bundle:
        if bundle.testzip():
            raise RuntimeError(f"Corrupt archive: {target}")


def tree(directory: Path):
    return [file for file in directory.rglob("*") if file.is_file()
            and "__pycache__" not in file.parts and file.suffix not in {".pyc", ".pyo"}]


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    stem = f"SnowMM-{__version__}"
    app_dir = ROOT / "dist" / "SnowMM"
    if not (app_dir / "SnowMM.exe").exists():
        raise FileNotFoundError("Build the Windows app with tools/build_exe.ps1 first")
    shutil.copytree(ROOT / "snowmm" / "assets", app_dir / "_internal" / "snowmm" / "assets", dirs_exist_ok=True)
    for name in ("README.md", "README_EN.md", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md"):
        shutil.copy2(ROOT / name, app_dir / name)
    archive(OUTPUT / f"{stem}-windows-x64.zip",
            [(file, "SnowMM/" + file.relative_to(app_dir).as_posix()) for file in tree(app_dir)])
    source_files = []
    for name in ("snowmm", "snow_mod_manager", "tests", "tools", "docs"):
        source_files.extend(tree(ROOT / name))
    source_files.extend(ROOT / name for name in (
        "main.py", "pyproject.toml", "requirements.txt", "MANIFEST.in", ".gitignore", ".gitattributes",
        "README.md", "README_EN.md", "THIRD_PARTY_NOTICES.md", "CHANGELOG.md",
    ))
    archive(OUTPUT / f"{stem}-source.zip",
            [(file, stem + "/" + file.relative_to(ROOT).as_posix()) for file in source_files])
    archive(OUTPUT / f"{stem}-assets.zip",
            [(file, "assets/" + file.relative_to(ROOT / "snowmm" / "assets").as_posix())
             for file in tree(ROOT / "snowmm" / "assets")]
            + [(ROOT / "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md")])
    for pattern in ("*.whl", "*.tar.gz"):
        for file in (ROOT / "dist").glob(pattern):
            shutil.copy2(file, OUTPUT / file.name)
    notes = f"""# SnowMM v{__version__} — Major Update

从 0.2.x 升级：全新 PySide6 界面、54 位角色无字图片、完整中英角色名、
新应用图标、成组模组导入与启停、图片放大查看、迁移与备份。
修复卡片重叠、筛选瞬时小窗口、空角色无法点击、配套文件拆散与备注丢失。

Windows：下载 windows-x64.zip，完整解压并运行 SnowMM/SnowMM.exe。
请保留 _internal 目录。原有数据继续位于 %APPDATA%/SnowMM/。
压缩包导入暂不支持；请先解压再导入文件夹。Windows 应用未签名。

Major upgrade from 0.2.x: PySide6 UI, 54 clean portraits, English operative/exosuit
names, new application icons, package-aware imports/toggles, zoomable image previews,
migration and backups. Fixes card overlap, transient filter windows, unclickable
empty characters, split companion files and lost notes.

Windows: extract the entire windows-x64 archive and run SnowMM/SnowMM.exe.
Keep the _internal folder. User data remains in %APPDATA%/SnowMM/.
Archive import remains disabled; extract first and import the folder. Unsigned x64 build.

57 core/resource checks and UI smoke/interaction regressions pass. The frozen app
self-test validates its bundled artwork, translations, icons and navigation.
Live game mounting has not been verified.

Artwork sources and third-party notices are included. See CHANGELOG.md for details.
"""
    (OUTPUT / "RELEASE_NOTES.md").write_text(notes, encoding="utf-8")
    hashes = []
    for file in sorted(OUTPUT.iterdir()):
        if file.name != "SHA256SUMS.txt" and file.is_file():
            hashes.append(f"{hashlib.sha256(file.read_bytes()).hexdigest()}  {file.name}")
            print(f"{file.name}: {file.stat().st_size / 1024**2:.1f} MiB")
    (OUTPUT / "SHA256SUMS.txt").write_text("\n".join(hashes) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
