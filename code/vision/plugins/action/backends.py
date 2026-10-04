"""输入后端插件：鼠标/键盘。坐标一律绝对像素（相对坐标已由内核换算）。"""
from __future__ import annotations

import ctypes
import time

from kernel.input import BaseInput
from kernel.registry import action

# ---------------- DirectInput（游戏友好） ----------------

@action("input:directinput")
class DirectInputBackend(BaseInput):
    name = "directinput"

    def __init__(self):
        import pydirectinput
        self.pd = pydirectinput
        self.pd.FAILSAFE = True          # 鼠标甩到角落即中止（急停）
        self.pd.PAUSE = 0.0

    def _set_pos(self, x: int, y: int) -> None:
        ctypes.windll.user32.SetCursorPos(int(x), int(y))

    def click(self, x, y, button="left", clicks=1):
        self._set_pos(x, y)
        for _ in range(max(1, clicks)):
            self.pd.mouseDown(button=button)
            self.pd.mouseUp(button=button)

    def move(self, x, y, duration=0.0):
        if duration and duration > 0:
            import pyautogui  # 可选：平滑移动
            pyautogui.moveTo(int(x), int(y), duration=duration)
        else:
            self._set_pos(x, y)

    def drag(self, x1, y1, x2, y2, duration=0.2):
        self._set_pos(x1, y1)
        self.pd.mouseDown(button="left")
        steps = max(2, int(duration / 0.01))
        for i in range(1, steps + 1):
            self._set_pos(int(x1 + (x2 - x1) * i / steps), int(y1 + (y2 - y1) * i / steps))
            time.sleep(duration / steps)
        self.pd.mouseUp(button="left")

    def scroll(self, dy):
        self.pd.scroll(int(dy))

    def key(self, key, presses=1, down=False):
        if down:
            self.pd.keyDown(key)
        else:
            for _ in range(max(1, presses)):
                self.pd.press(key)

    def text(self, s):
        self.pd.write(s, interval=0.01)


# ---------------- SendInput（桌面/普通窗口） ----------------

PUL = ctypes.POINTER(ctypes.c_ulong)


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("union", _INPUTUNION)]


@action("input:sendinput")
class SendInputBackend(BaseInput):
    name = "sendinput"

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_ABSOLUTE = 0x8000
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_MIDDLEDOWN = 0x0020
    MOUSEEVENTF_MIDDLEUP = 0x0040
    MOUSEEVENTF_WHEEL = 0x0800
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_UNICODE = 0x0004

    def __init__(self):
        self.user32 = ctypes.windll.user32
        self.user32.SetProcessDPIAware()
        self.sw = self.user32.GetSystemMetrics(0)
        self.sh = self.user32.GetSystemMetrics(1)

    def _send(self, inp: _INPUT):
        self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    def _mouse(self, flags: int, dx: int = 0, dy: int = 0, data: int = 0):
        inp = _INPUT(type=0, union=_INPUTUNION(mi=_MOUSEINPUT(dx, dy, data, flags, 0, None)))
        self._send(inp)

    def _abs(self, x: int, y: int):
        nx = int(x * 65535 / max(1, self.sw - 1))
        ny = int(y * 65535 / max(1, self.sh - 1))
        self._mouse(self.MOUSEEVENTF_MOVE | self.MOUSEEVENTF_ABSOLUTE, nx, ny)

    def click(self, x, y, button="left", clicks=1):
        down, up = {
            "left": (self.MOUSEEVENTF_LEFTDOWN, self.MOUSEEVENTF_LEFTUP),
            "right": (self.MOUSEEVENTF_RIGHTDOWN, self.MOUSEEVENTF_RIGHTUP),
            "middle": (self.MOUSEEVENTF_MIDDLEDOWN, self.MOUSEEVENTF_MIDDLEUP),
        }.get(button, (self.MOUSEEVENTF_LEFTDOWN, self.MOUSEEVENTF_LEFTUP))
        self._abs(x, y)
        for _ in range(max(1, clicks)):
            self._mouse(down)
            self._mouse(up)

    def move(self, x, y, duration=0.0):
        if duration and duration > 0:
            cx, cy = self.user32.GetCursorPos.__self__ and (0, 0) or (0, 0)
            start = ctypes.wintypes.POINT() if hasattr(ctypes, "wintypes") else None
            self._abs(x, y)
        else:
            self._abs(x, y)

    def drag(self, x1, y1, x2, y2, duration=0.2):
        self._abs(x1, y1)
        self._mouse(self.MOUSEEVENTF_LEFTDOWN)
        steps = max(2, int(duration / 0.01))
        for i in range(1, steps + 1):
            self._abs(int(x1 + (x2 - x1) * i / steps), int(y1 + (y2 - y1) * i / steps))
            time.sleep(duration / steps)
        self._mouse(self.MOUSEEVENTF_LEFTUP)

    def scroll(self, dy):
        self._mouse(self.MOUSEEVENTF_WHEEL, data=int(dy) * 120)

    def key(self, key, presses=1, down=False):
        vk = VK_MAP.get(key.lower()) if isinstance(key, str) else int(key)
        if vk is None:
            return
        for _ in range(max(1, presses)):
            if not down:
                self._send(_INPUT(type=1, union=_INPUTUNION(ki=_KEYBDINPUT(0, vk, 0, 0, None))))
                self._send(_INPUT(type=1, union=_INPUTUNION(ki=_KEYBDINPUT(0, vk, self.KEYEVENTF_KEYUP, 0, None))))
            else:
                self._send(_INPUT(type=1, union=_INPUTUNION(ki=_KEYBDINPUT(0, vk, 0, 0, None))))

    def text(self, s: str):
        for ch in s:
            code = ord(ch)
            self._send(_INPUT(type=1, union=_INPUTUNION(ki=_KEYBDINPUT(0, code, self.KEYEVENTF_UNICODE, 0, None))))
            self._send(_INPUT(type=1, union=_INPUTUNION(
                ki=_KEYBDINPUT(0, code, self.KEYEVENTF_UNICODE | self.KEYEVENTF_KEYUP, 0, None))))


VK_MAP = {
    "esc": 0x01, "escape": 0x01, "tab": 0x0F, "space": 0x39, "enter": 0x1C, "return": 0x1C,
    "shift": 0x10, "ctrl": 0x11, "alt": 0x12, "backspace": 0x0E,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    **{f"f{i}": 0x6F + i for i in range(1, 13)},
    **{str(d): 0x30 + d for d in range(10)},
    **{chr(c): 0x41 + (c - 97) for c in range(97, 123)},
}
