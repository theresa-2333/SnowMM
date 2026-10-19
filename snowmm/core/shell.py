"""Small helpers for interacting with the operating system shell."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def reveal(path: str | Path) -> None:
    """Open the containing folder and select ``path`` when possible."""
    target = Path(path)
    if not target.exists():
        target = target.parent
    try:
        if sys.platform == "win32":
            if target.is_dir():
                os.startfile(str(target))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["explorer", "/select,", str(target)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target if target.is_dir() else target.parent)])
    except OSError:
        pass


def open_path(path: str | Path) -> None:
    """Open a file or folder with the default application."""
    target = Path(path)
    if not target.exists():
        return
    try:
        if sys.platform == "win32":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except OSError:
        pass


def open_url(url: str) -> None:
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices

    if not url:
        return
    if "://" not in url:
        url = f"https://{url}"
    QDesktopServices.openUrl(QUrl(url))


def launch_executable(executable: str, arguments: str = "") -> str | None:
    """Start the game; returns an error message on failure."""
    target = Path(executable)
    if not target.exists():
        return "missing"
    try:
        command = [str(target)] + ([arguments] if arguments else [])
        subprocess.Popen(command, cwd=str(target.parent))
    except OSError as error:
        return str(error)
    return None
