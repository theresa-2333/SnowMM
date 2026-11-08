"""Exercise Windows link spelling differences through ownership and real transactions.

The transaction fixture replaces only symlink APIs, so these regressions also run
without SeCreateSymbolicLinkPrivilege. File moves, journals and rollback are real.
"""

import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from snowmm.enhanced.deployment import Deployment
from snowmm.enhanced.library import LibraryManager
from snowmm.enhanced.storage import EnhancedSettings, LibraryStore


@unittest.skipUnless(os.name == "nt", "Windows path spelling")
class WindowsLinkIdentityTests(unittest.TestCase):
    def matches(self, actual, expected, link=None, is_link=True):
        link = link or Path(r"G:\game\~SnowMM\.snowmm-txn-fixture\new\测试.pak")
        with (
            patch("snowmm.enhanced.deployment.os.path.lexists", return_value=True),
            patch.object(Path, "is_symlink", return_value=is_link),
            patch("snowmm.enhanced.deployment.os.readlink", return_value=actual),
        ):
            return Deployment.matches(link, {"mode": "symlink", "source": expected})

    def test_extended_drive_path_matches_plain_manifest(self):
        self.assertTrue(self.matches(r"\\?\G:\中文 资源库\原始_100_P.pak", r"G:\中文 资源库\原始_100_P.pak"))

    def test_plain_path_matches_extended_manifest(self):
        self.assertTrue(self.matches(r"G:\模组\原件.pak", r"\\?\G:\模组\原件.pak"))

    def test_extended_unc_path_matches_plain_unc_manifest(self):
        self.assertTrue(self.matches(r"\\?\UNC\server\share\中文\a.pak", r"\\server\share\中文\a.pak"))

    def test_case_differences_still_match(self):
        self.assertTrue(self.matches(r"\\?\g:\Mods\ORIGINAL.pak", r"G:\mods\original.pak"))

    def test_relative_link_is_anchored_at_its_parent(self):
        self.assertTrue(self.matches(r"..\..\library\a.pak", r"G:\library\a.pak", Path(r"G:\game\~SnowMM\a.pak")))

    def test_relative_link_is_not_resolved_against_process_cwd(self):
        self.assertFalse(self.matches("a.pak", str(Path.cwd() / "a.pak")))

    def test_different_file_is_not_owned(self):
        self.assertFalse(self.matches(r"\\?\G:\mods\other.pak", r"G:\mods\original.pak"))

    def test_different_unc_share_is_not_owned(self):
        self.assertFalse(self.matches(r"\\?\UNC\server\other\a.pak", r"\\server\share\a.pak"))

    def test_regular_file_is_not_a_matching_link(self):
        self.assertFalse(self.matches(r"G:\mods\a.pak", r"G:\mods\a.pak", is_link=False))

    def test_volume_device_path_is_not_guessed_to_be_a_drive(self):
        self.assertFalse(self.matches(r"\\?\Volume{fixture}\mods\a.pak", r"G:\mods\a.pak"))


@unittest.skipUnless(os.name == "nt", "Windows symlink substitution paths")
class WindowsLinkTransactionTests(unittest.TestCase):
    marker = b"SnowMM test symlink\0"

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        settings = EnhancedSettings.load_portable(self.root / "home")
        settings.storage_path = str(self.root / "中文 资源库")
        settings.deploy_path = str(self.root / "game/~SnowMM")
        settings.deploy_mode = "symlink"
        self.manager = LibraryManager(LibraryStore(Path(settings.storage_path), self.root / "home").load(), settings)
        self.manager.running_check = lambda: False
        source = self.root / "测试_100_P.pak"
        source.write_bytes(b"original mod fixture")
        imported = self.manager.import_paths([source], category=["杂项"])
        self.assertEqual(imported.errors, [])
        self.mod = imported.added[0]
        self.original = self.mod.disk_path.read_bytes()
        real_is_symlink = Path.is_symlink

        def is_symlink(path):
            return (path.is_file() and path.read_bytes().startswith(self.marker)) or real_is_symlink(path)

        def symlink(source, target):
            Path(target).write_bytes(self.marker + ("\\\\?\\" + str(source)).encode("utf-8"))

        def readlink(path):
            return Path(path).read_bytes()[len(self.marker) :].decode("utf-8")

        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.object(Path, "is_symlink", is_symlink))
        self.patches.enter_context(patch("snowmm.enhanced.deployment.os.symlink", side_effect=symlink))
        self.patches.enter_context(patch("snowmm.enhanced.deployment.os.readlink", side_effect=readlink))

    def enable(self):
        self.assertEqual(self.manager.set_enabled([self.mod], True), (1, []))
        return self.manager.deployment.root / self.mod.filename

    def test_extended_target_can_stage_commit_refresh_and_disable(self):
        target = self.enable()
        self.assertTrue(target.is_symlink())
        self.assertEqual(self.manager.deployment.enabled_ids(), {self.mod.id})
        self.assertEqual(self.manager.deployment.errors(), [])
        self.assertEqual(self.manager.set_enabled([self.mod], False), (1, []))
        self.assertFalse(os.path.lexists(target))
        self.assertEqual(self.mod.disk_path.read_bytes(), self.original)

    def test_dangling_extended_target_can_still_be_removed_safely(self):
        target = self.enable()
        hidden = self.mod.disk_path.with_suffix(".temporarily-hidden")
        self.mod.disk_path.rename(hidden)
        self.assertEqual(self.manager.set_enabled([self.mod], False), (1, []))
        self.assertFalse(os.path.lexists(target))
        self.assertEqual(hidden.read_bytes(), self.original)

    def test_retargeted_link_is_preserved_and_removal_refused(self):
        target = self.enable()
        target.write_bytes(self.marker + str(self.root / "foreign.pak").encode("utf-8"))
        foreign = target.read_bytes()
        self.assertTrue(self.manager.set_enabled([self.mod], False)[1])
        self.assertEqual(target.read_bytes(), foreign)
        self.assertEqual(self.mod.disk_path.read_bytes(), self.original)

    def test_failed_commit_restores_previous_prefixed_link(self):
        target = self.enable()
        before = target.read_bytes()
        real_replace = Path.replace

        def fail_staged_commit(path, destination):
            if path.parent.name == "new" and path.name == self.mod.filename:
                raise OSError("injected commit failure")
            return real_replace(path, destination)

        with (
            patch.object(Path, "replace", fail_staged_commit),
            self.assertRaisesRegex(OSError, "injected commit failure"),
        ):
            self.manager.deployment.apply([self.mod], "copy")
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(self.manager.deployment.enabled_ids(), {self.mod.id})
        self.assertEqual(self.mod.disk_path.read_bytes(), self.original)
