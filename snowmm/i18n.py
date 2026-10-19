"""Tiny translation layer (Chinese / English) for the whole user interface."""

from __future__ import annotations

import json
from functools import lru_cache

from .core import paths

LANGUAGES = ("zh_CN", "en_US")
LANGUAGE_LABELS = {"zh_CN": "简体中文", "en_US": "English"}

DEFAULT_LANGUAGE = "zh_CN"

TRANSLATIONS: dict[str, dict[str, str]] = {
    "zh_CN": {
        "app_title": "SnowMM · 尘白禁区 Mod 管理器",
        "app_tagline": "现代化 Mod 管理器",
        "button_import_folder": "导入文件夹",
        "preview_click_hint": "点击放大预览；使用下方按钮更换图片",
        "preview_fit": "适应窗口",
        "preview_controls": "滚轮缩放 · 拖动平移 · Esc 关闭",
        "preview_close": "关闭",
        "toast_import_empty": "没有找到可导入的 pak 或 utoc 文件，请选择模组文件或包含模组的文件夹。",
        # navigation
        "nav_characters": "角色概览",
        "nav_mods": "模组总览",
        "nav_issues": "冲突检查",
        "nav_settings": "设置",
        "page_characters_sub": "浏览角色，查看与管理每个角色的模组",
        "page_mods_sub": "所有模组的统一列表，支持批量操作",
        "page_issues_sub": "检测冲突、缺失文件与命名问题",
        "page_settings_sub": "路径、外观、语言与数据管理",
        # search / filters
        "search_characters": "搜索角色...",
        "search_mods": "搜索模组...",
        "filter_favorites": "收藏",
        "filter_with_mods": "有模组",
        "filter_show_all": "显示全部角色",
        "filter_show_all_hint": "显示尚未添加模组的角色",
        "filter_element": "属性",
        "filter_all": "全部",
        "role_dps": "输出",
        "role_buffer": "增伤辅助",
        "role_support": "功能辅助",
        "label_armors": "同角色装甲",
        "label_switch_armor": "切换装甲",
        "label_full_name": "角色全名",
        "hint_full_name": "格式为「角色-装甲」，例如 凯茜娅-狂诗",
        "label_element": "属性",
        "label_role": "定位",
        "button_enable_only": "只启用选中",
        "dialog_character_hint": "角色条目以「角色-装甲」为唯一名称，模组目录中的文件夹名也要一致。",
        "dialog_character_name_hint": "凯茜娅-狂诗",
        "dialog_character_name_locked": "角色全名是角色库与模组文件夹的唯一标识，不可修改。",
        "label_paste_hint": "支持直接粘贴剪贴板中的图片",
        "label_settings_art": "角色图片库",
        "settings_art_hint": "内置的 {count} 个角色立绘，每个属性一个子文件夹，文件名为「角色-装甲」。",
        "warning_pick_character_first": "请先进入某个角色的二级页面，再添加模组。",
        "button_flatten": "转换目录结构",
        "settings_flatten_hint": "把旧的「角色/装甲/服装」三层目录整理成「角色-装甲」单层目录",
        "toast_flattened": "已整理 {count} 个文件",
        "toast_flatten_none": "目录结构已经是新的，无需转换",
        "status_all": "全部",
        "status_enabled": "已启用",
        "status_disabled": "已禁用",
        "status_missing": "文件缺失",
        # stats
        "stat_mods": "模组",
        "stat_enabled": "已启用",
        "stat_characters": "角色",
        "stat_missing": "缺失",
        # buttons
        "button_refresh": "刷新",
        "button_rescan": "扫描目录",
        "button_launch": "启动游戏",
        "button_open_folder": "打开目录",
        "button_add_mod": "添加模组",
        "button_import": "导入",
        "button_enable": "启用",
        "button_disable": "禁用",
        "button_enable_all": "全部启用",
        "button_disable_all": "全部禁用",
        "button_delete": "删除",
        "button_save": "保存",
        "button_cancel": "取消",
        "button_browse": "浏览...",
        "button_edit": "编辑",
        "button_open_link": "打开链接",
        "button_choose_image": "选择图片",
        "button_paste_image": "粘贴图片",
        "button_back": "返回",
        "button_copy_path": "复制路径",
        "button_backup": "备份数据",
        "button_migrate": "迁移旧版数据",
        "button_toggle_theme": "切换主题",
        "button_disable_character": "禁用该角色全部模组",
        # labels
        "label_character": "角色",
        "label_name": "名称",
        "label_author": "作者",
        "label_source": "来源链接",
        "label_note": "备注",
        "label_preview": "预览图",
        "label_size": "大小",
        "label_mods": "模组",
        "label_none": "无",
        "label_unknown": "未知",
        "label_settings_storage": "模组目录",
        "label_settings_game": "游戏程序",
        "label_theme": "主题",
        "label_language": "语言",
        "label_behavior": "行为",
        "label_data": "数据",
        "label_about": "关于",
        "label_enabled_of": "{enabled} / {total} 已启用",
        "label_files": "文件",
        # columns
        "column_enabled": "启用",
        "column_name": "模组名称",
        "column_character": "角色",
        "column_author": "作者",
        "column_added": "添加时间",
        "column_size": "大小",
        "column_note": "备注",
        # tabs
        "tab_mods": "模组",
        "tab_folders": "文件夹",
        # empty states
        "empty_characters_title": "还没有任何模组",
        "empty_characters_desc": "先在设置里选择模组目录，然后添加或扫描你的模组。",
        "empty_mods_title": "该角色暂无模组",
        "empty_mods_desc": "点击「添加模组」把文件复制进来，或直接拖拽到窗口。",
        "empty_results_title": "没有匹配的结果",
        "empty_results_desc": "试试其他关键词或筛选条件。",
        "empty_issues_title": "一切正常",
        "empty_issues_desc": "未发现冲突或缺失文件。",
        # toasts and messages
        "toast_imported": "已导入 {count} 个模组",
        "toast_scan_done": "扫描完成，新增 {count} 个模组",
        "toast_scan_none": "扫描完成，没有发现新模组",
        "toast_changed": "已更新 {count} 个模组",
        "toast_copied": "已复制到剪贴板",
        "toast_pasted": "已粘贴剪贴板中的图片",
        "toast_paste_empty": "剪贴板里没有图片",
        "toast_backup_done": "备份已保存到 {path}",
        "toast_migrated": "已迁移 {count} 个旧版模组",
        "warning_storage_missing_desc": "请先在「设置」中选择游戏的 Game/Content/Paks/mods 目录。",
        "warning_launch_missing_desc": "请先在「设置」中选择游戏的可执行文件。",
        "warning_select_first": "请先选择至少一个模组。",
        "warning_confirm_delete_title": "确认删除",
        "warning_confirm_delete_body": "将删除 {count} 个模组记录及其文件，此操作不可撤销。",
        "warning_import_failed": "导入失败：{detail}",
        "dialog_import_title": "添加模组",
        "dialog_import_hint": "文件会被复制到该角色的模组文件夹",
        "dialog_import_files": "选择的文件",
        "dialog_character_edit": "编辑角色资料",
        "dialog_character_new": "新建角色",
        "dialog_about_body": "SnowMM 是为《尘白禁区》打造的现代化 Mod 管理器。",
        # issues
        "issue_multi_enabled": "「{character}」同时启用了 {count} 个模组",
        "issue_multi_enabled_desc": "同一角色启用多个模组时可能互相覆盖，建议只保留一个。",
        "issue_missing_file": "文件缺失：{file}",
        "issue_missing_file_desc": "记录指向的文件已不存在，可能被手动移动或删除。",
        "issue_unknown_character": "「{character}」不在角色名单中（{count} 个模组）",
        "issue_unknown_character_desc": "文件夹名不是角色全名，请把文件移到正确的角色文件夹，或删除记录。",
        "issue_duplicate_path": "重复记录：{file}",
        "issue_duplicate_path_desc": "多个记录指向同一个文件。",
        "issue_disable_others": "只保留一个",
        "issue_remove_record": "删除记录",
        "issue_reveal": "打开所在目录",
        "issue_count": "{count} 项",
        # settings
        "settings_storage_hint": "通常为 游戏根目录/Game/Content/Paks/mods",
        "settings_game_hint": "用于「启动游戏」按钮，可留空",
        "settings_theme_system": "跟随系统",
        "settings_theme_light": "浅色",
        "settings_theme_dark": "深色",
        "settings_hide_empty": "隐藏没有模组的角色",
        "settings_confirm_delete": "删除前确认",
        "settings_open_data": "打开数据目录",
        "settings_data_hint": "数据库文件：{path}",
        "settings_rescan_hint": "扫描模组目录，把已存在的文件收录进来",
        "settings_migrate_hint": "从旧版 0.2.x 配置目录导入模组记录",
        "settings_language_hint": "切换后立即生效",
        "settings_about_body": "版本 {version} · 作者 theresa-2333",
        "settings_stats": "共 {mods} 个模组 · {characters} 个角色",
        # misc
    },
    "en_US": {
        "app_title": "SnowMM · Snowbreak Mod Manager",
        "app_tagline": "A modern mod manager",
        "button_import_folder": "Import folder",
        "preview_click_hint": "Click to enlarge; use the buttons below to change the image",
        "preview_fit": "Fit to window",
        "preview_controls": "Scroll to zoom · Drag to pan · Esc to close",
        "preview_close": "Close",
        "toast_import_empty": "No pak or utoc files found. Choose a mod file or a folder containing mods.",
        "nav_characters": "Characters",
        "nav_mods": "All mods",
        "nav_issues": "Health check",
        "nav_settings": "Settings",
        "page_characters_sub": "Browse characters and manage their mods",
        "page_mods_sub": "Every mod in one table with bulk actions",
        "page_issues_sub": "Conflicts, missing files and naming problems",
        "page_settings_sub": "Paths, appearance, language and data",
        "search_characters": "Search characters...",
        "search_mods": "Search mods...",
        "filter_favorites": "Favorites",
        "filter_with_mods": "With mods",
        "filter_show_all": "Show all characters",
        "filter_show_all_hint": "Include characters without mods",
        "filter_element": "Element",
        "filter_all": "All",
        "role_dps": "Damage",
        "role_buffer": "Damage buff",
        "role_support": "Utility",
        "label_armors": "Armors",
        "label_switch_armor": "Switch armor",
        "label_full_name": "Full name",
        "hint_full_name": "Format is character-armor, e.g. 凯茜娅-狂诗",
        "label_element": "Element",
        "label_role": "Role",
        "button_enable_only": "Enable selection only",
        "dialog_character_hint": "Keyed by full name (character-armor), matching the folder name on disk.",
        "dialog_character_name_hint": "凯茜娅-狂诗",
        "dialog_character_name_locked": "The full name keys the roster and the mods folder, so it cannot change.",
        "label_paste_hint": "You can paste an image straight from the clipboard",
        "label_settings_art": "Character art library",
        "settings_art_hint": "{count} characters ship with the app - one folder per element, files named char-armor.",
        "warning_pick_character_first": "Open a character page first, then add mods from there.",
        "button_flatten": "Convert folder layout",
        "settings_flatten_hint": "Turn the old character/armor/outfit tree into flat character-armor folders",
        "toast_flattened": "Reorganised {count} files",
        "toast_flatten_none": "Folder layout is already up to date",
        "status_all": "All",
        "status_enabled": "Enabled",
        "status_disabled": "Disabled",
        "status_missing": "Missing files",
        "stat_mods": "Mods",
        "stat_enabled": "Enabled",
        "stat_characters": "Characters",
        "stat_missing": "Missing",
        "button_refresh": "Refresh",
        "button_rescan": "Scan folder",
        "button_launch": "Launch game",
        "button_open_folder": "Open folder",
        "button_add_mod": "Add mod",
        "button_import": "Import",
        "button_enable": "Enable",
        "button_disable": "Disable",
        "button_enable_all": "Enable all",
        "button_disable_all": "Disable all",
        "button_delete": "Delete",
        "button_save": "Save",
        "button_cancel": "Cancel",
        "button_browse": "Browse...",
        "button_edit": "Edit",
        "button_open_link": "Open link",
        "button_choose_image": "Choose image",
        "button_paste_image": "Paste image",
        "button_back": "Back",
        "button_copy_path": "Copy path",
        "button_backup": "Backup data",
        "button_migrate": "Migrate v0.2.x data",
        "button_toggle_theme": "Toggle theme",
        "button_disable_character": "Disable character mods",
        "label_character": "Character",
        "label_name": "Name",
        "label_author": "Author",
        "label_source": "Source link",
        "label_note": "Notes",
        "label_preview": "Preview",
        "label_size": "Size",
        "label_mods": "Mods",
        "label_none": "None",
        "label_unknown": "Unknown",
        "label_settings_storage": "Mods folder",
        "label_settings_game": "Game executable",
        "label_theme": "Theme",
        "label_language": "Language",
        "label_behavior": "Behaviour",
        "label_data": "Data",
        "label_about": "About",
        "label_enabled_of": "{enabled} / {total} enabled",
        "label_files": "Files",
        "column_enabled": "On",
        "column_name": "Mod",
        "column_character": "Character",
        "column_author": "Author",
        "column_added": "Added",
        "column_size": "Size",
        "column_note": "Notes",
        "tab_mods": "Mods",
        "tab_folders": "Folders",
        "empty_characters_title": "No mods yet",
        "empty_characters_desc": "Pick your mods folder in Settings, then add or scan your mods.",
        "empty_mods_title": "No mods for this character",
        "empty_mods_desc": "Use Add mod, or simply drop files onto the window.",
        "empty_results_title": "Nothing matches",
        "empty_results_desc": "Try another keyword or filter.",
        "empty_issues_title": "All good",
        "empty_issues_desc": "No conflicts or missing files detected.",
        "toast_imported": "Imported {count} mod(s)",
        "toast_scan_done": "Scan finished, {count} new mod(s)",
        "toast_scan_none": "Scan finished, nothing new",
        "toast_changed": "Updated {count} mod(s)",
        "toast_copied": "Copied to clipboard",
        "toast_pasted": "Pasted the clipboard image",
        "toast_paste_empty": "No image on the clipboard",
        "toast_backup_done": "Backup written to {path}",
        "toast_migrated": "Migrated {count} mod(s) from v0.2.x",
        "warning_storage_missing_desc": "Choose Game/Content/Paks/mods in Settings first.",
        "warning_launch_missing_desc": "Pick the game executable in Settings first.",
        "warning_select_first": "Select at least one mod first.",
        "warning_confirm_delete_title": "Confirm delete",
        "warning_confirm_delete_body": "This deletes {count} mod record(s) and their files permanently.",
        "warning_import_failed": "Import failed: {detail}",
        "dialog_import_title": "Add mod",
        "dialog_import_hint": "The files are copied into this character's folder",
        "dialog_import_files": "Selected files",
        "dialog_character_edit": "Edit character",
        "dialog_character_new": "New character",
        "dialog_about_body": "SnowMM is a modern mod manager for Snowbreak: Containment Zone.",
        "issue_multi_enabled": "{count} mods enabled for {character}",
        "issue_multi_enabled_desc": "Mods for the same character can overwrite each other; keep only one enabled.",
        "issue_missing_file": "Missing file: {file}",
        "issue_missing_file_desc": "The tracked file no longer exists.",
        "issue_unknown_character": "{character} is not part of the roster ({count} mod(s))",
        "issue_unknown_character_desc": "That folder is not a full character name; move the files or drop the record.",
        "issue_duplicate_path": "Duplicate record: {file}",
        "issue_duplicate_path_desc": "Several records point at the same file.",
        "issue_disable_others": "Keep only one",
        "issue_remove_record": "Remove record",
        "issue_reveal": "Show in folder",
        "issue_count": "{count} item(s)",
        "settings_storage_hint": "Usually <game>/Game/Content/Paks/mods",
        "settings_game_hint": "Used by the Launch button, optional",
        "settings_theme_system": "System",
        "settings_theme_light": "Light",
        "settings_theme_dark": "Dark",
        "settings_hide_empty": "Hide characters without mods",
        "settings_confirm_delete": "Confirm before deleting",
        "settings_open_data": "Open data folder",
        "settings_data_hint": "Database file: {path}",
        "settings_rescan_hint": "Adopt files already present in the mods folder",
        "settings_migrate_hint": "Import mod records from the old 0.2.x folder",
        "settings_language_hint": "Applies immediately",
        "settings_about_body": "Version {version} · by theresa-2333",
        "settings_stats": "{mods} mod(s) · {characters} character(s)",
    },
}

