# -*- coding: utf-8 -*-
"""emu_window.py — 模拟器窗口定位 + 仅抓「窗口客户区」的采集器

⚠ 踩过的坑（§7.57）：BetterCam/dxcam 默认抓**整个桌面**（本机是 2560×1600），
而所有 ROI 都是在**模拟器帧缓冲坐标**（1920×1080，来自 adb screencap）下标定的。
直接抓桌面会把 ROI 打到无关像素上 —— 表现为「费用数字恒读同一个值、置信度恒定」
「费用条恒为满格」，看着像识别坏了，其实是坐标系错位。

本模块用 Win32 找到 MuMu 的**客户区**窗口（标题 MuMuPlayer），返回它在桌面上的矩形，
再用 `grab(region=...)` 只抓这块 ⇒ 得到与 adb 帧缓冲**逐像素对齐**的 1920×1080 图像，
ROI 可以直接复用。
"""
from __future__ import annotations

import ctypes
import threading
import time
from dataclasses import dataclass

import numpy as np

DEFAULT_TITLES = ('MuMuPlayer', 'MuMu模拟器', 'Arknights', '明日方舟')


@dataclass
class WindowRect:
    left: int
    top: int
    width: int
    height: int

    @property
    def region(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.left + self.width, self.top + self.height)

    def to_fb(self, x: int, y: int) -> tuple[int, int]:
        """桌面坐标 → 帧缓冲（窗口内）坐标。"""
        return int(x) - self.left, int(y) - self.top

    def to_desktop(self, x: int, y: int) -> tuple[int, int]:
        """帧缓冲坐标 → 桌面坐标（注入用）。"""
        return int(x) + self.left, int(y) + self.top


def find_window(substrs: tuple[str, ...] = DEFAULT_TITLES, min_size=(640, 360),
                expect: tuple[int, int] = (1920, 1080)) -> WindowRect | None:
    """枚举顶层窗口，返回标题匹配且足够大的那个（客户区矩形）。

    优先级：**尺寸正好等于帧缓冲**（1920×1080）的客户区 > 面积最大者。
    很多模拟器会有"宿主窗口（带边框，1920×1143）+ 渲染子窗口（1920×1080）"两层，
    必须选后者，否则抓到的图与 adb 帧缓冲**逐像素对不齐**（差 63px 顶部边框）。
    """
    import ctypes.wintypes as wt
    user32 = ctypes.windll.user32
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass
    found: list[WindowRect] = []
    EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(h, _l):
        n = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(h, n, 512)
        title = n.value or ''
        if user32.IsWindowVisible(h) and any(s in title for s in substrs):
            r = wt.RECT()
            if user32.GetClientRect(h, ctypes.byref(r)):
                pt = wt.POINT(0, 0)
                user32.ClientToScreen(h, ctypes.byref(pt))
                w, hgt = r.right - r.left, r.bottom - r.top
                if w >= min_size[0] and hgt >= min_size[1]:
                    found.append(WindowRect(pt.x, pt.y, w, hgt))
        return True

    user32.EnumWindows(EnumProc(cb), 0)
    if not found:
        return None
    exact = [r for r in found if (r.width, r.height) == tuple(expect)]
    if exact:
        return exact[0]
    found.sort(key=lambda r: -(r.width * r.height))
    return found[0]


class WgcCapture:
    """**Windows Graphics Capture** 后端：抓的是**窗口自己的内容**，与遮挡无关。

    §7.58 的结论：桌面区域抓屏（BetterCam region=）会被上层窗口遮挡，`
    PrintWindow` 对硬件加速窗口返回全黑。WGC 是唯一既快又遮挡无关的合规路径
    （只是普通的屏幕捕获 API，不碰游戏内存）。

    回调式 API → 用后台线程持续更新"最新帧"，对上层暴露同步 `grab()`。
    """

    name = 'wgc'

    def __init__(self, window_name: str | None = None, hwnd: int | None = None,
                 expect: tuple[int, int] = (1920, 1080), timeout: float = 6.0):
        self.window_name = window_name
        self.hwnd = hwnd
        self.expect = expect
        self.timeout = timeout
        self._latest = None
        self._lock = threading.Lock()
        self._cap = None
        self._thread = None
        self._closed = False

    def _resolve_hwnd(self) -> int | None:
        """用自家的 Win32 枚举找出**尺寸等于帧缓冲**的模拟器客户区窗口句柄。"""
        import ctypes
        import ctypes.wintypes as wt
        user32 = ctypes.windll.user32
        titles = DEFAULT_TITLES if not self.window_name else (self.window_name,)
        hits: list[int] = []
        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def cb(h, _l):
            n = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(h, n, 512)
            if user32.IsWindowVisible(h) and any(s in (n.value or '') for s in titles):
                r = wt.RECT()
                if user32.GetClientRect(h, ctypes.byref(r)):
                    if (r.right - r.left, r.bottom - r.top) == tuple(self.expect):
                        hits.append(h)
            return True

        user32.EnumWindows(EnumProc(cb), 0)
        return hits[0] if hits else None

    def open(self) -> 'WgcCapture':
        from windows_capture import WindowsCapture
        hwnd = self.hwnd or self._resolve_hwnd()
        # 优先用 HWND：WGC 的 window_name 需要**精确标题**，子串匹配拿不到帧（实测首帧超时）
        kw = {'window_hwnd': int(hwnd)} if hwnd else {'window_name': self.window_name or 'MuMuPlayer'}
        cap = WindowsCapture(cursor_capture=False, draw_border=False, **kw)

        @cap.event
        def on_frame_arrived(frame, capture_control):        # noqa: ANN001
            try:
                buf = frame.frame_buffer
                img = np.ascontiguousarray(buf[:, :, :3])     # BGRA → BGR
            except Exception:
                return
            with self._lock:
                self._latest = img

        @cap.event
        def on_closed():                                     # noqa: ANN001
            self._closed = True

        self._cap = cap

        def _run():
            try:
                cap.start()
            except Exception:
                self._closed = True

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        t0 = time.time()
        while time.time() - t0 < self.timeout:
            with self._lock:
                if self._latest is not None:
                    return self
            time.sleep(0.01)
        raise RuntimeError('WGC 首帧超时（窗口名是否正确？）')

    def grab(self):
        with self._lock:
            img = None if self._latest is None else self._latest
        if img is None:
            img = np.zeros((self.expect[1], self.expect[0], 3), 'uint8')
        return type('Frame', (), {'image': img, 'origin': (0, 0), 'rect': None})()

    def close(self) -> None:
        self._closed = True


