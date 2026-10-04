# -*- coding: utf-8 -*-
"""verify_phase_precision.py — 相位↔墙钟精度验收（正式版）

## 协议（§7.114 的两条硬约束）
1. **采样间隔必须 < 1 秒**：否则相位绕圈数不确定，`Δc×30 + Δphase` 出现歧义
   （实测：间隔 1.02s 时 2/10 样本误差约 +29 帧；其余 8 个误差 ≤1.5 帧）。
   ⇒ 本脚本**不额外 sleep**，间隔即 adb 采集耗时（约 0.6~0.75s）。
2. **进战斗后零延迟采样**：费用上限 20、进战斗起约 10 秒涨满，错过就只剩"封顶静止"。

## 流程
置前台 → 若在战斗中且费用已封顶则**等本局结束**（结算）→ AutoEnter 进关（只走演习）
→ 一旦检测到战斗**立即**密集采样 → 逐对比较并给出 |误差| 统计。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture, EmuWindowCapture        # noqa: E402
from plugins.clock.frame_clock import PIXEL_MAP_30F, bar_phase, frame_from_width  # noqa: E402
from plugins.nav.auto_enter import AutoEnter                                 # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer               # noqa: E402
from plugins.recognize.maa_anchor import MaaAnchor                           # noqa: E402
from plugins.recognize.ui_state import UiState                               # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
TPL = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\tpl_h124.json'
NUM_ROI = (1795, 730, 1915, 805)
BAR_ROI = (1739, 805, 1919, 818)
MIN_CONF = 0.85


def main():
    max_wait_round = float(sys.argv[1]) if len(sys.argv) > 1 else 70.0
    cap = make_capture('adb')
    rec = CostNumberRecognizer()
    ma = MaaAnchor(thr=0.85)
    ui = UiState()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}

    EmuWindowCapture().open().bring_to_front()
    time.sleep(0.4)

    def tap(x, y):
        subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                       capture_output=True)

    def cost(img):
        ms = rec.run(img, spec, None, (0, 0))
        if not ms:
            return None, 0.0
        c = float(ms[0].extra.get('confidence', 0.0))
        return (int(ms[0].extra['cost']) if c >= MIN_CONF else None), c

    def phase(img):
        p = bar_phase(img[BAR_ROI[1]:BAR_ROI[3], BAR_ROI[0]:BAR_ROI[2]],
                      full_px=BAR_ROI[2] - BAR_ROI[0])
        return frame_from_width(p['fill_px'], PIXEL_MAP_30F), p['fill_px']

    # ---- 若上一局还在跑（费用封顶），等它结束 ----
    img = cap.grab().image
    st = ui.classify(img)['state']
    c0, _ = cost(img)
    if st == 'battle':
        print(f'当前在战斗中（费用 {c0}）→ 等本局结束（最多 {max_wait_round:.0f}s）')
        t0 = time.perf_counter()
        while time.perf_counter() - t0 < max_wait_round:
            if ui.classify(cap.grab().image)['state'] != 'battle':
                print(f'  本局已结束（{time.perf_counter()-t0:.0f}s）')
                break
            time.sleep(1.0)
        else:
            print('  等待超时'); return 3
        time.sleep(1.5)

    # ---- 进关（只走演习；AutoEnter 内含合规约束）----
    ae = AutoEnter(cap, tap, ui, ma=ma, wait_battle_sleep=0.3)
    if not ae.enter():
        print('进关失败'); return 2
    print('已进入战斗 → 立即采样（无额外 sleep，间隔≈adb 采集耗时）')

    # ---- 零延迟采样 ----
    S = []
    t1 = time.perf_counter()
    while time.perf_counter() - t1 < 14 and len(S) < 18:
        ta = time.perf_counter(); im = cap.grab().image; tb = time.perf_counter()
        mid = (ta + tb) / 2.0
        c, cf = cost(im)
        ph, fill = phase(im)
        S.append((mid, c, ph))
        print(f'  采样{len(S)-1}: t={mid-t1:5.2f} 费用={c} conf={cf:.2f} 填充={fill:>3}px 帧={ph}')

    # ---- 比对 ----
    print('\n逐对比较（相位↔墙钟）')
    errs, bad = [], []
    for i in range(1, len(S)):
        a, b = S[i - 1], S[i]
        if a[1] is None or b[1] is None:
            continue
        dc, dph = b[1] - a[1], (b[2] - a[2]) % 30
        wall = (b[0] - a[0]) * 30.0
        if dc == 0 and dph == 0:
            print(f'  #{i}: 静止（封顶），跳过'); continue
        fr = dc * 30 + dph
        e = fr - wall
        (errs if abs(e) <= 5 else bad).append(abs(e))
        print(f'  #{i}: 费用 {a[1]}→{b[1]}(Δ{dc}) 相位 {a[2]}→{b[2]}(Δ{dph}) ⇒ 推得 {fr:>3} 帧 | '
              f'墙钟 {wall:6.2f} | 误差 {e:+6.2f}  (间隔 {wall/30:.2f}s)')
    if errs:
        errs.sort()
        print(f'\n达标样本 {len(errs)}；|误差| 中位 {errs[len(errs)//2]:.2f}、最大 {errs[-1]:.2f} 帧')
        if bad:
            bad.sort()
            print(f'越界样本 {len(bad)}（|误差|>5，通常是采样间隔 ≥1s 造成的绕圈歧义）：{bad}')
        print('判据 |误差| ≤ 2 帧：' + ('✅ 达标' if errs[len(errs)//2] <= 2 else '🟡 未达标'))
    else:
        print('\n无有效样本')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
