"""Application shell: sidebar navigation, top bar, page stack and toasts."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..core import migrate, paths, shell
from ..i18n import character_name, set_language, tr
from . import icons
from . import theme as theme_module
from .context import AppContext
from .dialogs import ImportDialog
from .pages import (
    CharacterDetailPage,
    CharactersPage,
    IssuesPage,
    ModsPage,
    SettingsPage,
)
from .widgets.cards import ROLE_KEYS, role_label
from .widgets.common import SearchBox, ToastHost

NAV_ITEMS = (
    ("characters", "grid"),
    ("mods", "list"),
    ("issues", "shield"),
    ("settings", "gear"),
)


class MainWindow(QMainWindow):
    """Top level window; owns navigation and the shared application context."""

    data_changed = Signal()

    def __init__(self, ctx: AppContext) -> None:
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle(f"{tr('app_title')} · v{__version__}")
        self.setMinimumSize(QSize(880, 560))
        self.setAcceptDrops(True)
        self._restore_geometry()
        icon_path = paths.asset("icons", "app.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        root = QWidget()
        root.setObjectName("Root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_sidebar())

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(self._build_topbar())
        self.stack = QStackedWidget()
        right_layout.addWidget(self.stack, 1)
        layout.addWidget(right, 1)
        self.setCentralWidget(root)

        self.toast_host = ToastHost(root, ctx.theme)
        ctx.toast = self.toast_host
        self._create_pages()
        self.refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        self.refresh_shortcut.activated.connect(self.repair_and_refresh)
        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self._focus_search)
        self.apply_theme()
        self._navigate(self.ctx.settings.last_page if self.ctx.settings.last_page in dict(NAV_ITEMS) else "characters")

        if not self.ctx.settings.storage_path:
            self._navigate("settings")
            self.toast_host.show_message(tr("warning_storage_missing_desc"), "warning")
        elif getattr(self.ctx.manager, "compatibility_errors", []):
            self.toast_host.show_message(self.ctx.manager.compatibility_errors[0], "warning")
        elif migrate.legacy_available() and not self.ctx.store.mods:
            self.toast_host.show_message(tr("button_migrate"), "info")

    # ------------------------------------------------------------------ chrome
    def open_gallery(self) -> None:
        page = self.stack.currentWidget()
        if page not in (self.detail_page, self.mods_page):
            self._navigate("mods")
            page = self.mods_page
        page.show_gallery()

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(224)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 18, 14, 16)
        layout.setSpacing(6)

        header = QWidget()
        header.setObjectName("SidebarHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(6, 0, 0, 10)
        header_layout.setSpacing(10)
        self.brand_icon = QLabel()
        self.brand_icon.setFixedSize(36, 36)
        self.brand_icon.setPixmap(QIcon(str(paths.asset("icons", "app.ico"))).pixmap(36, 36))
        header_layout.addWidget(self.brand_icon)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(2)
        self.app_name_label = QLabel("SnowMM")
        self.app_name_label.setObjectName("AppName")
        self.app_tagline_label = QLabel(tr("app_tagline"))
        self.app_tagline_label.setObjectName("AppTagline")
        brand_text.addWidget(self.app_name_label)
        brand_text.addWidget(self.app_tagline_label)
        header_layout.addLayout(brand_text)
        layout.addWidget(header)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, _glyph in NAV_ITEMS:
            button = QPushButton(tr(f"nav_{key}"))
            button.setObjectName("NavItem")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIconSize(QSize(18, 18))
            button.clicked.connect(lambda _checked=False, page=key: self._navigate(page))
            self.nav_group.addButton(button)
            self.nav_buttons[key] = button
            layout.addWidget(button)

        layout.addStretch(1)
        self.theme_button = QPushButton(tr("button_toggle_theme"))
        self.theme_button.setObjectName("Ghost")
        self.theme_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_button.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_button)

        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setObjectName("Faint")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.version_label)
        return sidebar

    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("Card")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(12)

        titles = QVBoxLayout()
        titles.setSpacing(0)
        self.page_title = QLabel()
        self.page_title.setObjectName("PageTitle")
        self.page_subtitle = QLabel()
        self.page_subtitle.setObjectName("PageSubtitle")
        titles.addWidget(self.page_title)
        titles.addWidget(self.page_subtitle)
        layout.addLayout(titles)
        layout.addStretch(1)

        self.search_box = SearchBox(tr("search_mods"), self.ctx.theme)
        self.search_box.textChanged.connect(self._on_search)
        # Flexible, so the bar keeps fitting when the window gets narrow.
        self.search_box.setMinimumWidth(160)
        self.search_box.setMaximumWidth(360)

        self.refresh_button = QPushButton(tr("button_refresh"))
        self.refresh_button.clicked.connect(self.repair_and_refresh)
        self.launch_button = QPushButton(tr("button_launch"))
        self.launch_button.setObjectName("Primary")
        self.launch_button.clicked.connect(self.launch_game)
        self.folder_button = QPushButton(tr("button_open_folder"))
        self.folder_button.clicked.connect(self.open_mods_folder)

        layout.addWidget(self.search_box, 1)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.folder_button)
        layout.addWidget(self.launch_button)
        return bar

    # ------------------------------------------------------------------- pages
    def _flush_notes(self) -> None:
        for name in ("mods_page", "detail_page"):
            page = getattr(self, name, None)
            if page is not None and page.inspector._note_timer.isActive():
                page.inspector._commit_note()
                page.inspector._note_timer.stop()

    def _create_pages(self) -> None:
        self._flush_notes()
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
            widget.deleteLater()

        self.characters_page = CharactersPage(self.ctx)
        self.characters_page.open_character.connect(self.open_character)
        self.characters_page.changed.connect(self.refresh_all)

        self.mods_page = ModsPage(self.ctx)
        self.mods_page.changed.connect(self.refresh_all)

        self.issues_page = IssuesPage(self.ctx)
        self.issues_page.changed.connect(self.refresh_all)

        self.settings_page = SettingsPage(self.ctx)
        self.settings_page.paths_changed.connect(self.refresh_all)
        self.settings_page.theme_changed.connect(self.apply_theme)
        self.settings_page.language_changed.connect(self.change_language)

        self.detail_page = CharacterDetailPage(self.ctx)
        self.detail_page.back_requested.connect(lambda: self._navigate("characters"))
        self.detail_page.changed.connect(self.refresh_all)
        self.detail_page.add_mod_requested.connect(self.import_dialog)
        self.detail_page.add_folder_requested.connect(self.import_folder)
        self.detail_page.navigate_requested.connect(self.open_character)

        self.pages = {
            "characters": self.characters_page,
            "mods": self.mods_page,
            "issues": self.issues_page,
            "settings": self.settings_page,
        }
        for page in list(self.pages.values()) + [self.detail_page]:
            self.stack.addWidget(page)

    def _navigate(self, key: str) -> None:
        page = self.pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        button = self.nav_buttons.get(key)
        if button is not None:
            button.setChecked(True)
        self.page_title.setText(tr(page.title_key) if page.title_key else "")
        self.page_subtitle.setText(tr(page.subtitle_key) if page.subtitle_key else "")
        self.search_box.setPlaceholderText(tr("search_characters") if key == "characters" else tr("search_mods"))
        self.search_box.setEnabled(key in {"characters", "mods"})
        self.search_box.blockSignals(True)
        self.search_box.clear()
        self.search_box.blockSignals(False)
        page.set_search("")
        page.refresh()
        self.ctx.settings.last_page = key
        self.ctx.settings.save()
        self._apply_compact_layout()

    def open_character(self, name: str) -> None:
        character = self.ctx.catalog.get(name)
        if character is None:
            # The roster is fixed, so a name outside it has no page.
            return
        self.stack.setCurrentWidget(self.detail_page)
        self.detail_page.show_character(name)
        subtitle = character.subtitle
        self.page_title.setText(character_name(character.name, character.name_en))
        self.page_subtitle.setText(
            role_label(subtitle) if subtitle in ROLE_KEYS else subtitle or tr("label_mods")
        )
        self.search_box.setEnabled(False)
        self._apply_compact_layout()

    # ------------------------------------------------------------- responsive
    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_compact_layout()

    def _apply_compact_layout(self) -> None:
        """Drop secondary chrome before it starts to clip on a narrow window."""
        compact = self.width() < 1040
        self.search_box.setMinimumWidth(140 if compact else 160)
        self.folder_button.setVisible(not compact)
        self.page_subtitle.setVisible(not compact and bool(self.page_subtitle.text()))

    # ---------------------------------------------------------------- searching
    def _focus_search(self) -> None:
        if self.search_box.isEnabled():
            self.search_box.setFocus()
            self.search_box.selectAll()

    def _on_search(self, text: str) -> None:
        page = self.stack.currentWidget()
        if hasattr(page, "set_search"):
            page.set_search(text)

    # ------------------------------------------------------------------ actions
    def repair_and_refresh(self) -> None:
        _changed, errors = self.ctx.manager.repair_legacy_layout(self.ctx.known_characters())
        if errors:
            self.toast_host.show_message(errors[0], "warning")
        self.refresh_all()

    def refresh_all(self) -> None:
        self.ctx.manager.refresh_states()
        # The art library can change on disk (or in the settings) at any moment,
        # so rebuild the catalog from it and merge the user's own entries on top.
        self.ctx.catalog.reload(
            self.ctx.store.characters, paths.resolve_art_dir()
        )
        self.ctx.store.save()
        current = self.stack.currentWidget()
        for page in list(self.pages.values()) + [self.detail_page]:
            if page is not current:
                page.refresh()
        if hasattr(current, "refresh"):
            current.refresh()
        self.toast_host.set_theme(self.ctx.theme)

    def toggle_theme(self) -> None:
        order = ["dark", "light", "system"]
        try:
            index = order.index(self.ctx.settings.theme)
        except ValueError:
            index = 0
        self.ctx.settings.theme = order[(index + 1) % len(order)]
        self.ctx.settings.save()
        self.apply_theme()

    def apply_theme(self) -> None:
        dark = True
        try:
            scheme = QGuiApplication.styleHints().colorScheme()
            dark = scheme == Qt.ColorScheme.Dark
        except AttributeError:
            dark = True
        theme = theme_module.resolve(self.ctx.settings.theme, dark)
        self.ctx.theme = theme
        self.ctx.images.set_dark(theme.name == "dark")
        self.ctx.images.clear()
        application = QApplication.instance()
        if application is not None:
            application.setStyleSheet(
                theme_module.stylesheet(theme, icons.write_check_mark(paths.BASE_DIR))
            )
        for page in list(self.pages.values()) + [self.detail_page]:
            page.apply_theme(self.ctx)
        self.search_box.apply_theme(theme)
        self._recolor()
        self.toast_host.set_theme(theme)

    def _recolor(self) -> None:
        theme = self.ctx.theme
        muted = theme.text_dim
        for key, glyph in NAV_ITEMS:
            button = self.nav_buttons.get(key)
            if button is not None:
                button.setIcon(icons.icon(glyph, muted, 18))
        self.theme_button.setIcon(icons.icon("moon" if theme.name == "dark" else "sun", muted, 16))
        self.refresh_button.setIcon(icons.icon("refresh", muted, 16))
        self.launch_button.setIcon(icons.icon("play", theme.accent_text, 14, filled=True))
        self.folder_button.setIcon(icons.icon("folder", muted, 16))

    def change_language(self) -> None:
        set_language(self.ctx.settings.language)
        self.setWindowTitle(f"{tr('app_title')} · v{__version__}")
        self.app_tagline_label.setText(tr("app_tagline"))
        for key, _glyph in NAV_ITEMS:
            self.nav_buttons[key].setText(tr(f"nav_{key}"))
        self.theme_button.setText(tr("button_toggle_theme"))
        self.refresh_button.setText(tr("button_refresh"))
        self.launch_button.setText(tr("button_launch"))
        self.folder_button.setText(tr("button_open_folder"))
        self._create_pages()
        self.apply_theme()
        self._navigate(self.ctx.settings.last_page)

    def open_mods_folder(self) -> None:
        if not self.ctx.settings.storage_path:
            self.toast_host.show_message(tr("warning_storage_missing_desc"), "warning")
            return
        shell.open_path(self.ctx.settings.storage_path)

    def launch_game(self) -> None:
        executable = self.ctx.settings.game_exe
        if not executable:
            self.toast_host.show_message(tr("warning_launch_missing_desc"), "warning")
            self._navigate("settings")
            return
        error = shell.launch_executable(executable, self.ctx.settings.game_args)
        if error:
            self.toast_host.show_message(error, "warning")

    # ------------------------------------------------------------------- import
    def import_folder(self, character: str) -> None:
        folder = QFileDialog.getExistingDirectory(self, tr("button_import_folder"))
        if folder:
            self.import_dialog(character, [Path(folder)])

    def import_dialog(self, character: str = "", sources: list[Path] | None = None) -> None:
        """Ask for the mod details and copy the files into ``character``."""
        if not self.ctx.settings.storage_path:
            self.toast_host.show_message(tr("warning_storage_missing_desc"), "warning")
            self._navigate("settings")
            return
        if not character or character not in self.ctx.known_characters():
            # Importing always happens from a character page, so the target is
            # always known - a stray drop must not invent a new character.
            self.toast_host.show_message(tr("warning_pick_character_first"), "warning")
            return
        if sources is None:
            files, _ = QFileDialog.getOpenFileNames(
                self,
                tr("dialog_import_title"),
                "",
                "Mods (*.pak *.utoc *.ucas *.sig *.zip *.7z *.rar);;All files (*.*)",
            )
            sources = [Path(item) for item in files]
        if not sources:
            return
        dialog = ImportDialog(self.ctx, sources, character=character, parent=self)
        if self.detail_page.character_name == character:
            dialog.skin_combo.setCurrentIndex(max(0, dialog.skin_combo.findData(self.detail_page.selected_skin)))
        if dialog.exec() != ImportDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = self.ctx.manager.import_paths(
                sources,
                character=character,
                skin=values["skin"],
                name=values["name"],
                author=values["author"],
                source_url=values["source_url"],
                note=values["note"],
            )
        finally:
            QApplication.restoreOverrideCursor()
        if values["preview"] and result.added:
            for mod in result.added:
                try:
                    self.ctx.manager.set_preview(mod, Path(values["preview"]))
                except OSError:
                    break
        self.ctx.store.save()
        self.refresh_all()
        if result.errors:
            self.toast_host.show_message(self._describe_import_error(result.errors[0]), "warning")
        elif result.added:
            self.toast_host.show_message(tr("toast_imported", count=len(result.added)))
        else:
            self.toast_host.show_message(tr("toast_import_empty"), "warning")

    @staticmethod
    def _describe_import_error(error: str) -> str:
        """Turn a manager error code into a readable, translated message."""
        return tr("warning_import_failed", detail=error)

    # -------------------------------------------------------------------- drops
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        sources = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.toLocalFile()]
        if sources:
            event.acceptProposedAction()
            # A drop only makes sense with a target character, which is exactly
            # what the character page provides.
            character = self.detail_page.character_name if self.stack.currentWidget() is self.detail_page else ""
            self.import_dialog(character=character, sources=sources)

    # ------------------------------------------------------------------ window
    def _restore_geometry(self) -> None:
        stored = self.ctx.settings.window_geometry
        if stored:
            try:
                self.restoreGeometry(QByteArray.fromBase64(stored.encode("ascii")))
                return
            except (ValueError, TypeError):
                pass
        self.resize(1280, 820)

    def closeEvent(self, event) -> None:
        self._flush_notes()
        self.ctx.settings.window_geometry = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.ctx.store.save()
        self.ctx.settings.save()
        super().closeEvent(event)
