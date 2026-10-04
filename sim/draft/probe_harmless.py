# -*- coding: utf-8 -*-
"""probe_harmless.py — 查 h12-4 里带 `isUnharmfulAndAlwaysCountAsKilled` 的出怪条目是谁，
以及它们在模拟里是否真的出现了（用于核对"无害目标"实现）。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle     # noqa: E402

LV = 'obt/hard/level_hard_12-04'
b = Battle(LV, seed=0, record=True, record_every=1, max_frames=30 * 260)
tagged = [(a['t'], a.get('key'), a.get('route'), a.get('wave'), a.get('frag'))
          for a in b.schedule if a.get('harmless_counted')]
print(f'带无害标记的出怪条目 {len(tagged)} 条：')
for t, k, r, w, f in tagged[:20]:
    print(f'   t={t if t is None else round(t, 1)}s key={k} route={r} wave{w} frag{f}')

for _ in range(30 * 260):
    b.tick()

keys = {k for _t, k, _r, _w, _f in tagged}
spawned = [l for l in b.logs if l.kind == 'spawn' and l.detail.get('key') in keys]
print(f'\n这些 key 的 spawn 次数：{len(spawned)}')
esc_h = [l for l in b.logs if l.kind == 'escape_harmless']
esc_n = [l for l in b.logs if l.kind == 'escape']
print(f'escape_harmless {len(esc_h)}；escape {len(esc_n)}')
if spawned:
    print('样例 spawn:', spawned[0].detail, 'frame', spawned[0].frame)
    u = b.units.get(1)
    # 找存活/已逃的同 key 单位
    same = [x for x in b.units.values() if x.key in keys]
    print(f'同 key 单位 {len(same)} 个；示例 extra = {same[0].extra if same else None}')
