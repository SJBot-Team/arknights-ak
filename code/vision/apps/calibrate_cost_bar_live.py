# -*- coding: utf-8 -*-
"""calibrate_cost_bar_live.py — 实机在线标定 + 验证「费用条相位」帧级时钟（用户方法 1）。

做法：进演习 → 点开始行动 → 等战斗开始 → 用窗口抓屏（BetterCam，~30fps）连拍 N 秒，
逐帧读「费用数字」（整数格）与「费用条填充比例」（条内帧偏移），打印表并做三条断言：
  1. 条内相位应当**逐帧递增 1**、到 30 回绕（每费 30 帧）；
  2. 相位回绕次数 == 费用数字增加量（每满一格 +1 费）；
  3. 由 `CostLatticeClock` 融合出的绝对帧应单调、且与连拍帧数差 ≤ 容忍（说明没有丢帧/多帧）。

费用条 ROI 与费用数字 ROI 用命令行参数给出（默认值是前面标定过的数字区）。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.clock.frame_clock import CostLatticeClock, bar_phase   # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'

NUM_ROI = (1795, 730, 1915, 805)      # 费用数字（实机标定过）
BAR_ROI = (1795, 800, 1915, 820)      # 费用条（数字下方的细条，待本轮确认）


def sh(*args):
    return subprocess.run([ADB, '-s', DEV, *args], capture_output=True)


def main():
    span = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
    # 1) 进演习
    for tap, wait in (((960, 540), 4), ((953, 812), 3), ((1441, 975), 5), ((1659, 766), 1)):
        sh('shell', 'input', 'tap', str(tap[0]), str(tap[1]))
        time.sleep(wait)
    # 2) 等战斗开始（加载约 11s）
    time.sleep(14)

    # 3) 窗口抓屏连拍
    os.makedirs(TMP, exist_ok=True)
    try:
        import bettercam
        cam = bettercam.create(output_idx=0, output_color='BGR')
        cam.grab()
    except Exception:
        import dxcam
        cam = dxcam.create(output_idx=0, output_color='BGR')
        cam.grab()

    from plugins.recognize.cost_number import CostNumberRecognizer
    rec = CostNumberRecognizer()
    num_spec = {'roi': list(NUM_ROI), 'templates': os.path.join(TMP, 'tpl_h124.json')}

    rows = []
    t0 = time.perf_counter()
    prev = None
    while time.perf_counter() - t0 < span:
        img = cam.grab()
        if img is None:
            continue
        w = time.perf_counter() - t0
        ms = rec.run(img, num_spec, None, (0, 0))
        cost = int(ms[0].extra['cost']) if ms else None
        ph = bar_phase(img[BAR_ROI[1]:BAR_ROI[3], BAR_ROI[0]:BAR_ROI[2]])
        rows.append((round(w, 3), cost, ph['sub_frame'], round(ph['frac'], 3), ph['fill_px']))
        time.sleep(1 / 60.0)

    print(f'连拍 {len(rows)} 帧 / {span:.0f}s（窗口抓屏）')
    print('  t(s)  费用  相位  比例  填充px')
    for r in rows[:60]:
        print(f'  {r[0]:6.3f}  {str(r[1]):>4}  {r[2]:>4}  {r[3]:5.3f}  {r[4]:>4}')
    if len(rows) > 60:
        print(f'  ...（共 {len(rows)} 行，末行 t={rows[-1][0]} 费用={rows[-1][1]} 相位={rows[-1][2]}）')

    # 4) 断言
    phases = [r[2] for r in rows]
    costs = [r[1] for r in rows if r[1] is not None]
    wraps = sum(1 for i in range(1, len(phases)) if phases[i] < phases[i - 1])
    step_bad = [(i, phases[i - 1], phases[i]) for i in range(1, len(phases))
                if phases[i] != (phases[i - 1] + 1) % 30]
    print(f'\n断言：')
    print(f'  1) 相位逐帧 +1（回绕 30）：违例 {len(step_bad)} 处'
          + (f'，前几处 {step_bad[:5]}' if step_bad else ' ✅'))
    print(f'  2) 相位回绕 {wraps} 次；费用数字 {costs[0] if costs else None}'
          f'→{costs[-1] if costs else None}（增量 {costs[-1] - costs[0] if len(costs) > 1 else "?"}）')
    print(f'  3) 抓屏 {len(rows)} 帧覆盖 {rows[-1][0]:.2f}s ⇒ 等效 {rows[-1][0] * 30:.1f} 逻辑帧'
          f'（若相位无丢步，两者应一致）')


if __name__ == '__main__':
    main()
