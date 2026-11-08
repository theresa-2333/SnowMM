"""Permission failure/cancellation must not change modes, deploy or close the app."""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from snowmm.enhanced.permissions import check_link_permission, request_admin_restart, restart_command


class PermissionTests(unittest.TestCase):
    def test_probe_denied_cleans_unique_files_and_preserves_existing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".symlink_test_src").write_bytes(b"user data")
            with patch("snowmm.enhanced.permissions.os.symlink", side_effect=PermissionError("denied")):
                result = check_link_permission(root / "not-created" / "~SnowMM")
            self.assertFalse(result.allowed)
            self.assertIn("权限不足", result.message)
            self.assertEqual(list(root.iterdir()), [root / ".symlink_test_src"])
            self.assertEqual((root / ".symlink_test_src").read_bytes(), b"user data")

    def test_probe_success_verifies_content_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as temp:
            with (
                patch("snowmm.enhanced.permissions.os.symlink", side_effect=shutil.copyfile),
                patch("pathlib.Path.is_symlink", return_value=True),
            ):
                self.assertTrue(check_link_permission(Path(temp)).allowed)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_probe_other_io_error_not_claimed_to_be_admin_problem(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch("snowmm.enhanced.permissions.os.symlink", side_effect=OSError("unsupported filesystem")):
                result = check_link_permission(Path(temp))
            self.assertFalse(result.allowed)
            self.assertIn("文件系统", result.message)
            self.assertNotIn("权限不足", result.message)

    def test_probe_file_path_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "file"
            file.write_bytes(b"original")
            self.assertFalse(check_link_permission(file).allowed)
            self.assertEqual(file.read_bytes(), b"original")

    def test_restart_only_passes_entry_and_same_profile(self):
        with tempfile.TemporaryDirectory(prefix="中文 space ") as temp:
            with patch.object(sys, "argv", ["ignored.exe", "--self-test", "never-forward"]):
                executable, args, cwd = restart_command(Path(temp))
            self.assertEqual(executable, str(Path(sys.executable).resolve()))
            self.assertIn("enhanced_main.py", args)
            self.assertIn('--enhanced-home "', args)
            self.assertIn(str(Path(temp).resolve()), args)
            self.assertNotIn("self-test", args)
            self.assertEqual(cwd, str(Path(executable).parent))

    def test_frozen_restart_does_not_pass_script_or_duplicate_exe(self):
        with patch.object(sys, "frozen", True, create=True):
            executable, args, _ = restart_command(Path("中文 profile"))
        self.assertTrue(executable)
        self.assertTrue(args.startswith("--enhanced-home "))
        self.assertNotIn("enhanced_main.py", args)

    @unittest.skipUnless(sys.platform == "win32", "Windows shell API")
    def test_uac_cancel_returns_false_without_real_uac(self):
        shell = Mock()
        shell.ShellExecuteExW.return_value = 0
        with patch("ctypes.WinDLL", return_value=shell), patch("ctypes.get_last_error", return_value=1223):
            self.assertFalse(request_admin_restart(Path("profile")))
        info = shell.ShellExecuteExW.call_args.args[0]._obj
        self.assertEqual(info.lpVerb, "runas")
        self.assertIn("--enhanced-home", info.lpParameters)

    @unittest.skipUnless(sys.platform == "win32", "Windows shell API")
    def test_shell_error_is_not_treated_as_success(self):
        shell = Mock()
        shell.ShellExecuteExW.return_value = 0
        with (
            patch("ctypes.WinDLL", return_value=shell),
            patch("ctypes.get_last_error", return_value=5),
            self.assertRaises(OSError),
        ):
            request_admin_restart(Path("profile"))

    @unittest.skipUnless(sys.platform == "win32", "Windows shell API")
    def test_shell_success_closes_only_process_handle(self):
        shell, kernel = Mock(), Mock()

        def accepted(pointer):
            pointer._obj.hProcess = 123
            return 1

        shell.ShellExecuteExW.side_effect = accepted
        with patch("ctypes.WinDLL", side_effect=[shell, kernel]):
            self.assertTrue(request_admin_restart(Path("profile")))
        kernel.CloseHandle.assert_called_once_with(123)
