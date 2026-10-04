# -*- coding: utf-8 -*-
"""enter_and_pause.py — 进关后**立即（准备阶段＝0 帧）暂停**，为"从局内开始"运行 PRTS+ 做准备

## 依据（用户 2026-09-14）
> 看起来发生了开局暂停次数错误导致它的操作顺序有误。由于**暂停和结束暂停的输入是相同的**，
> 取决于当前是否处于暂停状态，这次运行出错了。你可以**进入关卡 0 帧暂停**，
> 再运行赛博塑料**从局内开始**，应该可以解决问题。

⇒ 做法：用 AutoEnter 走**演习**进关（只点「演习」/编队「开始行动」），
一旦检测到战斗（此时是**准备阶段**，游戏时间仍为 0）就**立刻点暂停**，
使游戏停在"暂停"状态；随后再运行 `prts+.exe --xlsm ...`（**不加 --autoenter**，即"从局内开始"）。

暂停按钮：右上角（帧坐标约 1877, 76）。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture, EmuWindowCapture       # noqa: E402
from plugins.nav.auto_enter import AutoEnter                                # noqa: E402
from plugins.recognize.maa_anchor import MaaAnchor                          # noqa: E402
from plugins.recognize.ui_state import UiState                              # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
TAP_PAUSE = (1877, 76)


def main():
    cap = make_capture('adb')
    EmuWindowCapture().open().bring_to_front()
    time.sleep(0.4)
    ui = UiState()
    ma = MaaAnchor(thr=0.85)

    def tap(x, y):
        subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                       capture_output=True)

    def fp(img):
        return cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')

    ae = AutoEnter(cap, tap, ui, ma=ma, wait_battle_sleep=0.2)
    if not ae.enter():
        print('进关失败'); return 2
    print('已进入战斗（准备阶段）→ 立即暂停')

    # 立刻暂停（尽量赶在 0 帧附近）
    img0 = cap.grab().image
    tap(*TAP_PAUSE)
    time.sleep(0.8)
    img1 = cap.grab().image
    d = float(np.abs(fp(img0) - fp(img1)).mean())
    print(f'  点暂停后画面变化 {d:.2f}')

    # 校验：暂停后画面应静止（连采两帧差异≈0）
    a = cap.grab().image
    time.sleep(1.2)
    b = cap.grab().image
    d2 = float(np.abs(fp(a) - fp(b)).mean())
    print(f'  暂停后两帧差异 {d2:.4f} ⇒ {"已暂停（静止）" if d2 < 0.005 else "仍在动（未暂停）"}')
    cv2.imwrite(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\.tmp', 'paused_ready.png'), b)
    if d2 >= 0.005:
        print('  ⚠ 可能没暂停成功，可再点一次暂停')
        tap(*TAP_PAUSE)
        time.sleep(1.0)
        c = cap.grab().image
        time.sleep(1.2)
        e = cap.grab().image
        d3 = float(np.abs(fp(c) - fp(e)).mean())
        print(f'  再点一次后两帧差异 {d3:.4f} ⇒ {"已暂停" if d3 < 0.005 else "仍未暂停"}')
    print('\n现在可运行：prts+.exe --xlsm D:\\__soft\\ak\\prts_plan_h124.xlsm  （从局内开始）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
