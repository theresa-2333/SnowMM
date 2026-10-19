"""Inline SVG icon set rendered into ``QIcon``/``QPixmap`` on demand.

Keeping the icons as SVG source avoids shipping binary assets and lets every
icon be recoloured to match the active theme.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_SVG = {
    "grid": '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
    "list": '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1.4"/><circle cx="4" cy="12" r="1.4"/><circle cx="4" cy="18" r="1.4"/>',
    "layers": '<path d="M12 3 3 8l9 5 9-5-9-5Z"/><path d="m3 13 9 5 9-5"/>',
    "shield": '<path d="M12 3l7 3v6c0 4.2-2.9 7.6-7 9-4.1-1.4-7-4.8-7-9V6l7-3Z"/><path d="M9 12l2 2 4-4"/>',
    "gear": '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.5v2.2M12 19.3v2.2M4.2 7.3l1.9 1.1M17.9 15.6l1.9 1.1M4.2 16.7l1.9-1.1M17.9 8.4l1.9-1.1"/>',
    "search": '<circle cx="11" cy="11" r="6.2"/><path d="m16 16 4.5 4.5"/>',
    "refresh": '<path d="M20 12a8 8 0 1 1-2.6-5.9"/><path d="M20 4v4h-4"/>',
    "play": '<path d="M7 4.5 19 12 7 19.5v-15Z"/>',
    "folder": '<path d="M3 7.5A1.5 1.5 0 0 1 4.5 6H9l2 2.5h8.5A1.5 1.5 0 0 1 21 10v7.5A1.5 1.5 0 0 1 19.5 19h-15A1.5 1.5 0 0 1 3 17.5v-10Z"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "check": '<path d="m5 12.5 4.5 4.5L19 7"/>',
    "trash": '<path d="M4 7h16M9 7V5h6v2M6.5 7l1 12.5h9L17.5 7"/>',
    "edit": '<path d="M4 20h4L20 8l-4-4L4 16v4Z"/><path d="m14 6 4 4"/>',
    "star": '<path d="m12 4 2.5 5.2 5.5.8-4 3.9 1 5.6-5-2.8-5 2.8 1-5.6-4-3.9 5.5-.8L12 4Z"/>',
    "chevron-left": '<path d="M14.5 6 9 12l5.5 6"/>',
    "chevron-down": '<path d="m6 9.5 6 5.5 6-5.5"/>',
    "image": '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><circle cx="8.5" cy="10" r="1.6"/><path d="m4 17 5-4.5 4 3.5 3-2.5 4 3.5"/>',
    "link": '<path d="M10 13.5a4 4 0 0 0 5.7 0l2.8-2.8a4 4 0 0 0-5.7-5.7l-1.3 1.3"/><path d="M14 10.5a4 4 0 0 0-5.7 0l-2.8 2.8a4 4 0 0 0 5.7 5.7l1.3-1.3"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5"/>',
    "moon": '<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
    "package": '<path d="M21 8.5 12 4 3 8.5v7L12 20l9-4.5v-7Z"/><path d="M3 8.5 12 13l9-4.5M12 13v7"/>',
    "warning": '<path d="M12 4 2.5 20h19L12 4Z"/><path d="M12 10v4.5M12 17.2v.3"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 8.2v.3"/>',
    "copy": '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M15 6.5A2.5 2.5 0 0 0 12.5 4h-6A2.5 2.5 0 0 0 4 6.5v6A2.5 2.5 0 0 0 6.5 15"/>',
    "save": '<path d="M5 4h11l4 4v12H5V4Z"/><path d="M9 4v5h6V4M9 20v-6h6v6"/>',
    "filter": '<path d="M3 6h18l-7 8v6l-4-2v-4L3 6Z"/>',
    "database": '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "eye": '<path d="M2.5 12S6 6.5 12 6.5 21.5 12 21.5 12 18 17.5 12 17.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="2.6"/>',
    "user": '<circle cx="12" cy="8.5" r="3.6"/><path d="M5 20c.6-3.5 3.5-5.5 7-5.5s6.4 2 7 5.5"/>',
    "external": '<path d="M14 4h6v6"/><path d="M20 4 11 13"/><path d="M18 14.5V19a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 19V7.5A1.5 1.5 0 0 1 5 6h4.5"/>',
}


def _svg_markup(name: str, color: str, width: float = 1.7, filled: bool = False) -> str:
    body = _SVG.get(name, _SVG["info"])
    if filled:
        style = f'fill="{color}" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"'
    else:
        style = (
            f'fill="none" stroke="{color}" stroke-width="{width}" '
            'stroke-linecap="round" stroke-linejoin="round"'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f"<g {style}>{body}</g></svg>"
    )


@lru_cache(maxsize=512)
def pixmap(name: str, color: str, size: int = 20, width: float = 1.7, filled: bool = False) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(_svg_markup(name, color, width, filled).encode("utf-8")))
    canvas = QPixmap(QSize(size, size))
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return canvas


def icon(name: str, color: str, size: int = 20, width: float = 1.7, filled: bool = False) -> QIcon:
    return QIcon(pixmap(name, color, size, width, filled))


CHECK_MARK_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
    '<path d="M4 8.5 7 11.5 12.5 5" fill="none" stroke="#ffffff" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


def write_check_mark(directory) -> str:
    """Materialise the checkbox check-mark so the stylesheet can reference it."""
    target = directory / "check.svg"
    try:
        if not target.exists() or target.read_text(encoding="utf-8") != CHECK_MARK_SVG:
            target.write_text(CHECK_MARK_SVG, encoding="utf-8")
    except OSError:
        return ""
    return str(target)
