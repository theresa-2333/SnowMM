"""Small building blocks: cards, tags, search box, empty states and toasts."""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import icons
from ..theme import Theme


class WheelGuard(QObject):
    """Keep the mouse wheel from changing text boxes, combos and spin boxes.

    Scrolling a page while a combo box sat under the pointer used to change the
    selection silently.  Unless the widget has focus the wheel is passed on, so
    the surrounding scroll area moves instead.
    """

    GUARDED = (QComboBox, QAbstractSpinBox, QLineEdit, QTextEdit, QPlainTextEdit)

    def eventFilter(self, watched, event) -> bool:
        if (
            event.type() == QEvent.Type.Wheel
            and isinstance(watched, self.GUARDED)
            and not watched.hasFocus()
        ):
            event.ignore()
            return True
        return False


class FlowLayout(QLayout):
    """Wraps its children onto as many lines as the width allows.

    Rows of chips and buttons are the main thing that breaks on a narrow
    window, so they use this instead of a fixed ``QHBoxLayout``.
    """

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 8) -> None:
        super().__init__(parent)
        self._items: list = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    # ------------------------------------------------------------ QLayout API
    def addItem(self, item) -> None:  # noqa: N802 - Qt naming
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    # ------------------------------------------------------------- internals
    def _layout(self, rect: QRect, *, apply: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, line_height = area.x(), area.y(), 0
        spacing = self.spacing()
        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            hint = item.sizeHint()
            if x + hint.width() > area.right() and line_height > 0:
                x = area.x()
                y += line_height + spacing
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + spacing
            line_height = max(line_height, hint.height())
        return y + line_height - rect.y() + margins.bottom()


class Card(QFrame):
    """Rounded surface used as the base for every panel."""

    def __init__(self, parent: QWidget | None = None, object_name: str = "Card") -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class Divider(QFrame):
    """One pixel separator that matches the active theme."""

    def __init__(self, vertical: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("VSeparator" if vertical else "Separator")
        if vertical:
            self.setFixedWidth(1)
            self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        else:
            self.setFixedHeight(1)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class Tag(QLabel):
    """Pill shaped label; ``variant`` selects one of the styled object names."""

    VARIANTS = {
        "": "Tag",
        "accent": "TagAccent",
        "success": "TagSuccess",
        "danger": "TagDanger",
        "warning": "TagWarning",
    }

    def __init__(self, text: str = "", variant: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName(self.VARIANTS.get(variant, "Tag"))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)


class ChipButton(QPushButton):
    """Checkable filter chip."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setObjectName("Chip")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class SearchBox(QLineEdit):
    """Line edit with a leading search glyph."""

    def __init__(self, placeholder: str = "", theme: Theme | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Search")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.setMinimumWidth(220)
        self._icon_action = None
        if theme is not None:
            self.apply_theme(theme)

    def apply_theme(self, theme: Theme) -> None:
        if self._icon_action is not None:
            self.removeAction(self._icon_action)
        self._icon_action = self.addAction(
            icons.icon("search", theme.text_dim, 16), QLineEdit.ActionPosition.LeadingPosition
        )


class EmptyState(QWidget):
    """Illustration plus message shown when a list has nothing to display."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 48, 24, 48)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label = QLabel()
        self.title_label.setObjectName("SectionTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label = QLabel()
        self.desc_label.setObjectName("Dim")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.desc_label.setWordWrap(True)
        self.action_button = QPushButton()
        self.action_button.setObjectName("Primary")
        self.action_button.hide()
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.desc_label)
        layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignCenter)

    def show_state(
        self,
        title: str,
        description: str = "",
        *,
        icon: str = "package",
        theme: Theme | None = None,
        action: str = "",
    ) -> None:
        if theme is not None:
            self.icon_label.setPixmap(icons.pixmap(icon, theme.text_faint, 40, 1.4))
        self.title_label.setText(title)
        self.desc_label.setText(description)
        self.desc_label.setVisible(bool(description))
        self.action_button.setText(action)
        self.action_button.setVisible(bool(action))


class Toast(QWidget):
    """Floating, self-dismissing notification anchored to the parent window."""

    closed = Signal()

    def __init__(self, parent: QWidget, message: str, theme: Theme, icon_name: str = "check") -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 16, 10)
        layout.setSpacing(10)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap(icon_name, theme.success, 18))
        self.text_label = QLabel(message)
        self.text_label.setObjectName("ToastText")
        layout.addWidget(glyph)
        layout.addWidget(self.text_label)
        self.adjustSize()
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(0.0)
        self._animation: QPropertyAnimation | None = None
        self.hide()

    def popup(self, duration_ms: int = 2600) -> None:
        self.show()
        self.raise_()
        self._animate(0.0, 1.0, 180)
        QTimer.singleShot(duration_ms, self._fade_out)

    def _fade_out(self) -> None:
        self._animate(1.0, 0.0, 260, on_done=self._finish)

    def _finish(self) -> None:
        self.hide()
        self.closed.emit()
        self.deleteLater()

    def _animate(self, start: float, end: float, duration: int, on_done=None) -> None:
        animation = QPropertyAnimation(self._effect, b"opacity", self)
        animation.setStartValue(start)
        animation.setEndValue(end)
        animation.setDuration(duration)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        if on_done is not None:
            animation.finished.connect(on_done)
        animation.start(QPropertyAnimation.DeletionPolicy.KeepWhenStopped)
        self._animation = animation


class ToastHost(QWidget):
    """Stacks toasts in the bottom-right corner of the main window."""

    def __init__(self, parent: QWidget, theme: Theme) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.theme = theme
        self._toasts: list[Toast] = []
        parent.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.Resize:
            self._reposition()
        return super().eventFilter(watched, event)

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme

    def show_message(self, message: str, icon_name: str = "check") -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        toast = Toast(parent, message, self.theme, icon_name)
        toast.closed.connect(lambda: self._forget(toast))
        self._toasts.append(toast)
        self._reposition()
        toast.popup()

    def _forget(self, toast: Toast) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        self._reposition()

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        margin = 24
        offset = 0
        for toast in reversed(self._toasts):
            toast.adjustSize()
            x = parent.width() - toast.width() - margin
            y = parent.height() - toast.height() - margin - offset
            toast.move(max(margin, x), max(margin, y))
            offset += toast.height() + 10
