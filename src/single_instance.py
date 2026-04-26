from __future__ import annotations

import atexit
import ctypes
import logging
import sys
from ctypes import wintypes

logger = logging.getLogger(__name__)

ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9
SW_SHOW = 5
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040

MUTEX_NAME = r"Local\BackTestPanel.SingleInstance"


class SingleInstance:
    def __init__(self, mutex_name: str = MUTEX_NAME) -> None:
        self.mutex_name = mutex_name
        self.handle: int | None = None
        self.already_running = False

    def acquire(self) -> bool:
        if sys.platform != "win32":
            return True

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.CreateMutexW(None, False, self.mutex_name)
        self.handle = int(handle) if handle else None

        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

        self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS
        if self.already_running:
            self.release()
            return False

        atexit.register(self.release)
        return True

    def release(self) -> None:
        if sys.platform != "win32" or not self.handle:
            return

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.CloseHandle(wintypes.HANDLE(self.handle))
        self.handle = None


def activate_existing_window(title: str) -> bool:
    if sys.platform != "win32":
        return False

    hwnd = _find_window_by_title(title)
    if not hwnd:
        logger.warning("Instancia existente encontrada, mas a janela '%s' nao foi localizada.", title)
        return False

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.BringWindowToTop.argtypes = [wintypes.HWND]
    user32.BringWindowToTop.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL

    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    else:
        user32.ShowWindow(hwnd, SW_SHOW)

    user32.SetWindowPos(hwnd, wintypes.HWND(0), 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    return True


def _find_window_by_title(title: str) -> int | None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND

    hwnd = user32.FindWindowW(None, title)
    if hwnd:
        return int(hwnd)

    return _enum_windows_by_title(title)


def _enum_windows_by_title(title: str) -> int | None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int

    expected = title.strip().casefold()
    result: int | None = None

    def callback(hwnd: wintypes.HWND, _lparam: wintypes.LPARAM) -> bool:
        nonlocal result
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True

        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        current = buffer.value.strip().casefold()

        if current == expected:
            result = int(hwnd)
            return False

        return True

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(callback)
    user32.EnumWindows(enum_proc, 0)
    return result
