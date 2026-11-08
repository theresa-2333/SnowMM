"""Safety regressions exercise real library/deployment operations on disposable files."""

import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from snowmm.enhanced.library import LibraryManager
from snowmm.enhanced.storage import EnhancedSettings, LibraryStore


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.settings = EnhancedSettings.load_portable(self.root / "home")
        self.settings.storage_path = str(self.root / "分类库")
        self.settings.deploy_path = str(self.root / "game" / "~SnowMM")
        self.settings.deploy_mode = "copy"
        self.store = LibraryStore(Path(self.settings.storage_path), self.root / "home").load()
        self.manager = LibraryManager(self.store, self.settings)
        self.manager.running_check = lambda: False

    def tearDown(self):
        self.temp.cleanup()

    def mod(self, name="original_100_P.pak", content=b"content", category=None):
        source = self.root / ("source" + str(len(self.manager.mods))) / name
        source.parent.mkdir()
        source.write_bytes(content)
        result = self.manager.import_paths([source], category=category or ["角色", "芬妮", "澄意", "原皮"])
        self.assertEqual(result.errors, [])
        return result.added[0]

    def test_copy_deploy_deactivate_preserves_original_and_foreign(self):
        mod = self.mod()
        self.assertEqual(self.manager.set_enabled([mod], True), (1, []))
        root = self.manager.deployment.root
        (root / "foreign.pak").write_bytes(b"unknown")
        self.assertEqual((root / mod.filename).read_bytes(), b"content")
        self.assertEqual(self.manager.set_enabled([mod], False), (1, []))
        self.assertTrue(mod.disk_path.exists())
        self.assertEqual((root / "foreign.pak").read_bytes(), b"unknown")

    def test_unknown_same_name_refused(self):
        mod = self.mod()
        root = self.manager.deployment.root
        root.mkdir(parents=True)
        (root / mod.filename).write_bytes(b"foreign")
        self.assertTrue(self.manager.set_enabled([mod], True)[1])
        self.assertEqual((root / mod.filename).read_bytes(), b"foreign")

    def test_modified_owned_file_not_removed(self):
        mod = self.mod()
        self.manager.set_enabled([mod], True)
        target = self.manager.deployment.root / mod.filename
        target.write_bytes(b"changed by user")
        self.assertTrue(self.manager.set_enabled([mod], False)[1])
        self.assertEqual(target.read_bytes(), b"changed by user")

    def test_permission_does_not_fallback(self):
        mod = self.mod()
        self.settings.deploy_mode = "symlink"
        with patch("snowmm.enhanced.deployment.os.symlink", side_effect=PermissionError("blocked")):
            self.assertTrue(self.manager.set_enabled([mod], True)[1])
        self.assertFalse(self.manager.deployment.enabled_ids())
        self.assertEqual(self.settings.deploy_mode, "symlink")

    def test_real_symlink_broken_link_owned_removal(self):
        mod = self.mod()
        self.settings.deploy_mode = "symlink"
        count, errors = self.manager.set_enabled([mod], True)
        if errors and "Windows" in errors[0]:
            self.skipTest("Host has no symbolic-link privilege")
        self.assertEqual(errors, [])
        target = self.manager.deployment.root / mod.filename
        self.assertTrue(target.is_symlink())
        source = mod.disk_path
        source.rename(source.with_suffix(".hidden"))
        self.assertTrue(os.path.lexists(target))
        self.assertEqual(self.manager.set_enabled([mod], False), (1, []))
        self.assertFalse(os.path.lexists(target))

    def test_mutual_exclusion_and_same_category_stacking(self):
        first = self.mod("one.pak")
        second = self.mod("two.pak")
        self.manager.set_enabled([first, second], True)
        self.assertEqual(self.manager.deployment.enabled_ids(), {first.id, second.id})
        first.conflict_group = second.conflict_group = "同一衣服"
        self.manager.set_enabled([second], True)
        self.assertEqual(self.manager.deployment.enabled_ids(), {second.id})

    def test_library_rebuild_and_read_only_scan(self):
        mod = self.mod()
        mod.author = "作者"
        self.store.save()
        original = (Path(mod.folder) / "mod.json").read_bytes()
        self.store.path.unlink()
        self.manager.scan_storage()
        self.assertEqual(self.store.mods[0].author, "作者")
        self.assertEqual((Path(mod.folder) / "mod.json").read_bytes(), original)

    def test_paired_files_and_unicode_names_preserved(self):
        source = self.root / "source"
        source.mkdir()
        for extension in ["pak", "utoc", "ucas", "sig"]:
            (source / ("中文_100_P." + extension)).write_bytes(extension.encode())
        result = self.manager.import_paths([source], category=["NPC", "示例"])
        self.assertFalse(result.errors)
        mod = result.added[0]
        self.assertEqual(len(mod.files()), 4)
        self.assertEqual(self.manager.set_enabled([mod], True), (1, []))
        self.assertEqual(len(list(self.manager.deployment.root.glob("中文_100_P.*"))), 4)

    def test_archive_preserved_and_traversal_rejected(self):
        archive = self.root / "mods.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("nested/原名_100_P.pak", b"archive")
        result = self.manager.import_paths([archive], category=["插画"])
        self.assertFalse(result.errors)
        mod = result.added[0]
        self.assertEqual((Path(mod.folder) / "原始压缩包/mods.zip").read_bytes(), archive.read_bytes())
        with zipfile.ZipFile(self.root / "bad.zip", "w") as z:
            z.writestr("../escape.pak", b"no")
        self.assertTrue(self.manager.import_paths([self.root / "bad.zip"], category=["其他"]).errors)
        self.assertFalse((self.root.parent / "escape.pak").exists())

    def test_deploy_failure_rolls_back(self):
        first, second = self.mod("first.pak"), self.mod("second.pak")
        self.manager.set_enabled([first], True)
        replace = Path.replace

        def fail_one(path, target):
            if path.parent.name == "new" and path.name == "second.pak":
                raise OSError("simulated rename failure")
            return replace(path, target)

        with patch.object(Path, "replace", fail_one):
            self.assertTrue(self.manager.set_enabled([second], True)[1])
        self.assertEqual(self.manager.deployment.enabled_ids(), {first.id})
        self.assertEqual((self.manager.deployment.root / "first.pak").read_bytes(), b"content")

    def test_game_running_queues_without_file_changes(self):
        mod = self.mod()
        self.manager.running_check = lambda: True
        self.assertEqual(self.manager.set_enabled([mod], True)[0], 0)
        self.assertFalse(self.manager.deployment.manifest.exists())
        self.manager.running_check = lambda: False
        self.manager.apply_pending()
        self.assertTrue(mod.enabled)

    def test_category_rename_and_preset(self):
        mod = self.mod(category=["NPC", "旧分类"])
        self.manager.set_enabled([mod], True)
        self.manager.change_category(["NPC"], ["配角"])
        self.assertIn("配角", mod.folder)
        self.assertTrue(self.manager.is_enabled(mod))
        self.manager.save_preset("方案A")
        self.manager.set_enabled([mod], False)
        self.manager.load_preset("方案A")
        self.manager.apply_pending()
        self.assertTrue(self.manager.is_enabled(mod))

    def test_library_deploy_overlap_rejected(self):
        mod = self.mod()
        self.settings.deploy_path = str(self.store.root / "危险")
        self.assertTrue(self.manager.set_enabled([mod], True)[1])

    def test_same_name_and_altered_source_rejected(self):
        first, second = self.mod("same.pak"), self.mod("same.pak", b"other")
        self.assertTrue(self.manager.set_enabled([first, second], True)[1])
        first.disk_path.write_bytes(b"changed")
        self.assertTrue(self.manager.set_enabled([first], True)[1])

    def test_new_version_does_not_inherit_verified_status(self):
        mod = self.mod()
        original = mod.current_version
        mod.tested = "已验证"
        mod.game_versions = "3.6.0.186"
        mod.save()
        update = self.root / "update.pak"
        update.write_bytes(b"new revision")
        revision = self.manager.add_revision(mod, [update])
        self.manager.select_version(mod, revision)
        self.assertEqual(mod.tested, "未实测")
        self.assertEqual(mod.game_versions, "待确认")
        self.manager.select_version(mod, original)
        self.assertEqual(mod.tested, "已验证")

    def test_unknown_transaction_directory_not_removed(self):
        mod = self.mod()
        unknown = self.manager.deployment.root / ".snowmm-txn-not-owned"
        unknown.mkdir(parents=True)
        (unknown / "user-data.txt").write_bytes(b"keep")
        self.assertEqual(self.manager.set_enabled([mod], True), (1, []))
        self.assertEqual((unknown / "user-data.txt").read_bytes(), b"keep")

    def test_interrupted_transaction_recovers_prior_files(self):
        import json

        first, second = self.mod("first.pak"), self.mod("second.pak", b"next")
        self.manager.set_enabled([first], True)
        deployment = self.manager.deployment
        old = deployment.state()
        identity = "f" * 32
        stage = deployment.root / (".snowmm-txn-" + identity)
        (stage / "new").mkdir(parents=True)
        (stage / "old").mkdir()
        (stage / "owner.json").write_text(json.dumps({"owner": "SnowMMEnhanced", "id": identity}))
        (deployment.root / "first.pak").replace(stage / "old/first.pak")
        target = deployment.root / "second.pak"
        target.write_bytes(b"next")
        info = second.version()["files"][0]
        new = {
            "schema": 1,
            "files": [
                {
                    "name": "second.pak",
                    "mod_id": second.id,
                    "mode": "copy",
                    "source": str(second.disk_path.absolute()),
                    "sha256": info["sha256"],
                    "size": 4,
                    "version": second.current_version,
                }
            ],
        }
        (stage / "journal.json").write_text(json.dumps({"id": identity, "old": old, "new": new}))
        deployment.recover()
        self.assertFalse(target.exists())
        self.assertFalse(stage.exists())
        self.assertEqual(deployment.enabled_ids(), {first.id})


if __name__ == "__main__":
    unittest.main()