class AdbDisplayCapture:
    """**adb display 通道**采集器（§7.64 实测）：遮挡无关、真画面、约 596ms/帧。

    命令：`adb -s <dev> exec-out screencap -p -d 2`（MuMu 的 display 2 = 游戏画面）。
    速度慢，但按用户 §7.62 的结论——**暂停时游戏时间冻结，采集慢不影响帧级精度**——
    这是"合规 + 遮挡无关"的保底通道：既能进战斗做界面判断，也能作为窗口快路径的校验源。
    """

    name = 'adb_display'

    def __init__(self, device: str = '127.0.0.1:16384',
                 adb: str = r'D:\__soft\MuMu Player 12\shell\adb.exe', display: int = 2):
        self.device = device
        self.adb = adb
        self.display = display
        self.origin = (0, 0)

    def open(self) -> 'AdbDisplayCapture':
        return self

    def grab(self):
        import subprocess
        import cv2
        cmd = [self.adb, '-s', self.device, 'exec-out', 'screencap', '-p']
        if self.display is not None:
            cmd += ['-d', str(self.display)]
        p = subprocess.run(cmd, capture_output=True)
        data = p.stdout or b''
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR) if data else None
        if img is None:
            img = np.zeros((1080, 1920, 3), 'uint8')
        return type('Frame', (), {'image': img, 'origin': self.origin, 'rect': None})()

    def close(self) -> None:
        return None


def make_capture(prefer: str = 'wgc', **kw):
    """按优先级建采集器：adb_display（可靠/遮挡无关/慢）> wgc > emu_window。"""
    if prefer in ('adb', 'adb_display'):
        return AdbDisplayCapture(**{k: v for k, v in kw.items()
                                    if k in ('device', 'adb', 'display')}).open()
    if prefer in ('wgc', 'auto'):
        try:
            return WgcCapture(**{k: v for k, v in kw.items()
                                 if k in ('window_name', 'expect', 'timeout')}).open()
        except Exception as e:
            print(f'WGC 不可用（{type(e).__name__}: {e}），退回桌面区域抓屏')
    return EmuWindowCapture(**kw).open()


