# -*- coding: utf-8 -*-
"""tap_and_shot.py — 界面级"点一下 → 截图"原子算子（**只做点击与截图，不读游戏文件/内存**）。

用于按 MAA 流程导航时的**逐步验证**：每次点击后立刻截图，确认落到预期界面，
避免"盲点"导致误入禁用界面（仓库/基建/抽卡/商店/邮件/养成/模组）。

用法：
    python apps/tap_and_shot.py 1427 224 out.png --wait 1.2
    python apps/tap_and_shot.py --shot out.png            # 只截图不点击
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture      # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'


def tap(x: int, y: int) -> None:
    subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True)


def swipe(x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> None:
    subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'swipe',
                    str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(ms))],
                   capture_output=True)


def shot(out: str) -> str:
    import cv2
    img = make_capture('adb').grab().image
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    cv2.imwrite(out, img)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('x', nargs='?', type=int)
    ap.add_argument('y', nargs='?', type=int)
    ap.add_argument('out')
    ap.add_argument('--wait', type=float, default=1.2)
    ap.add_argument('--shot', action='store_true')
    ap.add_argument('--swipe', default=None, help='x1,y1,x2,y2[,ms]：滑动而非点击')
    a = ap.parse_args()
    import time
    if a.swipe:
        v = [int(t) for t in a.swipe.split(',')]
        swipe(*v)
        print(f'[tap_and_shot] swipe {v}')
    elif not a.shot:
        tap(a.x, a.y)
        print(f'[tap_and_shot] tap ({a.x},{a.y})')
    time.sleep(a.wait)
    p = shot(a.out)
    print(f'[tap_and_shot] 截图 → {p}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
