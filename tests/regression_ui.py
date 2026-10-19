"""Regression checks for real card clicks, transient windows and full-image viewing.

Run with ``python tests/regression_ui.py``; uses isolated temporary data.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
TEST_HOME = tempfile.TemporaryDirectory(prefix="snowmm-interactions-")
os.environ["SNOWMM_HOME"] = TEST_HOME.name
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QEvent, QObject, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPixmap  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget  # noqa: E402

from snowmm.app import build_context  # noqa: E402
from snowmm.ui.main_window import MainWindow  # noqa: E402
from snowmm.ui.widgets.cards import CharacterCard  # noqa: E402


class WindowShows(QObject):
    """Capture even windows that disappear before processEvents returns."""

    def __init__(self):
        super().__init__()
        self.unexpected = []

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.Show and isinstance(watched, QWidget)
            and watched.isWindow() and not isinstance(watched, QMainWindow)
        ):
            self.unexpected.append((type(watched).__name__, watched.objectName()))
        return False


def main():
    app = QApplication([])
    app.setStyle("Fusion")
    font_path = Path("C:/Windows/Fonts/msyh.ttc")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
        app.setFont(QFont("Microsoft YaHei", 10))
    shows = WindowShows()
    app.installEventFilter(shows)
    ctx = build_context()
    ctx.settings.storage_path = str(Path(os.environ["SNOWMM_HOME"]) / "mods")
    window = MainWindow(ctx)
    window.show()
    window._navigate("characters")
    page = window.characters_page

    def settle():
        for _ in range(8):
            app.processEvents()

    def check_grid():
        settle()
        cards = page.grid.items
        for card in cards:
            assert card.parentWidget() is page.grid and not card.isWindow()
            assert card.isEnabled(), card.character.name
            assert card.geometry().right() < page.grid.width(), (
                card.geometry(), page.grid.size(), page.grid._columns, page.grid._cell_size,
            )
        for index, card in enumerate(cards):
            rect = card.geometry()
            for other in cards[index + 1:]:
                other_rect = other.geometry()
                assert not rect.intersects(other_rect), (rect, other_rect)
                if rect.y() == other_rect.y():
                    assert other_rect.left() - rect.right() - 1 >= page.grid.spacing
                elif rect.x() == other_rect.x():
                    assert other_rect.top() - rect.bottom() - 1 >= page.grid.spacing
        assert not shows.unexpected, shows.unexpected

    original_cards = dict(page._cards)
    for width in (880, 1280, 1600, 940):
        window.resize(width, 800)
        for _ in range(2):
            page.show_all_chip.click()
            check_grid()
            page.show_all_chip.click()
            check_grid()
            for element, chip in page._element_chips.items():
                chip.click()
                assert page._element == element
                check_grid()
        page._select_element("")
        check_grid()
    assert all(page._cards[name] is card for name, card in original_cards.items())
    if "--screenshots" in sys.argv:
        output = Path(__file__).resolve().parent.parent / "docs" / "review"
        output.mkdir(parents=True, exist_ok=True)
        window.resize(1280, 820)
        settle()
        window.grab().save(str(output / "characters-fixed.png"))

    # Exercise mouse hit testing instead of bypassing the UI with signal.emit().
    empty_card = page.grid.items[0]
    for part in ("portrait", "name_label", "mod_tag", "element_badge"):
        window._navigate("characters")
        page.scroll.ensureWidgetVisible(empty_card)
        settle()
        QTest.mouseClick(getattr(empty_card, part), Qt.MouseButton.LeftButton)
        settle()
        assert window.stack.currentWidget() is window.detail_page, part
        assert window.detail_page.character_name == empty_card.character.name
        assert window.detail_page.table.rowCount() == 0
    window._navigate("characters")
    settle()
    QTest.mouseClick(empty_card.favorite_button, Qt.MouseButton.LeftButton)
    assert window.stack.currentWidget() is page

    # A character whose only mod is disabled remains navigable.
    source = Path(os.environ["SNOWMM_HOME"]) / "Sample.pak"
    source.write_bytes(b"pak")
    mod = ctx.manager.import_paths([source], character=empty_card.character.name).added[0]
    ctx.manager.set_enabled([mod], False)
    window.refresh_all()
    settle()
    assert empty_card.isEnabled()
    QTest.mouseClick(empty_card.portrait, Qt.MouseButton.LeftButton)
    assert window.stack.currentWidget() is window.detail_page

    # Loading a brand-new card must not show the element badge as a window.
    extra = CharacterCard(empty_card.character, ctx.images, ctx.theme, page.grid)
    assert not shows.unexpected, shows.unexpected
    extra.deleteLater()

    # A full-resolution, non-square image is shown without thumbnail cropping.
    image_path = Path(os.environ["SNOWMM_HOME"]) / "preview.png"
    image = QPixmap(1200, 800)
    image.fill(QColor("#4080d0"))
    assert image.save(str(image_path))
    ctx.manager.set_preview(mod, image_path)
    window.open_character(mod.character)
    inspector = window.detail_page.inspector
    settle()
    assert inspector.current is mod
    shows.unexpected.clear()
    QTest.mouseClick(inspector.preview, Qt.MouseButton.LeftButton)
    settle()
    dialog = inspector._preview_dialog
    assert dialog is not None and dialog.isVisible()
    assert dialog.view.sceneRect().width() == 1200
    assert dialog.view.sceneRect().height() == 800
    before = dialog.view.transform().m11()
    dialog.view.zoom(1.25)
    assert dialog.view.transform().m11() > before
    dialog.view.actual_size()
    assert dialog.view.transform().m11() == 1
    dialog.view.fit_image()
    assert len(shows.unexpected) == 1 and shows.unexpected[0][0] == "ImagePreviewDialog"
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    settle()
    assert inspector._preview_dialog is None
    shows.unexpected.clear()
    assert not any(widget.isVisible() and widget.isWindow() and widget is not window
                   for widget in app.topLevelWidgets())
    window.close()
    app.quit()
    TEST_HOME.cleanup()
    print("regression ok: card spacing, transient Show events, filter reuse, empty/disabled card clicks, image viewer")


if __name__ == "__main__":
    main()
