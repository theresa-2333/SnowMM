# Changelog

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
