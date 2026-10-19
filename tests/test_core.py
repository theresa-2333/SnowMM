"""Core (Qt free) unit tests: run with ``python -m unittest discover tests``."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

os.environ.setdefault("SNOWMM_HOME", tempfile.mkdtemp(prefix="snowmm-tests-"))

from snowmm.core import migrate, paths  # noqa: E402
from snowmm.core.catalog import Catalog, scan_art, slugify  # noqa: E402
from snowmm.core.manager import ModManager  # noqa: E402
from snowmm.core.models import Mod, human_size, unique_in_order  # noqa: E402
from snowmm.core.settings import Settings  # noqa: E402
from snowmm.core.store import Store  # noqa: E402


class TempCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="snowmm-case-"))
        self.mods_dir = self.tmp / "mods"
        self.mods_dir.mkdir()
        self.settings = Settings(storage_path=str(self.mods_dir))
        self.store = Store(self.tmp / "data.json")
        self.manager = ModManager(self.store, self.settings)

    def make_pak(self, relative: str, payload: str = "x") -> Path:
        path = self.mods_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
        return path


class ModModelTests(TempCase):
    def test_enabled_path_round_trip(self) -> None:
        mod = Mod(name="A", file=str(self.mods_dir / "A_100_P.pak.disabled"))
        self.assertEqual(mod.enabled_path.name, "A_100_P.pak")
        self.assertEqual(mod.disabled_path.name, "A_100_P.pak.disabled")

    def test_full_name_is_split_for_display(self) -> None:
        mod = Mod(name="A", character="凯茜娅-狂诗")
        self.assertEqual(mod.base_name, "凯茜娅")
        self.assertEqual(mod.armor_name, "狂诗")
        self.assertEqual(mod.pretty_name, "凯茜娅 · 狂诗")
        self.assertEqual(mod.category, ("凯茜娅-狂诗",))

    def test_legacy_schema_folds_armor_into_the_name(self) -> None:
        raw = {
            "name": "Cryo Odette",
            "path": str(self.mods_dir / "Cryo Odette.pak"),
            "note": "original Cryo Odette.pak",
            "image_path": "C:/images/a.png",
            "category1": "奥黛特",
            "category2": "冰",
            "category3": "默认",
        }
        mod = Mod.from_dict(raw)
        self.assertEqual(mod.character, "奥黛特-冰")
        self.assertEqual(mod.armor_name, "冰")
        self.assertEqual(mod.preview, "C:/images/a.png")

    def test_human_size(self) -> None:
        self.assertEqual(human_size(0), "0 B")
        self.assertTrue(human_size(2048).endswith("KB"))

    def test_unique_in_order(self) -> None:
        self.assertEqual(unique_in_order(["a", "", "b", "a"]), ["a", "b"])


class ManagerTests(TempCase):
    def test_import_enable_disable_delete(self) -> None:
        source = self.tmp / "My Mod_100_P.pak"
        source.write_text("pak", encoding="utf-8")
        result = self.manager.import_paths([source], character="里芙-狂猎", name="My Mod")
        self.assertEqual(len(result.added), 1)
        mod = result.added[0]
        self.assertTrue(Path(mod.file).exists())
        self.assertEqual(Path(mod.file).parent, self.mods_dir / "里芙-狂猎")

        self.manager.refresh_states()
        self.assertTrue(mod.enabled)

        self.manager.set_enabled([mod], False)
        self.assertTrue(Path(str(mod.file) + ".disabled").exists())
        self.assertFalse(Path(mod.file).exists())

        self.manager.set_enabled([mod], True)
        self.assertTrue(Path(mod.file).exists())

        removed, errors = self.manager.delete([mod])
        self.assertEqual(removed, 1)
        self.assertEqual(errors, [])
        self.assertFalse(Path(mod.file).exists())
        self.assertEqual(self.store.mods, [])

    def test_import_without_character_is_rejected(self) -> None:
        source = self.tmp / "x_100_P.pak"
        source.write_text("pak", encoding="utf-8")
        result = self.manager.import_paths([source], character="  ")
        self.assertEqual(result.added, [])
        self.assertEqual(result.errors, ["character-missing"])

    def test_companion_files_are_toggled_together(self) -> None:
        directory = self.mods_dir / "里芙-狂猎"
        directory.mkdir(parents=True)
        pak = directory / "Trio_100_P.pak"
        pak.write_text("pak", encoding="utf-8")
        (directory / "Trio_100_P.utoc").write_text("utoc", encoding="utf-8")
        mod = self.manager.scan_storage()[0]
        self.manager.refresh_states()
        self.manager.set_enabled([mod], False)
        self.assertTrue((directory / "Trio_100_P.pak.disabled").exists())
        self.assertTrue((directory / "Trio_100_P.utoc.disabled").exists())
        self.manager.set_enabled([mod], True)
        self.assertTrue(pak.exists())
        self.assertTrue((directory / "Trio_100_P.utoc").exists())

    def test_scan_adopts_existing_files(self) -> None:
        self.make_pak("芬妮-咎冠/Golden_100_P.pak")
        self.make_pak("芬妮-咎冠/Other_100_P.pak.disabled")
        adopted = self.manager.scan_storage()
        self.assertEqual(len(adopted), 2)
        by_name = {mod.name: mod for mod in adopted}
        self.assertFalse(by_name["Other_100_P"].enabled)
        self.assertEqual(by_name["Golden_100_P"].character, "芬妮-咎冠")
        self.assertEqual(self.manager.scan_storage(), [])

    def test_scan_ignores_folders_that_are_not_characters(self) -> None:
        self.make_pak("未知角色/ghost_100_P.pak")
        self.make_pak("里芙-狂猎/real_100_P.pak")
        self.make_pak("loose_100_P.pak")
        adopted = self.manager.scan_storage(known_characters={"里芙-狂猎"})
        self.assertEqual([mod.character for mod in adopted], ["里芙-狂猎"])
        self.assertEqual(self.manager.stats()["characters"], 1)

    def test_failed_import_leaves_no_empty_folder_behind(self) -> None:
        archive = self.tmp / "pack.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("x_100_P.pak", "payload")
        result = self.manager.import_paths([archive], character="里芙-狂猎")
        self.assertEqual(result.added, [])
        self.assertFalse((self.mods_dir / "里芙-狂猎").exists())

    def test_issues_reports_conflicts_and_unknown_characters(self) -> None:
        known = {"里芙-狂猎"}
        self.make_pak("里芙-狂猎/a_100_P.pak")
        self.make_pak("里芙-狂猎/b_100_P.pak")
        self.manager.scan_storage(known_characters=known)
        self.manager.refresh_states()
        kinds = {issue.kind for issue in self.manager.issues(known_characters=known)}
        self.assertIn("multi_enabled", kinds)
        self.assertNotIn("unknown_character", kinds)

    def test_issues_flags_mods_outside_the_roster(self) -> None:
        source = self.tmp / "stray_100_P.pak"
        source.write_text("pak", encoding="utf-8")
        self.manager.import_paths([source], character="某不存在的角色-装甲")
        issues = self.manager.issues(known_characters={"里芙-狂猎"})
        unknown = [issue for issue in issues if issue.kind == "unknown_character"]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0].data["character"], "某不存在的角色-装甲")
        self.assertEqual(unknown[0].data["count"], "1")

    def test_missing_file_is_reported(self) -> None:
        source = self.tmp / "gone_100_P.pak"
        source.write_text("pak", encoding="utf-8")
        mod = self.manager.import_paths([source], character="肴-夜天光").added[0]
        Path(mod.file).unlink()
        self.manager.refresh_states()
        kinds = {issue.kind for issue in self.manager.issues()}
        self.assertIn("missing_file", kinds)

    def test_move_mod_between_characters(self) -> None:
        source = self.tmp / "move_100_P.pak"
        source.write_text("pak", encoding="utf-8")
        mod = self.manager.import_paths([source], character="肴-夜天光").added[0]
        error = self.manager.move_mod(mod, "肴-冬至")
        self.assertIsNone(error)
        self.assertTrue((self.mods_dir / "肴-冬至" / "move_100_P.pak").exists())
        self.assertEqual(mod.character, "肴-冬至")
        self.assertEqual(mod.armor_name, "冬至")
        self.assertFalse((self.mods_dir / "肴-夜天光").exists())

    def test_rename_stem_keeps_suffix_and_state(self) -> None:
        source = self.tmp / "OldName_100_P.pak"
        source.write_text("pak", encoding="utf-8")
        mod = self.manager.import_paths([source], character="恩雅-羽蜕").added[0]
        self.manager.set_enabled([mod], False)
        error = self.manager.rename_stem(mod, "NewName_100_P")
        self.assertIsNone(error)
        directory = self.mods_dir / "恩雅-羽蜕"
        self.assertTrue((directory / "NewName_100_P.pak.disabled").exists(), list(directory.iterdir()))
        self.assertEqual(mod.filename, "NewName_100_P.pak")

    def test_set_character_enabled_toggles_only_that_character(self) -> None:
        first = self.tmp / "one_100_P.pak"
        second = self.tmp / "two_100_P.pak"
        other = self.tmp / "three_100_P.pak"
        for path in (first, second, other):
            path.write_text("x", encoding="utf-8")
        self.manager.import_paths([first, second], character="恩雅-羽蜕")
        self.manager.import_paths([other], character="恩雅-澜风")
        changed, errors = self.manager.set_character_enabled("恩雅-羽蜕", False)
        self.assertEqual(errors, [])
        self.assertEqual(changed, 2)
        self.manager.refresh_states()
        states = {mod.character: mod.enabled for mod in self.store.mods}
        self.assertFalse(states["恩雅-羽蜕"])
        self.assertTrue(states["恩雅-澜风"])

    def test_store_round_trip(self) -> None:
        source = self.tmp / "persist_100_P.pak"
        source.write_text("pak", encoding="utf-8")
        self.manager.import_paths([source], character="辰星-紫贝")
        self.store.save()
        reloaded = Store(self.store.path).load()
        self.assertEqual(len(reloaded.mods), 1)
        self.assertEqual(reloaded.mods[0].character, "辰星-紫贝")
        self.assertEqual(json.loads(self.store.path.read_text(encoding="utf-8"))["schema"], 3)

    def test_corrupt_store_is_backed_up(self) -> None:
        self.store.path.write_text("{ not json", encoding="utf-8")
        recovered = Store(self.store.path).load()
        self.assertEqual(recovered.mods, [])
        self.assertTrue(self.store.path.with_suffix(".corrupt.json").exists())


class ArchiveImportTests(TempCase):
    def test_archives_are_refused_until_support_returns(self) -> None:
        archive = self.tmp / "pack.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("皮肤/模型_100_P.pak", "payload")
        result = self.manager.import_paths([archive], character="测试角色-装甲")
        self.assertEqual(result.added, [])
        self.assertEqual(len(result.errors), 1)
        self.assertIn(".zip", result.errors[0])
        self.assertFalse((self.mods_dir / "测试角色-装甲").exists())

    def test_folder_import_copies_nested_files(self) -> None:
        folder = self.tmp / "bundle"
        (folder / "sub").mkdir(parents=True)
        (folder / "sub" / "inner_100_P.pak").write_text("pak", encoding="utf-8")
        result = self.manager.import_paths([folder], character="安卡希雅-辉夜")
        self.assertEqual(len(result.added), 1)
        self.assertTrue((self.mods_dir / "安卡希雅-辉夜" / "inner_100_P.pak").exists())

    def test_duplicate_names_keep_the_mount_suffix(self) -> None:
        first = self.tmp / "same_100_P.pak"
        first.write_text("a", encoding="utf-8")
        self.manager.import_paths([first], character="A-B")
        second = self.tmp / "other" / "same_100_P.pak"
        second.parent.mkdir(parents=True, exist_ok=True)
        second.write_text("b", encoding="utf-8")
        result = self.manager.import_paths([second], character="A-B")
        self.assertEqual(len(result.added), 1)
        names = sorted(item.name for item in (self.mods_dir / "A-B").iterdir())
        self.assertEqual(names, ["same (2)_100_P.pak", "same_100_P.pak"])

    def test_7z_archive_is_refused(self) -> None:
        archive = self.tmp / "pack.7z"
        archive.write_bytes(b"7z")
        result = self.manager.import_paths([archive], character="凯茜娅-狂诗")
        self.assertEqual(result.added, [])
        self.assertEqual(len(result.errors), 1)
        self.assertIn(".7z", result.errors[0])


class PackageRegressionTests(TempCase):
    def bundle(self, folder="download", stem="Skin_100_P", disabled=False):
        directory = self.tmp / folder
        directory.mkdir(parents=True, exist_ok=True)
        files = []
        for ext in (".pak", ".utoc", ".ucas", ".sig"):
            path = directory / (stem + ext + (".disabled" if disabled else ""))
            path.write_text(ext, encoding="utf-8")
            files.append(path)
        return files

    def test_single_pak_import_includes_companions_and_scan_is_idempotent(self):
        files = self.bundle()
        result = self.manager.import_paths([files[0]], character="A-B")
        self.assertEqual(len(result.added), 1)
        self.assertEqual(len(self.manager.siblings(result.added[0])), 4)
        self.assertEqual(self.manager.scan_storage(), [])

    def test_multiple_selected_companions_create_one_record(self):
        result = self.manager.import_paths(self.bundle(), character="A-B")
        self.assertEqual(len(result.added), 1)
        self.assertEqual(result.errors, [])

    def test_folder_registers_every_package(self):
        self.bundle("download/one")
        self.bundle("download/two", stem="Other")
        result = self.manager.import_paths([self.tmp / "download"], character="A-B")
        self.assertEqual(len(result.added), 2)
        self.assertEqual(len(list((self.mods_dir / "A-B").iterdir())), 8)

    def test_collision_uses_one_stem_for_whole_package(self):
        files = self.bundle()
        self.make_pak("A-B/Skin_100_P.utoc.disabled", "existing")
        mod = self.manager.import_paths([files[0]], character="A-B").added[0]
        self.assertEqual(mod.stem, "Skin (2)_100_P")
        self.assertEqual(len(self.manager.siblings(mod)), 4)
        self.assertEqual((self.mods_dir / "A-B/Skin_100_P.utoc.disabled").read_text(), "existing")

    def test_disabled_import_preserves_state(self):
        files = self.bundle(disabled=True)
        mod = self.manager.import_paths([files[0]], character="A-B").added[0]
        self.assertFalse(mod.enabled)
        self.assertFalse(mod.file.endswith(".disabled"))
        self.assertEqual(self.manager.set_enabled([mod], True), (1, []))
        self.assertTrue(mod.enabled_path.exists())

    def test_failed_toggle_keeps_actual_state_and_does_not_touch_companions(self):
        mod = self.manager.import_paths([self.bundle()[0]], character="A-B").added[0]
        collision = Path(str(mod.enabled_path.with_suffix(".utoc")) + ".disabled")
        collision.write_text("keep", encoding="utf-8")
        changed, errors = self.manager.set_enabled([mod], False)
        self.assertEqual(changed, 0)
        self.assertTrue(errors)
        self.assertTrue(mod.enabled)
        self.assertTrue(mod.enabled_path.exists())
        self.assertTrue(mod.enabled_path.with_suffix(".utoc").exists())

    def test_runtime_move_failure_rolls_back_package(self):
        mod = self.manager.import_paths([self.bundle()[0]], character="A-B").added[0]
        import shutil
        original = shutil.move
        calls = 0
        def fail_second(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("locked")
            return original(source, target)
        with mock.patch("snowmm.core.manager.shutil.move", side_effect=fail_second):
            changed, errors = self.manager.set_enabled([mod], False)
        self.assertEqual(changed, 0)
        self.assertTrue(errors)
        self.assertTrue(mod.enabled)
        self.assertEqual(len(list(mod.directory.glob("*.disabled"))), 0)
        self.assertEqual(len(self.manager.siblings(mod)), 4)

    def test_move_collision_preserves_package_and_disabled_state(self):
        mod = self.manager.import_paths([self.bundle()[0]], character="A-B").added[0]
        self.manager.set_enabled([mod], False)
        self.make_pak("C-D/Skin_100_P.ucas")
        self.assertIsNone(self.manager.move_mod(mod, "C-D"))
        self.assertEqual(mod.stem, "Skin (2)_100_P")
        self.assertFalse(mod.enabled_path.exists())
        self.assertEqual(len(self.manager.siblings(mod)), 4)
        self.assertFalse((self.mods_dir / "A-B").exists())

    def test_rename_collision_is_checked_before_any_file_moves(self):
        mod = self.manager.import_paths([self.bundle()[0]], character="A-B").added[0]
        self.make_pak("A-B/New.utoc.disabled")
        self.assertIsNotNone(self.manager.rename_stem(mod, "New"))
        self.assertEqual(len(self.manager.siblings(mod)), 4)
        self.assertEqual(mod.stem, "Skin_100_P")

    def test_delete_does_not_delete_unrelated_same_stem_files(self):
        mod = self.manager.import_paths([self.bundle()[0]], character="A-B").added[0]
        note = mod.enabled_path.with_suffix(".txt")
        note.write_text("keep", encoding="utf-8")
        self.assertEqual(self.manager.delete([mod]), (1, []))
        self.assertTrue(note.exists())

    def test_delete_failure_preserves_record(self):
        mod = self.manager.import_paths([self.bundle()[0]], character="A-B").added[0]
        with mock.patch.object(Path, "unlink", side_effect=PermissionError("locked")):
            removed, errors = self.manager.delete([mod])
        self.assertEqual(removed, 0)
        self.assertTrue(errors)
        self.assertIn(mod, self.store.mods)

    def test_invalid_target_folder_is_rejected(self):
        files = self.bundle()
        result = self.manager.import_paths([files[0]], character="../escape")
        self.assertTrue(result.errors)
        self.assertFalse((self.tmp / "escape").exists())

    def test_failed_copy_cleans_up_partial_package(self):
        files = self.bundle()
        with mock.patch("snowmm.core.manager.shutil.copyfileobj", side_effect=OSError("disk full")):
            result = self.manager.import_paths([files[0]], character="A-B")
        self.assertTrue(result.errors)
        self.assertFalse(result.added)
        self.assertFalse((self.mods_dir / "A-B").exists())


class LayoutFlattenTests(TempCase):
    def test_flattens_the_legacy_tree(self) -> None:
        self.make_pak("凯茜娅/狂诗/默认/one_100_P.pak")
        self.make_pak("凯茜娅/狂诗/泳装/two_100_P.pak")
        self.make_pak("凯茜娅/蓝闪/默认/three_100_P.pak")
        self.assertEqual(migrate.legacy_layout_count(self.mods_dir), 2)

        moved, warnings = migrate.flatten_layout(self.mods_dir)

        self.assertEqual(moved, 3)
        self.assertEqual(warnings, [])
        self.assertTrue((self.mods_dir / "凯茜娅-狂诗" / "one_100_P.pak").exists())
        self.assertTrue((self.mods_dir / "凯茜娅-狂诗" / "two_100_P.pak").exists())
        self.assertTrue((self.mods_dir / "凯茜娅-蓝闪" / "three_100_P.pak").exists())
        self.assertFalse((self.mods_dir / "凯茜娅").exists())
        self.assertEqual(migrate.legacy_layout_count(self.mods_dir), 0)

    def test_collisions_are_renamed_not_lost(self) -> None:
        self.make_pak("凯茜娅/狂诗/默认/same_100_P.pak")
        self.make_pak("凯茜娅/狂诗/泳装/same_100_P.pak")

        moved, warnings = migrate.flatten_layout(self.mods_dir)

        self.assertEqual(moved, 2)
        self.assertEqual(len(warnings), 1)
        names = sorted(item.name for item in (self.mods_dir / "凯茜娅-狂诗").iterdir())
        self.assertEqual(names, ["same (2)_100_P.pak", "same_100_P.pak"])

    def test_flatten_keeps_disabled_packages_together_and_updates_records(self):
        source = self.make_pak("角色/装甲/默认/Skin_100_P.pak.disabled")
        self.make_pak("角色/装甲/默认/Skin_100_P.utoc.disabled")
        self.make_pak("角色-装甲/Skin_100_P.ucas")
        mod = Mod(file=str(source), character="角色-装甲")
        self.store.add_mod(mod)
        moved, warnings = migrate.flatten_layout(self.mods_dir, store=self.store)
        self.assertEqual(moved, 2)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(mod.stem, "Skin (2)_100_P")
        self.assertTrue(mod.disabled_path.exists())
        self.assertTrue(mod.disabled_path.with_name("Skin (2)_100_P.utoc.disabled").exists())
        self.assertTrue(Store(self.store.path).load().mods[0].exists)

    def test_flat_layout_is_left_alone(self) -> None:
        self.make_pak("凯茜娅-狂诗/one_100_P.pak")
        self.assertEqual(migrate.legacy_layout_count(self.mods_dir), 0)
        self.assertEqual(migrate.flatten_layout(self.mods_dir), (0, []))


class MigrationTests(TempCase):
    def setUp(self) -> None:
        super().setUp()
        self.legacy = self.tmp / "legacy"
        (self.legacy / "images").mkdir(parents=True)
        self.legacy_preview = self.legacy / "images" / "preview.png"
        self.legacy_preview.write_bytes(b"png")
        self.mod_file = self.make_pak("奥黛特-冰/Odette_100_P.pak")
        projects = [
            {
                "name": "Odette OG",
                "path": str(self.mod_file),
                "note": "original Odette_100_P.pak",
                "image_path": str(self.legacy_preview),
                "category1": "奥黛特",
                "category2": "冰",
                "category3": "默认",
            }
        ]
        (self.legacy / "projects.json").write_text(json.dumps(projects), encoding="utf-8")
        (self.legacy / "config.json").write_text(
            json.dumps({"storage_path": str(self.mods_dir), "theme": "light", "language": "en_US"}),
            encoding="utf-8",
        )

    def _patch_paths(self):
        return mock.patch.multiple(
            paths,
            LEGACY_PROJECTS_FILE=self.legacy / "projects.json",
            LEGACY_CONFIG_FILE=self.legacy / "config.json",
        )

    def test_imports_records_settings_and_preview(self) -> None:
        with self._patch_paths():
            imported, warnings = migrate.migrate(self.store, self.settings)
        self.assertEqual(imported, 1)
        self.assertEqual(warnings, [])
        self.assertEqual(len(self.store.mods), 1)
        mod = self.store.mods[0]
        self.assertEqual(mod.character, "奥黛特-冰")
        self.assertNotEqual(mod.preview, str(self.legacy_preview))
        self.assertTrue(Path(mod.preview).exists())
        self.assertEqual(self.settings.theme, "light")
        self.assertEqual(self.settings.language, "en_US")

    def test_migration_is_idempotent(self) -> None:
        with self._patch_paths():
            migrate.migrate(self.store, self.settings)
            imported_again, _ = migrate.migrate(self.store, self.settings)
        self.assertEqual(imported_again, 0)
        self.assertEqual(len(self.store.mods), 1)


class ArtLibraryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="snowmm-art-"))
        (self.tmp / "高热").mkdir()
        (self.tmp / "低温").mkdir()
        # The 40x40 element icon sits next to the portraits and must be skipped.
        (self.tmp / "高热" / "高热.png").write_bytes(b"icon")
        (self.tmp / "高热" / "妮塔-悸响.png").write_bytes(b"art")
        (self.tmp / "高热" / "肴-冬至.png").write_bytes(b"art")
        (self.tmp / "低温" / "凯茜娅-狂诗.png").write_bytes(b"art")
        (self.tmp / "低温" / "notes.txt").write_text("not an image", encoding="utf-8")

    def test_scan_reads_element_folders_and_skips_icons(self) -> None:
        found = {character.name: character for character in scan_art(self.tmp)}
        self.assertEqual(sorted(found), ["凯茜娅-狂诗", "妮塔-悸响", "肴-冬至"])
        self.assertEqual(found["凯茜娅-狂诗"].element, "低温")
        self.assertTrue(found["妮塔-悸响"].portrait.endswith("妮塔-悸响.png"))

    def test_bundled_catalog_matches_the_art_library(self) -> None:
        catalog = Catalog.load([])
        names = catalog.names()
        self.assertGreaterEqual(len(catalog), 50)
        self.assertIn("凯茜娅-狂诗", names)
        self.assertIn("卜卜-灵鉴", names)
        entry = catalog.get("凯茜娅-狂诗")
        self.assertEqual(entry.element, "低温")
        self.assertEqual(entry.role, "dps")
        self.assertEqual(entry.armor_name, "狂诗")
        self.assertTrue(Path(entry.portrait).exists())
        self.assertEqual(catalog.elements()[0], "高热")

    def test_siblings_lists_the_other_armors(self) -> None:
        catalog = Catalog.load([])
        siblings = {item.name for item in catalog.siblings("凯茜娅-狂诗")}
        self.assertIn("凯茜娅-蓝闪", siblings)
        self.assertIn("凯茜娅-朝翼", siblings)
        self.assertNotIn("凯茜娅-狂诗", siblings)
        self.assertNotIn("里芙-狂猎", siblings)

    def test_annotations_never_invent_characters(self) -> None:
        # A metadata entry without a matching image must not create a card.
        empty = Path(tempfile.mkdtemp(prefix="snowmm-empty-"))
        catalog = Catalog.load([], art_dir=empty)
        self.assertEqual(len(catalog), 0)

    def test_user_characters_override_annotations(self) -> None:
        catalog = Catalog.load([{"name": "凯茜娅-狂诗", "name_en": "Katya (edited)"}])
        merged = catalog.get("凯茜娅-狂诗")
        self.assertEqual(merged.name_en, "Katya (edited)")
        self.assertTrue(merged.user_defined)
        self.assertEqual(merged.element, "低温")

    def test_roster_is_the_fixed_54_and_records_never_grow_it(self) -> None:
        # The bundled art library is the single source of truth; a stored record
        # may annotate an existing entry but can never invent a character.
        self.assertEqual(len(Catalog.load([])), 54)
        stored = Catalog.load(
            [
                {"name": "凯茜娅-狂诗", "name_en": "Katya (edited)"},
                {"name": "Not A Character", "element": "高热"},
            ]
        )
        self.assertEqual(len(stored), 54)
        self.assertNotIn("Not A Character", stored.names())
        self.assertEqual(stored.get("凯茜娅-狂诗").name_en, "Katya (edited)")

    def test_reload_keeps_references_valid(self) -> None:
        catalog = Catalog.load([])
        before = len(catalog)
        catalog.reload([])
        self.assertEqual(len(catalog), before)

    def test_slug_is_stable_and_safe(self) -> None:
        first = slugify("里芙")
        self.assertEqual(first, slugify("里芙"))
        self.assertNotIn("/", first)


class SettingsTests(unittest.TestCase):
    def test_unknown_keys_and_bad_values_are_ignored(self) -> None:
        settings = Settings.from_dict({"theme": "neon", "language": "fr_FR", "nonsense": 1})
        self.assertEqual(settings.theme, "dark")
        self.assertEqual(settings.language, "zh_CN")

    def test_favourite_toggle(self) -> None:
        settings = Settings()
        self.assertTrue(settings.toggle_favorite("凯茜娅-狂诗"))
        self.assertTrue(settings.is_favorite("凯茜娅-狂诗"))
        self.assertFalse(settings.toggle_favorite("凯茜娅-狂诗"))

    def test_round_trip(self) -> None:
        target = Path(tempfile.mkdtemp(prefix="snowmm-settings-")) / "settings.json"
        settings = Settings(storage_path="C:/mods", favorites=["里芙"], theme="light")
        settings.save(target)
        self.assertEqual(Settings.load(target).storage_path, "C:/mods")
        self.assertEqual(Settings.load(target).favorites, ["里芙"])


if __name__ == "__main__":
    unittest.main()