_current = DEFAULT_LANGUAGE


@lru_cache(maxsize=1)
def _character_names() -> dict[str, str]:
    data = json.loads(paths.asset("catalog", "characters.json").read_text(encoding="utf-8"))
    return {item["name"]: item.get("name_en", "") for item in data}


def character_name(name: str, name_en: str = "") -> str:
    """Translate display text only; directory names and database keys stay stable."""
    if _current == "en_US":
        translated = name_en or _character_names().get(name)
        if translated:
            return translated.replace(" - ", " · ")
    return name.replace("-", " · ")


def armor_name(name: str, name_en: str = "") -> str:
    return character_name(name, name_en).partition(" · ")[2] or character_name(name, name_en)


def element_name(element: str) -> str:
    if _current == "en_US":
        return {"高热": "Thermal", "低温": "Frost", "电击": "Electrical",
                "动能": "Kinetic", "特异": "Chaos"}.get(element, element)
    return element


def set_language(language: str) -> None:
    global _current
    if language in TRANSLATIONS:
        _current = language


def get_language() -> str:
    return _current


def tr(key: str, **kwargs: object) -> str:
    """Translate ``key`` into the active language, formatting with ``kwargs``."""
    text = TRANSLATIONS.get(_current, {}).get(key)
    if text is None:
        text = TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
