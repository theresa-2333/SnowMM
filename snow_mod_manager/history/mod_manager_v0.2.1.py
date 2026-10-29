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

from translations import tr, set_language, get_translator

# --- Constants ---
APP_VERSION = "0.2.1"
AUTHOR = "theresa-2333"
UPDATE_URL = "https://github.com/theresa-2333/Snowbreak_Mod_Manager" 
AVAILABLE_LANGUAGES = ["zh_CN", "en_US"]  # Available languages: Chinese, English 

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
        self.setWindowTitle(tr("about_dialog_title"))
        
        layout = QVBoxLayout(self)
        
        title_label = QLabel(tr("message_app_info"))
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(title_label, alignment=Qt.AlignCenter)

        version_label = QLabel(tr("message_version", version=APP_VERSION))
        layout.addWidget(version_label, alignment=Qt.AlignCenter)

        author_label = QLabel(tr("message_author", author=AUTHOR))
        layout.addWidget(author_label, alignment=Qt.AlignCenter)
        
        url_label = QLabel(f'<a href="{UPDATE_URL}">{tr("button_check_update")}</a>')
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
        self.setWindowTitle(tr("category_dialog_title"))
        self.categories = categories
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("primary_category")))
        self.cat1_combo = QComboBox()
        self.cat1_combo.setEditable(True)
        self.cat1_combo.addItems(sorted(self.categories.keys()))
        self.cat1_combo.currentTextChanged.connect(self._update_cat2_combo)
        layout.addWidget(self.cat1_combo)
        layout.addWidget(QLabel(tr("secondary_category")))
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
        self.current_language = "zh_CN"  # Default language
        self._load_config()
        set_language(self.current_language)  # Set global language
        self._load_projects_data()

        self.setWindowTitle(tr("main_window_title"))
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
        self.project_tree.setHeaderLabel(tr("mod_tree_header"))
        self.project_tree.currentItemChanged.connect(self._on_item_selection_changed)
        left_layout.addWidget(self.project_tree)
        left_btn_layout = QHBoxLayout()
        add_btn = QPushButton(tr("button_add_mod"))
        add_btn.clicked.connect(self.add_project_from_file)
        delete_btn = QPushButton(tr("button_delete_mod"))
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
        """Creates the top bar for path, theme toggle, language selection, and about button."""
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel(tr("mod_storage_path")))
        self.path_edit = QLineEdit(self.storage_path)
        self.path_edit.setReadOnly(True)
        top_layout.addWidget(self.path_edit, 1) # Give stretch factor
        browse_btn = QPushButton(tr("button_browse"))
        browse_btn.clicked.connect(self.browse_storage_path)
        top_layout.addWidget(browse_btn)

        top_layout.addStretch() # Pushes following buttons to the right
        
        # Language selection
        top_layout.addWidget(QLabel(tr("language")))
        self.language_combo = QComboBox()
        self.language_combo.addItems(AVAILABLE_LANGUAGES)
        self.language_combo.setCurrentText(self.current_language)
        self.language_combo.currentTextChanged.connect(self._on_language_changed)
        top_layout.addWidget(self.language_combo)

        theme_btn = QPushButton(tr("button_toggle_theme"))
        theme_btn.clicked.connect(self._toggle_theme)
        top_layout.addWidget(theme_btn)

        about_btn = QPushButton(tr("button_about"))
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
        self.details_enable_check = QCheckBox(tr("enable_mod"))
        self.details_enable_check.stateChanged.connect(self._on_enable_changed)
        controls_layout.addWidget(self.details_enable_check)
        controls_layout.addStretch()
        change_image_btn = QPushButton(tr("button_change_image"))
        change_image_btn.clicked.connect(self.change_image)
        controls_layout.addWidget(change_image_btn)
        save_changes_btn = QPushButton(tr("button_save_changes"))
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
    
    def _on_language_changed(self, language):
        """Handle language change event."""
        if language != self.current_language and language in AVAILABLE_LANGUAGES:
            self.current_language = language
            set_language(language)
            self._save_config()
            # Refresh UI text
            self._refresh_ui_text()
            QMessageBox.information(self, tr("message_saved"), 
                                  "Language changed successfully.\nPlease restart the application for full effect.")
    
    def _refresh_ui_text(self):
        """Refresh all UI text after language change."""
        self.setWindowTitle(tr("main_window_title"))
        self.path_edit.setPlaceholderText(tr("mod_storage_path"))
        self.project_tree.setHeaderLabel(tr("mod_tree_header"))
        # Find and update buttons in left panel
        for btn in self.findChildren(QPushButton):
            if "add" in btn.text().lower() or "添加" in btn.text():
                btn.setText(tr("button_add_mod"))
            elif "delete" in btn.text().lower() or "删除" in btn.text():
                btn.setText(tr("button_delete_mod"))
            elif "browse" in btn.text().lower() or "更改" in btn.text():
                btn.setText(tr("button_browse"))
            elif "theme" in btn.text().lower() or "主题" in btn.text():
                btn.setText(tr("button_toggle_theme"))
            elif "about" in btn.text().lower() or "关于" in btn.text():
                btn.setText(tr("button_about"))
            elif "change" in btn.text().lower() or "更换" in btn.text():
                btn.setText(tr("button_change_image"))
            elif "save" in btn.text().lower() or "保存" in btn.text():
                btn.setText(tr("button_save_changes"))
        
        self.details_enable_check.setText(tr("enable_mod"))
        
    # --- Data and Config Management ---
    def _load_projects_data(self):
        if not os.path.exists(PROJECTS_FILE):
            self.projects = []
            return
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                self.projects = json.load(f)
        except (json.JSONDecodeError, TypeError):
            QMessageBox.critical(self, tr("error_title"), tr("error_load_projects"))
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
                    self.current_language = config.get("language", "zh_CN")  # Load language
            except (json.JSONDecodeError, TypeError):
                pass

    def _save_config(self):
        config = {
            "storage_path": self.storage_path,
            "theme": self.current_theme, # Save theme
            "language": self.current_language  # Save language
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
            cat1_name = project_data.get("category1", tr("tree_uncategorized"))
            cat2_name = project_data.get("category2", tr("tree_default"))
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
            self.details_image.setText(tr("no_image"))
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
        path = QFileDialog.getExistingDirectory(self, tr("select_folder_title"), self.storage_path)
        if path and path != self.storage_path:
            self.storage_path = path
            self.path_edit.setText(path)
            self._save_config()
            QMessageBox.information(self, tr("message_path_updated"), 
                                  tr("message_path_updated_desc", path=path))
            
    def add_project_from_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, tr("select_mod_file_title"), "", tr("file_filter_all"))
        if not file_path: return
        categories = defaultdict(set)
        for p in self.projects:
            if "category1" in p and "category2" in p:
                categories[p["category1"]].add(p["category2"])
        dialog = CategorySelectionDialog(categories, self)
        if not dialog.exec_(): return
        cat1, cat2 = dialog.get_selected_categories()
        if not cat1 or not cat2:
            QMessageBox.warning(self, tr("warning_invalid_category"), 
                              tr("warning_invalid_category_desc"))
            return
        file_name = os.path.basename(file_path)
        dest_dir = os.path.join(self.storage_path, cat1, cat2)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, file_name)
        if os.path.exists(dest_path) or os.path.exists(dest_path + DISABLED_EXT):
            QMessageBox.warning(self, tr("warning_file_exists"), 
                              tr("warning_file_exists_desc", filename=file_name))
            return
        try:
            shutil.copy(file_path, dest_path)
        except OSError as e:
            QMessageBox.critical(self, tr("error_copy_file"), 
                               tr("error_copy_file_desc", error=str(e)))
            return
        project_data = {
            "name": os.path.splitext(file_name)[0], "path": dest_path,
            "note": tr("original_file") + f" {file_name}", "image_path": "",
            "category1": cat1, "category2": cat2
        }
        self.projects.append(project_data)
        self.save_projects()
        self._populate_tree()
        
    def delete_project(self):
        current_item = self.project_tree.currentItem()
        if not current_item or current_item.data(0, Qt.UserRole) is None:
            QMessageBox.warning(self, tr("warning_title"), tr("warning_select_mod"))
            return
        project_index = current_item.data(0, Qt.UserRole)
        project_data = self.projects[project_index]
        reply = QMessageBox.question(self, tr("confirm_delete"),
            tr("confirm_delete_desc", name=project_data['name']),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            file_path = project_data.get('path', '')
            enabled_path = file_path.replace(DISABLED_EXT, '')
            disabled_path = enabled_path + DISABLED_EXT
            try:
                if os.path.exists(enabled_path): os.remove(enabled_path)
                if os.path.exists(disabled_path): os.remove(disabled_path)
            except OSError as e:
                QMessageBox.critical(self, tr("error_title"), 
                                   tr("error_delete_file", error=str(e)))
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
        QMessageBox.information(self, tr("message_saved"), tr("message_saved_desc"))

    def _on_enable_changed(self, state):
        file_path = self.details_frame.property("current_project_path")
        if not file_path: return
        self.toggle_project_enabled(file_path, bool(state))
        project_index = self.project_tree.currentItem().data(0, Qt.UserRole)
        self._update_details_panel(self.projects[project_index])
        
    def change_image(self):
        current_item = self.project_tree.currentItem()
        if not current_item or current_item.data(0, Qt.UserRole) is None:
            QMessageBox.warning(self, tr("warning_title"), tr("warning_select_before_image"))
            return
        file_path, _ = QFileDialog.getOpenFileName(self, tr("select_image_title"), "", tr("file_filter_images"))
        if not file_path: return
        image_name = os.path.basename(file_path)
        dest_path = os.path.join(IMAGES_DIR, image_name)
        try:
            shutil.copyfile(file_path, dest_path)
        except OSError as e:
            QMessageBox.critical(self, tr("error_copy_image"), 
                               tr("error_copy_image_desc", error=str(e)))
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
            QMessageBox.critical(None, tr("error_title"), 
                               tr("error_rename_file", error=str(e)))

# --- Application Entry Point ---
def main():
    app = QApplication(sys.argv)
    window = ProjectManagerWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
