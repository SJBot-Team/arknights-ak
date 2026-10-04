"""窗口定位（Windows）：找窗口 → 客户区矩形 → 作为采集区域与相对坐标基准。

场景①（客户端）需要：把识别与点击都锁定在游戏窗口内，窗口移动后仍生效。
"""
from __future__ import annotations

import time

from .types import Rect

try:  # Windows only
    import win32con
    import win32gui
    import win32process
except Exception:  # pragma: no cover
    win32gui = None


def list_windows(keyword: str = "") -> list[dict]:
    """列出可见窗口（可按标题关键字过滤）。"""
    if win32gui is None:
        return []
    out = []

    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title:
            return
        if keyword and keyword.lower() not in title.lower():
            return
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        out.append({"hwnd": hwnd, "title": title, "pid": pid})

    win32gui.EnumWindows(cb, None)
    return out


def find_window(keyword: str, process_id: int | None = None) -> dict | None:
    cands = list_windows(keyword)
    if process_id is not None:
        cands = [c for c in cands if c["pid"] == process_id] or cands
    return cands[0] if cands else None


def client_rect(hwnd: int) -> Rect:
    """客户区在屏幕上的绝对矩形（排除标题栏与边框）。"""
    l, t, r, b = win32gui.GetClientRect(hwnd)
    sl, st = win32gui.ClientToScreen(hwnd, (l, t))
    sr, sb = win32gui.ClientToScreen(hwnd, (r, b))
    return Rect(sl, st, sr, sb)


def window_rect(hwnd: int) -> Rect:
    l, t, r, b = win32gui.GetWindowRect(hwnd)
    return Rect(l, t, r, b)


def activate(hwnd: int, wait: float = 0.15) -> bool:
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(wait)
        return True
    except Exception:
        return False


def is_foreground(hwnd: int) -> bool:
    return bool(win32gui) and win32gui.GetForegroundWindow() == hwnd
