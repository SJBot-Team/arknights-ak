# -*- coding: utf-8 -*-
"""relocate_bar_in_battle.py — 进战斗后立刻采集，用帧间差分**重定位费用条 ROI**，并用自检判定

## 解决 §7.128 的两个疑点
1. **链路是否真的是 H12-4 演习**：本脚本打印 `UiState` 每一次命中证据（上一版没打印，导致无法复盘）；
2. **费用条 ROI 是否仍成立**：进战斗后在"费用未满"窗口内密集采 8 帧并存盘，
   对相邻帧做**帧间差分**（费用条每帧都在动，而周围 UI 静止），找横向覆盖 >50% 的长横条；
   随后用**新旧两套 ROI** 各算一遍相位，交给 `bar_sanity` 判定——**哪套能通过自检就是对的**。
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

from plugins.capture.emu_window import make_capture, EmuWindowCapture        # noqa: E402
from plugins.clock.bar_sanity import summarize as sanity                     # noqa: E402
from plugins.clock.frame_clock import PIXEL_MAP_30F, bar_phase, frame_from_width  # noqa: E402
from plugins.nav.auto_enter import AutoEnter                                 # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer               # noqa: E402
from plugins.recognize.maa_anchor import MaaAnchor                           # noqa: E402
from plugins.recognize.ui_state import UiState                               # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TPL = os.path.join(TMP, 'tpl_h124.json')
NUM_ROI = (1795, 730, 1915, 805)
OLD_BAR = (1739, 805, 1919, 818)
SEARCH = (1650, 700, 1920, 900)      # 费用条搜索范围
MIN_CONF = 0.85


def main():
    cap = make_capture('adb')
    EmuWindowCapture().open().bring_to_front()
    time.sleep(0.4)
    rec = CostNumberRecognizer()
    ui = UiState()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}

    def tap(x, y):
        subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                       capture_output=True)

    def cost(img):
        ms = rec.run(img, spec, None, (0, 0))
        if not ms:
            return None, 0.0
        c = float(ms[0].extra.get('confidence', 0.0))
        return (int(ms[0].extra['cost']) if c >= MIN_CONF else None), c

    # ---- 进关（AutoEnter 会打印 UiState 证据 = 链路复核）----
    ae = AutoEnter(cap, tap, ui, ma=MaaAnchor(thr=0.85), wait_battle_sleep=0.3)
    if not ae.enter():
        print('进关失败'); return 2
    print('=== 链路证据（UiState 命中）===')
    for t in ae.trace:
        print(f'   {t}')

    # ---- 立刻密集采 8 帧并存盘（费用未满窗口）----
    frames, rows = [], []
    t0 = time.perf_counter()
    for i in range(8):
        img = cap.grab().image
        t = time.perf_counter() - t0
        cv2.imwrite(os.path.join(TMP, f'reloc_{i}.png'), img)
        c, cf = cost(img)
        po = bar_phase(img[OLD_BAR[1]:OLD_BAR[3], OLD_BAR[0]:OLD_BAR[2]],
                       full_px=OLD_BAR[2] - OLD_BAR[0])
        frames.append(img)
        rows.append((t, c, cf, po['fill_px']))
        print(f'  采样{i}: t={t:5.2f} 费用={c} conf={cf:.2f} 旧ROI填充={po["fill_px"]}px')
        time.sleep(0.12)

    # ---- 帧间差分定位"长横条" ----
    x0, y0, x1, y1 = SEARCH
    acc = None
    for i in range(1, len(frames)):
        a = cv2.cvtColor(frames[i - 1][y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype('float32')
        b = cv2.cvtColor(frames[i][y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype('float32')
        d = np.abs(a - b)
        acc = d if acc is None else acc + d
    print('\n=== 帧间差分行能量（Top 12）===')
    row = acc.mean(axis=1)
    order = np.argsort(row)[::-1][:12]
    for j in sorted(order):
        seg = acc[j, :]
        frac = float((seg > seg.max() * 0.5).mean()) if seg.max() > 0 else 0.0
        print(f'   y={y0+j:>4}  能量={row[j]:6.2f}  横向覆盖={frac*100:5.1f}%'
              f'{"   ← 长横条" if frac > 0.5 else ""}')

    # 取"能量较高且横向覆盖大"的行聚成条带
    cand = [int(j) for j in np.argsort(row)[::-1][:40]
            if float((acc[j, :] > acc[j, :].max() * 0.5).mean()) > 0.5]
    if cand:
        ya, yb = y0 + min(cand), y0 + max(cand)
        new_bar = (x0, ya, x1, yb + 1)
        print(f'\n候选新 ROI = {new_bar}（行 {ya}~{yb}）')
    else:
        new_bar = None
        print('\n未找到长横条候选（可能费用条此刻未在动）')

    # ---- 用两套 ROI 各算相位，交给自检判定 ----
    def series(bar):
        out = []
        for (t, c, cf, _f), img in zip(rows, frames):
            p = bar_phase(img[bar[1]:bar[3], bar[0]:bar[2]], full_px=bar[2] - bar[0])
            out.append((c, p['fill_px'], frame_from_width(p['fill_px'], PIXEL_MAP_30F)))
        return out

    print('\n=== 旧 ROI 相位序列 ===')
    for s in series(OLD_BAR):
        print('   ', s)
    print(sanity(series(OLD_BAR)))
    if new_bar:
        print('\n=== 新 ROI 相位序列 ===')
        for s in series(new_bar):
            print('   ', s)
        print(sanity(series(new_bar)))
    print('\n判定：哪套 ROI 的自检通过 ⇒ 该套就是当前链路下的正确费用条位置。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
