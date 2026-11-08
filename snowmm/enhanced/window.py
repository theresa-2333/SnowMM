"""Extend the original window rather than replacing its catalog and galleries."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..ui.main_window import MainWindow
from . import VERSION
from .capture import CaptureSession, Hotkey
from .category_page import CategoryPage, RosterPage, category_paths
from .permissions import check_link_permission, is_admin, request_admin_restart
from .settings_page import EnhancedSettingsPage
from .workbench import Workbench


class EnhancedWindow(MainWindow):
    def __init__(self, ctx):
        previous_page = ctx.settings.last_page
        super().__init__(ctx)
        self.setWindowTitle(f"SnowMM增强版 · {VERSION}")
        self.app_name_label.setText("SnowMM 增强版")
        self.version_label.setText(VERSION)
        self.nav_buttons["characters"].setText("角色概览")
        self.nav_buttons["mods"].setText("全部模组 / 画廊")
        self.nav_buttons["settings"].setText("增强设置")
        self.setMinimumSize(1180, 700)
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1540, available.width()), min(950, available.height() - 30))
        self.capture_session = CaptureSession(self, self.confirm_capture)
        self.hotkey = Hotkey(self.capture_preview)
        self._navigate(previous_page if previous_page in self.nav_buttons else "characters")
        if not Path(ctx.settings.game_exe).is_file():
            self._navigate("settings")
            self.toast_host.show_message("建议的游戏路径不存在，请先选择本机实际路径", "warning")
        if os.environ.get("SNOWMM_TEST_NO_HOTKEY") != "1":
            QTimer.singleShot(0, self.register_hotkey)

    def _build_sidebar(self):
        sidebar = super()._build_sidebar()
        self._sidebar = sidebar
        self._nav_container = QWidget()
        self._nav_layout = QVBoxLayout(self._nav_container)
        self._nav_layout.setContentsMargins(0, 0, 0, 0)
        self._nav_layout.setSpacing(6)
        self._nav_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        for button in self.nav_buttons.values():
            sidebar.layout().removeWidget(button)
            self._nav_layout.addWidget(button)
        for index in reversed(range(sidebar.layout().count())):
            if sidebar.layout().itemAt(index).spacerItem():
                sidebar.layout().takeAt(index)
        scroll = QScrollArea()
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._nav_container)
        sidebar.layout().insertWidget(1, scroll, 1)
        button = QPushButton("全部资源库")
        button.setObjectName("NavItem")
        button.setCheckable(True)
        button.clicked.connect(lambda: self._navigate("library"))
        self.nav_group.addButton(button)
        self.nav_buttons["library"] = button
        self._nav_layout.insertWidget(1, button)
        self.category_buttons = {}
        self._sync_category_navigation()
        return sidebar

    def _sync_category_navigation(self):
        roots = list(dict.fromkeys(p[0] for p in category_paths(self.ctx) if p and p[0] != "角色"))
        existing = getattr(self, "category_buttons", {})
        if list(existing) == roots:
            return
        checked = self.nav_group.checkedButton()
        checked_key = next((k for k, b in self.nav_buttons.items() if b is checked), "")
        for name, button in existing.items():
            self._nav_layout.removeWidget(button)
            self.nav_group.removeButton(button)
            self.nav_buttons.pop("category:" + name, None)
            button.hide()
            button.deleteLater()
        self.category_buttons = {}
        for index, name in enumerate(roots, 1):
            key = "category:" + name
            button = QPushButton(name)
            button.setObjectName("NavItem")
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, k=key: self._navigate(k))
            self.nav_group.addButton(button)
            self.nav_buttons[key] = button
            self.category_buttons[name] = button
            self._nav_layout.insertWidget(index, button)
        if checked_key in self.nav_buttons:
            self.nav_buttons[checked_key].setChecked(True)

    def _create_pages(self):
        super()._create_pages()
        previous_roster = self.characters_page
        self.stack.removeWidget(previous_roster)
        previous_roster.deleteLater()
        self.characters_page = RosterPage(self.ctx)
        self.characters_page.open_character.connect(self.open_character)
        self.characters_page.changed.connect(self.refresh_all)
        self.pages["characters"] = self.characters_page
        self.stack.addWidget(self.characters_page)
        previous = self.settings_page
        self.stack.removeWidget(previous)
        previous.deleteLater()
        self.settings_page = EnhancedSettingsPage(self.ctx, self)
        self.settings_page.paths_changed.connect(self.refresh_all)
        self.settings_page.theme_changed.connect(self.apply_theme)
        self.settings_page.language_changed.connect(self.change_language)
        self.pages["settings"] = self.settings_page
        self.stack.addWidget(self.settings_page)
        self.library_page = Workbench(self.ctx, self)
        self.pages["library"] = self.library_page
        self.stack.addWidget(self.library_page)
        self.category_page = CategoryPage(self.ctx, self)
        self.pages["category"] = self.category_page
        self.stack.addWidget(self.category_page)
        self._sync_category_navigation()

    def refresh_all(self):
        # Refresh is read-only with respect to folder-owned metadata and layout.
        if (
            hasattr(self, "library_page")
            and self.library_page.has_unsaved()
            and not self.library_page.commit_metadata()
        ):
            return
        self.ctx.manager.refresh_states()
        self.ctx.catalog.reload(self.ctx.store.characters)
        self._sync_category_navigation()
        for page in list(self.pages.values()) + [self.detail_page]:
            page.refresh()
        self.toast_host.set_theme(self.ctx.theme)

    def _navigate(self, key):
        if (
            hasattr(self, "library_page")
            and self.library_page.has_unsaved()
            and not self.library_page.commit_metadata()
        ):
            return
        root = key.removeprefix("category:") if key.startswith("category:") else ""
        if root:
            self.category_page.path = [root]
            key = "category"
        super()._navigate(key)
        if key == "library":
            self.page_title.setText("分类资源库")
            self.page_subtitle.setText("原件、历史、预览与信息随模组文件夹保存")
            self.search_box.setEnabled(True)
        elif key == "settings":
            self.page_title.setText("增强设置")
            self.page_subtitle.setText("独立资源库、链接部署、截图与启动方式")
        elif key == "category":
            self.page_title.setText(self.category_page.path[0])
            self.page_subtitle.setText("小分类卡片 · 逐级浏览模组和版本")
            self.search_box.setEnabled(True)
            button = self.nav_buttons.get("category:" + self.category_page.path[0])
            if button:
                button.setChecked(True)
            self.ctx.settings.last_page = "category:" + self.category_page.path[0]
            self.ctx.settings.save()

    def change_language(self):
        super().change_language()
        self.setWindowTitle(f"SnowMM增强版 · {VERSION}")
        self.nav_buttons["characters"].setText("角色概览")
        self.nav_buttons["mods"].setText("全部模组 / 画廊")
        self.nav_buttons["settings"].setText("增强设置")

    def open_category(self, path):
        if not path or not self.library_page.commit_metadata():
            return
        self._navigate("category:" + path[0])
        self.category_page.show_path(path)

    def open_library_category(self, path, mod=None):
        if not self.library_page.commit_metadata():
            return
        self._navigate("library")
        page = self.library_page
        page.category = list(path)
        page.current = mod
        page.refresh()
        if path:
            self.page_title.setText(" / ".join(path))
            button = self.nav_buttons.get("category:" + path[0])
            if button:
                button.setChecked(True)

    def open_character(self, name):
        if name in {"基地", "杂项"}:
            self.open_category([name])
        else:
            super().open_character(name)

    def check_link_permission(self):
        result = check_link_permission(Path(self.ctx.settings.deploy_path))
        QMessageBox.information(self, "符号链接权限检测", f"检测位置：{result.directory}\n{result.message}")
        return result

    def restart_as_admin(self):
        if getattr(self, "busy", False) or not self.library_page.commit_metadata():
            return False
        if is_admin():
            QMessageBox.information(
                self, "已经是管理员", "当前已使用管理员权限；若链接仍失败，请检查目录权限和文件系统。"
            )
            return False
        answer = QMessageBox.question(
            self,
            "以管理员身份重启",
            "先保存信息和待办，再请求Windows UAC授权。\n"
            "仅重启管理器，不会自动启用模组或执行原操作。管理器及其启动程序将使用管理员权限。\n"
            "取消授权会保留当前窗口；也可继续使用普通权限和复制模式。是否继续？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        try:
            self.ctx.store.save()
            self.ctx.settings.save()
            if not request_admin_restart(self.ctx.settings._home):
                self.toast_host.show_message("已取消管理员授权，当前窗口和待办保持不变", "warning")
                return False
            self.close()
            return True
        except OSError as error:
            QMessageBox.warning(self, "管理员重启未完成", str(error))
            return False

    def repair_and_refresh(self):
        if self.library_page.has_unsaved() and not self.library_page.commit_metadata():
            return
        self.ctx.manager.scan_storage()
        self.library_page.current = None
        self.refresh_all()

    def import_folder(self, character=""):
        folder = QFileDialog.getExistingDirectory(self, "选择来源目录（只复制）")
        if folder:
            if character:
                super().import_dialog(character, [Path(folder)])
            else:
                self._navigate("library")
                self.library_page.import_sources([Path(folder)])

    def import_dialog(self, character="", sources=None):
        if character:
            return super().import_dialog(character, sources)
        self._navigate("library")
        if sources:
            self.library_page.import_sources(sources)
        else:
            self.library_page.import_files()

    def register_hotkey(self):
        try:
            self.hotkey.register(self.ctx.settings.hotkey)
            self.toast_host.show_message("截图热键已注册：" + self.ctx.settings.hotkey)
        except (OSError, ValueError) as error:
            self.toast_host.show_message(str(error), "warning")

    def capture_preview(self):
        if getattr(self, "busy", False):
            self.toast_host.show_message("当前任务尚未完成，请稍后截图", "warning")
            return
        if not self.ctx.manager.mods:
            self.toast_host.show_message("请先导入模组，再截图设置预览", "warning")
            return
        self.capture_session.start()

    def confirm_capture(self, image):
        if not isinstance(image, QImage) or image.isNull():
            self.toast_host.show_message("没有可保存的截图", "warning")
            return
        mods = self.ctx.manager.mods
        if not mods:
            return
        labels = [f"{m.name} · {' / '.join(m.category_parts)} · {m.id[-6:]}" for m in mods]
        current = self.library_page.current
        default = mods.index(current) if current in mods else 0
        label, ok = QInputDialog.getItem(self, "确认截图归属", "保存到哪个模组？", labels, default, False)
        if not ok:
            return
        mod = mods[labels.index(label)]
        purpose, ok = QInputDialog.getItem(
            self, "保存预览", "图片用途：", ["设为封面并加入预览", "追加预览（保留封面）"], editable=False
        )
        if not ok:
            return
        try:
            with tempfile.TemporaryDirectory(prefix="capture-", dir=self.ctx.settings._home) as temporary:
                file = Path(temporary) / "截图.png"
                if not image.save(str(file), "PNG"):
                    raise OSError("截图保存失败")
                self.ctx.manager.set_preview(mod, file, cover=purpose.startswith("设为"))
            self.refresh_all()
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "截图未保存", str(error))

    def launch_game(self):
        settings = self.ctx.settings
        mode = settings.launch_mode
        executable = (
            settings.game_exe if mode == "direct" else settings.server_exe if mode == "server" else settings.custom_exe
        )
        arguments = settings.game_args if mode == "direct" else settings.custom_args if mode == "custom" else ""
        try:
            path = Path(executable)
            if not executable or not path.is_file() or path.suffix.lower() != ".exe":
                raise ValueError("请选择存在的 EXE；Game.exe 与启动器、服务端是不同程序")
            cwd = Path(settings.launch_cwd) if settings.launch_cwd else path.parent
            if not cwd.is_dir():
                raise ValueError("启动工作目录不存在")
            flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" and mode == "server" else 0
            subprocess.Popen([str(path), *QProcess.splitCommand(arguments)], cwd=cwd, shell=False, creationflags=flags)
            if mode == "server":
                QMessageBox.information(
                    self, "本地服务端已打开", "等待服务端启动完成后，在其控制台手动输入 game。管理器不会自动输入命令。"
                )
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "启动未完成", str(error))

    def dropEvent(self, event):
        self._navigate("library")
        self.library_page.dropEvent(event)

    def closeEvent(self, event):
        if getattr(self, "busy", False):
            event.ignore()
            return
        if self.library_page.has_unsaved() and not self.library_page.commit_metadata():
            event.ignore()
            return
        if self.capture_session.busy:
            self.capture_session.finish(None)
        self.hotkey.close()
        super().closeEvent(event)
