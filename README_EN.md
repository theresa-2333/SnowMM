# SnowMM · Snowbreak Mod Manager

[简体中文](README.md) · [Changelog](CHANGELOG.md) · [Issues](https://github.com/theresa-2333/Snowbreak_Mod_Manager/issues)

**v1.0.0** is a major upgrade from 0.2.x: a PySide6 desktop app with character cards,
package-aware mod management, image previews, and a fully offline asset library.

## Run

Download `SnowMM-1.0.0-windows-x64.zip` from
[Releases](https://github.com/theresa-2333/Snowbreak_Mod_Manager/releases).
Extract the **whole archive**, then run `SnowMM/SnowMM.exe`. Keep its `_internal` folder alongside it.

From source (Python 3.10+):

```powershell
python -m pip install -r requirements.txt
python main.py
```

First launch opens Settings. Select the game's mods directory, usually
`<game>/Game/Content/Paks/mods`, then scan to adopt existing mods.
Choose English in Settings; language changes apply immediately.

![English character overview](docs/screenshots/14-characters-english.png)

![English character detail](docs/screenshots/15-detail-english.png)

## Features

- 54 bundled operatives with clean portraits, damage-type filters, favorites, and search.
  Characters with no mods can still be opened.
- English character names, exosuit names, damage types, and interface text.
  Chinese storage keys and folder names stay unchanged, preserving existing collections.
- Import pak files or whole folders from a character's page. Same-stem utoc, ucas, and sig
  companions are included automatically; each package receives its own record.
- Collision handling keeps one shared stem across a package. Toggle, rename, and move
  operations preflight destinations and attempt rollback on failure.
- Choose, drop, or paste a preview image. Click an existing image to view it in full,
  zoom with the wheel, drag to pan, select 100% or Fit, and press Esc to close.
- Missing files, duplicate records, multiple active mods, and unknown-character checks.
- Legacy record migration, directory conversion, backups, dark/light themes, and a new app icon.
- Selection survives refresh; pending notes are saved before selection/language changes or closing.
  Narrow windows collapse the portrait and secondary columns.

Shortcuts: F5 refreshes, Ctrl+F focuses search, and Ctrl+V pastes an image into the inspector.

## Storage and upgrades

Files are stored under `<mods>/<Chinese character-exosuit>/`.
Enabled files retain their extensions; disabled files receive `.disabled`.
Companion files are toggled together. `_100_P` is optional, and existing suffixes are preserved.
Archive import (`.zip/.7z/.rar`) remains disabled; extract the archive and import its folder.

User data lives in `%APPDATA%/SnowMM/`: settings, database, previews, and backups.
Keep this directory when upgrading. The app can migrate `~/.snowbreak_mod_manager/projects.json`
and convert the old character/armor/outfit directory layout while updating tracked paths.

## Development and release builds

```powershell
python -m unittest discover -s tests -t .   # 57 core/resource checks
python tests/smoke_ui.py
python tests/regression_ui.py
python -m ruff check .
python -m pip install -e ".[dev]"
pwsh -NoProfile -File tools/build_exe.ps1
python tools/package_release.py
```

Release tooling creates portable Windows, source, and resource archives with SHA-256 hashes.
See [release instructions](docs/RELEASE.md). The old 0.2.x app remains under `snow_mod_manager/`.

## Credits

Portraits: [GameKee](https://www.gamekee.com/snow/second/61949), with Sparkdrive artwork from
[BWIKI](https://wiki.biligame.com/sonw/芙提雅·炬芯).
English names: [Snowbreak Wiki](https://snowbreak.fandom.com/wiki/Characters) and
[GachaData](https://gacha-data.com/snowbreak/characters/).
Individual image URLs and digests are recorded in `snowmm/assets/catalog/artwork.json`.
Interface inspiration: [JASM](https://github.com/Kiyanami/JASM).

This is an unofficial tool. Game artwork and trademarks belong to their respective owners.
See [third-party notices](THIRD_PARTY_NOTICES.md).
