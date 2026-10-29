"""Modal dialogs: importing mods and editing character metadata."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..core import paths
from ..core.catalog import Character
from ..core.skins import skins_for
from ..i18n import character_name, element_name, get_language, tr
from .context import AppContext
from .imaging import save_clipboard_image

ROLE_CHOICES = ("dps", "buffer", "support")


def _element_combo(current: str = "") -> QComboBox:
    """Editable combo listing the game's damage types, with their icons."""
    combo = QComboBox()
    combo.setEditable(True)
    combo.addItem(tr("label_none"), "")
    for element in paths.ELEMENTS:
        icon = paths.element_icon(element)
        combo.addItem(QIcon(str(icon)) if icon else QIcon(), element_name(element), element)
    combo.setIconSize(QSize(16, 16))
    index = combo.findData(current)
    combo.setCurrentIndex(index if index >= 0 else 0)
    if index < 0 and current:
        combo.setCurrentText(current)
    return combo


class ImportDialog(QDialog):
    """Collects the details for new mod files.

    The target character is decided by the page that opened the dialog, so it is
    shown for context instead of being an editable field.
    """

    def __init__(
        self,
        ctx: AppContext,
        sources: list[Path],
        character: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.sources = sources
        self.character = character
        self.setWindowTitle(tr("dialog_import_title"))
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        header = QLabel(tr("dialog_import_title"))
        header.setObjectName("SectionTitle")
        known = ctx.catalog.get(character)
        where = character_name(known.name, known.name_en) if known is not None else (character or "-")
        subtitle = QLabel(f"{tr('dialog_import_hint')} · {where}")
        subtitle.setObjectName("Dim")
        subtitle.setWordWrap(True)
        layout.addWidget(header)
        layout.addWidget(subtitle)

        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(110)
        for path in sources:
            self.file_list.addItem(path.name)
        layout.addWidget(QLabel(tr("dialog_import_files")))
        layout.addWidget(self.file_list)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)

        single_file = (len(self.sources) == 1 and self.sources[0].is_file()
                       and self.sources[0].suffix.lower() not in {".zip", ".7z", ".rar"})
        self.name_edit = QLineEdit(self.sources[0].stem if single_file else "")
        self.name_edit.setPlaceholderText(tr("import_name_hint"))
        self.author_edit = QLineEdit()
        self.source_edit = QLineEdit()
        self.note_edit = QTextEdit()
        self.note_edit.setFixedHeight(64)

        self.skin_combo = QComboBox()
        for skin in skins_for(character):
            self.skin_combo.addItem(skin.name_en if get_language() == "en_US" else skin.name, skin.id)
        form.addRow(tr("label_skin"), self.skin_combo)

        form.addRow(tr("label_name"), self.name_edit)
        form.addRow(tr("label_author"), self.author_edit)
        form.addRow(tr("label_source"), self.source_edit)
        form.addRow(tr("label_note"), self.note_edit)
        layout.addLayout(form)

        preview_row = QHBoxLayout()
        self.preview_label = QLabel(tr("label_none"))
        self.preview_label.setObjectName("Faint")
        self.preview_label.setToolTip(tr("label_paste_hint"))
        paste_button = QPushButton(tr("button_paste_image"))
        paste_button.setToolTip(tr("label_paste_hint"))
        paste_button.clicked.connect(self._paste_preview)
        preview_button = QPushButton(tr("button_choose_image"))
        preview_button.clicked.connect(self._choose_preview)
        preview_row.addWidget(self.preview_label, 1)
        preview_row.addWidget(paste_button)
        preview_row.addWidget(preview_button)
        layout.addLayout(preview_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("button_import"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("button_cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.preview_path = ""

    def _choose_preview(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("button_choose_image"), "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self.preview_path = path
            self.preview_label.setText(Path(path).name)

    def _paste_preview(self) -> None:
        path = save_clipboard_image(paths.PREVIEW_DIR, "import")
        if not path:
            self.preview_label.setText(tr("toast_paste_empty"))
            return
        self.preview_path = path
        self.preview_label.setText(Path(path).name)

    # ------------------------------------------------------------------ result
    def values(self) -> dict[str, str]:
        return {
            "name": self.name_edit.text().strip(),
            "skin": self.skin_combo.currentData() or "default",
            "author": self.author_edit.text().strip(),
            "source_url": self.source_edit.text().strip(),
            "note": self.note_edit.toPlainText().strip(),
            "preview": self.preview_path,
        }


class CharacterEditorDialog(QDialog):
    """Edit the metadata of a bundled character.

    The full name is a stable database key mapped to an English directory, so
    it stays locked once a character exists.
    """

    def __init__(self, ctx: AppContext, character: Character | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.character = character
        self.setWindowTitle(tr("dialog_character_edit") if character else tr("dialog_character_new"))
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        hint = QLabel(tr("dialog_character_hint"))
        hint.setObjectName("Dim")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(8)
        self.name_edit = QLineEdit(character.name if character else "")
        self.name_edit.setPlaceholderText(tr("dialog_character_name_hint"))
        if character is not None:
            # The name is the roster key and the on-disk folder, so it may not
            # be renamed once the character exists.
            self.name_edit.setReadOnly(True)
            self.name_edit.setToolTip(tr("dialog_character_name_locked"))
        self.name_en_edit = QLineEdit(character.name_en if character else "")
        self.name_en_edit.setPlaceholderText("Lyfe")
        self.element_combo = _element_combo(character.element if character else "")
        self.role_combo = QComboBox()
        self.role_combo.setEditable(True)
        self.role_combo.addItem(tr("label_none"), "")
        for key in ROLE_CHOICES:
            self.role_combo.addItem(tr(f"role_{key}"), key)
        role_index = self.role_combo.findData(character.role if character else "")
        self.role_combo.setCurrentIndex(max(0, role_index))

        form.addRow(tr("label_full_name"), self.name_edit)
        form.addRow("English", self.name_en_edit)
        form.addRow(tr("label_element"), self.element_combo)
        form.addRow(tr("label_role"), self.role_combo)
        layout.addLayout(form)

        portrait_row = QHBoxLayout()
        existing = Path(character.portrait).name if character and character.portrait else ""
        self.portrait_label = QLabel(existing or tr("label_none"))
        self.portrait_label.setObjectName("Faint")
        portrait_button = QPushButton(tr("button_choose_image"))
        portrait_button.clicked.connect(self._choose_portrait)
        portrait_row.addWidget(self.portrait_label, 1)
        portrait_row.addWidget(portrait_button)
        layout.addLayout(portrait_row)
        self.portrait_path = character.portrait if character else ""

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("button_save"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("button_cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _choose_portrait(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("button_choose_image"), "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self.portrait_path = path
            self.portrait_label.setText(Path(path).name)

    def _current(self, combo: QComboBox) -> str:
        """The stored value of an editable combo (``itemData`` or free text)."""
        index = combo.currentIndex()
        if index >= 0 and combo.currentText() == combo.itemText(index):
            return str(combo.itemData(index) or "")
        return combo.currentText().strip()

    # ------------------------------------------------------------------ result
    def payload(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "name_en": self.name_en_edit.text().strip(),
            "element": self._current(self.element_combo),
            "role": self._current(self.role_combo),
            "portrait": self.portrait_path,
        }
