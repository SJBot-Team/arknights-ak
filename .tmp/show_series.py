# -*- coding: utf-8 -*-
"""打印某录像前 N 秒的费用序列（每 0.5s 一个点），并估计回费速率"""
import json
import sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\video_cost_scan.json'
d = json.load(open(P, encoding='utf-8'))
key = sys.argv[1] if len(sys.argv) > 1 else '明日方舟(128).mp4'
T = float(sys.argv[2]) if len(sys.argv) > 2 else 40.0
rows = d[key]['samples']
sel = [r for r in rows if r['t'] <= T]
print(f'{key} 前 {T:.0f}s（每点 0.2s，仅显示 0.5s 整数倍）：')
line = []
for r in sel:
    if abs(r['t'] * 2 - round(r['t'] * 2)) < 1e-6:
        line.append(f'{r["t"]:.1f}:{r["cost"] if r["cost"] is not None else "-"}')
print('  ' + '  '.join(line))
ok = [r for r in rows if r['cost'] is not None]
pairs = [(a, b) for a, b in zip(ok, ok[1:]) if 0.9 <= b['t'] - a['t'] <= 1.3]
pos = [(b['cost'] - a['cost']) / (b['t'] - a['t']) for a, b in pairs if b['cost'] - a['cost'] > 0]
print(f'\n约 1s 间隔样本对 {len(pairs)} 个，其中上升 {len(pos)} 个；上升速率中位 = '
      f'{(np.median(pos) if pos else float("nan")):.3f}/s')
hist = {}
for a, b in pairs:
    hist[b['cost'] - a['cost']] = hist.get(b['cost'] - a['cost'], 0) + 1
print('1s 内费用变化分布:', dict(sorted(hist.items())))
