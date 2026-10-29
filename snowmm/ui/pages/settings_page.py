"""Settings: paths, appearance, behaviour and data maintenance."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ... import __version__
from ...core import migrate, paths, shell
from ...core.settings import THEME_DARK, THEME_LIGHT, THEME_SYSTEM
from ...i18n import LANGUAGE_LABELS, tr
from ..widgets.common import Card, Divider, FlowLayout
from .base import Page

REPO_URL = "https://github.com/theresa-2333/Snowbreak_Mod_Manager"


class SettingsPage(Page):
    title_key = "nav_settings"
    subtitle_key = "page_settings_sub"

    paths_changed = Signal()
    theme_changed = Signal()
    language_changed = Signal()

    def __init__(self, ctx, parent: QWidget | None = None) -> None:
        super().__init__(ctx, parent)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("ScrollHost")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(16)

        layout.addWidget(self._build_paths())
        layout.addWidget(self._build_appearance())
        layout.addWidget(self._build_behaviour())
        layout.addWidget(self._build_data())
        layout.addWidget(self._build_about())
        layout.addStretch(1)
        scroll.setWidget(container)
        self.root.addWidget(scroll, 1)

    # -------------------------------------------------------------- sections
    @staticmethod
    def _section(title: str) -> tuple[Card, QVBoxLayout]:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        label = QLabel(title.upper())
        label.setObjectName("Faint")
        layout.addWidget(label)
        layout.addWidget(Divider())
        return card, layout

    def _build_paths(self) -> Card:
        card, layout = self._section(tr("nav_settings"))

        layout.addWidget(self._label(tr("label_settings_storage")))
        row = QHBoxLayout()
        self.storage_edit = QLineEdit(self.ctx.settings.storage_path)
        self.storage_edit.setPlaceholderText(tr("settings_storage_hint"))
        self.storage_edit.editingFinished.connect(self._apply_storage)
        browse = QPushButton(tr("button_browse"))
        browse.clicked.connect(self._browse_storage)
        open_button = QPushButton(tr("button_open_folder"))
        open_button.clicked.connect(lambda: shell.open_path(self.ctx.settings.storage_path))
        row.addWidget(self.storage_edit, 1)
        row.addWidget(browse)
        row.addWidget(open_button)
        layout.addLayout(row)
        hint = QLabel(tr("settings_storage_hint"))
        hint.setObjectName("Faint")
        layout.addWidget(hint)

        layout.addWidget(self._label(tr("label_settings_game")))
        game_row = QHBoxLayout()
        self.game_edit = QLineEdit(self.ctx.settings.game_exe)
        self.game_edit.setPlaceholderText(tr("settings_game_hint"))
        self.game_edit.editingFinished.connect(self._apply_game)
        game_browse = QPushButton(tr("button_browse"))
        game_browse.clicked.connect(self._browse_game)
        game_row.addWidget(self.game_edit, 1)
        game_row.addWidget(game_browse)
        layout.addLayout(game_row)
        game_hint = QLabel(tr("settings_game_hint"))
        game_hint.setObjectName("Faint")
        layout.addWidget(game_hint)

        layout.addWidget(self._label(tr("label_settings_art")))
        art_hint = QLabel(tr("settings_art_hint", count=len(self.ctx.catalog)))
        art_hint.setObjectName("Faint")
        art_hint.setWordWrap(True)
        layout.addWidget(art_hint)
        art_row = QHBoxLayout()
        art_open = QPushButton(tr("button_open_folder"))
        art_open.clicked.connect(lambda: shell.open_path(str(paths.ART_DIR)))
        art_row.addWidget(art_open)
        art_row.addStretch(1)
        layout.addLayout(art_row)
        return card

    def _build_appearance(self) -> Card:
        card, layout = self._section(tr("label_theme"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        grid.addWidget(self._label(tr("label_theme")), 0, 0)
        self.theme_combo = QComboBox()
        for key, label in (
            (THEME_SYSTEM, tr("settings_theme_system")),
            (THEME_LIGHT, tr("settings_theme_light")),
            (THEME_DARK, tr("settings_theme_dark")),
        ):
            self.theme_combo.addItem(label, key)
        index = self.theme_combo.findData(self.ctx.settings.theme)
        self.theme_combo.setCurrentIndex(max(0, index))
        self.theme_combo.currentIndexChanged.connect(self._apply_theme)
        self.theme_combo.setFixedWidth(200)
        grid.addWidget(self.theme_combo, 0, 1)

        grid.addWidget(self._label(tr("label_language")), 1, 0)
        self.language_combo = QComboBox()
        for key, label in LANGUAGE_LABELS.items():
            self.language_combo.addItem(label, key)
        language_index = self.language_combo.findData(self.ctx.settings.language)
        self.language_combo.setCurrentIndex(max(0, language_index))
        self.language_combo.currentIndexChanged.connect(self._apply_language)
        self.language_combo.setFixedWidth(200)
        grid.addWidget(self.language_combo, 1, 1)
        grid.addWidget(self._label(tr("settings_language_hint")), 1, 2)
        grid.setColumnStretch(2, 1)
        layout.addLayout(grid)
        return card

    def _build_behaviour(self) -> Card:
        card, layout = self._section(tr("label_behavior"))
        self.hide_empty_check = QCheckBox(tr("settings_hide_empty"))
        self.hide_empty_check.setChecked(self.ctx.settings.hide_empty_characters)
        self.hide_empty_check.toggled.connect(self._apply_checkboxes)
        self.confirm_check = QCheckBox(tr("settings_confirm_delete"))
        self.confirm_check.setChecked(self.ctx.settings.confirm_delete)
        self.confirm_check.toggled.connect(self._apply_checkboxes)
        for widget in (self.hide_empty_check, self.confirm_check):
            layout.addWidget(widget)
        return card

    def _build_data(self) -> Card:
        card, layout = self._section(tr("label_data"))
        self.data_hint = QLabel(tr("settings_data_hint", path=paths.BASE_DIR))
        self.data_hint.setObjectName("Faint")
        self.data_hint.setWordWrap(True)
        layout.addWidget(self.data_hint)

        row = FlowLayout(spacing=8)
        open_data = QPushButton(tr("settings_open_data"))
        open_data.clicked.connect(lambda: shell.open_path(paths.BASE_DIR))
        rescan = QPushButton(tr("button_rescan"))
        rescan.setToolTip(tr("settings_rescan_hint"))
        rescan.clicked.connect(self._rescan)
        backup = QPushButton(tr("button_backup"))
        backup.clicked.connect(self._backup)
        migrate_button = QPushButton(tr("button_migrate"))
        migrate_button.setToolTip(tr("settings_migrate_hint"))
        migrate_button.clicked.connect(self._migrate)
        flatten = QPushButton(tr("button_flatten"))
        flatten.setToolTip(tr("settings_flatten_hint"))
        flatten.clicked.connect(self._flatten)
        normalize = QPushButton(tr("button_normalize"))
        normalize.clicked.connect(self._normalize)
        for widget in (open_data, rescan, backup, migrate_button, flatten, normalize):
            row.addWidget(widget)
        layout.addLayout(row)
        return card

    def _build_about(self) -> Card:
        card, layout = self._section(tr("label_about"))
        title = QLabel("SnowMM")
        title.setObjectName("CardTitle")
        body = QLabel(tr("dialog_about_body"))
        body.setWordWrap(True)
        credit = QLabel(tr("settings_about_body", version=__version__))
        credit.setObjectName("Faint")
        link = QPushButton(tr("button_open_link"))
        link.clicked.connect(lambda: shell.open_url(REPO_URL))
        row = QHBoxLayout()
        row.addWidget(link)
        row.addStretch(1)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(credit)
        layout.addLayout(row)
        return card

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Dim")
        return label

    # ---------------------------------------------------------------- actions
    def _browse_storage(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, tr("label_settings_storage"), self.storage_edit.text())
        if directory:
            self.storage_edit.setText(directory)
            self._apply_storage()

    def _browse_game(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("label_settings_game"), "", "Executables (*.exe)")
        if path:
            self.game_edit.setText(path)
            self._apply_game()

    def _apply_storage(self) -> None:
        text = self.storage_edit.text().strip()
        if text == self.ctx.settings.storage_path:
            return
        self.ctx.settings.storage_path = text
        self.ctx.settings.save()
        _changed, errors = self.ctx.manager.repair_legacy_layout(self.ctx.known_characters())
        if errors:
            self.ctx.toast and self.ctx.toast.show_message(errors[0], "warning")
        self.paths_changed.emit()

    def _apply_game(self) -> None:
        self.ctx.settings.game_exe = self.game_edit.text().strip()
        self.ctx.settings.save()

    def _apply_theme(self) -> None:
        self.ctx.settings.theme = self.theme_combo.currentData()
        self.ctx.settings.save()
        self.theme_changed.emit()

    def _apply_language(self) -> None:
        self.ctx.settings.language = self.language_combo.currentData()
        self.ctx.settings.save()
        self.language_changed.emit()

    def _apply_checkboxes(self) -> None:
        self.ctx.settings.hide_empty_characters = self.hide_empty_check.isChecked()
        self.ctx.settings.confirm_delete = self.confirm_check.isChecked()
        self.ctx.settings.save()
        self.paths_changed.emit()

    def _rescan(self) -> None:
        _changed, errors = self.ctx.manager.repair_legacy_layout(self.ctx.known_characters())
        adopted = self.ctx.manager.scan_storage(known_characters=self.ctx.known_characters())
        message = tr("toast_scan_done", count=len(adopted)) if adopted else tr("toast_scan_none")
        if self.ctx.toast:
            self.ctx.toast.show_message(errors[0] if errors else message, "warning" if errors else "check")
        self.paths_changed.emit()

    def _normalize(self) -> None:
        try:
            changed, errors = self.ctx.manager.repair_legacy_layout(self.ctx.known_characters())
        except OSError as error:
            changed, errors = 0, [str(error)]
        message = tr("toast_normalized", count=changed)
        if errors:
            message += f" - {errors[0]}"
        self.ctx.toast and self.ctx.toast.show_message(message, "warning" if errors else "check")
        self.paths_changed.emit()

    def _backup(self) -> None:
        paths.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = paths.BACKUP_DIR / f"data-{stamp}.json"
        self.ctx.store.save()
        try:
            self.ctx.store.backup(target)
        except OSError as error:
            self.ctx.toast and self.ctx.toast.show_message(str(error), "warning")
            return
        self.ctx.toast and self.ctx.toast.show_message(tr("toast_backup_done", path=str(target)))

    def _migrate(self) -> None:
        imported, warnings = migrate.migrate(self.ctx.store, self.ctx.settings)
        if imported:
            message = tr("toast_migrated", count=imported)
        else:
            message = warnings[0] if warnings else tr("toast_scan_none")
        self.ctx.toast and self.ctx.toast.show_message(message)
        self.paths_changed.emit()

    def _flatten(self) -> None:
        directory = self.ctx.settings.storage_dir
        if directory is None:
            self.ctx.toast and self.ctx.toast.show_message(tr("warning_storage_missing_desc"), "warning")
            return
        moved, warnings = self.ctx.manager.repair_legacy_layout(self.ctx.known_characters())
        message = tr("toast_flattened", count=moved) if moved else tr("toast_flatten_none")
        if warnings and len(warnings) <= 3:
            message = f"{message} - {'; '.join(warnings)}"
        self.ctx.toast and self.ctx.toast.show_message(message, "warning" if warnings else "check")
        self.paths_changed.emit()

    def refresh(self) -> None:
        self.storage_edit.setText(self.ctx.settings.storage_path)
        self.game_edit.setText(self.ctx.settings.game_exe)
        self.data_hint.setText(tr("settings_data_hint", path=paths.BASE_DIR))
