# -*- coding: utf-8 -*-
"""verify_bar_phase.py — 用实测定位的费用条 ROI 验证「相位 ↔ 费用数字」一致性（方法一在线验证）

实测定位（§7.68）：费用条在 **y∈[805,817]**（峰值 810–816），是 9 帧两两差分里唯一稳定出现的强变化带
（diff 39~81，其余行 <35）；费用读数在同期为 11→13→14→15→17→18→20，置信度 0.94~0.97。

本脚本对那批帧：
  1. 用 y∈[805,817] 测「每帧填充比例 → 相位」，并找费用条的横向起止（x 范围）；
  2. 检查 相位 与 费用数字 的一致性：相邻帧费用差 Δcost ⇒ 相位应推进 ~Δcost×30 帧（mod 30）；
  3. 费用顶上限（20）后相位应**停住**（用户方法一的前提：条不动了就要"故意消耗"）。
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.clock.frame_clock import bar_phase                          # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer           # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
FRAMES = os.path.join(TMP, 'battle_frames')
TPL = os.path.join(TMP, 'tpl_h124.json')
NUM_ROI = (1795, 730, 1915, 805)
BAR_Y = (805, 818)
BAR_X = (1700, 1920)          # 费用条的横向搜索范围（数字区左侧到屏右）


def main():
    files = sorted(f for f in os.listdir(FRAMES) if f.endswith('.png'))
    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}
    rows = []
    for fn in files:
        img = cv2.imread(os.path.join(FRAMES, fn))
        if img is None:
            continue
        ms = rec.run(img, spec, None, (0, 0))
        cost = int(ms[0].extra['cost']) if ms else None
        band = img[BAR_Y[0]:BAR_Y[1], BAR_X[0]:BAR_X[1]]
        ph = bar_phase(band)
        # 横向起止：亮度 > 60% 峰值的列范围
        g = band[..., :3].mean(axis=2)
        colmax = g.max(axis=0)
        peak = colmax.max() if colmax.size else 0
        cols = np.where(colmax >= peak * 0.6)[0] if peak > 0 else np.array([])
        xs = (int(cols.min()) + BAR_X[0], int(cols.max()) + BAR_X[0]) if cols.size else None
        rows.append((fn, cost, ph['sub_frame'], round(ph['frac'], 3), ph['fill_px'], xs))

    print('帧            费用  相位  比例  填充px  亮列范围(绝对x)')
    for fn, cost, sub, frac, fill, xs in rows:
        print(f'  {fn}  {str(cost):>4}  {sub:>4}  {frac:5.3f}  {fill:>4}   {xs}')
    print('\n一致性检查（相邻帧）：')
    for i in range(1, len(rows)):
        _, c0, s0, _, _, _ = rows[i - 1]
        _, c1, s1, _, _, _ = rows[i]
        if c0 is None or c1 is None:
            continue
        dc = c1 - c0
        adv = (s1 - s0) % 30
        exp = (dc * 30) % 30
        ok = '✓' if (c1 == c0 and adv == 0) or (c1 > c0 and abs(adv - exp) <= 3) else \
             ('（费用未变，相位应停住）' if c1 == c0 else '✗')
        print(f'  {rows[i-1][0]}→{rows[i][0]}: 费用 {c0}→{c1}(Δ{dc})  相位 {s0}→{s1}(推进 {adv})  '
              f'期望 {exp}  {ok}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
