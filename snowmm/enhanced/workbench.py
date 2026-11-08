"""Category-first library UI; upstream character catalog/gallery remain available."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core import shell
from .deployment import LinkPermissionError
from .repair import RepairService
from .storage import component, inside


def text_dialog(parent, title, text):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(820, 600)
    layout = QVBoxLayout(dialog)
    viewer = QPlainTextEdit()
    viewer.setReadOnly(True)
    viewer.setPlainText(text)
    layout.addWidget(viewer)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()


class Job(QThread):
    done = Signal(object, object)

    def __init__(self, function, parent):
        super().__init__(parent)
        self.function = function

    def run(self):
        try:
            self.done.emit(self.function(), None)
        except Exception as error:
            self.done.emit(None, str(error))


class Workbench(QWidget):
    title_key = ""
    subtitle_key = ""

    def apply_theme(self, *args):
        pass

    def __init__(self, ctx, owner):
        super().__init__()
        self.ctx, self.owner = ctx, owner
        self.search = ""
        self._loading = False
        self.current = None
        self.category = []
        layout = QVBoxLayout(self)
        title = QLabel("资源库 · 中文多级分类")
        title.setStyleSheet("font-size:24px;font-weight:600;padding:8px")
        layout.addWidget(title)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        bar = QHBoxLayout()
        for title, callback in [
            ("导入文件/压缩包", self.import_files),
            ("导入文件夹", self.import_folder),
            ("重扫资源库", self.rescan),
            ("角色概览", lambda: owner._navigate("characters")),
            ("分类卡片", lambda: owner.open_category(self.category or ["杂项"])),
            ("截图", owner.capture_preview),
            ("粘贴图片", self.paste),
            ("应用待办", self.apply_pending),
        ]:
            button = QPushButton(title)
            button.clicked.connect(callback)
            bar.addWidget(button)
        layout.addLayout(bar)
        splitter = QSplitter()
        layout.addWidget(splitter, 1)
        left = QWidget()
        self.category_panel = left
        left_layout = QVBoxLayout(left)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("大分类 / 小分类")
        self.tree.currentItemChanged.connect(self.choose_category)
        left_layout.addWidget(self.tree)
        for labels in [
            [("新增", self.add_category), ("改名/移动", self.rename_category)],
            [("上移", lambda: self.order_category(-1)), ("下移", lambda: self.order_category(1))],
        ]:
            row = QHBoxLayout()
            for label, callback in labels:
                button = QPushButton(label)
                button.clicked.connect(callback)
                row.addWidget(button)
            left_layout.addLayout(row)
        splitter.addWidget(left)
        left.hide()  # Categories live in the main sidebar and the card browser.
        center = QWidget()
        center_layout = QVBoxLayout(center)
        self.table = QTreeWidget()
        self.table.setHeaderLabels(["模组", "部署状态", "当前版本", "互斥组"])
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.currentItemChanged.connect(self.choose_mod)
        self.table.itemDoubleClicked.connect(lambda *_: self.toggle(True))
        center_layout.addWidget(self.table)
        row = QHBoxLayout()
        for label, callback in [
            ("启用选中", lambda: self.toggle(True)),
            ("停用选中", lambda: self.toggle(False)),
            ("保存方案", self.save_preset),
            ("预览/加载方案", self.load_preset),
            ("移至回收目录", self.trash),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        center_layout.addLayout(row)
        splitter.addWidget(center)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        detail = QWidget()
        self.form = QFormLayout(detail)
        self.edits = {}
        for key, label in [
            ("name", "自定义名称"),
            ("author", "作者"),
            ("source_url", "来源链接"),
            ("target", "作用对象"),
            ("game_versions", "游戏版本"),
            ("tags", "标签（逗号分隔）"),
            ("category", "分类（/ 分隔）"),
            ("conflict_group", "互斥组（空=允许叠加）"),
        ]:
            edit = QLineEdit()
            self.edits[key] = edit
            self.form.addRow(label, edit)
        self.character = QComboBox()
        for character in ctx.catalog:
            self.character.addItem(character.name, character.name)
        self.form.addRow("角色图鉴归属", self.character)
        self.skin = QComboBox()
        self.character.currentIndexChanged.connect(self.fill_skins)
        self.form.addRow("服装归属", self.skin)
        self.tested = QComboBox()
        self.tested.addItems(["未实测", "已验证", "失效", "部分可用"])
        self.form.addRow("实测状态（人工确认）", self.tested)
        self.original = QLabel()
        self.original.setWordWrap(True)
        self.form.addRow("原始文件", self.original)
        self.version = QComboBox()
        self.form.addRow("版本选择", self.version)
        self.note = QPlainTextEdit()
        self.note.setMaximumHeight(110)
        self.form.addRow("备注", self.note)
        self.preview = QLabel("选择模组查看预览")
        self.preview.setMinimumHeight(145)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.mousePressEvent = self.open_preview
        self.form.addRow(self.preview)
        self.previews = QListWidget()
        self.previews.setMaximumHeight(105)
        self.previews.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.previews.currentItemChanged.connect(self.show_preview)
        self.previews.model().rowsMoved.connect(self.reorder_previews)
        self.form.addRow("多张预览（可拖动排序）", self.previews)
        for buttons in [
            [("保存信息", self.save_metadata), ("放弃未保存信息", self.discard_metadata)],
            [("切换选定版本", self.switch_version)],
            [("导入更新版", self.import_revision), ("打开模组目录", self.reveal)],
            [("选择预览图", self.choose_picture), ("设为封面", self.set_cover)],
            [("评估兼容性", lambda: self.repair(False)), ("生成修复候选", lambda: self.repair(True))],
            [("查看校验与历史", self.history), ("工具版本信息", self.engine_info)],
        ]:
            row = QHBoxLayout()
            for label, callback in buttons:
                button = QPushButton(label)
                button.clicked.connect(callback)
                row.addWidget(button)
            self.form.addRow(row)
        scroll.setWidget(detail)
        splitter.addWidget(scroll)
        splitter.setSizes([210, 500, 370])
        self.paste_shortcut = QShortcut(QKeySequence("Ctrl+V"), self)
        self.paste_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.paste_shortcut.activated.connect(self.paste)
        self.setAcceptDrops(True)
        self.refresh()

    def message(self, message):
        QMessageBox.information(self, "SnowMM增强版", str(message))

    def attempt(self, action):
        try:
            return action()
        except LinkPermissionError as error:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            box = QMessageBox(self)
            box.setWindowTitle("符号链接权限不足")
            box.setText(str(error) + "\n可由你请求UAC授权重启，或选择其他方式。不会自动执行原操作。")
            admin = box.addButton("以管理员身份重启", QMessageBox.ButtonRole.ActionRole)
            developer = box.addButton("打开开发者设置", QMessageBox.ButtonRole.ActionRole)
            copy_button = box.addButton("切换复制并重试", QMessageBox.ButtonRole.AcceptRole)
            box.addButton(QMessageBox.StandardButton.Cancel)
            box.exec()
            if box.clickedButton() is admin:
                self.owner.restart_as_admin()
            elif box.clickedButton() is developer:
                QDesktopServices.openUrl(QUrl("ms-settings:developers"))
            elif box.clickedButton() is copy_button:
                self.ctx.settings.deploy_mode = "copy"
                self.ctx.settings.save()
                self.owner.settings_page.mode.setCurrentIndex(1)
                return self.attempt(action)
            return None
        except Exception as error:
            QMessageBox.warning(self, "操作未完成", str(error))
            return None

    def selected(self):
        return [self.ctx.store.get_mod(item.data(0, Qt.ItemDataRole.UserRole)) for item in self.table.selectedItems()]

    def set_search(self, value):
        self.search = value.casefold()
        self.refresh_table()

    def refresh(self):
        self._loading = True
        chosen = self.category[:]
        self.tree.clear()
        all_item = QTreeWidgetItem(self.tree, ["全部模组"])
        all_item.setData(0, Qt.ItemDataRole.UserRole, [])
        nodes = {(): all_item}
        paths = self.ctx.store.categories + [m.category_parts for m in self.ctx.manager.mods]
        for parts in paths:
            for length in range(1, len(parts) + 1):
                key = tuple(parts[:length])
                if key not in nodes:
                    parent = self.tree if length == 1 else nodes[key[:-1]]
                    item = QTreeWidgetItem(parent, [key[-1]])
                    item.setData(0, Qt.ItemDataRole.UserRole, list(key))
                    nodes[key] = item
        self.tree.expandToDepth(0)
        self.tree.setCurrentItem(nodes.get(tuple(chosen), all_item))
        self._loading = False
        self.refresh_table()

    def choose_category(self, item, _previous):
        if item:
            self.category = item.data(0, Qt.ItemDataRole.UserRole) or []
        if not self._loading:
            self.refresh_table()

    def refresh_table(self):
        identity = self.current.id if self.current else None
        self.ctx.manager.refresh_states()
        pending = self.ctx.manager.desired_ids()
        self.table.clear()
        selected_item = None
        for mod in self.ctx.manager.mods:
            if self.category and mod.category_parts[: len(self.category)] != self.category:
                continue
            haystack = " ".join([mod.name, mod.author, mod.note, mod.target, *mod.tags, *mod.category_parts]).casefold()
            if self.search and self.search not in haystack:
                continue
            state = "已部署" if mod.enabled else "未部署"
            if self.ctx.settings.has_pending:
                state += " → 待启用" if mod.id in pending else " → 待停用"
            item = QTreeWidgetItem(self.table, [mod.name, state, mod.current_version, mod.conflict_group or "可叠加"])
            item.setData(0, Qt.ItemDataRole.UserRole, mod.id)
            item.setToolTip(0, str(Path(mod.folder)))
            if mod.id == identity:
                selected_item = item
        if selected_item:
            self.table.setCurrentItem(selected_item)
        elif self.table.topLevelItemCount():
            self.table.setCurrentItem(self.table.topLevelItem(0))
        else:
            self.current = None
            self.preview.clear()
        total = len(self.ctx.manager.mods)
        issues = self.ctx.manager.compatibility_errors
        self.status.setText(
            f"{total} 个模组 · 当前模式：{'符号链接' if self.ctx.settings.deploy_mode == 'symlink' else '复制'}"
            f" · {'有待应用更改' if self.ctx.settings.has_pending else '无待办'}\n"
            f"资源库：{self.ctx.settings.storage_path}\n应用目录：{self.ctx.settings.deploy_path}"
            + ("\n检查提示：" + issues[0] if issues else "")
        )

    def choose_mod(self, item, _previous):
        if not item:
            return
        candidate = self.ctx.store.get_mod(item.data(0, Qt.ItemDataRole.UserRole))
        if (
            self.current
            and candidate
            and candidate.id != self.current.id
            and self.has_unsaved()
            and not self.commit_metadata()
        ):
            for index in range(self.table.topLevelItemCount()):
                previous = self.table.topLevelItem(index)
                if previous.data(0, Qt.ItemDataRole.UserRole) == self.current.id:
                    self.table.blockSignals(True)
                    self.table.setCurrentItem(previous)
                    self.table.blockSignals(False)
                    break
            return
        self.current = candidate
        if not self.current:
            return
        mod = self.current
        for key, edit in self.edits.items():
            value = (
                "/".join(mod.category_parts)
                if key == "category"
                else ", ".join(mod.tags)
                if key == "tags"
                else getattr(mod, key)
            )
            edit.setText(value)
        self.note.setPlainText(mod.note)
        self.tested.setCurrentText(mod.tested)
        self.character.setCurrentIndex(max(0, self.character.findData(mod.character)))
        self.fill_skins()
        self.skin.setCurrentIndex(max(0, self.skin.findData(mod.skin)))
        self.original.setText("\n".join(mod.original_names))
        self.version.clear()
        for version in mod.versions:
            self.version.addItem(version["id"] + " · " + version.get("label", ""), version["id"])
        self.version.setCurrentIndex(max(0, self.version.findData(mod.current_version)))
        self._loading = True
        self.previews.clear()
        for index, relative in enumerate(mod.previews):
            item = QListWidgetItem(("★ " if relative == mod.cover else "") + f"预览 {index + 1}")
            item.setIcon(QIcon(str(Path(mod.folder) / relative)))
            item.setData(Qt.ItemDataRole.UserRole, relative)
            self.previews.addItem(item)
        self._loading = False
        if self.previews.count():
            self.previews.setCurrentRow(max(0, mod.previews.index(mod.cover) if mod.cover in mod.previews else 0))
        else:
            self.preview.clear()
            self.preview.setText("尚无预览 · 截图、粘贴或拖入图片")

    def fill_skins(self):
        from ..core.skins import skins_for

        self.skin.clear()
        for skin in skins_for(self.character.currentData() or "杂项"):
            self.skin.addItem(skin.name, skin.id)

    def save_metadata(self):
        if self.commit_metadata():
            self.owner.refresh_all()

    def discard_metadata(self):
        self.choose_mod(self.table.currentItem(), None)

    def has_unsaved(self):
        if self._loading or not self.current:
            return False
        mod = self.current
        values = {key: edit.text().strip() for key, edit in self.edits.items()}
        expected = {key: str(getattr(mod, key)) for key in values if key not in {"category", "tags"}}
        expected["category"] = "/".join(mod.category_parts)
        expected["tags"] = ", ".join(mod.tags)
        return (
            values != expected
            or self.note.toPlainText() != mod.note
            or self.tested.currentText() != mod.tested
            or self.character.currentData() != mod.character
            or self.skin.currentData() != mod.skin
        )

    def commit_metadata(self):
        if not self.current:
            return True

        def action():
            import copy

            mod = self.current
            snapshot = copy.deepcopy(mod.__dict__)
            try:
                for key, edit in self.edits.items():
                    if key not in {"category", "tags"}:
                        setattr(mod, key, edit.text().strip())
                mod.category_parts = [
                    component(p.strip()) for p in self.edits["category"].text().split("/") if p.strip()
                ]
                if not mod.category_parts or not mod.name:
                    raise ValueError("名称和分类不能为空")
                mod.tags = [s.strip() for s in self.edits["tags"].text().split(",") if s.strip()]
                mod.note = self.note.toPlainText()
                mod.tested = self.tested.currentText()
                mod.character = self.character.currentData() or "杂项"
                mod.skin = self.skin.currentData() or "default"
                self.ctx.store.save()
            except BaseException:
                mod.__dict__.update(snapshot)
                raise
            return True

        return bool(self.attempt(action))

    def add_category(self):
        value, ok = QInputDialog.getText(
            self, "新增分类", "完整分类路径（例如 NPC/安保）：", text="/".join(self.category)
        )
        if ok:

            def action():
                parts = [component(p.strip()) for p in value.split("/") if p.strip()]
                if not parts:
                    raise ValueError("分类不能为空")
                inside(self.ctx.store.root, self.ctx.store.root.joinpath(*parts)).mkdir(parents=True, exist_ok=True)
                if parts not in self.ctx.store.categories:
                    self.ctx.store.categories.append(parts)
                self.ctx.store.save()
                self.category = parts
                self.owner.refresh_all()

            self.attempt(action)

    def rename_category(self):
        if not self.category:
            return
        old = self.category[:]
        value, ok = QInputDialog.getText(self, "改名或移动分类", "新的完整路径：", text="/".join(old))
        if ok:

            def action():
                parts = [component(p.strip()) for p in value.split("/") if p.strip()]
                if not parts:
                    raise ValueError("分类不能为空")
                self.ctx.manager.change_category(old, parts)
                self.category = parts
                self.owner.refresh_all()

            self.attempt(action)

    def order_category(self, delta):
        categories = []
        for parts in self.ctx.store.categories + [m.category_parts for m in self.ctx.manager.mods]:
            for length in range(1, len(parts) + 1):
                if parts[:length] not in categories:
                    categories.append(parts[:length])
        if not self.category:
            return
        depth = len(self.category)
        siblings = [p for p in categories if len(p) == depth and p[:-1] == self.category[:-1]]
        index = siblings.index(self.category)
        target_index = index + delta
        if not 0 <= target_index < len(siblings):
            return
        target = siblings[target_index]
        block = [p for p in categories if p[:depth] == self.category]
        remaining = [p for p in categories if p not in block]
        positions = [i for i, p in enumerate(remaining) if p[:depth] == target]
        insert = min(positions) if delta < 0 else max(positions) + 1
        self.ctx.store.categories = remaining[:insert] + block + remaining[insert:]
        self.ctx.store.save()
        self.owner.refresh_all()

    def import_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "选择模组或压缩包", "", "Mods (*.pak *.utoc *.zip *.7z *.rar)")
        if files:
            self.import_sources([Path(f) for f in files])

    def import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择来源目录（只复制，不剪切）")
        if folder:
            self.import_sources([Path(folder)])

    def import_sources(self, sources):
        category = self.category or ["杂项"]

        def inspect():
            return self.ctx.manager.preview_import(sources)

        def confirm(plan):
            if not plan:
                self.message("没有发现可导入包；已整理文件夹可用更新后的导入器识别。")
                return
            summary = f"分类：{' / '.join(category)}\n将复制 {len(plan)} 个包，原目录不变，导入后不自动部署。\n\n"
            summary += "\n".join("、".join(p["files"]) for p in plan[:35])
            if QMessageBox.question(self, "导入预览", summary) != QMessageBox.StandardButton.Yes:
                return
            name, ok = QInputDialog.getText(self, "模组名称", "自定义名称（留空保留原名；多包会分别命名）：")
            if not ok:
                return
            character = "杂项"
            if len(category) >= 3 and category[0] == "角色":
                guess = category[1] + "-" + category[2]
                if guess in self.ctx.known_characters():
                    character = guess
            self.run_job(
                lambda: self.ctx.manager.import_paths(sources, character=character, category=category, name=name),
                "正在导入",
                lambda result: self.message(f"导入 {len(result.added)} 项\n" + "\n".join(result.errors)),
            )

        self.run_job(inspect, "正在分析导入内容", confirm)

    def run_job(self, function, label, callback):
        if not self.commit_metadata():
            return
        self.owner.busy = True
        progress = QProgressDialog(label, "", 0, 0, self)
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        self.job = Job(function, self)

        def finished(result, error):
            progress.close()
            self.owner.busy = False
            if error:
                QMessageBox.warning(self, "操作未完成", error)
            else:
                callback(result)
            self.owner.refresh_all()

        self.job.done.connect(finished)
        self.job.finished.connect(self.job.deleteLater)
        self.job.start()
        progress.show()

    def rescan(self):
        self.attempt(lambda: self.ctx.manager.scan_storage())
        self.owner.refresh_all()

    def toggle(self, enabled):
        def action():
            count, errors = self.ctx.manager.set_enabled(self.selected(), enabled)
            if errors:
                if "Windows不允许建立符号链接" in errors[0]:
                    raise LinkPermissionError(errors[0])
                self.message("\n".join(errors))
            self.owner.refresh_all()

        self.attempt(action)

    def apply_pending(self):
        def action():
            self.ctx.manager.apply_pending()
            self.owner.refresh_all()
            self.message("待办已应用，请重新启动游戏检查效果。")

        self.attempt(action)

    def switch_version(self):
        if self.current:
            self.attempt(
                lambda: self.message(self.ctx.manager.select_version(self.current, self.version.currentData()))
            )
            self.owner.refresh_all()

    def import_revision(self):
        if not self.current:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择该模组的更新文件", "", "Mods (*.pak *.utoc *.zip *.7z *.rar)"
        )
        if files:
            mod = self.current
            self.run_job(
                lambda: self.ctx.manager.add_revision(mod, [Path(p) for p in files]),
                "正在保存更新版本",
                lambda version: self.message(f"已保存 {version}，未切换当前版本。"),
            )

    def save_preset(self):
        name, ok = QInputDialog.getText(self, "保存方案", "方案名称：")
        if ok:
            self.attempt(lambda: self.ctx.manager.save_preset(name))

    def load_preset(self):
        names = list(self.ctx.store.presets)
        if not names:
            self.message("尚无保存的方案")
            return
        name, ok = QInputDialog.getItem(self, "方案预览", "选择方案：", names, editable=False)
        if ok:
            preset = self.ctx.store.presets[name]
            detail = "\n".join(
                (self.ctx.store.get_mod(i).name if self.ctx.store.get_mod(i) else f"缺失：{i}")
                + " · "
                + preset["versions"].get(i, "")
                for i in preset["ids"]
            )
            if (
                QMessageBox.question(self, "加载方案为待办", detail + "\n\n保存为待办？应用前不会改变游戏文件。")
                == QMessageBox.StandardButton.Yes
            ):
                self.attempt(lambda: self.ctx.manager.load_preset(name))
                self.refresh_table()

    def trash(self):
        mods = self.selected()
        if (
            mods
            and QMessageBox.question(
                self, "移至资源库回收目录", "先停用选中项，再将其完整目录移入 .回收站；不会永久删除。"
            )
            == QMessageBox.StandardButton.Yes
        ):
            _count, errors = self.ctx.manager.delete(mods)
            if errors:
                self.message("\n".join(errors))
            self.owner.refresh_all()

    def reveal(self):
        if self.current:
            shell.reveal(Path(self.current.folder))

    def show_preview(self, item, _previous):
        if item and self.current:
            path = Path(self.current.folder) / item.data(Qt.ItemDataRole.UserRole)
            pixmap = QPixmap(str(path))
            self.preview.setPixmap(
                pixmap.scaled(330, 210, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )

    def open_preview(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.current:
            return
        item = self.previews.currentItem()
        if item:
            from ..ui.widgets.image_preview import ImagePreviewDialog

            pixmap = QPixmap(str(Path(self.current.folder) / item.data(Qt.ItemDataRole.UserRole)))
            if not pixmap.isNull():
                self._preview_dialog = ImagePreviewDialog(pixmap, self.current.name, self)
                self._preview_dialog.show()

    def reorder_previews(self, *args):
        if not self._loading and self.current:
            self.current.previews = [
                self.previews.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.previews.count())
            ]
            self.current.save()

    def set_cover(self):
        item = self.previews.currentItem()
        if item and self.current:
            self.current.cover = item.data(Qt.ItemDataRole.UserRole)
            self.current.save()
            self.choose_mod(self.table.currentItem(), None)

    def choose_picture(self):
        if self.current:
            file, _ = QFileDialog.getOpenFileName(self, "添加预览", "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
            if file:
                self.attempt(lambda: self.ctx.manager.set_preview(self.current, Path(file)))
                self.choose_mod(self.table.currentItem(), None)

    def paste(self):
        image = QApplication.clipboard().image()
        if image.isNull():
            self.message("剪贴板没有图片，请先截图或复制图片。")
        else:
            self.owner.confirm_capture(image)

    def repair(self, fix):
        if not self.current:
            return
        mod = self.current
        if (
            fix
            and QMessageBox.question(
                self,
                "生成修复候选",
                "保留当前版本和原件；候选不会自动应用。该工具只修复特定网格问题，不能保证恢复全部功能。继续？",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        service = RepairService(self.ctx.settings)
        self.run_job(
            lambda: service.fix(mod) if fix else service.assess(mod),
            "正在修复与验证" if fix else "只读评估中",
            lambda report: text_dialog(
                self,
                "修复候选报告（未实测）" if fix else "只读评估报告",
                json.dumps(report, ensure_ascii=False, indent=2),
            ),
        )

    def history(self):
        if self.current:
            text_dialog(self, "模组元数据与历史", json.dumps(self.current.to_dict(), ensure_ascii=False, indent=2))

    def engine_info(self):
        self.attempt(
            lambda: text_dialog(
                self,
                "修复工具和数据快照",
                json.dumps(RepairService(self.ctx.settings).describe(), ensure_ascii=False, indent=2),
            )
        )

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasImage():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasImage():
            self.owner.confirm_capture(event.mimeData().imageData())
        elif event.mimeData().hasUrls():
            paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
            if (
                len(paths) == 1
                and paths[0].suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
                and self.current
            ):
                self.attempt(lambda: self.ctx.manager.set_preview(self.current, paths[0]))
                self.choose_mod(self.table.currentItem(), None)
            else:
                self.import_sources(paths)
        event.acceptProposedAction()
