# -*- coding: utf-8 -*-
"""scan_video_events.py — 逐帧扫描录像，产出"事件精确帧"（费用/相位/上限锚点/速度倍率）

## 为什么用录像
用户 2026-09-14 提示：录像的帧号是**精确**的，适合把"事件发生在哪一帧"与模拟器结果比对，
且完全不受实机采集延迟与遮挡影响。视频 fps≈29.99 ⇒ 视频帧号 ≈ 游戏逻辑帧号。

## 做法
1. 把 1600×900 的帧**缩放到 1920×1080**，从而**复用既有的全部 ROI 与字形模板**（免去重标定）；
2. 逐帧读取：
   - **费用数字**（`CostNumberRecognizer`，带置信度阈值）
   - **费用条相位**（官方 pixel_map 查表 → 精确帧）
   - **「COST N」浮动提示**（上限突破/返还的视觉表现，§7.140）——用顶部 ROI 的亮色像素突增检测
   - **速度倍率**（1X/2X，右上角图标区域的平均色/亮度变化）
3. 输出：费用/相位序列、锚点候选帧、倍率切换帧，供与模拟器逐帧比对。

用法：
    python apps/scan_video_events.py "<视频路径>" [起始帧] [结束帧] [步长]
"""
from __future__ import annotations

import json
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.clock.frame_clock import PIXEL_MAP_30F, bar_phase, frame_from_width  # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer                     # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TPL = os.path.join(TMP, 'tpl_h124.json')
NUM_ROI = (1795, 730, 1915, 805)          # 1920×1080 基准
BAR_ROI = (1739, 805, 1919, 818)
MIN_CONF = 0.85
# 「COST N」浮动提示：从抽帧看位于顶部中央偏右（1600×900 下约 x 560~720、y 55~85）
# 换算到 1920×1080：x 672~864、y 66~102
COST_HINT_ROI = (660, 55, 900, 115)
HINT_THRESH = 0.02                        # 该 ROI 内高亮像素占比阈值


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    f0 = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    f1 = int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9
    step = int(sys.argv[4]) if len(sys.argv) > 4 else 1

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print('打不开视频:', path); return 2
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f'视频 {os.path.basename(path)}：{total} 帧 @ {fps:.3f}fps；扫描 {f0}~{min(f1, total)} 步长 {step}')

    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}
    cap.set(cv2.CAP_PROP_POS_FRAMES, f0)

    rows = []          # (frame, cost, conf, sub_frame, fill_px, hint, hint_ratio)
    hints = []         # 「COST N」候选帧
    t0 = time.perf_counter()
    fr = f0
    while fr < min(f1, total):
        ok, img = cap.read()
        if not ok:
            break
        if step > 1 and (fr - f0) % step:
            fr += 1
            continue
        if img.shape[1] != 1920 or img.shape[0] != 1080:
            img = cv2.resize(img, (1920, 1080), interpolation=cv2.INTER_LINEAR)
        ms = rec.run(img, spec, None, (0, 0))
        cost = None; conf = 0.0
        if ms:
            conf = float(ms[0].extra.get('confidence', 0.0))
            if conf >= MIN_CONF:
                cost = int(ms[0].extra['cost'])
        p = bar_phase(img[BAR_ROI[1]:BAR_ROI[3], BAR_ROI[0]:BAR_ROI[2]],
                      full_px=BAR_ROI[2] - BAR_ROI[0])
        sub = frame_from_width(p['fill_px'], PIXEL_MAP_30F)
        g = cv2.cvtColor(img[COST_HINT_ROI[1]:COST_HINT_ROI[3],
                             COST_HINT_ROI[0]:COST_HINT_ROI[2]], cv2.COLOR_BGR2GRAY)
        hint_ratio = float((g > 190).mean())
        hint = hint_ratio > HINT_THRESH
        if hint:
            hints.append(fr)
        rows.append((fr, cost, round(conf, 3), sub, p['fill_px'], bool(hint), round(hint_ratio, 4)))
        fr += 1
        if len(rows) % 2000 == 0:
            print(f'   …已扫描 {len(rows)} 帧（当前帧 {fr}，用时 {time.perf_counter()-t0:.0f}s）')
    cap.release()

    print(f'\n扫描完成：{len(rows)} 帧，用时 {time.perf_counter()-t0:.0f}s')
    costs = [r[1] for r in rows if r[1] is not None]
    print(f'  读到费用数字 {len(costs)}/{len(rows)} 帧，范围 {min(costs) if costs else None}~{max(costs) if costs else None}')
    # 费用发生变化（+1）的帧
    chg = []
    prev = None
    for r in rows:
        if r[1] is not None:
            if prev is not None and r[1] != prev:
                chg.append((r[0], prev, r[1]))
            prev = r[1]
    print(f'  费用变化的帧 {len(chg)} 次，前 10 次：{chg[:10]}')
    # 「COST N」候选（合并相邻帧）
    groups = []
    for f in hints:
        if groups and f - groups[-1][-1] <= 3:
            groups[-1].append(f)
        else:
            groups.append([f])
    print(f'\n★「COST N」提示候选 {len(groups)} 组：')
    for g in groups[:20]:
        print(f'   帧 {g[0]}~{g[-1]}（共 {len(g)} 帧，约 {(g[0])/fps:.2f}s 起）')

    out = os.path.join(TMP, 'video_scan_' + os.path.splitext(os.path.basename(path))[0] + '.json')
    json.dump({'file': path, 'fps': fps, 'rows': rows,
               'hint_groups': groups, 'cost_changes': chg},
              open(out, 'w', encoding='utf-8'))
    print(f'\n明细已存：{out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