class EmuWindowCapture:
    """只抓模拟器窗口客户区的采集器；`.grab()` 返回对象带 .image(1920x1080) 与 .origin。

    ⚠ 遮挡问题（§7.58）：桌面区域抓屏（BetterCam region=）拿到的是**屏幕上最上层的内容**——
    如果 DSH 窗口/浏览器盖在模拟器上面，抓到的就是**别的窗口的画面**（实测抓到过聊天文本！
    表现为"费用数字恒定读同一个值"）。因此本采集器优先用 **PrintWindow(PW_RENDERFULLCONTENT)**
    抓窗口自身内容（**与遮挡无关**），失败才退回"置前台 + 区域抓屏"。
    """

    name = 'emu_window'

    def __init__(self, titles: tuple[str, ...] = DEFAULT_TITLES, backend: str = 'auto',
                 expect: tuple[int, int] = (1920, 1080), prefer_printwindow: bool = True):
        self.titles = titles
        self.expect = expect
        self.rect: WindowRect | None = None
        self._cam = None
        self.backend = backend
        self.prefer_printwindow = prefer_printwindow
        self._hwnd = None
        self._pw_ok = None

    # ---------- PrintWindow 路径（遮挡无关） ----------
    def _printwindow(self, hwnd, w: int, h: int):
        import ctypes
        import ctypes.wintypes as wt
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hdc_win = user32.GetWindowDC(hwnd)
        if not hdc_win:
            return None
        hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
        bmp = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
        gdi32.SelectObject(hdc_mem, bmp)
        PW_RENDERFULLCONTENT = 0x00000002
        ok = user32.PrintWindow(hwnd, hdc_mem, PW_RENDERFULLCONTENT)
        buf = ctypes.create_string_buffer(w * h * 4)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [('biSize', wt.DWORD), ('biWidth', ctypes.c_long), ('biHeight', ctypes.c_long),
                        ('biPlanes', wt.WORD), ('biBitCount', wt.WORD), ('biCompression', wt.DWORD),
                        ('biSizeImage', wt.DWORD), ('biXPelsPerMeter', ctypes.c_long),
                        ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', wt.DWORD),
                        ('biClrImportant', wt.DWORD)]

        bi = BITMAPINFOHEADER()
        bi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.biWidth = w
        bi.biHeight = -h          # top-down
        bi.biPlanes = 1
        bi.biBitCount = 32
        bi.biCompression = 0
        gdi32.GetDIBits(hdc_mem, bmp, 0, h, buf, ctypes.byref(bi), 0)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_win)
        if not ok:
            return None
        arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)[:, :, :3]
        return np.ascontiguousarray(arr)

    def _find_hwnd(self):
        import ctypes
        import ctypes.wintypes as wt
        user32 = ctypes.windll.user32
        hits = []
        EnumProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def cb(h, _l):
            n = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(h, n, 512)
            if user32.IsWindowVisible(h) and any(s in (n.value or '') for s in self.titles):
                r = wt.RECT()
                if user32.GetClientRect(h, ctypes.byref(r)):
                    w, hgt = r.right - r.left, r.bottom - r.top
                    if (w, hgt) == tuple(self.expect):
                        hits.append(h)
            return True

        user32.EnumWindows(EnumProc(cb), 0)
        return hits[0] if hits else None

    def open(self) -> 'EmuWindowCapture':
        self.rect = find_window(self.titles, expect=self.expect)
        if self.rect is None:
            raise RuntimeError(f'找不到模拟器窗口（标题含 {self.titles}）')
        self._hwnd = self._find_hwnd()
        mods = ['bettercam', 'dxcam'] if self.backend == 'auto' else [self.backend]
        last = None
        for m in mods:
            try:
                mod = __import__(m)
                self._cam = mod.create(output_idx=0, output_color='BGR')
                self.backend = m
                break
            except Exception as e:
                last = e
        if self._cam is None:
            raise RuntimeError(f'抓屏后端不可用：{last}')
        for _ in range(3):
            self._cam.grab()
        if self.prefer_printwindow and self._hwnd:
            img = self._printwindow(self._hwnd, self.rect.width, self.rect.height)
            self._pw_ok = img is not None and float(img.mean()) > 3.0
        return self

    def bring_to_front(self) -> bool:
        """把模拟器窗口**强制**拉到最前并置前（用户 2026-09-14 授权自由拉取窗口）。

        为什么必须做：PrintWindow 对硬件加速的模拟器窗口通常返回**全黑**（实测 `_pw_ok=False`），
        于是只能退回"桌面区域抓屏"，而区域抓屏拿到的是**最上层窗口**的内容；
        更糟的是 **MuMu 被遮挡/最小化时会停止渲染**，`adb screencap -d 2` 只会返回静止的最后一帧（§7.72）。

        仅用 `SetForegroundWindow` 不稳（前台锁会让它静默失败，实测时好时坏），
        因此按标准套路强制跳层：`SW_RESTORE` → `SetWindowPos(HWND_TOPMOST)` →
        `SetWindowPos(HWND_NOTOPMOST)`（跳到最上层但仍保持普通层级）→ `SetForegroundWindow`。
        """
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = self._hwnd
        if hwnd is None:
            return False
        SW_RESTORE = 9
        HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
        SWP_NOSIZE, SWP_NOMOVE, SWP_SHOWWINDOW = 0x0001, 0x0002, 0x0040
        try:
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
            user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.25)
            return True
        except Exception:
            return False

    def grab(self):
        if self._cam is None:
            self.open()
        assert self.rect is not None
        img = None
        if self.prefer_printwindow and self._pw_ok and self._hwnd:
            img = self._printwindow(self._hwnd, self.rect.width, self.rect.height)
        if img is None:
            for _ in range(3):
                img = self._cam.grab(region=self.rect.region)
                if img is not None and getattr(img, 'size', 0):
                    break
                time.sleep(0.002)
        if img is None:
            img = np.zeros((self.rect.height, self.rect.width, 3), 'uint8')
        return type('Frame', (), {'image': img, 'origin': (self.rect.left, self.rect.top),
                                  'rect': self.rect})()

    def close(self) -> None:
        try:
            self._cam.release()
        except Exception:
            pass
