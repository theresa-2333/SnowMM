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

OUTPUT = ROOT / "dist" / "release" / __version__


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
    for pattern in (f"snowmm-{__version__}-*.whl", f"snowmm-{__version__}.tar.gz"):
        for file in (ROOT / "dist").glob(pattern):
            shutil.copy2(file, OUTPUT / file.name)
    notes = f"""# SnowMM v{__version__} — Skins, automatic compatibility and inline gallery

新增默认皮肤和 BWIKI 收录的 116 套时装，支持详情页分类导入与皮肤归属调整。
启动、选择目录、扫描和 F5 刷新时，自动检测旧中文目录／角色-装甲-皮肤目录并兼容至英文路径。
转换前自动备份数据库，保留名称、备注、预览和启用状态，配套文件成组迁移、碰撞不覆盖。
模组总览及角色详情中的画廊均在当前页面切换，支持按钮和方向键／空格快捷开关。
修复卜卜封面旧路径回退、首次打开时启用状态，以及压缩包／文件夹导入名称编辑。

Windows：下载 windows-x64.zip，完整解压并运行 SnowMM/SnowMM.exe。
请保留 _internal 目录。原有数据继续位于 %APPDATA%/SnowMM/。
支持 ZIP／7z／RAR 导入、116 套时装分类及英文目录。solid RAR 需要 WinRAR／7-Zip。
基地／杂项卡片跳过重复检查。Windows 应用未签名。

Default skins and 116 BWIKI outfits, skin-aware imports, automatic legacy Chinese-path
repair with database backups, preserved metadata and grouped package moves.
Enabled-mod galleries switch within All Mods and character detail pages; no gallery popup.
Use card buttons, arrows and Space for quick toggles. Fixes stale cover paths,
startup enabled state and editable names for archive/folder imports.

Windows: extract the entire windows-x64 archive and run SnowMM/SnowMM.exe.
Keep the _internal folder. User data remains in %APPDATA%/SnowMM/.
ZIP / 7z / RAR imports, 116 outfits, English paths and utility cards are included.
Solid RAR needs WinRAR / 7-Zip. Unsigned x64 build.

87 core/resource checks and UI smoke/interaction regressions pass. The frozen app
self-test validates its bundled artwork, translations, icons and navigation.
Live game mounting has not been verified.
Nexus integration was evaluated only and is not included.

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
