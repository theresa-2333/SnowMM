"""Real UI regressions for startup state, import names, and gallery controls."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
TEST_HOME = tempfile.TemporaryDirectory(prefix="snowmm-gallery-ui-")
os.environ["SNOWMM_HOME"] = TEST_HOME.name
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from snowmm.app import create_application
from snowmm.core.models import Mod
from snowmm.core.settings import Settings
from snowmm.core.store import Store
from snowmm.ui.dialogs import ImportDialog


def main():
    home = Path(TEST_HOME.name)
    mods = home / "mods/凯茜娅/狂诗/默认"
    mods.mkdir(parents=True)
    enabled_file = mods / "Enabled.pak"
    enabled_file.write_bytes(b"pak")
    enabled_file.with_suffix(".utoc").write_bytes(b"utoc")
    disabled_file = mods / "Disabled.pak.disabled"
    disabled_file.write_bytes(b"disabled")
    store = Store()
    first = store.add_mod(Mod(name="Enabled", character="凯茜娅-狂诗", file=str(enabled_file)))
    second = store.add_mod(Mod(name="Disabled", character="凯茜娅-狂诗", file=str(disabled_file)))
    store.characters = [{"name": "卜卜-小天师", "portrait": "old/location/cover.png"}]
    store.save()
    Settings(storage_path=str(home / "mods"), last_page="mods").save()
    app, window = create_application([])
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
    app.setFont(QFont("Microsoft YaHei", 10))
    window.resize(1400, 950)
    window.show()
    app.processEvents()
    ctx = window.ctx
    first, second = ctx.store.get_mod(first.id), ctx.store.get_mod(second.id)
    preview = QPixmap(600, 400)
    preview.fill(QColor("#528bd0"))
    preview_path = home / "mod-preview.png"
    preview.save(str(preview_path))
    ctx.manager.set_preview(first, preview_path)
    assert first.enabled and not second.enabled
    assert first.directory.name == "katya-rhapsody"
    assert not enabled_file.exists()
    assert list(home.glob("data-before-compatibility-*.json"))
    assert ctx.stats()["enabled"] == 1
    bubu = ctx.catalog.get("卜卜-小天师")
    assert not QPixmap(ctx.images.portrait_path(bubu)).isNull()
    window.characters_page.refresh()
    card = window.characters_page._cards[bubu.name]
    assert card.character.portrait.endswith("bubu-the-geomancer.png")
    # A changed portrait must replace the cached card image without restarting.
    original = card.portrait.pixmap().toImage()
    ctx.store.characters = [{"name": bubu.name, "portrait": str(preview_path)}]
    window.refresh_all()
    assert window.characters_page._cards[bubu.name] is card
    assert card.portrait.pixmap().toImage() != original
    ctx.store.characters = [{"name": bubu.name, "portrait": "missing/old-cover.png"}]
    window.refresh_all()
    assert card.portrait.pixmap().toImage() == original

    # Name must accept actual keyboard editing for both archive and folder imports.
    archive = home / "download.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("Archive.pak", "pak")
    folder = home / "download"
    folder.mkdir()
    (folder / "Folder.pak").write_bytes(b"pak")
    for source, name in ((archive, "Custom Archive"), (folder, "Custom Folder")):
        def accept_named_import(name=name):
            dialog = QApplication.activeModalWidget()
            assert isinstance(dialog, ImportDialog)
            assert dialog.name_edit.isEnabled() and not dialog.name_edit.isReadOnly()
            QTest.mouseClick(dialog.name_edit, Qt.MouseButton.LeftButton)
            QTest.keyClicks(dialog.name_edit, name)
            dialog.accept()
        QTimer.singleShot(0, accept_named_import)
        window.import_dialog("凯茜娅-狂诗", [source])
        assert ctx.store.mods[-1].name == name

    window.open_character("凯茜娅-狂诗")
    app.processEvents()
    inspector = window.detail_page.inspector
    inspector.set_selection([first])
    QApplication.setActiveWindow(window)
    QTest.mouseClick(inspector.name_edit, Qt.MouseButton.LeftButton)
    inspector.name_edit.selectAll()
    QTest.keyClicks(inspector.name_edit, "Renamed with keyboard")
    QTest.keyClick(inspector.name_edit, Qt.Key.Key_Tab)
    app.processEvents()
    assert first.name == "Renamed with keyboard"
    assert Store().load().get_mod(first.id).name == first.name
    table = window.detail_page.table
    row = next(index for index, mod in enumerate(table.mod_rows()) if mod.id == first.id)
    assert table.item(row, table.columns.index("name")).text() == first.name

    # Snapshot includes all enabled mods, with each companion toggled atomically.
    window.open_gallery()
    gallery = window.detail_page.gallery
    app.processEvents()
    assert window.detail_page.content_stack.currentWidget() is gallery
    assert not gallery.isWindow() and gallery.window() is window
    assert len(gallery.cards) == 3
    assert second.id not in {card.mod.id for card in gallery.cards}
    first_card = next(card for card in gallery.cards if card.mod.id == first.id)
    for width in (620, 1100):
        gallery.resize(width, 780)
        app.processEvents()
        for card in gallery.cards:
            assert card.geometry().right() < gallery.scroll.viewport().width()
        for index, card in enumerate(gallery.cards):
            assert all(not card.geometry().intersects(other.geometry()) for other in gallery.cards[index + 1:])
    first_card.open_button.click()
    app.processEvents()
    assert first_card._preview_dialog is not None
    first_card._preview_dialog.close()
    QApplication.setActiveWindow(window)
    gallery.setFocus()
    app.processEvents()
    QTest.mouseClick(first_card.toggle, Qt.MouseButton.LeftButton)
    assert not first.enabled and first.disabled_path.exists()
    assert first.disabled_path.with_name("Enabled.utoc.disabled").exists()
    assert first_card in gallery.cards
    QTest.keyClick(gallery, Qt.Key.Key_Space)
    assert first.enabled and first.enabled_path.exists()
    assert first.enabled_path.with_suffix(".utoc").exists()
    old_index = gallery.selected_index
    QTest.keyClick(gallery, Qt.Key.Key_Right)
    assert gallery.selected_index == (old_index + 1) % len(gallery.cards)

    # A failed toggle must restore its checked state and report the failure.
    collision = first.enabled_path.with_suffix(".utoc.disabled")
    collision.write_bytes(b"keep")
    gallery.toggle_card(first_card)
    assert first.enabled and first_card.toggle.isChecked() and gallery.error.text()
    collision.unlink()
    gallery.toggle_card(first_card)
    gallery.reload()
    assert first.id not in {card.mod.id for card in gallery.cards}
    assert Store().load().get_mod(first.id).disabled_path.exists()
    for card in list(gallery.cards):
        gallery.toggle_card(card)
    gallery.reload()
    assert not gallery.cards and gallery.empty.isVisible()
    gallery.back_button.click()
    assert window.detail_page.content_stack.currentWidget() is window.detail_page.splitter

    # Rebuilt pages retain their gallery signal connections after language changes.
    ctx.settings.language = "en_US"
    window.change_language()
    window.open_character("凯茜娅-狂诗")
    ctx.manager.set_enabled([first], True)
    window.refresh_all()
    QTest.mouseClick(window.detail_page.inspector.gallery_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    gallery = window.detail_page.gallery
    assert gallery is not None and len(gallery.cards) == 1
    output = Path(__file__).resolve().parent.parent / ".work/update-preview"
    output.mkdir(exist_ok=True)
    window.grab().save(str(output / "enabled-gallery.png"))
    gallery.back_button.click()
    inspector = window.detail_page.inspector
    inspector.set_selection([first])
    QTest.mouseClick(inspector.preview, Qt.MouseButton.LeftButton)
    app.processEvents()
    viewer = inspector._preview_dialog
    assert viewer is not None
    viewer.gallery_button.click()
    assert window.detail_page.content_stack.currentWidget() is window.detail_page.gallery
    assert not window.detail_page.gallery.isWindow()
    assert inspector._preview_dialog is None
    window.detail_page.gallery.back_button.click()
    window._navigate("mods")
    window.mods_page.show_gallery()
    assert window.mods_page.content_stack.currentWidget() is window.mods_page.gallery
    assert not window.mods_page.gallery.isWindow()
    window.mods_page.gallery.back_button.click()
    assert window.mods_page.content_stack.currentWidget() is window.mods_page.splitter
    window.close()
    app.quit()
    print(json.dumps({"startup_state": True, "bubu_cover": True, "import_names": True,
                      "gallery_buttons_shortcuts_rollback": True}))


if __name__ == "__main__":
    main()
