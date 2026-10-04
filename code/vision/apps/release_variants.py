# -*- coding: utf-8 -*-
"""release_variants.py — 在"已抓起干员"的前提下，试多种**抬起/落格**变体。

## 背景
所有通道的"抓取"都成功（ADB motionevent、真实鼠标拖拽），但"抬起"从未被接受。
本脚本固定"先抓起"，然后逐个试：
  A. 拖到目标格 → **停稳 0.6s** → 抬起（可能游戏要求松手前有稳定期）
  B. 抬起后**再补一次真实鼠标点击**（点击落格）
  C. 用 `mouse_event` 的**绝对移动**（MOUSEEVENTF_MOVE|ABSOLUTE）做路径，再抬起
     （避免 SetCursorPos 与按键状态交错引起的怪异行为）
每个变体后判定"是否仍在悬停"（右侧剩余区 ≈52~58 = 悬停中；≈84 = 已结束）。

安全：仅界面级鼠标操作；演习不消耗理智。
"""
from __future__ import annotations

import ctypes
import os
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer                      # noqa: E402
from plugins.action.win_input import WinInput                    # noqa: E402
from plugins.capture.emu_window import make_capture             # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
u32 = ctypes.windll.user32
LD, LU = 0x0002, 0x0004
MOVE_ABS = 0x0001 | 0x8000
CARD, CELL, CANCEL = (63, 949), (934, 502), (732, 304)


def rest(cap):
    img = cap.grab().image
    return round(float(cv2.cvtColor(img[880:950, 1620:1920], cv2.COLOR_BGR2GRAY).mean()), 1)


def grip(wi, dep):
    """抓起干员：真实鼠标快速拖到 D6 并**保持按下**（不抬起）。"""
    p0 = wi.to_screen(*CARD)
    p1 = wi.to_screen(*CELL)
    u32.SetCursorPos(int(p0[0]), int(p0[1]))
    time.sleep(0.06)
    u32.mouse_event(LD, 0, 0, 0, 0)
    time.sleep(0.06)
    for k in range(1, 9):
        t = k / 9.0
        u32.SetCursorPos(int(p0[0] + (p1[0] - p0[0]) * t), int(p0[1] + (p1[1] - p0[1]) * t))
        time.sleep(0.015)


def release_abs(wi):
    sw, sh = wi.screen_size if hasattr(wi, 'screen_size') else (2560, 1600)
    x, y = wi.to_screen(*CELL)
    u32.mouse_event(MOVE_ABS, 0, 0, int(x * 65535 / sw), int(y * 65535 / sh), 0)
    time.sleep(0.05)
    u32.mouse_event(LU, 0, 0, 0, 0)


def click(wi, pt):
    x, y = wi.to_screen(*pt)
    u32.SetCursorPos(int(x), int(y))
    time.sleep(0.05)
    u32.mouse_event(LD, 0, 0, 0, 0)
    time.sleep(0.05)
    u32.mouse_event(LU, 0, 0, 0, 0)


def main() -> int:
    cap = make_capture('adb')
    dep, wi = Deployer(cap), WinInput()
    sw, sh = wi._screen_size() if hasattr(wi, '_screen_size') else (2560, 1600)
    wi.screen_size = (sw, sh)
    print(f'屏幕 {sw}x{sh}；frame→screen: 卡片{wi.to_screen(*CARD)} 格{wi.to_screen(*CELL)}')

    for tag in ('A', 'B', 'C'):
        if rest(cap) < 70:                       # 若已处于悬停，先取消
            dep.tap(*CANCEL)
            time.sleep(0.9)
        print(f'\n--- 变体 {tag} ---  起手剩余区={rest(cap)}')
        grip(wi, dep)
        time.sleep(0.5)
        h = rest(cap)
        print(f'  抓起后剩余区={h} ⇒ {"悬停中 ✓" if h < 70 else "未抓起 ✗"}')
        if h >= 70:
            continue
        if tag == 'A':
            print('  A: 停稳 0.6s 后抬起')
            time.sleep(0.6)
            u32.mouse_event(LU, 0, 0, 0, 0)
        elif tag == 'B':
            print('  B: 抬起 → 再补一次真实鼠标点击')
            u32.mouse_event(LU, 0, 0, 0, 0)
            time.sleep(0.35)
            click(wi, CELL)
        else:
            print('  C: 用绝对移动路径后抬起')
            release_abs(wi)
        time.sleep(1.2)
        img = cap.grab().image
        cv2.imwrite(os.path.join(TMP, f'rv_{tag}.png'), img)
        r = rest(cap)
        print(f'  结果：剩余区={r} ⇒ {"**悬停结束（可能已落格/或已取消）**" if r > 70 else "仍在悬停"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
