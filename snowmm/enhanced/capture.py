"""Desktop-only region capture and Windows RegisterHotKey (no game injection)."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget


class Hotkey(QAbstractNativeEventFilter):
    ID = 0x534D

    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.active = False

    def register(self, text):
        self.close()
        parts = text.upper().replace(" ", "").split("+")
        modifiers = 0x4000
        for key in parts[:-1]:
            if key not in {"CTRL", "ALT", "SHIFT", "WIN"}:
                raise ValueError("热键格式如 Ctrl+Alt+S 或 Ctrl+Shift+F8")
            modifiers |= {"ALT": 1, "CTRL": 2, "SHIFT": 4, "WIN": 8}[key]
        key = parts[-1]
        if len(key) == 1 and key.isascii() and key.isalnum():
            virtual_key = ord(key)
        elif key.startswith("F") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
            virtual_key = 111 + int(key[1:])
        else:
            raise ValueError("热键主键请使用字母、数字或 F1-F12")
        if os.name != "nt":
            raise OSError("全局热键仅在 Windows 下注册；仍可点击截图按钮")
        if not ctypes.windll.user32.RegisterHotKey(None, self.ID, modifiers, virtual_key):
            raise OSError("截图热键被占用或注册失败，请更换热键；仍可点击截图按钮或粘贴")
        self.active = True
        QApplication.instance().installNativeEventFilter(self)

    def close(self):
        if self.active:
            ctypes.windll.user32.UnregisterHotKey(None, self.ID)
            QApplication.instance().removeNativeEventFilter(self)
            self.active = False

    def nativeEventFilter(self, event_type, message):
        if os.name == "nt":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x0312 and msg.wParam == self.ID:
                QTimer.singleShot(0, self.callback)
                return True, 0
        return False, 0


class RegionOverlay(QWidget):
    captured = Signal(object)
    cancelled = Signal()

    def __init__(self, screen, pixmap):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setGeometry(screen.geometry())
        self.pixmap = pixmap
        self.begin = self.end = None
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self.pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        painter.setPen(QColor("white"))
        painter.drawText(QPoint(24, 35), "拖动框选截图 · Esc 取消 · 可在任一显示器选择")
        if self.begin is not None and self.end is not None:
            rectangle = QRect(self.begin, self.end).normalized()
            painter.setPen(QPen(QColor("#50c7ff"), 2))
            painter.drawRect(rectangle)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.begin = self.end = event.position().toPoint()
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()

    def mouseMoveEvent(self, event):
        if self.begin is not None:
            self.end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.begin is None:
            return
        self.end = event.position().toPoint()
        rectangle = QRect(self.begin, self.end).normalized().intersected(self.rect())
        if rectangle.width() < 3 or rectangle.height() < 3:
            return
        # Convert screen logical pixels to the captured pixmap's physical pixels.
        sx = self.pixmap.width() / self.width()
        sy = self.pixmap.height() / self.height()
        pixels = QRect(
            round(rectangle.x() * sx),
            round(rectangle.y() * sy),
            round(rectangle.width() * sx),
            round(rectangle.height() * sy),
        )
        image = self.pixmap.copy(pixels).toImage()
        image.setDevicePixelRatio(1)
        self.captured.emit(image)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()


class CaptureSession:
    def __init__(self, owner, done):
        self.owner, self.done = owner, done
        self.overlays = []
        self.busy = False

    def start(self):
        if self.busy:
            return
        self.busy = True
        self.owner.hide()
        QTimer.singleShot(200, self._capture)

    def _capture(self):
        try:
            frames = [(screen, screen.grabWindow(0)) for screen in QApplication.screens()]
            frames = [(screen, frame) for screen, frame in frames if not frame.isNull()]
            if not frames:
                raise RuntimeError("未能截取桌面，请用 Windows 截图后 Ctrl+V 粘贴")
            for screen, frame in frames:
                overlay = RegionOverlay(screen, frame)
                overlay.captured.connect(self.finish)
                overlay.cancelled.connect(lambda: self.finish(None))
                self.overlays.append(overlay)
                overlay.show()
                overlay.raise_()
                overlay.activateWindow()
        except Exception:
            self.finish(None)
            self.owner.toast_host.show_message(
                "桌面截图失败：请使用窗口/无边框模式，或用 Windows 截图后粘贴。", "warning"
            )

    def finish(self, image):
        if not self.busy:
            return
        self.busy = False
        for overlay in self.overlays:
            overlay.close()
            overlay.deleteLater()
        self.overlays.clear()
        self.owner.show()
        self.owner.raise_()
        self.owner.activateWindow()
        if image is not None:
            self.done(image)
