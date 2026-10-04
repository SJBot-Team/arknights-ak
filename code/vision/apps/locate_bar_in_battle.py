# -*- coding: utf-8 -*-
"""locate_bar_in_battle.py — 进战斗后**立刻**采样，用帧间差分定位费用条 ROI

思路（省掉"故意消耗"这一步的最简等价做法）：
  战斗开始后的**前 10 秒**费用从 10 涨到 20（`显示费用 = 初始费用 + t`），
  这段时间**费用条一直在跳** ⇒ 只要"进战斗后立刻采样"，就能满足方法一对"条在动"的要求。
  （若错过了这 10 秒、费用顶到上限，条就静止了，差分无变化——这正是上一轮的结果。）

流程：状态自适应进战斗（adb display 通道 + 置信度阈值）→ 判定 battle 后**立即**连拍 4 帧
     → 逐帧打印费用数字 → 帧间差分找"长横条" → 用候选 ROI 算条内相位 → 检查相位是否在推进。

用法：locate_bar_in_battle.py [采样帧数] [间隔秒]
"""
from __future__ import annotations

import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture                     # noqa: E402
from plugins.clock.frame_clock import bar_phase                          # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer           # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
NUM_ROI = (1795, 730, 1915, 805)
TPL = os.path.join(TMP, 'tpl_h124.json')
SEARCH = (1650, 700, 1920, 900)
TAP_H124, TAP_DRILL, TAP_START = (953, 812), (1441, 975), (1659, 766)
MIN_CONF = 0.85


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    gap = float(sys.argv[2]) if len(sys.argv) > 2 else 0.6
    cam = make_capture('adb')
    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}

    def read_cost(img=None):
        img = cam.grab().image if img is None else img
        ms = rec.run(img, spec, None, (0, 0))
        if not ms:
            return None, 0.0
        c = float(ms[0].extra.get('confidence', 0.0))
        return (int(ms[0].extra['cost']) if c >= MIN_CONF else None), c

    def tap(x, y):
        import subprocess
        subprocess.run([r'D:\__soft\MuMu Player 12\shell\adb.exe', '-s', '127.0.0.1:16384',
                        'shell', 'input', 'tap', str(x), str(y)], capture_output=True)

    # ---- 阶段1：进战斗 ----
    for step in range(10):
        img = cam.grab().image
        c, conf = read_cost(img)
        if c is not None:
            print(f'[{step}] 已在战斗（费用 {c} conf {conf:.3f}）→ 立即采样')
            break
        bright = lambda roi: float((cv2.cvtColor(img[roi[1]:roi[3], roi[0]:roi[2]],
                                                 cv2.COLOR_BGR2GRAY) > 200).mean())
        if bright((1540, 610, 1760, 900)) > 0.02:
            print(f'[{step}] squad → 点开始行动'); tap(*TAP_START)
        elif bright((1370, 930, 1510, 1020)) > 0.02:
            print(f'[{step}] detail → 点演习'); tap(*TAP_DRILL)
        else:
            print(f'[{step}] map → 点 H12-4'); tap(*TAP_H124)
        time.sleep(1.2)
    else:
        print('10 步内没进到战斗'); return 2

    # ---- 阶段2：立刻连拍 ----
    frames, costs = [], []
    for i in range(n):
        img = cam.grab().image
        c, conf = read_cost(img)
        frames.append(img)
        costs.append(c)
        print(f'   采样 {i}: 费用={c} conf={conf:.3f} 体积={img.shape}')
        if i + 1 < n:
            time.sleep(gap)

    # ---- 阶段3：帧间差分定位长横条 ----
    x0, y0, x1, y1 = SEARCH
    print('\n帧间差分行能量（>2.0 才列）：')
    diffs = []
    for i in range(1, len(frames)):
        ga = cv2.cvtColor(frames[i - 1][y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype('float32')
        gb = cv2.cvtColor(frames[i][y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype('float32')
        d = np.abs(ga - gb)
        diffs.append(d)
        row = d.mean(axis=1)
        ys = [(y0 + j, round(float(v), 2)) for j, v in enumerate(row) if v > 2.0]
        print(f'  帧{i-1}→{i}: ' + (', '.join(f'y={a}({b})' for a, b in ys) if ys else '无变化'))

    if diffs:
        d = np.mean(diffs, axis=0)
        row = d.mean(axis=1)
        ys = [j for j, v in enumerate(row) if v > 2.0]
        if ys:
            ya, yb = y0 + min(ys), y0 + max(ys)
            seg = d[min(ys):max(ys) + 1, :].mean(axis=0)
            frac = float((seg > seg.max() * 0.5).mean())
            print(f'\n候选条带 y∈[{ya},{yb}]（高 {yb-ya+1}px），横向覆盖 {frac*100:.1f}%'
                  f' {"← 长横条 ⇒ 很可能就是费用条" if frac > 0.5 else ""}')
            if frac > 0.5:
                bar_roi = (x0, ya, x1, yb)
                print(f'\n用候选 ROI {bar_roi} 算条内相位：')
                for i, f in enumerate(frames):
                    ph = bar_phase(f[ya:yb + 1, x0:x1])
                    print(f'   帧{i}: 费用={costs[i]} 相位={ph["sub_frame"]:>2} 比例={ph["frac"]:.3f} 填充={ph["fill_px"]}px')
                print('\n判据：①相位应各不相同（条在动）；②相位应与费用数字一致'
                      '（费用 +1 ⇒ 相位回绕一次）；③填充宽度应随相位数增加。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
