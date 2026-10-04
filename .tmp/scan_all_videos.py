# -*- coding: utf-8 -*-
"""对 H12-4 全部候选录像跑费用轨迹，输出「速率 + 消耗事件」，用于判定哪个是令+蕾缪安前半段解"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\code\vision\apps')
sys.stdout.reconfigure(encoding='utf-8')
import cv2
from video_cost_timeline import (lock_roi, lock_digit_zone, frame_at, glyphs_in_roi,
                                 classify, load_templates)

TPL = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\tpl_h124.json'
VIDS = [
    r'E:\MUMU共享文件夹\VideoRecords\H12-4\双\明日方舟(128).mp4',
    r'E:\MUMU共享文件夹\VideoRecords\H12-4\双\明日方舟(132).mp4',
    r'E:\MUMU共享文件夹\VideoRecords\H12-4\双\明日方舟(134).mp4',
    r'E:\MUMU共享文件夹\VideoRecords\H12-4\双\明日方舟(519).mp4',
    r'E:\MUMU共享文件夹\VideoRecords\H12-4\双\2025-11-15 13-46-02.mkv',
]
T1, STEP = 90.0, 0.2
tpl = load_templates(TPL)
out = {}
for v in VIDS:
    if not os.path.exists(v):
        continue
    cap = cv2.VideoCapture(v)
    fps = cap.get(cv2.CAP_PROP_FPS)
    print(f'\n===== {os.path.basename(v)} =====')
    roi = lock_roi(cap, fps)[:4]
    if roi[2] <= roi[0]:
        print('  ROI 定位失败，跳过')
        cap.release()
        continue
    xmin = lock_digit_zone(cap, fps, roi)
    rows = []
    t = 0.0
    while t <= T1:
        fr = frame_at(cap, fps, t)
        if fr is None:
            break
        val, conf = classify(glyphs_in_roi(fr[roi[1]:roi[3], roi[0]:roi[2]], xmin), tpl)
        rows.append({'t': round(t, 3), 'cost': int(val) if val and val.isdigit() else None,
                     'conf': round(conf, 3)})
        t += STEP
    cap.release()
    ok = [r for r in rows if r['cost'] is not None]
    # 速率：仅用 dt>=1s 的上升对
    pos = [(b['cost'] - a['cost']) / (b['t'] - a['t'])
           for a, b in zip(ok, ok[1:])
           if b['t'] - a['t'] >= 1.0 and 0 < b['cost'] - a['cost'] <= 3 * (b['t'] - a['t'])]
    rate = float(np.median(pos)) if pos else float('nan')
    drops = [{'t': round(b['t'], 1), 'drop': a['cost'] - b['cost'], 'from': a['cost'], 'to': b['cost']}
             for a, b in zip(ok, ok[1:]) if b['cost'] < a['cost'] - 0.5]
    # 合并 0.5s 内的重复检测
    merged = []
    for d in drops:
        if merged and d['t'] - merged[-1]['t'] <= 0.6:
            continue
        merged.append(d)
    print(f'  样本 {len(rows)} 有效 {len(ok)}（{len(ok)/max(1,len(rows)):.0%}）  '
          f'回费速率中位 = {rate:.2f}/s  → {"2 倍速" if rate > 1.5 else "1 倍速"}')
    print(f'  消耗事件（前 25 个）：')
    for d in merged[:25]:
        print(f'    t={d["t"]:>6.1f}s  降 {d["drop"]:>3}  {d["from"]}→{d["to"]}')
    out[os.path.basename(v)] = {'roi': list(roi), 'digit_zone': xmin, 'rate': rate,
                                'drops': merged, 'valid_ratio': round(len(ok) / max(1, len(rows)), 3),
                                'samples': rows}

dst = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\video_cost_scan.json'
with open(dst, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f'\n汇总 → {dst}')
