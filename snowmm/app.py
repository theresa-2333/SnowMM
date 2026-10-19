"""Application bootstrap: wires the core services to the Qt user interface."""

from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from . import APP_TITLE, __version__
from .core import paths
from .core.catalog import Catalog
from .core.manager import ModManager
from .core.migrate import legacy_available, migrate
from .core.settings import Settings
from .core.store import Store
from .i18n import set_language
from .ui import theme as theme_module
from .ui.context import AppContext
from .ui.imaging import ImageCache
from .ui.main_window import MainWindow
from .ui.widgets.common import WheelGuard


def system_prefers_dark() -> bool:
    try:
        scheme = QGuiApplication.styleHints().colorScheme()
        return scheme == Qt.ColorScheme.Dark
    except AttributeError:
        return True


def build_context() -> AppContext:
    """Load settings, database and catalog, then package them in a context."""
    paths.ensure_dirs()
    settings = Settings.load()
    set_language(settings.language)

    store = Store().load()
    if legacy_available() and not store.mods:
        # First run after upgrading from 0.2.x: pull in the existing collection.
        migrate(store, settings)
    manager = ModManager(store, settings)
    catalog = Catalog.load(store.characters, art_dir=paths.resolve_art_dir())
    images = ImageCache(dark=system_prefers_dark())
    theme = theme_module.resolve(settings.theme, system_prefers_dark())
    return AppContext(
        settings=settings,
        store=store,
        manager=manager,
        catalog=catalog,
        images=images,
        theme=theme,
    )


def create_application(argv: list[str] | None = None) -> tuple[QApplication, MainWindow]:
    if os.name == "nt":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("theresa2333.SnowMM")
    QApplication.setApplicationName("SnowMM")
    QApplication.setApplicationVersion(__version__)
    QApplication.setApplicationDisplayName(APP_TITLE)
    QApplication.setDesktopFileName("SnowMM")
    QApplication.setStyle("Fusion")
    application = QApplication(argv if argv is not None else sys.argv)
    application.setWindowIcon(QIcon(str(paths.asset("icons", "app.ico"))))
    guard = WheelGuard(application)
    application.installEventFilter(guard)
    context = build_context()
    window = MainWindow(context)
    return application, window


def main(argv: list[str] | None = None) -> int:
    arguments = argv if argv is not None else sys.argv
    application, window = create_application(argv)
    if "--self-test" in arguments:
        import json
        from pathlib import Path

        from PySide6.QtGui import QPixmap

        from .i18n import character_name

        report_path = Path(arguments[arguments.index("--self-test") + 1])
        report = {"version": __version__, "portraits": len(window.ctx.catalog), "ok": False}
        try:
            assert len(window.ctx.catalog) == 54
            assert not window.windowIcon().isNull()
            for character in window.ctx.catalog:
                assert not QPixmap(character.portrait).isNull(), character.name
                assert character.name_en, character.name
            window.ctx.settings.language = "en_US"
            window.change_language()
            assert character_name("里芙-狂猎") == "Lyfe · Wild Hunt"
            for page in ("characters", "mods", "issues", "settings"):
                window._navigate(page)
                application.processEvents()
            report["ok"] = True
        except Exception as error:
            report["error"] = str(error)
        finally:
            window.close()
            application.quit()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if report["ok"] else 1
    window.show()
    return application.exec()
