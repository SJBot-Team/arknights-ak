# -*- coding: utf-8 -*-
r"""t200_card_find.py — **按干员名找待部署区卡位**（T-200c 收官：卡位自动化）

依据 `plugins/recognize/operator_card.py` 的实测公式：
    卡心 x = 139 + pitch·(i+0.5)，pitch = (1959−139)/n_cards，y = 1007
本工具：①估 n_cards（用 `detect_card_columns`，失败则按 10/11 各试一遍）；
        ②对每个卡心裁头像带，用 `OperatorCardMatcher.rank` 打分；
        ③输出目标干员的 **卡心 x** 与置信度（第一名−第二名）。

用法：python t200_card_find.py 月见夜 11
"""
from __future__ import annotations

import os
import subprocess
import sys

import cv2

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)
from plugins.recognize.operator_card import (                    # noqa: E402
    OperatorCardMatcher, DEPLOY_X_LEFT, DEPLOY_X_RIGHT, DEPLOY_Y,
    PORTRAIT_HALF, PORTRAIT_Y)

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
SHOT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\_cardfind.png'


def grab() -> "cv2.Mat":
    subprocess.run([ADB, '-s', DEV, 'shell', 'screencap', '-p', '/sdcard/cf.png'],
                   capture_output=True)
    subprocess.run([ADB, '-s', DEV, 'pull', '/sdcard/cf.png', SHOT], capture_output=True)
    return cv2.imread(SHOT)


def main() -> int:
    name = sys.argv[1] if len(sys.argv) > 1 else '月见夜'
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 11
    img = grab()
    rec = OperatorCardMatcher()
    pitch = (DEPLOY_X_RIGHT - DEPLOY_X_LEFT) / n
    y0, y1 = PORTRAIT_Y
    rows = []
    for i in range(n):
        cx = DEPLOY_X_LEFT + pitch * (i + 0.5)
        x0, x1 = int(cx - PORTRAIT_HALF), int(cx + PORTRAIT_HALF)
        patch = img[y0:y1, max(0, x0):x1]
        if patch.size == 0:
            continue
        try:
            ranked = rec.rank(patch)
        except Exception as e:                                     # noqa: BLE001
            ranked = []
        top = ranked[0] if ranked else (0.0, None)          # rank() 返回 [(score, name), ...]
        second = ranked[1][0] if len(ranked) > 1 else 0.0
        hit = bool(ranked) and str(ranked[0][1]) == name
        rows.append((i, int(cx), str(top[1]), float(top[0]), float(top[0]) - float(second), hit))
    print(f'{"#":>2} {"cx":>5} {"识别":<8} {"NCC":>6} {"margin":>7}  命中')
    for r in rows:
        print(f'{r[0]:>2} {r[1]:>5} {r[2]:<8} {r[3]:>6.3f} {r[4]:>7.3f}  {"★" if r[5] else ""}')
    hits = [r for r in rows if r[5]]
    if hits:
        best = max(hits, key=lambda r: r[3])
        print(f'⇒ {name} 卡心 x = {best[1]}（NCC {best[3]:.3f}，margin {best[4]:.3f}）')
    else:
        print(f'⇒ 未找到 {name}（可能是 n_cards 不对，或该卡已用掉）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
