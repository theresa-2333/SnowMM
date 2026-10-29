"""Exercise v1.1 skin navigation, import defaults and special cards offscreen."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
HOME = tempfile.TemporaryDirectory(prefix="snowmm-update-ui-")
os.environ["SNOWMM_HOME"] = HOME.name
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtGui import QFont, QFontDatabase

from snowmm.app import create_application
from snowmm.ui.dialogs import ImportDialog


def main():
    app, window = create_application([])
    window.open_character("卜卜-小天师")
    app.processEvents()
    assert window.detail_page.folder_tree.topLevelItemCount() == 0
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/msyh.ttc")
    app.setFont(QFont("Microsoft YaHei", 10))
    ctx = window.ctx
    ctx.settings.storage_path = str(Path(HOME.name) / "mods")
    source = Path(HOME.name) / "Skin_100_P.pak"
    source.write_bytes(b"package")
    default = ctx.manager.import_paths([source], character="凯茜娅-狂诗").added[0]
    custom = ctx.manager.import_paths([source], character="凯茜娅-狂诗", skin="floral-flutter").added[0]
    window.resize(1500, 900)
    window.show()
    window.open_character("凯茜娅-狂诗")
    app.processEvents()
    page = window.detail_page
    assert page.selected_skin == "default"
    assert page._current_mods() == [default]
    assert page.outfit_combo.count() == 3
    page.outfit_combo.setCurrentIndex(page.outfit_combo.findData("floral-flutter"))
    assert page._current_mods() == [custom]
    page._set_all(False)
    assert not custom.enabled and default.enabled
    page.inspector.set_selection([custom])
    page.inspector.skin_combo.setCurrentIndex(0)
    page.inspector.skin_combo.activated.emit(0)
    assert custom.skin == "default" and custom.disabled_path.exists()
    assert page._current_mods() == []
    dialog = ImportDialog(ctx, [source], character="凯茜娅-狂诗")
    dialog.skin_combo.setCurrentIndex(dialog.skin_combo.findData(page.selected_skin))
    assert dialog.values()["skin"] == "floral-flutter"
    dialog.deleteLater()
    window.open_character("基地")
    assert not page.outfit_combo.isVisible()
    assert not page.skin_combo.isVisible()
    assert not page.skin_button.isVisible()
    assert page.add_button.isEnabled()
    ctx.manager.import_paths([source], character="基地")
    ctx.manager.import_paths([source], character="基地")
    assert not [issue for issue in ctx.issues() if issue.data.get("character") == "基地"]
    ctx.settings.language = "en_US"
    window.change_language()
    window.open_character("凯茜娅-狂诗")
    assert window.detail_page.outfit_combo.currentText() == "Default"
    assert window.detail_page.outfit_combo.findText("Floral Flutter") >= 0
    for width in (900, 1500):
        window.resize(width, 900)
        app.processEvents()
    output = Path(__file__).resolve().parent.parent / ".work/update-preview"
    output.mkdir(exist_ok=True)
    window.grab().save(str(output / "skin-detail.png"))
    window._navigate("characters")
    assert {"基地", "杂项"} <= set(window.characters_page._cards)
    app.processEvents()
    window.grab().save(str(output / "special-cards.png"))
    window.close()
    app.quit()
    print("update UI ok: skin scope, move, import selection, special categories, bilingual names")


if __name__ == "__main__":
    main()
