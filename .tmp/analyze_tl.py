# -*- coding: utf-8 -*-
"""按「只取正向增量」的方式估计回费速率（避免窗口内消耗污染），并列出消耗事件"""
import json
import sys

import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
P = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\23922\Documents\ds_harness\ak\.tmp\tl_v04_0_120.json'
d = json.load(open(P, encoding='utf-8'))
rows = d['samples']
ok = [r for r in rows if r['cost'] is not None]

print(f'{d["video"]}  roi={d["roi"]}  样本 {len(rows)}（有效 {len(ok)}，'
      f'有效率 {len(ok)/max(1,len(rows)):.0%}）')
print('\n=== 回费速率（每 5s，仅统计正向增量的中位数）===')
t_end = ok[-1]['t']
for start in np.arange(0, t_end, 5.0):
    seg = [(a, b) for a, b in zip(ok, ok[1:]) if start <= a['t'] < start + 5.0]
    pos = [(b['cost'] - a['cost']) / (b['t'] - a['t']) for a, b in seg
           if b['t'] > a['t'] and b['cost'] > a['cost'] and (b['cost'] - a['cost']) <= 4]
    drops = [(a['t'], a['cost'], b['cost']) for a, b in seg if b['cost'] < a['cost'] - 0.5]
    rate = float(np.median(pos)) if pos else float('nan')
    tag = '2×?' if 1.6 < rate < 2.4 else ('1×?' if 0.75 < rate < 1.25 else '')
    print(f'  t={start:>6.0f}-{start+5:<4.0f}s  速率中位={rate:>5.2f}/s {tag:<4} '
          f'窗口内下降点={[(round(t,1), c0, c1) for t, c0, c1 in drops]}')
