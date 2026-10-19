"""Image loading, cover-cropping and generated placeholder artwork."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGuiApplication,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRegion,
)

from ..core import paths
from ..core.catalog import Character
from ..core.models import Mod
from ..i18n import armor_name, character_name, get_language

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def save_clipboard_image(directory: Path, stem: str = "clipboard") -> str:
    """Write the image on the clipboard to ``directory``.

    Returns the saved path, or an empty string when the clipboard holds no
    image (text, files, nothing at all).
    """
    clipboard = QGuiApplication.clipboard()
    image = clipboard.image() if clipboard is not None else None
    if image is None or image.isNull():
        return ""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{stem}-{uuid.uuid4().hex[:8]}.png"
    if not image.save(str(target), "PNG"):
        return ""
    return str(target)


def cover(pixmap: QPixmap, size: QSize, vertical_anchor: float = 0.5) -> QPixmap:
    """Scale ``pixmap`` so it fills ``size`` while preserving the aspect ratio."""
    if pixmap.isNull():
        return pixmap
    scaled = pixmap.scaled(
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - size.width()) // 2)
    y = max(0, int((scaled.height() - size.height()) * vertical_anchor))
    return scaled.copy(x, y, size.width(), size.height())


def rounded(pixmap: QPixmap, radius: int) -> QPixmap:
    """Return ``pixmap`` clipped to a rounded rectangle."""
    if pixmap.isNull():
        return pixmap
    canvas = QPixmap(pixmap.size())
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, pixmap.width(), pixmap.height()), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return canvas


def _accent_for(name: str) -> tuple[QColor, QColor]:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()
    hue = int(digest[:4], 16) % 360
    top = QColor.fromHsv(hue, 130, 205)
    bottom = QColor.fromHsv((hue + 34) % 360, 165, 120)
    return top, bottom


def placeholder(name: str, size: QSize, dark: bool = True) -> QPixmap:
    """Generate a gradient card with the character's initial.

    Used whenever no portrait file is available, which keeps the grid looking
    intentional even with a completely offline, image-less catalog.
    """
    canvas = QPixmap(size)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    top, bottom = _accent_for(name or "?")
    if not dark:
        top = top.lighter(118)
        bottom = bottom.lighter(112)
    gradient = QLinearGradient(0, 0, size.width(), size.height())
    gradient.setColorAt(0.0, top)
    gradient.setColorAt(1.0, bottom)
    painter.setBrush(QBrush(gradient))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(0, 0, size.width(), size.height()), 12, 12)

    painter.setPen(QPen(QColor(255, 255, 255, 38), 1))
    step = max(18, size.width() // 6)
    for offset in range(step, size.width() + size.height(), step):
        painter.drawLine(offset, 0, offset - size.height(), size.height())

    initial = (name or "?").strip()[:1]
    font = QFont()
    font.setPointSize(max(14, size.height() // 3))
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255, 210))
    painter.drawText(QRectF(0, 0, size.width(), size.height()), Qt.AlignmentFlag.AlignCenter, initial)
    painter.end()
    return canvas


class ImageCache:
    """Loads portraits and mod previews, falling back to generated artwork."""

    def __init__(self, dark: bool = True) -> None:
        self.dark = dark
        self._files: dict[tuple[str, int], QPixmap] = {}
        self._derived: dict[tuple[str, int, int], QPixmap] = {}

    def set_dark(self, dark: bool) -> None:
        if dark != self.dark:
            self.dark = dark
            self._derived.clear()

    def clear(self) -> None:
        self._files.clear()
        self._derived.clear()

    # ------------------------------------------------------------- raw files
    def _load(self, path: str) -> QPixmap | None:
        if not path:
            return None
        target = Path(path)
        try:
            stamp = int(target.stat().st_mtime)
        except OSError:
            return None
        key = (str(target), stamp)
        cached = self._files.get(key)
        if cached is not None:
            return cached
        pixmap = QPixmap(str(target))
        if pixmap.isNull():
            return None
        self._files[key] = pixmap
        return pixmap

    def portrait_path(self, character: Character) -> str:
        """Resolve a portrait file: catalog path first, then the user cache."""
        if character.portrait and Path(character.portrait).exists():
            return character.portrait
        for suffix in IMAGE_SUFFIXES:
            candidate = paths.PORTRAIT_DIR / f"{character.slug}{suffix}"
            if candidate.exists():
                return str(candidate)
        return ""

    # ------------------------------------------------------------- rendered
    def _remember(self, key: tuple[str, int, int], pixmap: QPixmap) -> QPixmap:
        self._derived[key] = pixmap
        return pixmap

    def portrait(self, character: Character, size: QSize, radius: int = 12) -> QPixmap:
        key = (f"portrait:{get_language()}:{character.name}", size.width(), radius)
        cached = self._derived.get(key)
        if cached is not None:
            return cached
        source = self._load(self.portrait_path(character))
        if source is None:
            return self._remember(key, placeholder(character_name(character.name, character.name_en), size, self.dark))
        if source.hasAlphaChannel():
            bounds = QRegion(source.mask()).boundingRect()
            if not bounds.isEmpty():
                source = source.copy(bounds)
        return self._remember(key, rounded(cover(source, size, vertical_anchor=0.1), radius))

    def preview(self, mod: Mod, size: QSize, radius: int = 10) -> QPixmap:
        key = (f"preview:{get_language()}:{mod.id}:{mod.preview}", size.width(), radius)
        cached = self._derived.get(key)
        if cached is not None:
            return cached
        source = self._load(mod.preview)
        if source is None:
            canvas = placeholder(character_name(mod.character or mod.name), size, self.dark)
            painter = QPainter(canvas)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QColor(255, 255, 255, 55))
            font = QFont()
            font.setPointSize(max(9, size.height() // 12))
            painter.setFont(font)
            painter.drawText(
                QRectF(0, 0, size.width(), size.height() - 8),
                Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                armor_name(mod.character) if mod.character else "",
            )
            painter.end()
            return self._remember(key, canvas)
        return self._remember(key, rounded(cover(source, size), radius))
