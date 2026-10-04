# -*- coding: utf-8 -*-
"""probe_acquire_gou.py — ★精确测量：猎狗**进入芬范围**的帧与位置，对比标定反推。

标定：`432 芬 命中 猎狗`、`464 猎狗 被击杀`、`443 芬 阻挡 猎狗`。
芬攻击间隔 32 帧（由她对猎狗pro 的命中 221/253/285/317 得出）⇒ 若 432 是序列中的一次，
则其上一次次命中应在 400。
本脚本逐帧打印：猎狗位置、是否在芬的范围格内（含 0.1 受击体积）、芬的索敌/命中帧。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run          # noqa: E402

b = run({})
# 收集猎狗的逐帧位置
track = {}
for fr in b.frames:
    for u in (fr.get('units') or []):
        if u.get('name') == '猎狗' and u.get('side') == 'ENEMY':
            track[fr['f']] = (u['x'], u['y'])
print(f'猎狗轨迹帧数 {len(track)}；帧范围 {min(track)}~{max(track)}')

# 芬的索敌/命中事件
sel = [(l.frame, l.detail) for l in b.logs
       if l.kind == 'target_select' and l.detail.get('side') != 'ENEMY']
hit = [(l.frame, l.detail) for l in b.logs
       if l.kind == 'hit' and l.detail.get('attacker') == '芬'
       and l.detail.get('target') == '猎狗']
blk = [l.frame for l in b.logs if l.kind == 'block' and l.detail.get('enemy') == '猎狗']
print(f'芬→猎狗 命中帧: {[f for f, _ in hit]}')
print(f'芬 阻挡 猎狗 帧: {blk}')
print(f'芬的索敌事件（对猎狗）: {[f for f, d in sel if d.get("target") == "猎狗"]}')

print(f'\n{"帧":>5} {"x":>8} {"y":>8}  在芬范围格(3,5)/(3,4)内?')
for f in range(400, 470):
    if f not in track:
        continue
    x, y = track[f]
    in_a = (5.0 <= x <= 6.0) and (3.0 <= y <= 4.0)     # cell (3,5)
    in_b = (4.0 <= x <= 5.0) and (3.0 <= y <= 4.0)     # cell (3,4)
    mark = '★ACT' if f in [g for g, _ in hit] else ''
    if f % 2 == 0 or in_a or in_b:
        print(f'{f:>5} {x:>8.3f} {y:>8.3f}  (3,5)={in_a} (3,4)={in_b} {mark}')
