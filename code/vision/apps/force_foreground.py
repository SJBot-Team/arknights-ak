# -*- coding: utf-8 -*-
"""force_foreground.py — 强制把模拟器窗口拉到最前（破解前台锁）并校验渲染

背景（§7.72/§7.79）：MuMu 在窗口失去前台时会**暂停游戏逻辑**（省资源），表现为
"adb 截图恒定静止（差异 0.0）+ 点击完全无效"。仅 `SetForegroundWindow` 常被前台锁静默拒绝。

本脚本按可靠性递进尝试四种手段，每步都校验窗口是否真的到了最前、以及渲染是否恢复：
  1. ShowWindow(SW_RESTORE) + SetForegroundWindow
  2. SetWindowPos(HWND_TOPMOST) → SetWindowPos(HWND_NOTOPMOST) 跳层
  3. AttachThreadInput 破解前台锁后再 SetForegroundWindow（经典可靠做法）
  4. switchToThisWindow / BringWindowToTop
最后用"连续两帧画面差异 > 0.05"判定渲染是否恢复（冻结帧是精确 0.0）。
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
import time

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\code\vision')
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\code\vision')
from plugins.capture.emu_window import EmuWindowCapture, find_window          # noqa: E402


def _hwnds(titles=('MuMuPlayer', 'MuMu模拟器')):
    user32 = ctypes.windll.user32
    out = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _l):
        n = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(h, n, 512)
        if user32.IsWindowVisible(h) and any(s in (n.value or '') for s in titles):
            r = wt.RECT()
            if user32.GetClientRect(h, ctypes.byref(r)):
                if (r.right - r.left, r.bottom - r.top) == (1920, 1080):
                    out.append(h)
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    return out


def try_foreground():
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    hs = _hwnds()
    if not hs:
        print('找不到 MuMu 客户区窗口（1920x1080）')
        return []
    hwnd = hs[0]
    SW_RESTORE, HWND_TOPMOST, HWND_NOTOPMOST = 9, -1, -2
    SWP = 0x0001 | 0x0002 | 0x0040
    log = []

    def focused():
        return user32.GetForegroundWindow() == hwnd

    # 1
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    log.append(('SW_RESTORE+SetForegroundWindow', focused()))

    # 2
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, 0x0001 | 0x0002)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    log.append(('TOPMOST 跳层', focused()))

    # 3 破解前台锁
    fg = user32.GetForegroundWindow()
    tid_fg = user32.GetWindowThreadProcessId(fg, None)
    tid_me = kernel32.GetCurrentThreadId()
    user32.AttachThreadInput(tid_fg, tid_me, True)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    user32.AttachThreadInput(tid_fg, tid_me, False)
    time.sleep(0.3)
    log.append(('AttachThreadInput 破解前台锁', focused()))

    # 4
    try:
        user32.SwitchToThisWindow(hwnd, True)
    except Exception:
        pass
    time.sleep(0.3)
    log.append(('SwitchToThisWindow', focused()))

    for name, ok in log:
        print(f'  {name:<32} 置前成功={ok}')
    return hs


def check_rendering(seconds=3.0):
    cap = EmuWindowCapture().open()
    import numpy as np
    import cv2
    prev, best = None, 0.0
    t0 = time.time()
    while time.time() - t0 < seconds:
        img = cap.grab().image
        fp = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')
        if prev is not None:
            best = max(best, float(np.abs(fp - prev).mean()))
        prev = fp
        time.sleep(0.25)
    print(f'  窗口抓屏最大相邻帧差异 = {best:.3f}（冻结帧为 0.0）')
    return best


def main():
    print('=== 尝试置前 ===')
    try_foreground()
    print('=== 校验窗口抓屏是否在变 ===')
    d = check_rendering()
    if d < 0.05:
        print('窗口抓屏仍静止 ⇒ MuMu 可能仍处于"后台暂停"（游戏逻辑被挂起）')
    else:
        print('窗口抓屏在变 ⇒ 渲染已恢复')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
