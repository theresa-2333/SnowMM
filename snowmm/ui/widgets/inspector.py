"""Right hand inspector panel: preview, metadata editor and per-mod actions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core import paths, shell
from ...core.catalog import Catalog
from ...core.models import Mod, human_size
from ...core.skins import skins_for
from ...i18n import character_name, get_language, tr
from .. import icons
from ..imaging import ImageCache, save_clipboard_image
from ..theme import Theme
from .cards import icon_button, repolish
from .common import Card, EmptyState, FlowLayout, Tag
from .image_preview import ImagePreviewDialog


class ModInspector(Card):
    """Shows one mod (or a multi selection) and edits it in place."""

    changed = Signal(object)             # a Mod field changed and was saved
    enable_toggled = Signal(list, bool)
    delete_requested = Signal(list)
    reveal_requested = Signal(object)
    preview_requested = Signal(object)   # ask the page for an image file
    preview_dropped = Signal(object, str)
    paste_failed = Signal()
    category_changed = Signal(object, str)  # move a mod to another character
    skin_changed = Signal(object, str)
    gallery_requested = Signal()

    def __init__(
        self,
        theme: Theme,
        images: ImageCache,
        catalog: Catalog,
        parent: QWidget | None = None,
        *,
        show_character: bool = False,
    ) -> None:
        super().__init__(parent, "Card")
        self.theme = theme
        self.images = images
        self.catalog = catalog
        self.mods: list[Mod] = []
        self._preview_dialog: ImagePreviewDialog | None = None
        # The "all mods" view edits which character a mod belongs to; on a
        # character's own page that field would only repeat the page title.
        self.show_character = show_character
        self.character_combo: QComboBox | None = None
        self.acceptDrops()
        self.setMinimumWidth(260)
        self.setMaximumWidth(420)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        root.addWidget(self.stack)

        self.empty = EmptyState()
        self.empty.show_state(tr("label_preview"), tr("empty_mods_desc"), icon="eye", theme=theme)

        self.multi_page = self._build_multi_page()
        self.single_page = self._build_single_page()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.multi_page)
        self.stack.addWidget(self.single_page)
        self.stack.setCurrentWidget(self.empty)

    # ------------------------------------------------------------- construction
    def _build_multi_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        self.multi_title = QLabel()
        self.multi_title.setObjectName("SectionTitle")
        self.multi_subtitle = QLabel()
        self.multi_subtitle.setObjectName("Dim")
        self.multi_subtitle.setWordWrap(True)
        layout.addWidget(self.multi_title)
        layout.addWidget(self.multi_subtitle)
        layout.addStretch(1)

        buttons = QHBoxLayout()
        enable_all = QPushButton(tr("button_enable"))
        enable_all.clicked.connect(lambda: self.enable_toggled.emit(self.mods, True))
        disable_all = QPushButton(tr("button_disable"))
        disable_all.clicked.connect(lambda: self.enable_toggled.emit(self.mods, False))
        remove = QPushButton(tr("button_delete"))
        remove.setObjectName("Danger")
        remove.clicked.connect(lambda: self.delete_requested.emit(self.mods))
        buttons.addWidget(enable_all)
        buttons.addWidget(disable_all)
        buttons.addStretch(1)
        buttons.addWidget(remove)
        layout.addLayout(buttons)
        return page

    def _build_single_page(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        host.setObjectName("ScrollHost")
        scroll.setWidget(host)

        layout = QVBoxLayout(host)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.preview = QLabel()
        self.preview.setObjectName("InspectorPreview")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedHeight(170)
        self.preview.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview.setToolTip(tr("preview_click_hint"))
        self.preview.mousePressEvent = self._on_preview_clicked  # type: ignore[method-assign]
        layout.addWidget(self.preview)

        paste_row = FlowLayout(spacing=6)
        self.paste_button = QPushButton(tr("button_paste_image"))
        self.paste_button.setToolTip(tr("label_paste_hint"))
        self.paste_button.clicked.connect(self._paste_from_clipboard)
        choose_button = QPushButton(tr("button_choose_image"))
        choose_button.clicked.connect(self.choose_preview_file)
        paste_row.addWidget(self.paste_button)
        paste_row.addWidget(choose_button)
        self.gallery_button = QPushButton(tr("button_enabled_gallery"))
        self.gallery_button.clicked.connect(self._open_gallery)
        paste_row.addWidget(self.gallery_button)
        layout.addLayout(paste_row)

        if self.show_character:
            self.character_combo = self._field_combo(layout, tr("label_full_name"))
            self.character_combo.setEditable(False)
            self.character_combo.activated.connect(self._commit_character)

        self.skin_combo = self._field_combo(layout, tr("label_skin"))
        self.skin_combo.setEditable(False)
        self.skin_combo.activated.connect(self._commit_skin)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(tr("label_name"))
        self.name_edit.editingFinished.connect(self._commit_name)
        layout.addWidget(self.name_edit)

        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText(tr("label_author"))
        self.author_edit.editingFinished.connect(self._commit_author)
        layout.addWidget(self._label(tr("label_author")))
        layout.addWidget(self.author_edit)

        source_row = QHBoxLayout()
        source_row.setSpacing(6)
        self.source_edit = QLineEdit()
        self.source_edit.editingFinished.connect(self._commit_source)
        self.open_source_button = icon_button("external", self.theme, tr("button_open_link"))
        self.open_source_button.clicked.connect(self._open_source)
        source_row.addWidget(self.source_edit, 1)
        source_row.addWidget(self.open_source_button)
        layout.addWidget(self._label(tr("label_source")))
        layout.addLayout(source_row)

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText(tr("label_note"))
        self.note_edit.setFixedHeight(84)
        self.note_edit.textChanged.connect(self._schedule_note_save)
        layout.addWidget(self._label(tr("label_note")))
        layout.addWidget(self.note_edit)

        info = Card(object_name="SubtleCard")
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(12, 10, 12, 10)
        info_layout.setSpacing(6)
        self.file_label = QLabel()
        self.file_label.setObjectName("Faint")
        self.file_label.setWordWrap(True)
        self.size_label = QLabel()
        self.size_label.setObjectName("Faint")
        self.state_tag = Tag("", "success")
        state_row = QHBoxLayout()
        state_row.addWidget(self.state_tag)
        state_row.addStretch(1)
        info_layout.addWidget(self.file_label)
        info_layout.addWidget(self.size_label)
        info_layout.addLayout(state_row)
        layout.addWidget(info)

        buttons = FlowLayout(spacing=8)
        self.toggle_button = QPushButton(tr("button_enable"))
        self.toggle_button.setObjectName("Primary")
        self.toggle_button.clicked.connect(self._toggle_enabled)
        self.reveal_button = icon_button("folder", self.theme, tr("button_open_folder"))
        self.reveal_button.clicked.connect(lambda: self.mods and self.reveal_requested.emit(self.mods[0]))
        self.copy_button = icon_button("copy", self.theme, tr("button_copy_path"))
        self.copy_button.clicked.connect(self._copy_path)
        self.delete_button = icon_button("trash", self.theme, tr("button_delete"))
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(self.mods))
        buttons.addWidget(self.toggle_button)
        buttons.addWidget(self.reveal_button)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.delete_button)
        layout.addLayout(buttons)
        layout.addStretch(1)

        self._note_timer = QTimer(self)
        self._note_timer.setSingleShot(True)
        self._note_timer.setInterval(500)
        self._note_timer.timeout.connect(self._commit_note)
        return scroll

    def _label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Faint")
        return label

    def _field_combo(self, layout: QVBoxLayout, label: str) -> QComboBox:
        layout.addWidget(self._label(label))
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(combo)
        return combo

    # ------------------------------------------------------------------- state
    def set_catalog(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self._fill_character_combo()

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.empty.show_state(tr("label_preview"), tr("empty_mods_desc"), icon="eye", theme=theme)
        for button, name in (
            (self.open_source_button, "external"),
            (self.reveal_button, "folder"),
            (self.copy_button, "copy"),
            (self.delete_button, "trash"),
        ):
            button.setIcon(icons.icon(name, theme.text_dim, 18))

    def clear(self) -> None:
        if self._note_timer.isActive():
            self._commit_note()
        self._note_timer.stop()
        self.mods = []
        self.stack.setCurrentWidget(self.empty)

    def set_selection(self, mods: list[Mod]) -> None:
        if self._note_timer.isActive():
            self._commit_note()
        self._note_timer.stop()
        self.mods = list(mods)
        if not mods:
            self.stack.setCurrentWidget(self.empty)
            return
        if len(mods) > 1:
            self.multi_title.setText(f"{len(mods)} {tr('nav_mods')}")
            self.multi_subtitle.setText(tr("warning_select_first"))
            self.stack.setCurrentWidget(self.multi_page)
            return
        self._load(mods[0])
        self.stack.setCurrentWidget(self.single_page)

    def _fill_character_combo(self) -> None:
        combo = self.character_combo
        if combo is None:
            return
        combo.blockSignals(True)
        combo.clear()
        for name in self.catalog.names():
            combo.addItem(character_name(name, self.catalog.get(name).name_en), name)
        if self.mods:
            index = combo.findData(self.mods[0].character)
            combo.setCurrentIndex(max(0, index))
        combo.blockSignals(False)

    def _load(self, mod: Mod) -> None:
        self.skin_combo.blockSignals(True)
        self.skin_combo.clear()
        for skin in skins_for(mod.character):
            self.skin_combo.addItem(skin.name_en if get_language() == "en_US" else skin.name, skin.id)
        self.skin_combo.setCurrentIndex(max(0, self.skin_combo.findData(mod.skin)))
        self.skin_combo.blockSignals(False)
        self.name_edit.blockSignals(True)
        self.author_edit.blockSignals(True)
        self.source_edit.blockSignals(True)
        self.note_edit.blockSignals(True)
        self._fill_character_combo()

        self.name_edit.setText(mod.name)
        self.author_edit.setText(mod.author)
        self.source_edit.setText(mod.source_url)
        self.note_edit.setPlainText(mod.note)

        self._render_preview()
        self.file_label.setText(mod.filename)
        self.file_label.setToolTip(str(mod.enabled_path))
        self.size_label.setText(f"{tr('label_size')}: {human_size(mod.size)}")
        self.state_tag.setText(tr("button_enable") if mod.enabled else tr("button_disable"))
        self.state_tag.setObjectName(Tag.VARIANTS["success" if mod.enabled else ""])
        repolish(self.state_tag)
        self.toggle_button.setText(tr("button_disable") if mod.enabled else tr("button_enable"))
        self.delete_button.setToolTip(tr("button_delete"))

        for widget in (self.name_edit, self.author_edit, self.source_edit, self.note_edit):
            widget.blockSignals(False)

    # ---------------------------------------------------------------- commit
    def _commit_skin(self, index: int) -> None:
        if self.current and self.skin_combo.itemData(index) != self.current.skin:
            self.skin_changed.emit(self.current, self.skin_combo.itemData(index))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        QTimer.singleShot(0, self._render_preview)

    def _render_preview(self) -> None:
        mod = self.current
        if mod is not None:
            self.preview.setPixmap(self.images.preview(mod, QSize(max(1, self.preview.width()), 170), 12))

    @property
    def current(self) -> Mod | None:
        return self.mods[0] if len(self.mods) == 1 else None

    def _commit_name(self) -> None:
        mod = self.current
        if mod is None:
            return
        text = self.name_edit.text().strip()
        if text and text != mod.name:
            mod.name = text
            self.changed.emit(mod)

    def _commit_character(self) -> None:
        mod = self.current
        combo = self.character_combo
        if mod is None or combo is None:
            return
        name = str(combo.currentData() or "")
        if name and name != mod.character:
            self.category_changed.emit(mod, name)

    def _commit_author(self) -> None:
        mod = self.current
        if mod is not None and self.author_edit.text().strip() != mod.author:
            mod.author = self.author_edit.text().strip()
            self.changed.emit(mod)

    def _commit_source(self) -> None:
        mod = self.current
        if mod is not None and self.source_edit.text().strip() != mod.source_url:
            mod.source_url = self.source_edit.text().strip()
            self.changed.emit(mod)

    def _schedule_note_save(self) -> None:
        self._note_timer.start()

    def _commit_note(self) -> None:
        mod = self.current
        if mod is None:
            return
        text = self.note_edit.toPlainText().strip()
        if text != mod.note:
            mod.note = text
            self.changed.emit(mod)

    def _open_source(self) -> None:
        mod = self.current
        if mod is None:
            return
        text = self.source_edit.text().strip() or mod.source_url
        if text:
            shell.open_url(text)

    def _copy_path(self) -> None:
        mod = self.current
        if mod is None:
            return
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(str(mod.enabled_path))

    def _toggle_enabled(self) -> None:
        mod = self.current
        if mod is None:
            return
        self.enable_toggled.emit([mod], not mod.enabled)

    def _on_preview_clicked(self, event) -> None:
        mod = self.current
        if mod is None:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pixmap = QPixmap(mod.preview) if mod.preview else QPixmap()
            if pixmap.isNull():
                self.preview_requested.emit(mod)
                return
            if self._preview_dialog is not None:
                self._preview_dialog.close()
            dialog = ImagePreviewDialog(pixmap, mod.name, self, gallery_available=True)
            dialog.gallery_requested.connect(self._open_gallery)
            self._preview_dialog = dialog
            dialog.finished.connect(lambda _result: self._forget_preview(dialog))
            dialog.show()

    def _forget_preview(self, dialog: ImagePreviewDialog) -> None:
        if self._preview_dialog is dialog:
            self._preview_dialog = None

    def _open_gallery(self) -> None:
        if self._preview_dialog is not None:
            self._preview_dialog.close()
        self.gallery_requested.emit()

    def _paste_from_clipboard(self) -> None:
        """Store a clipboard image as this mod's preview."""
        mod = self.current
        if mod is None:
            return
        path = save_clipboard_image(paths.PREVIEW_DIR, mod.id)
        if not path:
            self.paste_failed.emit()
            return
        self.preview_dropped.emit(mod, path)

    # ------------------------------------------------------------------ drops
    def dragEnterEvent(self, event) -> None:
        if self.current is not None and event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        mod = self.current
        if mod is None:
            return
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
                self.preview_dropped.emit(mod, path)
                event.acceptProposedAction()
                return

    def choose_preview_file(self) -> str:
        mod = self.current
        path, _ = QFileDialog.getOpenFileName(
            self, tr("button_choose_image"), "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path and mod is not None:
            self.preview_dropped.emit(mod, path)
        return path
