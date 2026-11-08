"""Enhanced settings keep library and deployment separate, with explicit changes."""

from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..core import shell
from .library import LibraryManager
from .storage import DEFAULT_DEPLOY, DEFAULT_GAME, DEFAULT_LIBRARY, DEFAULT_SERVER, DEFAULT_TOOL, LibraryStore


class EnhancedSettingsPage(QWidget):
    title_key = ""
    subtitle_key = ""

    def apply_theme(self, *args):
        pass

    paths_changed = Signal()
    theme_changed = Signal()
    language_changed = Signal()

    def __init__(self, ctx, owner):
        super().__init__()
        self.ctx, self.owner = ctx, owner
        outer = QVBoxLayout(self)
        title = QLabel("增强设置 · 资源库与游戏应用目录分开")
        title.setStyleSheet("font-size:23px;font-weight:600;padding:10px")
        outer.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        self.edits = {}
        items = [
            ("storage_path", "资源库存储目录", True),
            ("deploy_path", "游戏应用目录", True),
            ("game_exe", "官方游戏程序 Game.exe", False),
            ("server_exe", "本地服务端程序", False),
            ("custom_exe", "自定义启动程序", False),
            ("launch_cwd", "启动工作目录（可留空）", True),
            ("custom_args", "自定义程序参数", None),
            ("game_args", "直接启动游戏参数", None),
            ("repair_tool", "1050修复工具目录", True),
            ("repair_python", "独立修复 Python", False),
            ("hotkey", "全局截图热键", None),
        ]
        for key, label, directory in items:
            row = QHBoxLayout()
            edit = QLineEdit(str(getattr(ctx.settings, key)))
            self.edits[key] = edit
            row.addWidget(edit)
            if directory is not None:
                browse = QPushButton("选择")
                browse.clicked.connect(lambda _=False, k=key, d=directory: self.browse(k, d))
                row.addWidget(browse)
                open_button = QPushButton("打开位置")
                open_button.clicked.connect(lambda _=False, k=key: shell.reveal(Path(self.edits[k].text())))
                row.addWidget(open_button)
            form.addRow(label, row)
        self.mode = QComboBox()
        self.bundled = QCheckBox("使用自行配置的便携修复工具与运行时（可选）")
        self.bundled.setChecked(ctx.settings.bundled_repair)
        form.addRow(self.bundled)
        self.mode.addItem("符号链接（默认，游戏目录几乎不占空间）", "symlink")
        self.mode.addItem("复制（占用额外空间，不需要链接权限）", "copy")
        self.mode.setCurrentIndex(max(0, self.mode.findData(ctx.settings.deploy_mode)))
        form.addRow("部署模式", self.mode)
        self.launch = QComboBox()
        for name, key in [
            ("直接启动官方游戏", "direct"),
            ("启动本地服务端（随后手动输入 game）", "server"),
            ("启动自定义程序", "custom"),
        ]:
            self.launch.addItem(name, key)
        self.launch.setCurrentIndex(max(0, self.launch.findData(ctx.settings.launch_mode)))
        form.addRow("启动方式", self.launch)
        self.theme = QComboBox()
        for label, key in [("暗色", "dark"), ("亮色", "light"), ("跟随系统", "system")]:
            self.theme.addItem(label, key)
        self.theme.setCurrentIndex(max(0, self.theme.findData(ctx.settings.theme)))
        form.addRow("外观", self.theme)
        self.language = QComboBox()
        self.language.addItem("简体中文", "zh_CN")
        self.language.addItem("English（原角色界面；增强工作台中文）", "en_US")
        self.language.setCurrentIndex(max(0, self.language.findData(ctx.settings.language)))
        form.addRow("语言", self.language)
        buttons = QHBoxLayout()
        save = QPushButton("保存设置")
        save.clicked.connect(self.save)
        buttons.addWidget(save)
        recommend = QPushButton("填入默认资源库路径")
        recommend.clicked.connect(self.defaults)
        buttons.addWidget(recommend)
        developer = QPushButton("打开 Windows 开发者设置")
        developer.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("ms-settings:developers")))
        buttons.addWidget(developer)
        permissions = QHBoxLayout()
        probe = QPushButton("检测符号链接权限")
        probe.clicked.connect(owner.check_link_permission)
        permissions.addWidget(probe)
        admin = QPushButton("以管理员身份重启")
        admin.clicked.connect(owner.restart_as_admin)
        permissions.addWidget(admin)
        form.addRow("链接权限", permissions)
        hotkey = QPushButton("重新注册热键")
        hotkey.clicked.connect(owner.register_hotkey)
        buttons.addWidget(hotkey)
        form.addRow(buttons)
        info = QLabel(
            "链接权限：可先检测，再选择管理员重启或自行开启开发者模式。本程序不自动提权或修改系统设置。\n"
            "管理员重启需你确认和Windows UAC授权；取消授权不会关闭当前窗口。重启后需手动重新应用。\n"
            "也可明确选择复制模式。变更模式会生成待办，请到资源库点击‘应用待办’。\n"
            "切换资源库或应用根目录前，须先停用全部受管理模组，避免留下旧部署。\n"
            "资料、预览和版本保存在每个模组文件夹中；程序 data 目录保存便携设置和可重建索引。\n"
            "原版 SnowMM 的 %APPDATA% 数据不会被读取或覆盖。"
        )
        info.setWordWrap(True)
        form.addRow(info)
        self.checks = QLabel()
        self.checks.setWordWrap(True)
        form.addRow("路径检查", self.checks)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.refresh()

    def browse(self, key, directory):
        if directory:
            value = QFileDialog.getExistingDirectory(self, "选择目录", self.edits[key].text())
        else:
            value, _ = QFileDialog.getOpenFileName(self, "选择程序", self.edits[key].text(), "Programs (*.exe)")
        if value:
            if value:
                self.edits[key].setText(value)
            if key == "game_exe" and len(Path(value).parents) > 2 and not self.edits["deploy_path"].text().strip():
                self.edits["deploy_path"].setText(str(Path(value).parents[2] / "Content/Paks/~SnowMM"))
            if key in {"repair_tool", "repair_python"}:
                self.bundled.setChecked(False)

    def defaults(self):
        for key, value in [
            ("storage_path", DEFAULT_LIBRARY),
            ("deploy_path", DEFAULT_DEPLOY),
            ("game_exe", DEFAULT_GAME),
            ("server_exe", DEFAULT_SERVER),
            ("repair_tool", DEFAULT_TOOL),
        ]:
            if value:
                self.edits[key].setText(value)

    def save(self):
        settings = self.ctx.settings
        values = {key: edit.text().strip() for key, edit in self.edits.items()}
        try:
            if not values["storage_path"] or not values["deploy_path"]:
                raise ValueError("资源库和部署目录不能为空")
            roots_changed = any(values[k] != getattr(settings, k) for k in ("storage_path", "deploy_path"))
            if roots_changed and self.ctx.manager.deployment.state()["files"]:
                raise ValueError("请先停用全部受管理模组，再切换根目录")
            from .deployment import Deployment

            Deployment(Path(values["deploy_path"])).validate(Path(values["storage_path"]))
            mode_changed = self.mode.currentData() != settings.deploy_mode
            enabled = self.ctx.manager.desired_ids()
            previous_theme, previous_language, previous_hotkey = settings.theme, settings.language, settings.hotkey
            for key, value in values.items():
                setattr(settings, key, value)
            settings.deploy_mode = self.mode.currentData()
            settings.bundled_repair = self.bundled.isChecked()
            if settings.bundled_repair:
                from .app import portable_root

                bundle = portable_root()
                if (bundle / "repair-engine").is_dir():
                    settings.repair_tool = str(bundle / "repair-engine")
                    self.edits["repair_tool"].setText(settings.repair_tool)
                if (bundle / "repair-runtime/python.exe").is_file():
                    settings.repair_python = str(bundle / "repair-runtime/python.exe")
                    self.edits["repair_python"].setText(settings.repair_python)
            settings.launch_mode = self.launch.currentData()
            settings.theme, settings.language = self.theme.currentData(), self.language.currentData()
            if roots_changed:
                self.ctx.store = LibraryStore(Path(settings.storage_path), settings._home).load()
                self.ctx.manager = LibraryManager(self.ctx.store, settings)
                self.owner.library_page.current = None
                settings.pending_ids, settings.pending_revisions = [], {}
                settings.has_pending = False
            elif mode_changed:
                settings.pending_ids = sorted(enabled)
                settings.has_pending = True
            settings.save()
            if previous_hotkey != settings.hotkey:
                self.owner.register_hotkey()
            self.paths_changed.emit()
            if previous_theme != settings.theme:
                self.theme_changed.emit()
            if previous_language != settings.language:
                self.language_changed.emit()
            self.refresh()
            QMessageBox.information(self, "设置已保存", "设置已保存。部署模式变化需到资源库应用待办。")
        except Exception as error:
            QMessageBox.warning(self, "设置未保存", str(error))

    def refresh(self):
        settings = self.ctx.settings
        messages = []
        for label, value in [
            ("游戏程序", settings.game_exe),
            ("修复引擎", settings.repair_tool),
            ("修复Python", settings.repair_python),
        ]:
            messages.append(f"{label}：{'存在' if value and Path(value).exists() else '未找到（请检查路径）'}")
        self.checks.setText("\n".join(messages))

    def set_search(self, text):
        pass
