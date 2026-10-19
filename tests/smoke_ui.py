"""Offscreen smoke test of the Qt layer.

Run with ``python tests/smoke_ui.py`` (no display required - the offscreen
platform plugin is used).  It builds the real main window, walks every page and
exercises the actions that touch the filesystem.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_LOGGING_RULES"] = "*.debug=false"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HOME = Path(tempfile.mkdtemp(prefix="snowmm-smoke-"))
os.environ["SNOWMM_HOME"] = str(HOME)

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from snowmm.app import create_application  # noqa: E402
from snowmm.ui.pages import CharactersPage  # noqa: E402


def make_mod(mods_dir: Path, character: str, filename: str) -> Path:
    """Create a mod file directly inside its character folder (flat layout)."""
    path = mods_dir / character / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fake pak payload", encoding="utf-8")
    return path


def stray_windows(window) -> list:
    """Visible top-level widgets that are not the main window (the popup bug)."""
    QApplication.processEvents()
    return [
        widget
        for widget in QApplication.topLevelWidgets()
        if widget is not window and widget.isVisible()
    ]


def main() -> int:
    application, window = create_application([])
    assert window.stack.currentWidget() is window.settings_page
    context = window.ctx
    mods_dir = Path(tempfile.mkdtemp(prefix="snowmm-mods-"))
    context.settings.storage_path = str(mods_dir)
    context.settings.save()

    make_mod(mods_dir, "里芙-狂猎", "Wild Hunt_100_P.pak")
    make_mod(mods_dir, "里芙-狂猎", "Second Skin_100_P.pak")
    make_mod(mods_dir, "芬妮-咎冠", "Coronet_100_P.pak")
    make_mod(mods_dir, "芬妮-咎冠", "NoSuffix.pak")

    # A stray folder that is not a character must never grow the roster.
    make_mod(mods_dir, "Not A Character", "Ghost_100_P.pak")

    adopted = context.manager.scan_storage(known_characters=context.known_characters())
    assert len(adopted) == 4, f"expected 4 adopted mods, got {len(adopted)}"
    context.manager.refresh_states()
    assert context.stats()["characters"] == 2
    assert "Not A Character" not in context.characters()

    # Import through the manager (the dialog is modal, so drive the service).
    source = mods_dir.parent / "New Mod_100_P.pak"
    source.write_text("payload", encoding="utf-8")
    result = context.manager.import_paths([source], character="里芙-狂猎")
    assert result.added, result.errors
    imported = result.added[0]
    assert imported.character == "里芙-狂猎"
    assert imported.disk_path.parent.name == "里芙-狂猎", imported.disk_path

    # The (modal) dialogs are built directly so their payloads stay consistent.
    from snowmm.ui.dialogs import CharacterEditorDialog, ImportDialog

    import_dialog = ImportDialog(context, [source], character="里芙-狂猎")
    # The target character comes from the page, so it is not an editable field.
    assert "character" not in import_dialog.values()
    assert import_dialog.character == "里芙-狂猎"
    assert import_dialog.values()["name"] == source.stem
    assert "armor" not in import_dialog.values()
    import_dialog.deleteLater()

    known = context.catalog.get("里芙-狂猎")
    editor = CharacterEditorDialog(context, known)
    # The full name keys the roster and the folder, so it stays locked.
    assert editor.name_edit.isReadOnly()
    payload = editor.payload()
    assert payload["name"] == "里芙-狂猎", payload
    assert payload["element"] == known.element, payload
    assert payload["role"] == known.role, payload
    editor.deleteLater()

    window.refresh_all()
    for key in ("characters", "mods", "issues", "settings"):
        window._navigate(key)
        page = window.pages[key]
        page.set_search("狂猎")
        page.set_search("")
        assert page is window.stack.currentWidget()

    characters_page = window.characters_page
    assert isinstance(characters_page, CharactersPage)
    assert characters_page.grid._items, "character grid should contain cards"

    # The roster is fixed: "show all" is on by default, so every bundled
    # character has a card - a stray folder cannot add one.
    assert characters_page.show_all_chip.isChecked()
    assert len(characters_page.grid._items) == len(context.catalog)
    # The headline count always matches the number of cards on screen.
    assert characters_page.stat_characters.value_label.text() == str(len(characters_page.grid._items))

    # Element classification: one chip per damage type, filtering the grid.
    elements = context.elements()
    assert elements, "the art library should provide at least one element"
    for element in elements:
        characters_page._select_element(element)
        cards = characters_page.grid._items
        assert cards, f"element {element} should have characters"
        assert all(card.character.element == element for card in cards), element
    characters_page._select_element("")
    assert len(characters_page.grid._items) == len(context.catalog)

    # Regenerating the grid must not promote cards to top-level windows, and a
    # plain refresh must not either (the "a window flashed on every page switch"
    # bug).
    for _ in range(3):
        window._navigate("characters")
        window.refresh_all()
        characters_page.refresh()
        window._navigate("mods")
    assert not stray_windows(window), "character cards leaked as windows"
    assert len(characters_page.grid._items) == len(context.catalog)

    # The grid must stay inside the window however often it relayouts.  A
    # minimum width that grew with the number of columns used to inflate it from
    # 600px to over 11000px on every resize until the stack overflowed.
    for width, height in ((900, 620), (1600, 940), (1000, 700), (1440, 900)):
        window.resize(width, height)
        for _ in range(4):
            application.processEvents()
        characters_page.refresh()
        application.processEvents()
        assert characters_page.grid.width() <= window.width(), (width, characters_page.grid.width())
        assert 0 < characters_page.grid._columns <= len(context.catalog)

    window.open_character("里芙-狂猎")
    assert window.stack.currentWidget() is window.detail_page
    detail = window.detail_page
    assert detail.table.rowCount() == 3, detail.table.rowCount()
    # The chrome and the panel agree, and the role key is translated.
    assert window.page_title.text() == "里芙 · 狂猎", window.page_title.text()
    assert window.page_subtitle.text() == "输出", window.page_subtitle.text()
    assert detail.title_label.text() == "里芙 · 狂猎"

    mod = context.store.mods[0]
    window.detail_page._on_toggle_requested([mod], False)
    context.manager.refresh_states()
    assert mod.enabled is False
    window.detail_page._on_toggle_requested([mod], True)
    context.manager.refresh_states()
    assert mod.enabled is True

    window.issues_page.refresh()
    assert window.issues_page.summary.text()
    # Every issue must render with real values - a stale placeholder would
    # silently fall back to the raw "{...}" template.
    from snowmm.i18n import tr

    for issue in context.issues():
        rendered = " ".join(
            (
                window.issues_page._title(issue),
                tr(f"issue_{issue.kind}_desc", **issue.data),
                tr(f"issue_{issue.kind}", **issue.data),
            )
        )
        assert "{" not in rendered, rendered

    # The armor switcher jumps to another armor of the same character.
    detail._fill_armor_combo(context.catalog.get("里芙-狂猎"))
    assert detail.skin_combo.count() >= 2, detail.skin_combo.count()
    other = next(
        index
        for index in range(detail.skin_combo.count())
        if detail.skin_combo.itemData(index) != "里芙-狂猎"
    )
    target_armor = detail.skin_combo.itemData(other)
    detail.skin_combo.setCurrentIndex(other)
    detail._on_armor_selected(other)
    assert detail.character_name == target_armor
    assert window.stack.currentWidget() is detail
    # ... and the dropdown follows the armor that is being viewed.
    assert detail.skin_combo.currentData() == target_armor
    window.open_character("里芙-狂猎")
    assert detail.skin_combo.currentData() == "里芙-狂猎"

    # "Only this one" keeps a single mod of the character enabled.
    mods = context.character_mods("里芙-狂猎")
    context.manager.set_enabled(mods, True)
    context.manager.refresh_states()
    detail.refresh()
    detail.table.selectRow(0)
    detail._enable_only_selection()
    context.manager.refresh_states()
    enabled = [item for item in context.character_mods("里芙-狂猎") if item.enabled]
    assert len(enabled) == 1, enabled

    # Folder tab lists the files of the character folder.
    assert detail.folder_tree.topLevelItemCount() > 0

    # Inspector edits must persist to the store.
    target = context.store.mods[0]
    detail.inspector.set_selection([target])
    # The character's own page repeats the name in its title, so the inspector
    # there has no full-name field at all.
    assert detail.inspector.character_combo is None
    assert window.mods_page.inspector.character_combo is not None
    assert detail.inspector.source_edit.placeholderText() == ""
    detail.inspector.author_edit.setText("Smoke Author")
    detail.inspector._commit_author()
    assert target.author == "Smoke Author"
    detail.inspector.name_edit.setText("Renamed Mod")
    detail.inspector._commit_name()
    assert target.name == "Renamed Mod"
    assert json.loads(Path(context.store.path).read_text(encoding="utf-8"))["mods"][0]["id"]

    # Table context actions.
    detail._on_table_action("copy", [target])

    # Moving a mod to another character stays available from the all-mods view.
    window.mods_page.refresh()
    combo = window.mods_page.inspector.character_combo
    index = combo.findData("芬妮-咎冠")
    combo.setCurrentIndex(index)
    window.mods_page.inspector._commit_character()
    context.manager.refresh_states()
    assert target.character == "芬妮-咎冠", target.character
    assert (mods_dir / "芬妮-咎冠" / target.filename).exists()
    assert not (mods_dir / "里芙-狂猎" / target.filename).exists()
    window.mods_page.inspector.set_selection([target])
    window.mods_page.inspector._commit_character()

    # Refresh retains multi-selection, including after toggling from the table.
    window.open_character("里芙-狂猎")
    detail.table.selectRow(0)
    from PySide6.QtCore import QItemSelectionModel
    detail.table.selectionModel().select(
        detail.table.model().index(1, 0),
        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
    )
    selected_ids = [item.id for item in detail.table.selected_mods()]
    detail.refresh()
    assert [item.id for item in detail.table.selected_mods()] == selected_ids
    detail._on_toggle_requested(detail.table.selected_mods(), False)
    assert [item.id for item in detail.table.selected_mods()] == selected_ids

    # Pending notes are committed to the previous mod before another is loaded.
    remaining = context.character_mods("里芙-狂猎")
    detail.inspector.set_selection([remaining[0]])
    detail.inspector.note_edit.setPlainText("pending note before selection changes")
    detail.inspector.set_selection([remaining[1]])
    assert remaining[0].note == "pending note before selection changes"
    assert remaining[1].note != remaining[0].note

    # Filtering to no results cannot leave a hidden, editable stale selection.
    window.mods_page.set_search("no-such-mod-ever")
    assert not window.mods_page.inspector.mods
    window.mods_page.set_search("")

    # The portrait collapses at small widths, leaving the table and inspector usable.
    window.show()
    for width in (880, 940, 1280, 1600):
        window.resize(width, 680)
        for _ in range(4):
            application.processEvents()
        assert detail.splitter.width() <= detail.width(), (width, detail.splitter.width(), detail.width())
        if width <= 940:
            assert detail.left_panel.isHidden()
            assert detail.table.columnWidth(detail.table.columns.index("name")) >= 120
            assert detail.inspector.single_page.horizontalScrollBar().maximum() == 0
    assert not detail.left_panel.isHidden()
    assert detail.folder_import_button.text() == "导入文件夹"

    # The wheel must never change a text box unless it has focus.
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent

    from snowmm.ui.widgets.common import WheelGuard

    guard = WheelGuard()
    wheel = QWheelEvent(
        QPointF(4, 4),
        QPointF(4, 4),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    combo.clearFocus()
    assert guard.eventFilter(combo, wheel) is True, "wheel should be swallowed"
    assert guard.eventFilter(detail.inspector.note_edit, wheel) is True
    # A widget that does have focus keeps its keyboard/mouse behaviour.
    combo.hasFocus = lambda: True
    assert guard.eventFilter(combo, wheel) is False, "a focused combo still scrolls"
    assert guard.eventFilter(detail.inspector.note_edit, wheel) is True

    # Switching the theme must also re-render the existing character cards.
    card = next(iter(window.characters_page._cards.values()))
    previous_theme = card.theme
    window.toggle_theme()
    assert card.theme is window.ctx.theme, "cards must follow the theme"
    assert card.theme is not previous_theme
    window.toggle_theme()
    window.toggle_theme()
    context.settings.language = "en_US"
    window.change_language()
    assert window.nav_buttons["characters"].text() == "Characters"
    assert window.detail_page.folder_import_button.text() == "Import folder"
    window._navigate("characters")
    window.characters_page.set_search("Katya")
    assert len(window.characters_page.grid.items) == 3
    assert all("Katya" in card.name_label.text() for card in window.characters_page.grid.items)
    assert window.characters_page._element_chips["低温"].text() == "Frost"
    window.open_character("凯茜娅-狂诗")
    assert window.page_title.text() == "Katya · Rhapsody"
    assert window.detail_page.skin_combo.currentText() == "Rhapsody"
    assert window.detail_page.character_name == "凯茜娅-狂诗"
    context.settings.language = "zh_CN"
    window.change_language()

    window.characters_page.set_search("no-such-character")
    assert not window.characters_page.grid._items
    window.characters_page.set_search("")

    for mod in list(context.store.mods):
        context.manager.set_enabled([mod], False)
    context.manager.refresh_states()
    window.refresh_all()

    final_mod = context.store.mods[0]
    window.mods_page.inspector.set_selection([final_mod])
    window.mods_page.inspector.note_edit.setPlainText("saved immediately on close")
    window.close()
    saved = json.loads(Path(context.store.path).read_text(encoding="utf-8"))
    assert next(mod for mod in saved["mods"] if mod["id"] == final_mod.id)["note"] == "saved immediately on close"
    application.quit()
    shutil.rmtree(mods_dir, ignore_errors=True)
    shutil.rmtree(HOME, ignore_errors=True)
    print(
        "smoke ok: fixed roster, element filter, detail, armor switch, toggling, "
        "mod reassignment, wheel guard, theme and i18n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
