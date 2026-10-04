# -*- coding: utf-8 -*-
"""wgc_render.py — 以 MuMu 的**渲染窗口** `render_wnd` 为目标的 WGC 采集器

## 为什么是它
§7.98 的发现：MuMu 的**主窗口与渲染窗口是两个不同 HWND**——
`MuMuManager.exe info -v 0` 会给出 `main_wnd`（容器，1920×1148）与 **`render_wnd`（真正的渲染面，1920×1080）**。
此前 WGC 用"客户区 1920×1080 的窗口"去枚举，抓到的其实是容器/父窗口 ⇒ **全黑**；
换成 `render_wnd` 才有可能拿到真实画面（且 WGC 与遮挡无关、延迟远低于 adb 的 ~600ms）。

## 用法
    cap = WgcRenderCapture().open()          # 自动向 MuMuManager 取 render_wnd
    img = cap.grab().image                   # BGR；全黑时会明确报告
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

import cv2
import numpy as np

MUMU_MANAGER = r'D:\__soft\MuMu Player 12\shell\MuMuManager.exe'


def mumu_render_hwnd(vmindex: int = 0, manager: str = MUMU_MANAGER) -> int | None:
    """向 MuMuManager 询问实例的渲染窗口句柄。"""
    try:
        p = subprocess.run([manager, 'info', '-v', str(vmindex)],
                           capture_output=True, text=True, errors='replace', timeout=20)
        d = json.loads(p.stdout or '{}')
    except Exception:
        return None
    for key in ('render_wnd', 'main_wnd'):
        v = d.get(key)
        if isinstance(v, str):
            try:
                return int(v, 16)
            except ValueError:
                continue
        if isinstance(v, int) and v > 0:
            return v
    return None


class WgcRenderCapture:
    """WGC 采集 MuMu 渲染窗口（遮挡无关）。冻结帧/黑帧会明确报告。"""

    name = 'wgc_render'

    def __init__(self, hwnd: int | None = None, vmindex: int = 0, timeout: float = 8.0):
        self.hwnd = hwnd
        self.vmindex = vmindex
        self.timeout = timeout
        self._latest = None
        self._lock = threading.Lock()
        self._closed = False
        self.black = True
        self.backend_ok = False

    def open(self) -> 'WgcRenderCapture':
        if self.hwnd is None:
            self.hwnd = mumu_render_hwnd(self.vmindex)
        if not self.hwnd:
            raise RuntimeError('取不到 MuMu render_wnd（MuMuManager info 失败？）')
        from windows_capture import WindowsCapture
        cap = WindowsCapture(cursor_capture=False, draw_border=False, window_hwnd=int(self.hwnd))

        @cap.event
        def on_frame_arrived(frame, control):           # noqa: ANN001
            try:
                buf = frame.frame_buffer
                img = np.ascontiguousarray(buf[:, :, :3])
            except Exception:
                return
            with self._lock:
                self._latest = img

        @cap.event
        def on_closed():                                 # noqa: ANN001
            self._closed = True

        def _run():
            try:
                cap.start()
            except Exception:
                self._closed = True

        self._backend = cap
        threading.Thread(target=_run, daemon=True).start()
        t0 = time.time()
        while time.time() - t0 < self.timeout:
            with self._lock:
                if self._latest is not None:
                    self.backend_ok = True
                    self.black = float(self._latest.mean()) < 3.0
                    return self
            time.sleep(0.01)
        raise RuntimeError('WGC 首帧超时（render_wnd 是否正确？）')

    def grab(self):
        with self._lock:
            img = None if self._latest is None else self._latest
        if img is None:
            img = np.zeros((1080, 1920, 3), 'uint8')
        return type('Frame', (), {'image': img, 'origin': (0, 0), 'rect': None})()

    def close(self):
        self._closed = True


def _probe():
    sys.stdout.reconfigure(encoding='utf-8')
    hwnd = mumu_render_hwnd()
    print('render_wnd hwnd =', hwnd, f'(0x{hwnd:08X})' if hwnd else '')
    try:
        cap = WgcRenderCapture(hwnd=hwnd).open()
    except Exception as e:
        print('WGC 打开失败:', e)
        return 1
    a = cap.grab().image
    time.sleep(1.0)
    b = cap.grab().image
    d = float(np.abs(cv2.resize(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')
                     - cv2.resize(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')).mean())
    print(f'WGC 出帧: shape={a.shape} mean={a.mean():.1f} 黑帧={cap.black} 两帧差异={d:.3f}')
    print('⇒', '★WGC(render_wnd) 可用且画面在变' if (not cap.black and d >= 0.005)
          else ('通道可用但画面冻结（渲染已停）' if not cap.black else '仍为黑帧（render_wnd 不对或 WGC 不支持该窗口）'))
    return 0


if __name__ == '__main__':
    raise SystemExit(_probe())
