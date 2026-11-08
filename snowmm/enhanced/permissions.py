"""Explicit Windows permission checks and user-requested elevation; no fallback."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LinkCheck:
    allowed: bool
    directory: str
    message: str


def check_link_permission(directory: Path) -> LinkCheck:
    """Probe in the closest existing target ancestor, using unique disposable files."""
    location = directory.absolute()
    while not location.exists() and location.parent != location:
        location = location.parent
    try:
        if not location.is_dir():
            raise ValueError("目标磁盘或目录不存在")
        with tempfile.TemporaryDirectory(prefix=".snowmm-link-check-", dir=location) as temporary:
            source, target = Path(temporary) / "source.txt", Path(temporary) / "link.txt"
            source.write_text("SnowMM disposable permission check", encoding="utf-8")
            os.symlink(source, target)
            if not target.is_symlink() or target.read_bytes() != source.read_bytes():
                raise OSError("链接创建后校验失败")
        return LinkCheck(True, str(location), "当前进程可以创建文件符号链接；实际部署仍会检查目标文件冲突。")
    except (OSError, ValueError) as error:
        privilege = getattr(error, "winerror", None) == 1314 or isinstance(error, PermissionError)
        hint = "权限不足，可选择管理员重启、开发者模式或复制模式。" if privilege else "请检查磁盘、目录权限和文件系统。"
        return LinkCheck(False, str(location), f"链接检测未通过：{error}\n{hint}")


def is_admin() -> bool:
    return os.name == "nt" and bool(ctypes.windll.shell32.IsUserAnAdmin())


def restart_command(home: Path) -> tuple[str, str, str]:
    executable = str(Path(sys.executable).resolve())
    entry = Path(__file__).resolve().parents[2] / "enhanced_main.py"
    args = [] if getattr(sys, "frozen", False) else [str(entry)]
    # Keep the same portable profile, but never inherit unrelated CLI commands.
    args += ["--enhanced-home", str(home.resolve())]
    return executable, subprocess.list2cmdline(args), str(Path(executable).parent)


def request_admin_restart(home: Path) -> bool:
    """Return False on UAC cancellation. Caller keeps its window and saved state."""
    if os.name != "nt":
        raise OSError("管理员重启仅适用于Windows")
    executable, arguments, directory = restart_command(home)
    from ctypes import wintypes

    class ShellExecuteInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("fMask", wintypes.ULONG),
            ("hwnd", wintypes.HWND),
            ("lpVerb", wintypes.LPCWSTR),
            ("lpFile", wintypes.LPCWSTR),
            ("lpParameters", wintypes.LPCWSTR),
            ("lpDirectory", wintypes.LPCWSTR),
            ("nShow", ctypes.c_int),
            ("hInstApp", wintypes.HINSTANCE),
            ("lpIDList", ctypes.c_void_p),
            ("lpClass", wintypes.LPCWSTR),
            ("hkeyClass", wintypes.HKEY),
            ("dwHotKey", wintypes.DWORD),
            ("hIcon", wintypes.HANDLE),
            ("hProcess", wintypes.HANDLE),
        ]

    info = ShellExecuteInfo()
    info.cbSize, info.fMask = ctypes.sizeof(info), 0x40 | 0x100  # process handle + no async
    info.lpVerb, info.lpFile, info.lpParameters = "runas", executable, arguments
    info.lpDirectory, info.nShow = directory, 1
    library = ctypes.WinDLL("shell32", use_last_error=True)
    execute = library.ShellExecuteExW
    execute.argtypes, execute.restype = [ctypes.POINTER(ShellExecuteInfo)], wintypes.BOOL
    if not execute(ctypes.byref(info)):
        code = ctypes.get_last_error()
        if code == 1223:  # ERROR_CANCELLED
            return False
        raise ctypes.WinError(code)
    if info.hProcess:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle(info.hProcess)
    return True
