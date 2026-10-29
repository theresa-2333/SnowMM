"""Filesystem locations used by the application and its bundled assets."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR_NAME = "SnowMM"
LEGACY_DIR_NAME = ".snowbreak_mod_manager"

PACKAGE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = PACKAGE_DIR / "assets"
ELEMENTS_DIR = ASSETS_DIR / "elements"

#: Bundled character art library: ``<art>/<english-element>/<english-id>.png``. It is the
#: single source of truth for which characters exist (54 of them), so it always
#: ships inside the package and is never user configurable.
ART_DIR = ASSETS_DIR / "characters"

# Damage types, in the order the game lists them.
ELEMENTS = ("高热", "低温", "电击", "动能", "特异")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def _base_dir() -> Path:
    """Return the writable per-user application directory."""
    override = os.environ.get("SNOWMM_HOME")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        root = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return Path(root) / APP_DIR_NAME


BASE_DIR = _base_dir()
DATA_FILE = BASE_DIR / "data.json"
SETTINGS_FILE = BASE_DIR / "settings.json"
IMAGES_DIR = BASE_DIR / "images"
PREVIEW_DIR = IMAGES_DIR / "mods"
PORTRAIT_DIR = IMAGES_DIR / "portraits"
BACKUP_DIR = BASE_DIR / "backups"

LEGACY_DIR = Path.home() / LEGACY_DIR_NAME
LEGACY_PROJECTS_FILE = LEGACY_DIR / "projects.json"
LEGACY_CONFIG_FILE = LEGACY_DIR / "config.json"
LEGACY_IMAGES_DIR = LEGACY_DIR / "images"


def ensure_dirs() -> None:
    """Create every directory the application writes to."""
    for directory in (BASE_DIR, IMAGES_DIR, PREVIEW_DIR, PORTRAIT_DIR, BACKUP_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def asset(*parts: str) -> Path:
    """Path to a bundled read-only asset."""
    return ASSETS_DIR.joinpath(*parts)


def resolve_art_dir() -> Path:
    """The bundled character art library."""
    return ART_DIR


def element_icon(element: str) -> Path | None:
    """Bundled 40x40 damage-type icon, if the element is known."""
    from .naming import ELEMENT_IDS

    for suffix in IMAGE_SUFFIXES:
        candidate = ELEMENTS_DIR / f"{ELEMENT_IDS.get(element, element)}{suffix}"
        if candidate.exists():
            return candidate
    return None
