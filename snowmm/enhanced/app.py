"""Bootstrap the upstream Qt UI with the folder library adapter."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from ..core import paths
from ..core.catalog import Catalog
from ..i18n import set_language
from ..ui import theme as theme_module
from ..ui.context import AppContext
from ..ui.imaging import ImageCache
from ..ui.widgets.common import WheelGuard
from . import VERSION
from .library import LibraryManager
from .storage import EnhancedSettings, LibraryStore
from .window import EnhancedWindow


def portable_root():
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parents[2]


def create_application(argv=None):
    arguments = argv if argv is not None else sys.argv
    if "--enhanced-home" in arguments and "--self-test" not in arguments:
        index = arguments.index("--enhanced-home") + 1
        if index >= len(arguments) or not arguments[index]:
            raise ValueError("--enhanced-home 后需要便携设置目录")
        os.environ["SNOWMM_ENHANCED_HOME"] = arguments[index]
    home = Path(os.environ.get("SNOWMM_ENHANCED_HOME", str(portable_root() / "data")))
    home.mkdir(parents=True, exist_ok=True)
    # Repoint only this process's upstream preview caches and save locations.
    paths.BASE_DIR = home
    paths.DATA_FILE, paths.SETTINGS_FILE = home / "index.json", home / "settings.json"
    paths.IMAGES_DIR, paths.BACKUP_DIR = home / "images", home / "backups"
    paths.PREVIEW_DIR, paths.PORTRAIT_DIR = home / "images/mods", home / "images/portraits"
    paths.ensure_dirs()
    settings = EnhancedSettings.load_portable(home)
    bundled_tool = portable_root() / "repair-engine"
    if bundled_tool.is_dir() and settings.bundled_repair:
        settings.repair_tool = str(bundled_tool)
    bundled_python = portable_root() / "repair-runtime/python.exe"
    if settings.bundled_repair and bundled_python.is_file():
        settings.repair_python = str(bundled_python)
    elif not settings.repair_python:
        settings.repair_python = "" if getattr(sys, "frozen", False) else sys.executable
    set_language(settings.language)
    store = LibraryStore(Path(settings.storage_path), home).load()
    manager = LibraryManager(store, settings)
    manager.refresh_states()
    application = QApplication(argv if argv is not None else sys.argv)
    if os.name == "nt" and "Microsoft YaHei" not in QFontDatabase.families():
        for name in ("msyh.ttc", "msyhbd.ttc"):
            font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
            if font.exists():
                QFontDatabase.addApplicationFont(str(font))
    application.setFont(QFont("Microsoft YaHei UI", 10))
    application.setApplicationName("SnowMMEnhanced")
    application.setApplicationDisplayName("SnowMM增强版")
    application.setApplicationVersion(VERSION)
    application.setStyle("Fusion")
    application.setWindowIcon(QIcon(str(paths.asset("icons", "app.ico"))))
    application._wheel_guard = WheelGuard(application)
    application.installEventFilter(application._wheel_guard)
    from ..app import system_prefers_dark

    theme = theme_module.resolve(settings.theme, system_prefers_dark())
    ctx = AppContext(
        settings, store, manager, Catalog.load(store.characters), ImageCache(dark=theme.name == "dark"), theme
    )
    window = EnhancedWindow(ctx)
    return application, window


def main(argv=None):
    arguments = argv or sys.argv
    isolated = None
    if "--self-test" in arguments:
        import tempfile

        from .storage import atomic_json

        isolated = tempfile.TemporaryDirectory(prefix="snowmm-self-test-")
        home = Path(isolated.name)
        os.environ["SNOWMM_ENHANCED_HOME"] = str(home)
        os.environ["SNOWMM_TEST_NO_HOTKEY"] = "1"
        atomic_json(
            home / "settings.json", {"storage_path": str(home / "library"), "deploy_path": str(home / "game/~SnowMM")}
        )
    application, window = create_application(arguments)
    if "--self-test" in arguments:
        output = Path(arguments[arguments.index("--self-test") + 1])
        report = {"version": VERSION, "ok": False}
        try:
            for page in ("library", "characters", "mods", "issues", "settings", "category:基地", "category:杂项"):
                window._navigate(page)
                application.processEvents()
            window.open_character("凯茜娅-狂诗")
            window.detail_page.show_gallery()
            window.mods_page.show_gallery()
            application.processEvents()
            assert len(window.ctx.catalog) == 56
            assert len(window.characters_page._collect()) == 54
            assert "基地" in window.category_buttons and "杂项" in window.category_buttons
            assert window.ctx.settings._home != Path(os.environ.get("APPDATA", "")) / "SnowMM"
            import zipfile

            import py7zr
            import rarfile

            source = home / "打包验证_100_P.pak"
            source.write_bytes(b"disposable self-test payload, not a playable mod")
            archive = home / "fixture.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.write(source, "nested/打包验证_100_P.pak")
            result = window.ctx.manager.import_paths([archive], category=["杂项", "打包自测"])
            assert result.ok, result.errors
            window.ctx.settings.deploy_mode = "copy"
            window.ctx.manager.running_check = lambda: False
            assert window.ctx.manager.set_enabled(result.added, True) == (1, [])
            assert window.ctx.manager.set_enabled(result.added, False) == (1, [])
            from .deployment import _link_target_key

            if os.name == "nt":
                for actual, expected in (
                    (r"\\?\G:\中文 模组\a_100_P.pak", r"G:\中文 模组\a_100_P.pak"),
                    (r"\\?\UNC\server\share\a.pak", r"\\server\share\a.pak"),
                ):
                    assert _link_target_key(actual, home) == _link_target_key(expected, home)
            window.ctx.settings.deploy_mode = "symlink"
            count, errors = window.ctx.manager.set_enabled(result.added, True)
            if errors:
                assert len(errors) == 1 and errors[0].startswith("Windows不允许建立符号链接"), errors
                link_execution = "skipped: Windows link privilege unavailable"
            else:
                assert count == 1
                assert window.ctx.manager.deployment.enabled_ids() == {result.added[0].id}
                assert window.ctx.manager.set_enabled(result.added, False) == (1, [])
                link_execution = "passed: real disposable symlink enable/disable"
            window.ctx.settings.deploy_mode = "copy"
            archive7 = home / "fixture.7z"
            with py7zr.SevenZipFile(archive7, "w") as bundle:
                bundle.write(source, "nested/Seven.pak")
            assert window.ctx.manager.import_paths([archive7], category=["杂项"]).ok
            window.refresh_all()
            window.open_category(["杂项"])
            assert "杂项/打包自测" in window.category_page.cards
            assert rarfile.RarFile
            from .repair import RepairService

            repair_help = "not configured (optional external tool)"
            if window.ctx.settings.repair_tool and Path(window.ctx.settings.repair_tool, "assess_mod.py").is_file():
                help_text = RepairService(window.ctx.settings)._run("assess_mod.py", ["-h"], home)
                assert "--json" in help_text
                repair_help = True
            report.update(
                ok=True,
                catalog_count=len(window.ctx.catalog),
                source_scan_read_only=True,
                zip_7z_backends=True,
                rar_backend_import=True,
                disposable_copy_deploy=True,
                repair_runtime_help=repair_help,
                sidebar_category_cards=True,
                utility_cards_merged=True,
                windows_link_path_spelling=True,
                real_symlink_deployment=link_execution,
            )
        except Exception as error:
            report["error"] = str(error)
        finally:
            window.close()
            application.quit()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        isolated.cleanup()
        return 0 if report["ok"] else 1
    window.show()
    return application.exec()
