# Changelog

## 1.1.0 — 2026-10-29

- Automatically detect and repair legacy Chinese flat and character/armor/skin layouts
  on startup, directory selection, scan and F5 refresh, with pre-migration database snapshots.
  Preserve metadata and enable state, keep companion packages together, and avoid overwrites.
- Embed the enabled-mod gallery in both All Mods and character details with a Back button.
  Gallery shortcuts apply only while the gallery has focus.

- Fix missing covers when stored portrait paths predate the English asset layout;
  refresh reused cards when portrait sources change.
- Restore enable states from disk before startup rendering.
- Allow names for archive/folder imports and update table labels immediately after metadata edits.
- Enabled-mod gallery from the preview panel, full-image viewer and all-mods toolbar;
  per-card toggles, arrow navigation and Space shortcuts, with disabled cards kept until refresh.

- Default skin for every armor and 116 offline, bilingual outfits sourced from BWIKI.
  Character details filter mods by skin; imports and inspector moves persist skin assignments.
- English character/element assets and managed mod paths, stable ASCII package names,
  and a Settings migration with a database snapshot, collision handling and package rollback.
- ZIP, 7z and RAR imports discover nested pak/utoc packages and their companions in temporary staging.
  Reject unsafe paths and links before extraction; enforce archive entry and expanded-size limits.
- Base and Miscellaneous cards skip multi-enabled and duplicate-record checks.
  Character conflicts now compare mods within the same armor and skin.
- Added core and UI regressions. Nexus Mods integration evaluated separately; no online feature implemented.

## 1.0.0 — 2026-10-19

Major update from the 0.2.x single-file PyQt5 application.

### New

- PySide6 application with separate core and UI layers, responsive character cards,
  three-panel character details, all-mods management, health checks and settings.
- 54 bundled, text-free character portraits, with a source and checksum manifest.
- Complete Chinese/English character, exosuit, damage-type and interface labels;
  character identity and Chinese storage paths remain compatible.
- Reference-based blue application emblem with multi-resolution ICO/PNG assets,
  Windows taskbar identity, window icon and sidebar branding.
- Folder and pak imports with automatic companion discovery, per-package records,
  clipboard/drop image assignment and full-image zoom/pan previews.
- Dark/light themes, favorites, filtering, F5 refresh and Ctrl+F search.
- Atomic JSON persistence, legacy data migration, backups and layout conversion.
- Windows portable/source/resource archives with SHA-256 checksums.

### Fixed

- Card overlap and missing spacing caused by mismatched content/outer widths.
- Transient standalone subtitle/badge windows during card creation and filtering.
- Empty/disabled-only character cards becoming unclickable due to the Qt enabled property.
- Recreated cards on filtering, lost multi-selection after refresh, stale inspector state.
- Partial package imports, independently renamed companions and duplicate pak/utoc records.
- Incorrect enabled state after an operation failed, missing rollback and lost records on failed deletion.
- Disabled files and stale database paths during legacy layout conversion.
- Pending note loss when selecting another mod, changing language or closing.

### Compatibility

- Legacy 0.2.x source and screenshots are retained in `snow_mod_manager/`.
- User data remains outside the application directory under `%APPDATA%/SnowMM/`.
- Archive import remains disabled; extract archives and import folders instead.
- Game mounting behavior has not been verified against a live game installation.

## 0.2.2

Legacy single-file PyQt5 manager with category navigation, conflict hints and search.
