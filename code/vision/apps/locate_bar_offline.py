# -*- coding: utf-8 -*-
"""locate_bar_offline.py — 对已录制的战斗帧做**离线**帧间差分，定位费用条 ROI

为什么离线：费用条只在"费用未达上限"时跳动。`enter_drill.py` 录下的那批帧覆盖了
费用 11→20 的上升段（条在动），直接拿它们做差分即可，**不必再进一次战斗**。
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
SEARCH = (1650, 700, 1920, 900)


def main():
    files = sorted(f for f in os.listdir(FRAMES) if f.endswith('.png'))
    print(f'已录制 {len(files)} 帧')
    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}
    imgs, costs = [], []
    for fn in files:
        img = cv2.imread(os.path.join(FRAMES, fn))
        if img is None:
            continue
        imgs.append(img)
        ms = rec.run(img, spec, None, (0, 0))
        costs.append((int(ms[0].extra['cost']), round(float(ms[0].extra['confidence']), 3)) if ms else (None, 0.0))
    print('逐帧费用读数：', costs)

    x0, y0, x1, y1 = SEARCH
    print('\n帧间差分行能量（>2.0 才列）：')
    acc = None
    for i in range(1, len(imgs)):
        ga = cv2.cvtColor(imgs[i - 1][y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype('float32')
        gb = cv2.cvtColor(imgs[i][y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype('float32')
        d = np.abs(ga - gb)
        acc = d if acc is None else acc + d
        row = d.mean(axis=1)
        ys = [(y0 + j, round(float(v), 2)) for j, v in enumerate(row) if v > 2.0]
        print(f'  {files[i-1]}→{files[i]}: '
              + (', '.join(f'y={a}({b})' for a, b in ys) if ys else '无变化'))
    if acc is None:
        print('只有一帧，无法差分'); return 1

    row = acc.mean(axis=1)
    ys = [j for j, v in enumerate(row) if v > 2.0]
    if not ys:
        print('\n整体无变化：说明这批帧里费用条已静止（费用顶上限）或画面未更新')
        return 1
    # 分带
    bands, s, prev = [], ys[0], ys[0]
    for y in ys[1:]:
        if y - prev > 2:
            bands.append((s, prev)); s = y
        prev = y
    bands.append((s, prev))
    print('\n候选条带：')
    best = None
    for (ya, yb) in bands:
        seg = acc[ya:yb + 1, :].mean(axis=0)
        frac = float((seg > seg.max() * 0.5).mean())
        tag = '← 长横条，像费用条' if frac > 0.5 else ''
        print(f'  y∈[{y0+ya},{y0+yb}] 高 {yb-ya+1}px  横向覆盖 {frac*100:5.1f}%  峰值 {seg.max():6.2f} {tag}')
        if frac > 0.5 and (best is None or (yb - ya) > (best[1] - best[0])):
            best = (ya, yb)
    if best:
        ya, yb = y0 + best[0], y0 + best[1]
        print(f'\n用候选 ROI ({x0},{ya},{x1},{yb}) 算条内相位：')
        for i, im in enumerate(imgs):
            ph = bar_phase(im[ya:yb + 1, x0:x1])
            print(f'   {files[i]}  费用={costs[i][0]}  相位={ph["sub_frame"]:>2}  '
                  f'比例={ph["frac"]:.3f}  填充={ph["fill_px"]:>3}px')
        print('\n判据：①相位随时间推进且回绕（费用 +1 ⇒ 回绕一次）；②填充宽度随相位数上升；'
              '③费用顶上限后相位应停住。')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
