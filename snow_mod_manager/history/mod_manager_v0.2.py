import os
import sys
import json
import shutil
import webbrowser
from collections import defaultdict
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QLabel,
    QCheckBox, QPushButton, QFileDialog, QMessageBox, QFrame,
    QLineEdit, QSplitter, QDialog, QComboBox, QDialogButtonBox,
    QSizePolicy
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon

# --- Constants ---
APP_VERSION = "0.2"
AUTHOR = "Gemini & theresa-2333"
UPDATE_URL = "https://github.com/theresa-2333/Snowbreak_Mod_Manager" # 请替换为您的项目地址

# --- Configuration ---
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".snowbreak_mod_manager")
os.makedirs(CONFIG_DIR, exist_ok=True)
PROJECTS_FILE = os.path.join(CONFIG_DIR, "projects.json")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
IMAGES_DIR = os.path.join(CONFIG_DIR, "images")
os.makedirs(IMAGES_DIR, exist_ok=True)
DISABLED_EXT = ".disabled"

# --- Light Theme (QSS) ---
LIGHT_STYLESHEET = """
QWidget {{
    font-family: 'Microsoft YaHei UI', 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
    color: #1c1c1c;
}}
QMainWindow {{
    background-color: #f3f3f3;
}}
QFrame#MainFrame, QFrame#DetailsFrame {{
    background-color: #ffffff;
    border-radius: 8px;
    padding: 5px;
}}
QLabel#DetailsImageLabel {{
    border: 1px solid #e0e0e0;
    border-radius: 6px;
    background-color: #f8f8f8;
}}
QLineEdit, QTextEdit {{
    background-color: #ffffff;
    border: 1px solid #dcdcdc;
    border-radius: 4px;
    padding: 6px;
}}
QLineEdit:focus, QTextEdit:focus {{
    border-color: #0078d4;
}}
QPushButton {{
    background-color: #f0f0f0;
    border: 1px solid #dcdcdc;
    border-radius: 4px;
    padding: 8px 12px;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: #e6e6e6;
    border-color: #c0c0c0;
}}
QPushButton:pressed {{
    background-color: #dcdcdc;
}}
QPushButton#DeleteButton {{
    background-color: #e81123;
    color: white;
    border: none;
}}
QPushButton#DeleteButton:hover {{
    background-color: #c20c1e;
}}
QCheckBox::indicator:checked {{
    background-color: #0078d4;
    border-color: #0078d4;
    image: url({check_svg_path});
}}
QTreeWidget {{
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    background-color: #fafafa;
}}
QTreeWidget::item:selected {{
    background-color: #cce4f7;
    color: #1c1c1c;
}}
QHeaderView::section {{
    background-color: #f3f3f3;
    border: 1px solid #e0e0e0;
}}
"""

# --- Dark Theme (QSS) ---
DARK_STYLESHEET = """
QWidget {{
    font-family: 'Microsoft YaHei UI', 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
    color: #e0e0e0;
}}
QMainWindow {{
    background-color: #2d2d2d;
}}
QFrame#MainFrame, QFrame#DetailsFrame {{
    background-color: #3c3c3c;
    border-radius: 8px;
    padding: 5px;
}}
QLabel#DetailsImageLabel {{
    border: 1px solid #555;
    border-radius: 6px;
    background-color: #2d2d2d;
}}
QLineEdit, QTextEdit {{
    background-color: #2d2d2d;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 6px;
    color: #e0e0e0;
}}
QLineEdit:focus, QTextEdit:focus {{
    border-color: #0078d4;
}}
QPushButton {{
    background-color: #555;
    border: 1px solid #666;
    border-radius: 4px;
    padding: 8px 12px;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: #666;
    border-color: #777;
}}
QPushButton:pressed {{
    background-color: #444;
}}
QPushButton#DeleteButton {{
    background-color: #c00;
    color: white;
    border: none;
}}
QPushButton#DeleteButton:hover {{
    background-color: #e00;
}}
QCheckBox::indicator:checked {{
    background-color: #0078d4;
    border-color: #0078d4;
    image: url({check_svg_path});
}}
QTreeWidget {{
    border: 1px solid #555;
    border-radius: 8px;
    background-color: #2d2d2d;
}}
QTreeWidget::item:selected {{
    background-color: #0078d4;
    color: #ffffff;
}}
QHeaderView::section {{
    background-color: #3c3c3c;
    border: 1px solid #555;
    color: #e0e0e0;
}}
QDialog {{
    background-color: #3c3c3c;
}}
"""

