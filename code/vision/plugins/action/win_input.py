# -*- coding: utf-8 -*-
"""win_input.py — **Windows 层鼠标/键盘注入**（SendInput），用于实现「划火柴」等精确操作

## 为什么必须用 Windows 层（2026-09-15 实测）
- MuMu 的**键鼠方案（F 时停 / W 划火柴 / S 0帧选取…）是"模拟器软件层"的宏**；
- **`adb shell input keyevent/tap` 不会触发这些宏**（实测 ESC/BACK 发出后游戏毫无反应）；
- ⇒ 要复用官方宏或实现同样的时序，必须从 **Windows 层**注入真实的鼠标/键盘事件。

## 关键换算
本机 MuMu 的**客户区 1920×1080 位于桌面 (2, 63)**（此前实测），因此：
    屏幕坐标 = (2 + frame_x, 63 + frame_y)
（若实例分辨率/位置变化，用 `calibrate_client_origin()` 重新标定。）

## 用法
    wi = WinInput()
    wi.focus_window('MuMu模拟器12')          # 注入前必须让窗口在前台（否则模拟器停止渲染）
    wi.click_frame(1806, 80)                  # 点帧坐标（暂停按钮）
    wi.key_tap('f')                           # 发 F（时停宏）
    wi.drag_frame([(87,995), (400,760), (900,560), (1327,405)], hold=0.05)   # 划火柴式拖拽
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL('user32', use_last_error=True)

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
MOUSEEVENTF_MOVE, MOUSEEVENTF_ABSOLUTE = 0x0001, 0x8000
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x0002, 0x0008

VK = {'f': 0x46, 'g': 0x47, 'w': 0x57, 's': 0x53, 'e': 0x45, 'a': 0x41, 'd': 0x44,
      'q': 0x51, 'c': 0x43, 'space': 0x20, 'esc': 0x1B, 'back': 0x08,
      # ★ 云迹方案用到的宏键（过帧/子弹时间/视角）
      'r': 0x52, 't': 0x54, 'y': 0x59, 'z': 0x5A, 'tab': 0x09,
      '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34, '5': 0x35,
      '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39, '0': 0x30}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG),
                ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong))]


class _INPUTunion(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [('type', wintypes.DWORD), ('u', _INPUTunion)]


class WinInput:
    CLIENT_ORIGIN = (2, 63)      # 兼容旧值；实际请用 resolve_render_rect() 动态标定
    FRAME_W, FRAME_H = 1920, 1080   # 游戏内部分辨率（adb 截帧尺寸）

    def __init__(self, client_origin=None, client_size=None, screen_size=None,
                 dpi_aware: bool = True):
        # ★依据 PRTS+：注入前须**设为 DPI aware**，否则 GetWindowRect 返回缩放后坐标、
        #   坐标换算整体偏移（本机屏幕 2560×1600 而窗口 1306×796，存在 DPI 缩放）。
        if dpi_aware:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PROCESS_PER_MONITOR_DPI_AWARE
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass
        self.SW, self.SH = screen_size or self._screen_size()
        self.log = []
        self.origin, self.size = None, None
        if client_origin and client_size:
            self.origin, self.size = tuple(client_origin), tuple(client_size)
        else:
            self.resolve_render_rect()

    # ---------- 动态标定：找到 MuMu 的"渲染区"在屏幕上的矩形 ----------
    def resolve_render_rect(self, title_substr: str = 'MuMu模拟器12'):
        """★关键：MuMu 窗口**通常不是 1920×1080**（本机实测 1296×791），
        游戏画面被缩放显示。必须用 **客户区(ClientRect)+ClientToScreen** 动态标定，
        否则"帧坐标 → 屏幕坐标"的换算会整体偏移，注入全部落空（已踩坑）。"""
        hwnds = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(h, _l):
            ln = user32.GetWindowTextLengthW(h)
            if ln > 0 and user32.IsWindowVisible(h):
                buf = ctypes.create_unicode_buffer(ln + 1)
                user32.GetWindowTextW(h, buf, ln + 1)
                if title_substr in buf.value:
                    hwnds.append(h)
            return True

        user32.EnumWindows(cb, 0)
        if not hwnds:
            self.origin, self.size = self.CLIENT_ORIGIN, (self.FRAME_W, self.FRAME_H)
            return False
        h = hwnds[0]
        self.hwnd = h
        rc = wintypes.RECT()
        user32.GetClientRect(h, ctypes.byref(rc))
        pt = wintypes.POINT(0, 0)
        user32.ClientToScreen(h, ctypes.byref(pt))
        # ★ MuMu 的标题栏是**自绘**的（客户区把它包含在内），实测顶部约 63px 不是游戏画面
        #   ⇒ 渲染区原点需下移该高度（可用 UIA 的 RenderWidget 矩形复核）。
        title_h = 63
        self.origin = (pt.x, pt.y + title_h)
        self.size = (rc.right - rc.left, (rc.bottom - rc.top) - title_h)
        return True

    def to_screen(self, fx, fy):
        """帧坐标(1920×1080) → 屏幕坐标（按渲染区实际尺寸等比缩放）。"""
        ox, oy = self.origin
        cw, ch = self.size
        return (int(ox + fx * cw / self.FRAME_W), int(oy + fy * ch / self.FRAME_H))

    @staticmethod
    def _screen_size():
        return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))

    def describe(self):
        ox, oy = self.origin
        cw, ch = self.size
        return (f'渲染区 屏幕原点=({ox},{oy}) 尺寸={cw}x{ch}  '
                f'缩放={cw / self.FRAME_W:.4f}  屏幕={self.SW}x{self.SH}')

    # ---------- ★PRTS+ 式后台鼠标：SendMessage（同步）+ 比例坐标 + MK_LBUTTON ----------
    # 依据：PRTS+ 开源实现 `src/mumu/mumu_controller.py`
    #   win32api.SendMessage(HANDLE, WM_LBUTTONDOWN, 0, MAKELONG(x, y))
    #   win32api.SendMessage(HANDLE, WM_MOUSEMOVE, MK_LBUTTON, MAKELONG(x, y))
    #   win32api.SendMessage(HANDLE, WM_LBUTTONUP, MK_LBUTTON, MAKELONG(x, y))
    # 坐标用 **GetWindowRect 的完整窗口尺寸** 做比例换算（不是客户区）。
    # 特点：**不移动真实光标、不抢用户鼠标**（消息直达窗口）。
    def window_rect_size(self, hwnd=None):
        hwnd = hwnd or getattr(self, 'hwnd', None)
        rc = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rc))
        return (rc.right - rc.left, rc.bottom - rc.top)

    def _to_win_px(self, fx, fy, hwnd=None):
        """★PRTS+ 口径：比例(0~1) × **GetWindowRect（完整窗口尺寸）** ⇒ 像素。

        PRTS+ 的 `handle_coordinates` 用的就是 `GetWindowRect` 的宽高，
        而不是客户区；本方法与之对齐（`window_rect_size` 亦用 GetWindowRect）。
        """
        w, h = self.window_rect_size(hwnd)
        rx, ry = fx / self.FRAME_W, fy / self.FRAME_H
        return int(rx * w), int(ry * h)

    @staticmethod
    def _makelong(x, y):
        return (int(y) << 16) | (int(x) & 0xFFFF)

    def sm_mouse(self, kind: str, fx=None, fy=None, hwnd=None, button='left'):
        """SendMessage 版鼠标事件（后台、不抢鼠标）。kind: move/down/up/click"""
        hwnd = hwnd or getattr(self, 'hwnd', None) or self.find_render_hwnd()
        if not hwnd:
            return False
        x, y = self._to_win_px(fx, fy, hwnd)
        lp = self._makelong(x, y)
        if kind == 'move':
            user32.SendMessageW(hwnd, self.WM_MOUSEMOVE, self.MK_LBUTTON, lp)
        elif kind == 'down':
            user32.SendMessageW(hwnd, self.WM_LBUTTONDOWN if button == 'left' else self.WM_RBUTTONDOWN, 0, lp)
        elif kind == 'up':
            user32.SendMessageW(hwnd, self.WM_LBUTTONUP if button == 'left' else self.WM_RBUTTONUP,
                                self.MK_LBUTTON, lp)
        elif kind == 'click':
            user32.SendMessageW(hwnd, self.WM_LBUTTONDOWN, 0, lp)
            user32.SendMessageW(hwnd, self.WM_LBUTTONUP, 0, lp)
        self.log.append(('sm_mouse', kind, (fx, fy), hwnd))
        return True

    def sm_drag(self, points, steps: int = 8, hold: float = 0.04, between: float = 0.012,
                hwnd=None, button: str = 'left'):
        """★划火柴（PRTS+ 式）：SendMessage 左键按下 → 带 MK_LBUTTON 连续移动 → 抬起。

        全程不移动真实光标 ⇒ **不抢用户的鼠标**；连续 `WM_MOUSEMOVE(MK_LBUTTON)`
        让游戏识别为拖拽（这正对应 MuMu 宏里 `curve_rel:mouse` 所依赖的连续位移）。
        """
        hwnd = hwnd or getattr(self, 'hwnd', None) or self.find_render_hwnd()
        if not hwnd:
            return False
        self.sm_mouse('move', points[0][0], points[0][1], hwnd)
        time.sleep(hold)
        self.sm_mouse('down', points[0][0], points[0][1], hwnd, button)
        time.sleep(hold)
        path = []
        for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
            for k in range(1, steps + 1):
                t = k / (steps + 1.0)
                path.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        path.append(points[-1])
        for (x, y) in path:
            self.sm_mouse('move', x, y, hwnd)
            time.sleep(between)
        time.sleep(hold)
        self.sm_mouse('up', points[-1][0], points[-1][1], hwnd, button)
        self.log.append(('sm_drag', points[0], points[-1], len(path)))
        return True

    def sm_xbutton(self, which: int = 2, hwnd=None):
        """鼠标侧键（PRTS+ 用它做"暂停/ESC"）：which=1 侧键1(XBUTTON1)、2 侧键2(XBUTTON2)。"""
        hwnd = hwnd or getattr(self, 'hwnd', None) or self.find_render_hwnd()
        WM_XBUTTONDOWN, WM_XBUTTONUP = 0x020B, 0x020C
        flag = (0x0001 if which == 1 else 0x0002) << 16
        user32.SendMessageW(hwnd, WM_XBUTTONDOWN, flag, 0)
        user32.SendMessageW(hwnd, WM_XBUTTONUP, flag, 0)
        self.log.append(('sm_xbutton', which, hwnd))
        return True

    # ---------- ★划火柴（真实鼠标）：宏读的是 GetCursorPos 的真实位移 ----------
    def drag_right_real(self, points, steps: int = 8, hold: float = 0.05, between: float = 0.015):
        """★用**真实鼠标**做"右键按住 → 滑动 → 松开"。

        为什么不能用 PostMessage：划火柴宏内部是 `curve_rel:mouse;(3.406,6.053)`，
        **依据的是真实鼠标位移**（GetCursorPos），WM_MOUSEMOVE 消息满足不了它
        ⇒ 键盘宏可以后台 PostMessage，**鼠标划火柴必须用真实输入**（仅瞬间占用鼠标）。
        注意：注入前需保证 MuMu 窗口在前台。
        """
        sx, sy = self.to_screen(*points[0])
        user32.SetCursorPos(int(sx), int(sy))
        time.sleep(hold)
        self._mouse(MOUSEEVENTF_RIGHTDOWN)
        time.sleep(hold)
        path = []
        for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
            for k in range(1, steps + 1):
                t = k / (steps + 1.0)
                path.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        path.append(points[-1])
        for (x, y) in path:
            tx, ty = self.to_screen(x, y)
            user32.SetCursorPos(int(tx), int(ty))
            time.sleep(between)
        time.sleep(hold)
        self._mouse(MOUSEEVENTF_RIGHTUP)
        self.log.append(('drag_right_real', points[0], points[-1], len(path)))
        return True

    # ---------- ★划火柴：PostMessage 右键拖拽 ----------
    def _post_move(self, hwnd, fx, fy, mk=0):
        cw, ch = self.size
        cx = int(fx * cw / self.FRAME_W)
        cy = int(fy * ch / self.FRAME_H)
        user32.PostMessageW(hwnd, self.WM_MOUSEMOVE, mk, (cy << 16) | (cx & 0xFFFF))
        return cx, cy

    def post_drag_right(self, points, hwnd=None, steps: int = 8, hold: float = 0.05,
                        between: float = 0.02):
        """★划火柴：**右键按下 → 沿路径滑动 → 右键松开**（PostMessage 后台投递）。

        云迹方案的「0帧划火柴」由**鼠标右键**触发，宏内部会自动"按住左键跟随鼠标"，
        并以 `curve_rel:mouse;(3.406,6.053)` 作为滑动曲线。
        因此本方只需：**暂停（F）→ 鼠标移到卡片 → 按右键 → 划到目标格 → 松开右键**。
        """
        hwnd = hwnd or getattr(self, 'render_hwnd', None) or self.find_render_hwnd()
        if not hwnd:
            return False
        cx, cy = self._post_move(hwnd, points[0][0], points[0][1])
        time.sleep(0.05)
        cx, cy = self._post_move(hwnd, points[0][0], points[0][1])
        user32.PostMessageW(hwnd, self.WM_RBUTTONDOWN, self.MK_RBUTTON, (cy << 16) | (cx & 0xFFFF))
        time.sleep(hold)
        path = []
        for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
            for k in range(1, steps + 1):
                t = k / (steps + 1.0)
                path.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
        path.append(points[-1])
        for (x, y) in path:
            self._post_move(hwnd, x, y, mk=self.MK_RBUTTON)
            time.sleep(between)
        time.sleep(hold)
        ex, ey = self._post_move(hwnd, points[-1][0], points[-1][1], mk=self.MK_RBUTTON)
        user32.PostMessageW(hwnd, self.WM_RBUTTONUP, 0, (ey << 16) | (ex & 0xFFFF))
        self.log.append(('post_drag_right', points[0], points[-1], len(path)))
        return True
    def _send(self, inp):
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _mouse(self, flags, dx=0, dy=0):
        mi = MOUSEINPUT(dx, dy, 0, flags, 0, None)
        self._send(INPUT(INPUT_MOUSE, _INPUTunion(mi=mi)))

    def _key(self, vk, up=False, scan=0):
        ki = KEYBDINPUT(vk, scan, KEYEVENTF_KEYUP if up else 0, 0, None)
        self._send(INPUT(INPUT_KEYBOARD, _INPUTunion(ki=ki)))

    # ---------- ★后台输入：PostMessage 直接投递（与用户的键鼠互不干扰） ----------
    WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
    WM_MOUSEMOVE = 0x0200
    WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
    WM_RBUTTONDOWN, WM_RBUTTONUP = 0x0204, 0x0205
    MK_LBUTTON, MK_RBUTTON = 0x0001, 0x0002

    def find_render_hwnd(self, title_substr: str = 'MuMu模拟器12'):
        """找 MuMu 用于接收输入的子窗口。

        ★依据 PRTS+ 的 `src/config.py`：`WINDOW_NAME="MuMu模拟器12"`、**`SUB_WINDOW_NAME="MuMuPlayer"`**
        ⇒ 应优先按 **class=`MuMuPlayer`** 找子窗口（此前本方误用 UIA 报的 `nemuwin`，注入无效）。
        """
        tops = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(h, _l):
            ln = user32.GetWindowTextLengthW(h)
            if ln > 0 and user32.IsWindowVisible(h):
                buf = ctypes.create_unicode_buffer(ln + 1)
                user32.GetWindowTextW(h, buf, ln + 1)
                if title_substr in buf.value:
                    tops.append(h)
            return True

        user32.EnumWindows(cb, 0)
        if not tops:
            return None
        main = tops[0]
        self.hwnd = main

        # ★依据 PRTS+（`src/mumu/mumu_connection.py`）：
        #   PARENT = FindWindow(None, "MuMu模拟器12")
        #   HANDLE = FindWindowEx(PARENT, 0, **None**, "MuMuPlayer")   ← **按标题找，class 传 None**
        #   它据此拿到的 HANDLE 正是 render_wnd（其日志：handle 7801904）。
        child = user32.FindWindowExW(main, 0, None, 'MuMuPlayer')
        if child:
            self.render_hwnd = child
            self.target_class = 'title:MuMuPlayer'
            return child
        # 回退：递归按类名找（nemuwin 等）
        found = {}

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def ccb(h, _l):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(h, buf, 256)
            found.setdefault(buf.value, h)
            return True

        user32.EnumChildWindows(main, ccb, 0)
        for cls in ('nemuwin', 'Qt5156QWindowIcon'):
            if cls in found:
                self.render_hwnd = found[cls]
                self.target_class = cls
                return self.render_hwnd
        self.render_hwnd = main
        self.target_class = 'main'
        return main

    # ---------- ★按住/松开（F 是"按下暂停、松开恢复"，必须分开控制） ----------
    def key_down(self, key: str, hwnd=None):
        """只发 `WM_KEYDOWN`（保持按住）。用于 F：**按住期间游戏暂停**。"""
        hwnd = hwnd or getattr(self, 'render_hwnd', None) or self.find_render_hwnd()
        vk = VK.get(key.lower())
        if vk is None:
            raise ValueError(f'未知按键 {key}')
        scan = user32.MapVirtualKeyW(vk, 0)
        user32.PostMessageW(hwnd, self.WM_KEYDOWN, vk, 1 | (scan << 16))
        self.log.append(('key_down', key, hwnd))
        return True

    def key_up(self, key: str, hwnd=None):
        """只发 `WM_KEYUP`（松开）。与 `key_down` 配对。"""
        hwnd = hwnd or getattr(self, 'render_hwnd', None) or self.find_render_hwnd()
        vk = VK.get(key.lower())
        if vk is None:
            raise ValueError(f'未知按键 {key}')
        scan = user32.MapVirtualKeyW(vk, 0)
        user32.PostMessageW(hwnd, self.WM_KEYUP, vk,
                            1 | (scan << 16) | (1 << 30) | (1 << 31))
        self.log.append(('key_up', key, hwnd))
        return True

    def post_key(self, key: str, hwnd=None):
        """PostMessage 投递按键（**必须带扫描码**，模拟器通常只认扫描码）。"""
        hwnd = hwnd or getattr(self, 'render_hwnd', None) or self.find_render_hwnd()
        if not hwnd:
            return False
        vk = VK.get(key.lower())
        if vk is None:
            raise ValueError(f'未知按键 {key}')
        scan = user32.MapVirtualKeyW(vk, 0)
        lp_down = 1 | (scan << 16)
        lp_up = 1 | (scan << 16) | (1 << 30) | (1 << 31)
        user32.PostMessageW(hwnd, self.WM_KEYDOWN, vk, lp_down)
        time.sleep(0.03)
        user32.PostMessageW(hwnd, self.WM_KEYUP, vk, lp_up)
        self.log.append(('post_key', key, hwnd))
        return True

    def post_click(self, fx, fy, hwnd=None, button='left'):
        """PostMessage 投递鼠标点击（坐标按渲染区的**相对像素**）。"""
        hwnd = hwnd or getattr(self, 'render_hwnd', None) or self.find_render_hwnd()
        if not hwnd:
            return False
        cw, ch = self.size
        cx = int(fx * cw / self.FRAME_W)
        cy = int(fy * ch / self.FRAME_H)
        lp = (cy << 16) | (cx & 0xFFFF)
        md = self.WM_LBUTTONDOWN if button == 'left' else self.WM_RBUTTONDOWN
        mu = self.WM_LBUTTONUP if button == 'left' else self.WM_RBUTTONUP
        mk = self.MK_LBUTTON if button == 'left' else self.MK_RBUTTON
        user32.PostMessageW(hwnd, self.WM_MOUSEMOVE, 0, lp)
        time.sleep(0.02)
        user32.PostMessageW(hwnd, md, mk, lp)
        time.sleep(0.03)
        user32.PostMessageW(hwnd, mu, 0, lp)
        self.log.append(('post_click', (fx, fy), hwnd, button))
        return True

    def _abs_norm(self, sx, sy):
        # SendInput 的绝对坐标是 0..65535 的归一化值（相对主屏）
        return (int(sx * 65535 / max(1, self.SW - 1)), int(sy * 65535 / max(1, self.SH - 1)))

    # ---------- 鼠标 ----------
    def move_frame(self, fx, fy):
        sx, sy = self.to_screen(fx, fy)
        nx, ny = self._abs_norm(sx, sy)
        self._mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, nx, ny)

    def click_frame(self, fx, fy, button='left', settle=0.05):
        self.move_frame(fx, fy)
        time.sleep(settle)
        self._mouse(MOUSEEVENTF_LEFTDOWN if button == 'left' else MOUSEEVENTF_RIGHTDOWN)
        time.sleep(0.03)
        self._mouse(MOUSEEVENTF_LEFTUP if button == 'left' else MOUSEEVENTF_RIGHTUP)
        self.log.append(('click', (fx, fy), button))

    def drag_frame(self, points, hold=0.04, between=0.012, button='left', curve_steps=0):
        """★"划火柴"式拖拽：移动到首点 → **按住** → 沿路径移动 → 松开。

        points: [(fx,fy), ...]（帧坐标）；curve_steps>0 时在相邻点之间插值，
        模拟官方宏的 `curve_rel` 曲线移动（游戏需要"连续移动"才认定为拖拽）。
        """
        self.move_frame(*points[0])
        time.sleep(0.03)
        self._mouse(MOUSEEVENTF_LEFTDOWN if button == 'left' else MOUSEEVENTF_RIGHTDOWN)
        time.sleep(hold)
        path = list(points[1:])
        if curve_steps > 0:
            interp = []
            for (x0, y0), (x1, y1) in zip(points[:-1], points[1:]):
                for k in range(1, curve_steps + 1):
                    t = k / (curve_steps + 1.0)
                    interp.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
            path = interp + [points[-1]]
        for (x, y) in path:
            self.move_frame(x, y)
            time.sleep(between)
        time.sleep(hold)
        self._mouse(MOUSEEVENTF_LEFTUP if button == 'left' else MOUSEEVENTF_RIGHTUP)
        self.log.append(('drag', points[0], points[-1], len(path)))

    # ---------- 键盘（触发 MuMu 的宏） ----------
    def key_tap(self, key: str, hold=0.05):
        vk = VK.get(key.lower(), None)
        if vk is None:
            raise ValueError(f'未知按键 {key}')
        self._key(vk)
        time.sleep(hold)
        self._key(vk, up=True)
        self.log.append(('key', key))

    def key_hold(self, key: str, seconds: float):
        vk = VK.get(key.lower())
        self._key(vk)
        time.sleep(seconds)
        self._key(vk, up=True)

    # ---------- 窗口聚焦 ----------
    def focus_window(self, title_substr: str) -> bool:
        hwnd = user32.FindWindowW(None, None)
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(h, _l):
            ln = user32.GetWindowTextLengthW(h)
            if ln > 0:
                buf = ctypes.create_unicode_buffer(ln + 1)
                user32.GetWindowTextW(h, buf, ln + 1)
                if title_substr in buf.value and user32.IsWindowVisible(h):
                    found.append((h, buf.value))
            return True

        user32.EnumWindows(cb, 0)
        if not found:
            return False
        h = found[0][0]
        user32.ShowWindow(h, 9)                 # SW_RESTORE
        user32.SetForegroundWindow(h)
        user32.BringWindowToTop(h)
        time.sleep(0.4)
        return True


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    wi = WinInput()
    print('屏幕尺寸:', (wi.SW, wi.SH), ' 客户区原点:', wi.CLIENT_ORIGIN)
    print('帧(1806,80) -> 屏幕', wi.to_screen(1806, 80))
    print('聚焦 MuMu:', wi.focus_window('MuMu模拟器12'))
