"""ADB 输入后端（input:adb）—— 与宿主真实鼠标/键盘隔离的注入通道

用途：模拟器（MuMu12/夜神等）多开与后台执行；不移动宿主真实光标，
因此自动打图时用户仍可正常使用电脑（需求 2.5）。

合规：ADB 注入等价于「触摸屏幕」（GUI 级操作），不读取/修改游戏文件或内存；
严禁在游戏运行时读取/复制/改动游戏数据文件（见合规声明 2026-09-02 第 4 条）。

spec/config：
  adb         adb 可执行文件路径（默认自动探测 MuMu12）
  serial      设备序列号（缺省用唯一连接设备；MuMu12 常见 127.0.0.1:16384）
  display_w   模拟器逻辑分辨率宽（默认 1920）
  display_h   模拟器逻辑分辨率高（默认 1080）
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time

from kernel.registry import action

DEFAULT_ADB_CANDIDATES = [
    r'D:\__soft\MuMu Player 12\shell\adb.exe',
    r'E:\Program Files\Netease\MuMu Player 12\shell\adb.exe',
    r'C:\Program Files\Netease\MuMu Player 12\shell\adb.exe',
    'adb',
]


def _find_adb(explicit: str | None = None) -> str | None:
    if explicit and os.path.exists(explicit):
        return explicit
    for c in DEFAULT_ADB_CANDIDATES:
        if c == 'adb':
            p = shutil.which('adb')
            if p:
                return p
        elif os.path.exists(c):
            return c
    return None


@action("input:adb")
class AdbInputBackend:
    name = 'adb'

    def __init__(self, adb: str | None = None, serial: str | None = None,
                 display_w: int = 1920, display_h: int = 1080, **kw):
        self.adb = _find_adb(adb)
        self.serial = serial
        self.display_w = display_w
        self.display_h = display_h
        self._scale_x = 1.0
        self._scale_y = 1.0
        self.dry_run = bool(kw.get('dry_run', False))
        self.log: list[dict] = []

    # ---------- 基础 ----------
    def set_screen(self, w: int, h: int):
        """告知注入坐标所处坐标系尺寸（如宿主窗口像素），用于换算到设备逻辑坐标。"""
        self._scale_x = self.display_w / max(1, w)
        self._scale_y = self.display_h / max(1, h)

    def _run(self, args: list[str]) -> str:
        if self.dry_run or not self.adb:
            self.log.append({'cmd': args, 'dry': True})
            return ''
        cmd = [self.adb]
        if self.serial:
            cmd += ['-s', self.serial]
        cmd += args
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            self.log.append({'cmd': args, 'rc': r.returncode, 'out': (r.stdout or '')[:200]})
            return r.stdout or ''
        except Exception as ex:
            self.log.append({'cmd': args, 'err': str(ex)})
            return ''

    def devices(self) -> str:
        return self._run(['devices'])

    def _dev_xy(self, x: int, y: int) -> tuple[int, int]:
        return int(x * self._scale_x), int(y * self._scale_y)

    # ---------- 动作（与内核 InputBackend 协议一致） ----------
    def click(self, x: int, y: int, button: str = 'left', clicks: int = 1):
        dx, dy = self._dev_xy(x, y)
        for _ in range(max(1, clicks)):
            self._run(['shell', 'input', 'tap', str(dx), str(dy)])
            if clicks > 1:
                time.sleep(0.05)

    def move(self, x: int, y: int, duration: float = 0.0):
        # ADB 无独立移动事件；用极短 swipe 模拟（同点）
        dx, dy = self._dev_xy(x, y)
        self._run(['shell', 'input', 'swipe', str(dx), str(dy), str(dx), str(dy), '1'])

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.2):
        a = self._dev_xy(x1, y1)
        b = self._dev_xy(x2, y2)
        self._run(['shell', 'input', 'swipe', str(a[0]), str(a[1]), str(b[0]), str(b[1]),
                   str(int(duration * 1000))])

    def scroll(self, dy: int):
        # 无通用滚轮：使用 swipe 模拟
        cx, cy = self.display_w // 2, self.display_h // 2
        self._run(['shell', 'input', 'swipe', str(cx), str(cy), str(cx), str(cy - dy * 10), '100'])

    def key(self, key: str, presses: int = 1, down: bool = False):
        code = {'esc': 111, 'back': 4, 'home': 3, 'space': 62, 'enter': 66}.get(key.lower())
        if code is None:
            return
        for _ in range(max(1, presses)):
            self._run(['shell', 'input', 'keyevent', str(code)])

    def text(self, s: str):
        safe = s.replace(' ', '%s')
        self._run(['shell', 'input', 'text', safe])


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    b = AdbInputBackend(dry_run=True)
    print('adb 路径:', b.adb)
    b.set_screen(1920, 1080)
    b.click(100, 200)
    b.drag(10, 10, 200, 200, 0.3)
    print('dry-run 日志:', b.log)