# --- Helper Functions and Custom Widgets ---

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class ImageLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumSize(1, 1)
        self._pixmap = QPixmap()

    def setPixmap(self, pixmap):
        self._pixmap = pixmap
        self._update_scaled_pixmap()

    def resizeEvent(self, event):
        self._update_scaled_pixmap()
        super().resizeEvent(event)

    def _update_scaled_pixmap(self):
        if self._pixmap.isNull():
            super().setPixmap(QPixmap())
            return
        scaled_pixmap = self._pixmap.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        super().setPixmap(scaled_pixmap)

# --- Dialogs ---

class AboutDialog(QDialog):
    """'About' dialog to show application information."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 Mod 管理器")
        
        layout = QVBoxLayout(self)
        
        title_label = QLabel(f"Snowbreak Mod 管理器")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title_label, alignment=Qt.AlignCenter)

        version_label = QLabel(f"版本: {APP_VERSION}")
        layout.addWidget(version_label, alignment=Qt.AlignCenter)

        author_label = QLabel(f"作者: {AUTHOR}")
        layout.addWidget(author_label, alignment=Qt.AlignCenter)
        
        url_label = QLabel(f'<a href="{UPDATE_URL}">检查更新或反馈</a>')
        url_label.setOpenExternalLinks(True)
        layout.addWidget(url_label, alignment=Qt.AlignCenter)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        
        self.setMinimumWidth(350)
        self.setFixedSize(self.sizeHint())


class CategorySelectionDialog(QDialog):
    def __init__(self, categories, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置 Mod 分类")
        self.categories = categories
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("一级分类 (角色名):"))
        self.cat1_combo = QComboBox()
        self.cat1_combo.setEditable(True)
        self.cat1_combo.addItems(sorted(self.categories.keys()))
        self.cat1_combo.currentTextChanged.connect(self._update_cat2_combo)
        layout.addWidget(self.cat1_combo)
        layout.addWidget(QLabel("二级分类 (角色皮肤):"))
        self.cat2_combo = QComboBox()
        self.cat2_combo.setEditable(True)
        layout.addWidget(self.cat2_combo)
        self._update_cat2_combo(self.cat1_combo.currentText())
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.setMinimumWidth(300)

    def _update_cat2_combo(self, text):
        self.cat2_combo.clear()
        if text in self.categories:
            self.cat2_combo.addItems(sorted(self.categories[text]))

    def get_selected_categories(self):
        return self.cat1_combo.currentText().strip(), self.cat2_combo.currentText().strip()

# --- Main Application Window ---

class ProjectManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.storage_path = os.path.join(os.path.expanduser("~"), "MyModProjects")
        self.projects = []
        self.current_theme = "light" # Default theme
        self._load_config()
        self._load_projects_data()

        self.setWindowTitle("Snowbreak Mod 管理器")
        self.resize(1280, 720)
        self.setWindowIcon(QIcon(resource_path("img/cbjq.ico")))
        
        self._setup_ui()
        self._apply_theme() # Apply theme on startup
        self._populate_tree()
        self._update_details_panel(None)

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_frame = QFrame(objectName="MainFrame")
        main_layout.addWidget(main_frame)
        content_layout = QVBoxLayout(main_frame)
        content_layout.setSpacing(10)
        self._setup_top_bar(content_layout)
        splitter = QSplitter(Qt.Horizontal)
        content_layout.addWidget(splitter)
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabel("Mod 分类")
        self.project_tree.currentItemChanged.connect(self._on_item_selection_changed)
        left_layout.addWidget(self.project_tree)
        left_btn_layout = QHBoxLayout()
        add_btn = QPushButton("添加新 Mod...")
        add_btn.clicked.connect(self.add_project_from_file)
        delete_btn = QPushButton("删除选中 Mod")
        delete_btn.setObjectName("DeleteButton")
        delete_btn.clicked.connect(self.delete_project)
        left_btn_layout.addStretch()
        left_btn_layout.addWidget(add_btn)
        left_btn_layout.addWidget(delete_btn)
        left_layout.addLayout(left_btn_layout)
        self._setup_details_panel()
        splitter.addWidget(left_panel)
        splitter.addWidget(self.details_frame)
        splitter.setSizes([350, 930])

    def _setup_top_bar(self, parent_layout):
        """Creates the top bar for path, theme toggle, and about button."""
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Mod 存放路径:"))
        self.path_edit = QLineEdit(self.storage_path)
        self.path_edit.setReadOnly(True)
        top_layout.addWidget(self.path_edit, 1) # Give stretch factor
        browse_btn = QPushButton("更改...")
        browse_btn.clicked.connect(self.browse_storage_path)
        top_layout.addWidget(browse_btn)

        top_layout.addStretch() # Pushes following buttons to the right

        theme_btn = QPushButton("切换主题")
        theme_btn.clicked.connect(self._toggle_theme)
        top_layout.addWidget(theme_btn)

        about_btn = QPushButton("关于")
        about_btn.clicked.connect(self._show_about_dialog)
        top_layout.addWidget(about_btn)

        parent_layout.addLayout(top_layout)

    def _setup_details_panel(self):
        self.details_frame = QFrame(objectName="DetailsFrame")
        details_layout = QVBoxLayout(self.details_frame)
        self.details_image = ImageLabel(alignment=Qt.AlignCenter)
        self.details_image.setObjectName("DetailsImageLabel")
        self.details_image.setMinimumHeight(300)
        self.details_image.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        details_layout.addWidget(self.details_image, 1)
        self.details_name_edit = QLineEdit()
        self.details_name_edit.setStyleSheet("font-size: 14pt; font-weight: bold;")
        details_layout.addWidget(self.details_name_edit)
        self.details_note_edit = QTextEdit()
        self.details_note_edit.setMaximumHeight(100)
        details_layout.addWidget(self.details_note_edit)
        controls_layout = QHBoxLayout()
        self.details_enable_check = QCheckBox("启用 Mod")
        self.details_enable_check.stateChanged.connect(self._on_enable_changed)
        controls_layout.addWidget(self.details_enable_check)
        controls_layout.addStretch()
        change_image_btn = QPushButton("更换图片")
        change_image_btn.clicked.connect(self.change_image)
        controls_layout.addWidget(change_image_btn)
        save_changes_btn = QPushButton("保存更改")
        save_changes_btn.clicked.connect(self.save_current_project_details)
        controls_layout.addWidget(save_changes_btn)
        details_layout.addLayout(controls_layout)
        self.details_frame.setVisible(False)
    
    # --- Theme Management ---
    def _apply_theme(self):
        """Applies the current theme's stylesheet to the application."""
        # 1. 根据当前主题选择正确的样式表字符串
        stylesheet = LIGHT_STYLESHEET if self.current_theme == "light" else DARK_STYLESHEET
        
        # 2. 获取图标资源的路径
        check_svg_path = resource_path("img/check.svg").replace("\\", "/")
        
        # 3. 使用 .format() 方法填充路径，并创建 final_stylesheet 变量
        #    (这很可能是您当前代码中缺失或错误的一行)
        final_stylesheet = stylesheet.format(check_svg_path=check_svg_path)
        
        # 4. 使用刚刚创建好的 final_stylesheet 变量来设置样式
        self.setStyleSheet(final_stylesheet)

    def _toggle_theme(self):
        """Switches between light and dark themes and saves the choice."""
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self._apply_theme()
        self._save_config()

    def _show_about_dialog(self):
        """Displays the 'About' dialog."""
        dialog = AboutDialog(self)
        dialog.exec_()
        
    # --- Data and Config Management ---
    def _load_projects_data(self):
        if not os.path.exists(PROJECTS_FILE):
            self.projects = []
            return
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                self.projects = json.load(f)
        except (json.JSONDecodeError, TypeError):
            QMessageBox.critical(self, "错误", "无法加载 projects.json，文件可能已损坏。")
            self.projects = []

    def save_projects(self):
        with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.projects, f, ensure_ascii=False, indent=2)

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.storage_path = config.get("storage_path", self.storage_path)
                    self.current_theme = config.get("theme", "light") # Load theme
            except (json.JSONDecodeError, TypeError):
                pass

    def _save_config(self):
        config = {
            "storage_path": self.storage_path,
            "theme": self.current_theme # Save theme
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

    def closeEvent(self, event):
        self.save_projects()
        event.accept()

    # --- Core Functionality (Remaining methods are mostly unchanged) ---
    def _populate_tree(self):
        self.project_tree.clear()
        category_items = {}
        for i, project_data in enumerate(self.projects):
            cat1_name = project_data.get("category1", "未分类")
            cat2_name = project_data.get("category2", "默认")
            if cat1_name not in category_items:
                cat1_item = QTreeWidgetItem(self.project_tree, [cat1_name])
                category_items[cat1_name] = cat1_item
            cat1_item = category_items[cat1_name]
            cat2_key = f"{cat1_name}/{cat2_name}"
            if cat2_key not in category_items:
                cat2_item = QTreeWidgetItem(cat1_item, [cat2_name])
                category_items[cat2_key] = cat2_item
            cat2_item = category_items[cat2_key]
            mod_item = QTreeWidgetItem(cat2_item, [project_data["name"]])
            mod_item.setData(0, Qt.UserRole, i)
        self.project_tree.expandAll()

    def _on_item_selection_changed(self, current_item, previous_item):
        if not current_item:
            self._update_details_panel(None)
            return
        project_index = current_item.data(0, Qt.UserRole)
        if project_index is not None:
            self._update_details_panel(self.projects[project_index])
        else:
            self._update_details_panel(None)

    def _update_details_panel(self, project_data):
        if project_data is None:
            self.details_frame.setVisible(False)
            return
        self.details_frame.setVisible(True)
        self.details_frame.setProperty("current_project_path", project_data.get("path"))
        for widget in [self.details_name_edit, self.details_note_edit, self.details_enable_check]:
            widget.blockSignals(True)
        self.details_name_edit.setText(project_data.get("name", ""))
        self.details_note_edit.setPlainText(project_data.get("note", ""))
        image_path = project_data.get("image_path")
        if image_path and os.path.exists(image_path):
            self.details_image.setPixmap(QPixmap(image_path))
        else:
            self.details_image.setPixmap(QPixmap())
            self.details_image.setText("无图片")
        file_path = project_data.get("path", "")
        enabled_path = file_path.replace(DISABLED_EXT, '')
        disabled_path = enabled_path + DISABLED_EXT
        is_missing = not os.path.exists(enabled_path) and not os.path.exists(disabled_path)
        self.details_enable_check.setEnabled(not is_missing)
        if is_missing:
            self.details_enable_check.setChecked(False)
            self.details_name_edit.setStyleSheet("color: red; font-size: 14pt; font-weight: bold;")
        else:
            self.details_name_edit.setStyleSheet("font-size: 14pt; font-weight: bold;")
            is_disabled = os.path.exists(disabled_path)
            self.details_enable_check.setChecked(not is_disabled)
        for widget in [self.details_name_edit, self.details_note_edit, self.details_enable_check]:
            widget.blockSignals(False)

    def browse_storage_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择存放路径", self.storage_path)
        if path and path != self.storage_path:
            self.storage_path = path
            self.path_edit.setText(path)
            self._save_config()
            QMessageBox.information(self, "路径已更新", f"新的 Mod 存放路径已设置为:\n{path}")
            
    def add_project_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 Mod 文件", "", "所有文件 (*)")
        if not file_path: return
        categories = defaultdict(set)
        for p in self.projects:
            if "category1" in p and "category2" in p:
                categories[p["category1"]].add(p["category2"])
        dialog = CategorySelectionDialog(categories, self)
        if not dialog.exec_(): return
        cat1, cat2 = dialog.get_selected_categories()
        if not cat1 or not cat2:
            QMessageBox.warning(self, "分类无效", "必须提供一级和二级分类。")
            return
        file_name = os.path.basename(file_path)
        dest_dir = os.path.join(self.storage_path, cat1, cat2)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, file_name)
        if os.path.exists(dest_path) or os.path.exists(dest_path + DISABLED_EXT):
            QMessageBox.warning(self, "文件已存在", f"名为 '{file_name}' 的文件已存在于目标分类中。")
            return
        try:
            shutil.copy(file_path, dest_path)
        except OSError as e:
            QMessageBox.critical(self, "文件复制失败", f"无法复制文件: {e}")
            return
        project_data = {
            "name": os.path.splitext(file_name)[0], "path": dest_path,
            "note": f"原始文件: {file_name}", "image_path": "",
            "category1": cat1, "category2": cat2
        }
        self.projects.append(project_data)
        self.save_projects()
        self._populate_tree()
        
    def delete_project(self):
        current_item = self.project_tree.currentItem()
        if not current_item or current_item.data(0, Qt.UserRole) is None:
            QMessageBox.warning(self, "警告", "请选择一个要删除的 Mod 项目。")
            return
        project_index = current_item.data(0, Qt.UserRole)
        project_data = self.projects[project_index]
        reply = QMessageBox.question(self, "确认删除",
            f"确定要永久删除 Mod '{project_data['name']}' 吗？\n这将从磁盘删除文件，此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            file_path = project_data.get('path', '')
            enabled_path = file_path.replace(DISABLED_EXT, '')
            disabled_path = enabled_path + DISABLED_EXT
            try:
                if os.path.exists(enabled_path): os.remove(enabled_path)
                if os.path.exists(disabled_path): os.remove(disabled_path)
            except OSError as e:
                QMessageBox.critical(self, "错误", f"删除文件失败: {e}")
                return
            self.projects.pop(project_index)
            self.save_projects()
            self._populate_tree()
            self._update_details_panel(None)

    def save_current_project_details(self):
        current_item = self.project_tree.currentItem()
        if not current_item or current_item.data(0, Qt.UserRole) is None: return
        project_index = current_item.data(0, Qt.UserRole)
        project_data = self.projects[project_index]
        project_data["name"] = self.details_name_edit.text()
        project_data["note"] = self.details_note_edit.toPlainText()
        self.save_projects()
        current_item.setText(0, project_data["name"])
        QMessageBox.information(self, "已保存", "更改已成功保存。")

    def _on_enable_changed(self, state):
        file_path = self.details_frame.property("current_project_path")
        if not file_path: return
        self.toggle_project_enabled(file_path, bool(state))
        project_index = self.project_tree.currentItem().data(0, Qt.UserRole)
        self._update_details_panel(self.projects[project_index])
        
    def change_image(self):
        current_item = self.project_tree.currentItem()
        if not current_item or current_item.data(0, Qt.UserRole) is None:
            QMessageBox.warning(self, "警告", "请先选择一个 Mod。")
            return
        file_path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "图片文件 (*.png *.jpg *.jpeg)")
        if not file_path: return
        image_name = os.path.basename(file_path)
        dest_path = os.path.join(IMAGES_DIR, image_name)
        try:
            shutil.copyfile(file_path, dest_path)
        except OSError as e:
            QMessageBox.critical(self, "图片复制失败", f"无法复制图片: {e}")
            return
        project_index = current_item.data(0, Qt.UserRole)
        project_data = self.projects[project_index]
        project_data["image_path"] = dest_path
        self._update_details_panel(project_data)
        
    @staticmethod
    def toggle_project_enabled(file_path, enable):
        if not file_path: return
        enabled_path = file_path.replace(DISABLED_EXT, '')
        disabled_path = enabled_path + DISABLED_EXT
        try:
            if enable and os.path.exists(disabled_path):
                os.rename(disabled_path, enabled_path)
            elif not enable and os.path.exists(enabled_path):
                os.rename(enabled_path, disabled_path)
        except OSError as e:
            QMessageBox.critical(None, "错误", f"重命名文件时出错: {e}")

# --- Application Entry Point ---
def main():
    app = QApplication(sys.argv)
    window = ProjectManagerWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
