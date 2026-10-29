"""Automatic repair must preserve packages, metadata and modern skin folders."""
from pathlib import Path
from unittest import mock

from snowmm.core.catalog import Catalog
from snowmm.core.models import Mod
from snowmm.core.naming import folder_for
from snowmm.core.store import Store
from tests.test_core import TempCase


class CompatibilityTests(TempCase):
    def repair(self):
        return self.manager.repair_legacy_layout(Catalog.load().names())

    def test_chinese_flat_folder_is_adopted_on_detection(self):
        source = self.make_pak("卜卜-小天师/中文_100_P.pak")
        self.assertEqual(self.repair(), (1, []))
        mod = self.store.mods[0]
        self.assertEqual(mod.character, "卜卜-小天师")
        self.assertEqual(mod.directory.name, "bubu-the-geomancer")
        self.assertTrue(mod.filename.isascii() and mod.enabled)
        self.assertFalse(source.exists())
        snapshots = list(self.tmp.glob("data-before-compatibility-*.json"))
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(self.repair(), (0, []))
        self.assertEqual(list(self.tmp.glob("data-before-compatibility-*.json")), snapshots)

    def test_old_three_level_skin_keeps_disabled_package_and_record(self):
        source = self.make_pak("凯茜娅/狂诗/花间蝶踪/皮肤_100_P.pak.disabled")
        self.make_pak("凯茜娅/狂诗/花间蝶踪/皮肤_100_P.utoc.disabled")
        self.make_pak("凯茜娅/狂诗/花间蝶踪/皮肤_100_P.ucas.disabled")
        mod = self.store.add_mod(Mod(file=str(source), character="凯茜娅-狂诗", name="Custom name",
                                     note="Keep note", author="Author", preview="original.png", tags=["favorite"]))
        original_id = mod.id
        self.assertEqual(self.repair(), (1, []))
        self.assertEqual((mod.id, mod.name, mod.note, mod.author, mod.preview, mod.tags),
                         (original_id, "Custom name", "Keep note", "Author", "original.png", ["favorite"]))
        self.assertEqual(mod.skin, "floral-flutter")
        self.assertEqual(mod.directory, self.mods_dir / "katya-rhapsody/floral-flutter")
        self.assertFalse(mod.enabled)
        self.assertEqual(len(self.manager.siblings(mod)), 3)
        self.assertTrue(Store(self.store.path).load().mods[0].disabled_path.exists())

    def test_chinese_and_modern_folders_merge_without_overwrite(self):
        self.make_pak("凯茜娅-狂诗/Default_100_P.pak", "old")
        self.make_pak("katya-rhapsody/Default_100_P.pak", "new")
        _changed, errors = self.repair()
        self.assertEqual(errors, [])
        self.assertEqual({mod.disk_path.read_text() for mod in self.store.mods}, {"old", "new"})
        self.assertEqual(len({mod.file for mod in self.store.mods}), 2)
        self.assertEqual(self.repair(), (0, []))

    def test_new_skin_subfolders_are_never_flattened(self):
        source = self.make_pak("katya-rhapsody/floral-flutter/Skin.pak")
        self.repair()
        self.assertTrue(source.exists())
        self.assertEqual(self.store.mods[0].skin, "floral-flutter")
        self.assertNotIn("katya-rhapsody-floral-flutter", self.store.characters_with_mods())

    def test_chinese_skin_subfolder_and_middle_dot_are_recognized(self):
        self.make_pak("凯茜娅·狂诗/星抚恋音/Skin.pak")
        self.repair()
        self.assertEqual(self.store.mods[0].skin, "starlove-vow")
        self.assertEqual(self.store.mods[0].directory.name, "starlove-vow")

    def test_unrelated_folders_and_files_stay_untouched(self):
        source = self.make_pak("Unknown/Armor/keep.pak")
        note = self.make_pak("凯茜娅-狂诗/readme.txt", "keep")
        self.assertEqual(self.repair(), (0, []))
        self.assertTrue(source.exists() and note.exists())
        self.assertFalse(self.store.mods)

    def test_failed_package_move_can_be_retried(self):
        source = self.make_pak("凯茜娅-狂诗/Skin.pak.disabled")
        self.make_pak("凯茜娅-狂诗/Skin.utoc.disabled")
        with mock.patch("snowmm.core.manager.shutil.move", side_effect=PermissionError("locked")):
            changed, errors = self.repair()
        self.assertEqual(changed, 0)
        self.assertTrue(errors and source.exists())
        self.assertFalse(self.store.mods)
        self.assertEqual(self.repair(), (1, []))
        self.assertFalse(self.store.mods[0].enabled)

    def test_missing_record_path_relinks_to_manually_renamed_folder(self):
        original = self.mods_dir / "凯茜娅-狂诗/Existing.pak"
        target = self.make_pak("katya-rhapsody/Existing.pak")
        mod = self.store.add_mod(Mod(file=str(original), character="凯茜娅-狂诗", name="Keep metadata"))
        self.repair()
        self.assertEqual(len(self.store.mods), 1)
        self.assertEqual(mod.enabled_path, target)
        self.assertEqual(mod.name, "Keep metadata")

    def test_backup_failure_prevents_moving_any_files(self):
        source = self.make_pak("凯茜娅-狂诗/Skin.pak")
        with mock.patch("snowmm.core.compatibility.shutil.copy2", side_effect=OSError("full")):
            changed, errors = self.repair()
        self.assertEqual(changed, 0)
        self.assertTrue(errors and source.exists())

    def test_old_custom_character_record_with_known_armor_is_adopted(self):
        # Existing English paths and filenames never depend on the UI language.
        source = self.make_pak(f"{folder_for('基地')}/Object.pak")
        self.repair()
        self.assertEqual(self.store.mods[0].character, "基地")
        self.assertEqual(self.store.mods[0].enabled_path, Path(source))
