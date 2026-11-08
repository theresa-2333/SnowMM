"""Public contribution must work without the original developer profile or repair bundle."""

import tempfile
import unittest
from pathlib import Path

from snowmm.enhanced.library import LibraryManager
from snowmm.enhanced.repair import RepairService
from snowmm.enhanced.storage import EnhancedSettings, LibraryStore


class PublicDefaultsTests(unittest.TestCase):
    def test_fresh_profile_has_no_machine_specific_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = EnhancedSettings.load_portable(Path(temp))
            self.assertEqual(settings.game_exe, "")
            self.assertEqual(settings.deploy_path, "")
            self.assertEqual(settings.server_exe, "")
            self.assertEqual(settings.repair_tool, "")
            self.assertFalse(settings.bundled_repair)
            self.assertEqual(Path(settings.storage_path), Path.home() / "SnowMM" / "Library")

    def test_unconfigured_deployment_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = EnhancedSettings.load_portable(root / "home")
            settings.storage_path = str(root / "library")
            manager = LibraryManager(LibraryStore(root / "library", root / "home").load(), settings)
            with self.assertRaisesRegex(ValueError, "游戏应用目录"):
                manager._apply_ids(set())
            self.assertFalse((root / "home/unconfigured-deployment").exists())

    def test_repair_without_external_tools_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = EnhancedSettings.load_portable(Path(temp))
            with self.assertRaisesRegex(FileNotFoundError, "尚未配置"):
                RepairService(settings)._run("assess_mod.py", ["-h"], temp)
