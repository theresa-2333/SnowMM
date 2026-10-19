"""Full-image viewer with fit, zoom and mouse panning."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ...i18n import tr


class ImageView(QGraphicsView):
    def __init__(self, pixmap: QPixmap, parent=None) -> None:
        super().__init__(parent)
        scene = QGraphicsScene(self)
        scene.addPixmap(pixmap)
        scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.setScene(scene)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._fit = True

    def fit_image(self) -> None:
        self._fit = True
        self.resetTransform()
        self.fitInView(self.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def actual_size(self) -> None:
        self._fit = False
        self.resetTransform()
        self.centerOn(self.sceneRect().center())

    def zoom(self, factor: float) -> None:
        scale = self.transform().m11() * factor
        if 0.01 <= scale <= 32:
            self._fit = False
            self.scale(factor, factor)

    def wheelEvent(self, event) -> None:
        self.zoom(1.25 if event.angleDelta().y() > 0 else 0.8)
        event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._fit:
            self.fit_image()


class ImagePreviewDialog(QDialog):
    def __init__(self, pixmap: QPixmap, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{tr('label_preview')} · {title}")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(1000, 760)
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(1000, int(available.width() * 0.9)), min(760, int(available.height() * 0.9)))
        layout = QVBoxLayout(self)
        self.view = ImageView(pixmap, self)
        layout.addWidget(self.view, 1)
        controls = QHBoxLayout()
        for label, action in (
            ("−", lambda: self.view.zoom(0.8)),
            ("+", lambda: self.view.zoom(1.25)),
            ("100%", self.view.actual_size),
            (tr("preview_fit"), self.view.fit_image),
        ):
            button = QPushButton(label)
            button.clicked.connect(action)
            controls.addWidget(button)
        hint = QLabel(tr("preview_controls"))
        hint.setWordWrap(True)
        controls.addWidget(hint, 1)
        close = QPushButton(tr("preview_close"))
        close.clicked.connect(self.close)
        controls.addWidget(close)
        layout.addLayout(controls)
        QTimer.singleShot(0, self.view.fit_image)
