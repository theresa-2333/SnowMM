"""Render every page to PNG for visual inspection.

By default a real window is shown briefly so the screenshots contain proper
fonts.  Set ``SNOWMM_OFFSCREEN=1`` to render without a display (text will not
be rendered because the headless platform exposes no font database).
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

if os.environ.get("SNOWMM_OFFSCREEN") == "1":
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# The shots double as the screenshots embedded in the READMEs, so they live in
# the repository (``.preview`` from older revisions is kept in .gitignore).
OUT = ROOT / "docs" / "screenshots"
HOME = Path(tempfile.mkdtemp(prefix="snowmm-shot-home-"))
os.environ["SNOWMM_HOME"] = str(HOME)

from snowmm.app import create_application  # noqa: E402

# Flat layout: one folder per full character name (``角色-装甲``).
SAMPLE = [
    ("里芙-狂猎", "Wild Hunt Dress_100_P.pak"),
    ("里芙-狂猎", "Noir Bunny_100_P.pak"),
    ("里芙-星期三", "Wednesday Swim_100_P.pak"),
    ("芬妮-咎冠", "Coronet OG Toggles_100_P.pak"),
    ("芬妮-咎冠", "Coronet White.pak"),
    ("芙提雅-缄默", "Bright Hour Casual_100_P.pak"),
    ("安卡希雅-辉夜", "Kaguya Lingerie_100_P.pak"),
    ("茉莉安-幽潮", "Marian Ghost_100_P.pak"),
    ("肴-夜天光", "Yao Night_100_P.pak"),
    ("琴诺-悖谬", "Cherno Paradox_100_P.pak"),
    ("恩雅-羽蜕", "Enya Plume_100_P.pak"),
    ("辰星-云篆", "Chenxing Shell_100_P.pak"),
    ("瑟瑞斯-瞬刻", "Siris Moment_100_P.pak"),
]


def main() -> int:
    application, window = create_application([])
    if os.environ.get("SNOWMM_OFFSCREEN") == "1":
        from PySide6.QtGui import QFont, QFontDatabase
        for filename in ("msyh.ttc", "segoeui.ttf"):
            font_path = Path("C:/Windows/Fonts") / filename
            if font_path.exists():
                QFontDatabase.addApplicationFont(str(font_path))
        application.setFont(QFont("Microsoft YaHei", 10))
    context = window.ctx
    mods_dir = Path(tempfile.mkdtemp(prefix="snowmm-shot-mods-"))
    context.settings.storage_path = str(mods_dir)
    context.settings.save()
    for character, filename in SAMPLE:
        path = mods_dir / character / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"0" * 4096)
    context.manager.scan_storage(known_characters=context.known_characters())
    for index, mod in enumerate(context.store.mods):
        mod.author = ["ToXiC", "Tomii41", "Nyaa", "Kuro"][index % 4]
        mod.source_url = "https://gamebanana.com/mods/703664"
        mod.note = "自动收录" if index % 3 else ""
    for mod in context.store.mods[:5]:
        context.manager.set_enabled([mod], True)
    context.settings.favorites = ["里芙-狂猎", "芬妮-咎冠"]
    window.refresh_all()
    window.resize(1440, 900)
    window.show()

    OUT.mkdir(exist_ok=True)
    application.processEvents()

    def shot(name: str) -> None:
        # Let stylesheet changes and lazy image loads settle before grabbing,
        # otherwise the shot can catch a half-repainted frame.
        for _ in range(3):
            application.processEvents()
        window.repaint()
        application.processEvents()
        window.grab().save(str(OUT / f"{name}.png"))

    window._navigate("characters")
    shot("01-characters")
    window.open_character("里芙-狂猎")
    shot("02-character-detail")
    window._navigate("mods")
    shot("03-mods")
    window._navigate("issues")
    shot("04-issues")
    window._navigate("characters")
    window.characters_page.set_search("芙")
    shot("08-characters-search")
    window.characters_page.set_search("")
    # The import dialog is the only place a mod is added, so capture it too.
    from snowmm.ui.dialogs import ImportDialog

    dialog = ImportDialog(
        context,
        [mods_dir / "里芙-狂猎" / "Wild Hunt Dress_100_P.pak"],
        character="里芙-狂猎",
        parent=window,
    )
    dialog.show()
    for _ in range(3):
        application.processEvents()
    dialog.grab().save(str(OUT / "09-import-dialog.png"))
    dialog.close()
    dialog.deleteLater()
    window._navigate("settings")
    shot("05-settings")
    context.settings.theme = "light"
    window.apply_theme()
    window._navigate("characters")
    shot("06-characters-light")
    window.open_character("里芙-狂猎")
    shot("07-detail-light")

    # Narrow window: every page must reflow instead of clipping.
    context.settings.theme = "dark"
    window.apply_theme()
    window.resize(940, 680)
    window._navigate("characters")
    shot("10-characters-narrow")
    window.open_character("里芙-狂猎")
    shot("11-detail-narrow")
    window._navigate("mods")
    shot("12-mods-narrow")
    window._navigate("settings")
    shot("13-settings-narrow")

    window.resize(1440, 900)
    context.settings.language = "en_US"
    window.change_language()
    window._navigate("characters")
    shot("14-characters-english")
    window.open_character("凯茜娅-狂诗")
    shot("15-detail-english")
    window._navigate("settings")
    shot("16-settings-english")

    window.close()
    application.quit()
    shutil.rmtree(mods_dir, ignore_errors=True)
    shutil.rmtree(HOME, ignore_errors=True)
    print(f"screenshots written to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
