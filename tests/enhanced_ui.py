"""Offscreen Qt workflow, clipboard targeting, DPI mapping and preview regressions."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["SNOWMM_TEST_NO_HOTKEY"] = "1"
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from snowmm.enhanced.app import create_application
from snowmm.enhanced.capture import RegionOverlay


def run():
    output = Path(__file__).resolve().parents[1] / "verification"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="enhanced-ui-") as temporary:
        root = Path(temporary)
        os.environ["SNOWMM_ENHANCED_HOME"] = str(root / "data")
        (root / "data").mkdir()
        (root / "data/settings.json").write_text(
            json.dumps(
                {
                    "storage_path": str(root / "library"),
                    "deploy_path": str(root / "game/~SnowMM"),
                    "deploy_mode": "copy",
                }
            ),
            encoding="utf-8",
        )
        app, window = create_application(["enhanced-ui-test"])
        window.resize(1540, 950)
        window.show()
        sources = root / "sources"
        sources.mkdir()
        for name, category in [
            ("角色_100_P.pak", ["角色", "芬妮", "澄意", "原皮"]),
            ("插画_100_P.pak", ["插画", "加载画面"]),
            ("NPC.pak", ["NPC", "安保"]),
        ]:
            file = sources / name
            file.write_bytes(b"disposable fixture, not for game loading")
            result = window.ctx.manager.import_paths(
                [file], category=category, character="芬妮-澄意" if category[0] == "角色" else "杂项"
            )
            assert not result.errors, result.errors
        window.refresh_all()
        app.processEvents()
        assert window.library_page.table.topLevelItemCount() == 3
        assert set(window.category_buttons) == {"插画", "Boss", "NPC", "基地", "反和谐", "杂项"}
        assert all(not entry[0].special for entry in window.characters_page._collect())
        assert len(window.characters_page._collect()) == 54
        window._navigate("category:插画")
        assert set(window.category_page.cards) == {"插画/加载画面"}
        window.category_page.cards["插画/加载画面"].clicked.emit("插画/加载画面")
        assert window.category_page.path == ["插画", "加载画面"]
        illustration = next(m for m in window.ctx.manager.mods if m.category_parts[0] == "插画")
        assert set(window.category_page.cards) == {illustration.id}
        window.category_page.cards[illustration.id].clicked.emit(illustration.id)
        assert window.library_page.current.id == illustration.id
        assert window.library_page.table.topLevelItemCount() == 1
        assert window.category_buttons["插画"].isChecked()
        window.ctx.store.categories.append(["新大类", "空小类"])
        window.refresh_all()
        assert "新大类" in window.category_buttons
        window._navigate("category:新大类")
        assert "新大类/空小类" in window.category_page.cards
        window.open_category(["新大类", "空小类"])
        assert not window.category_page.cards
        window.category_page.up()
        assert window.category_page.path == ["新大类"]
        window.open_character("基地")
        assert window.category_page.path == ["基地"]
        window.open_character("杂项")
        assert window.category_page.path == ["杂项"]
        window.ctx.settings.has_pending = True
        window.ctx.settings.pending_ids = [illustration.id]
        with (
            patch("snowmm.enhanced.window.is_admin", return_value=False),
            patch("snowmm.enhanced.window.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes),
            patch("snowmm.enhanced.window.request_admin_restart", return_value=False) as restart,
            patch.object(window, "close") as close,
        ):
            assert not window.restart_as_admin()
            restart.assert_called_once_with(window.ctx.settings._home)
            close.assert_not_called()
        assert window.ctx.settings.has_pending and window.ctx.settings.pending_ids == [illustration.id]
        with (
            patch("snowmm.enhanced.window.is_admin", return_value=False),
            patch("snowmm.enhanced.window.QMessageBox.question", return_value=QMessageBox.StandardButton.No),
            patch("snowmm.enhanced.window.request_admin_restart") as restart,
        ):
            assert not window.restart_as_admin()
            restart.assert_not_called()
        assert window.ctx.settings.deploy_mode == "copy"
        window.ctx.settings.has_pending = False
        window.ctx.settings.pending_ids = []
        window._navigate("category:插画")
        app.processEvents()
        assert window.grab().save(str(output / "左侧大分类与卡片.png"))
        window.open_library_category([])
        mod = window.ctx.manager.mods[0]
        window.ctx.manager.set_enabled([mod], True)
        window.refresh_all()
        image = QImage(600, 300, QImage.Format.Format_RGB32)
        image.fill(QColor("#205d88"))
        labels = [f"{m.name} · {' / '.join(m.category_parts)} · {m.id[-6:]}" for m in window.ctx.manager.mods]
        with patch(
            "snowmm.enhanced.window.QInputDialog.getItem", side_effect=[(labels[0], True), ("设为封面并加入预览", True)]
        ):
            window.confirm_capture(image)
        assert len(mod.previews) == 1 and mod.preview and Path(mod.preview).exists()
        with patch("snowmm.enhanced.window.QInputDialog.getItem", return_value=("", False)):
            window.confirm_capture(image)
        assert len(mod.previews) == 1
        window.library_page.edits["author"].setText("界面验证样本")
        window.library_page.note.setPlainText("源目录未改变；此为隔离测试数据。")
        window.library_page.save_metadata()
        assert mod.author == "界面验证样本"
        window.refresh_all()
        app.processEvents()
        assert window.grab().save(str(output / "资源库工作台.png"))
        window._navigate("settings")
        app.processEvents()
        assert window.grab().save(str(output / "增强设置.png"))
        window.open_character("芬妮-澄意")
        window.detail_page.show_gallery()
        app.processEvents()
        assert window.grab().save(str(output / "原角色界面与画廊.png"))

        class FakeScreen:
            def geometry(self):
                return QRect(0, 0, 200, 100)

        pixmap = QPixmap(400, 200)
        pixmap.fill(QColor("blue"))
        overlay = RegionOverlay(FakeScreen(), pixmap)
        captured = []
        cancelled = []
        overlay.captured.connect(captured.append)
        overlay.cancelled.connect(lambda: cancelled.append(True))
        overlay.show()
        app.processEvents()
        QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
        QTest.mouseMove(overlay, QPoint(60, 40))
        QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=QPoint(60, 40))
        assert captured and captured[0].width() == 102 and captured[0].height() == 62
        QTest.keyClick(overlay, Qt.Key.Key_Escape)
        assert cancelled
        overlay.close()
        window.close()
        app.quit()
        report = {
            "ok": True,
            "catalog": 56,
            "pages": 6,
            "sidebar_top_categories": True,
            "nested_category_cards": True,
            "roster_utility_cards_merged": True,
            "empty_custom_category": True,
            "uac_cancel_preserves_window_and_pending": True,
            "clipboard_target_confirmation": True,
            "cancel_preserves_preview": True,
            "capture_DPI_2x": True,
            "capture_Esc": True,
            "physical_multiple_monitors": "not tested",
            "game_mounting": "not tested",
        }
        (output / "ui-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report))


if __name__ == "__main__":
    run()
