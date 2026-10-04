# -*- coding: utf-8 -*-
"""cmp_target_models.py — ★对比两种索敌口径对**两条链**的还原（找能同时成立的口径）。

背景：用户 2026-09-15 明确"索敌 = 方格范围 + 受击判定体积"；
但引擎注释记载旧口径 `legacy_center_distance`（`range_distance_tol=1.5`）曾让 1-1 达 **16/16**，
且"帧 414 的欧氏距离恰为 1.50"。本轮把两种口径放在**同一次对比**里，看各自对两条链的还原：

- `猎狗pro` 标定命中：221 / 253 / 285 / 317（索敌 ≈ 200，正面沿行 3 进入范围格）
- `猎狗`   标定命中：432（索敌 ≈ 414，斜向逼近）
- 阻挡：236 / 443
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score        # noqa: E402

CASES = [
    ('grid_plus_hit_volume（现默认，用户指定语义）',
     {'targeting_model': 'grid_plus_hit_volume'}),
    ('legacy_center_distance tol=1.5',
     {'targeting_model': 'legacy_center_distance', 'range_distance_tol': 1.5}),
    ('legacy_center_distance tol=1.5811（= 2 格范围最远角距 √(1.5²+0.5²)）',
     {'targeting_model': 'legacy_center_distance', 'range_distance_tol': 1.5811}),
    ('grid_plus_hit_volume + 外扩 0.7071',
     {'targeting_model': 'grid_plus_hit_volume', 'acquire_uses_block_radius': True}),
]
for title, extra in CASES:
    b = run(dict(extra))
    pro = [l.frame for l in b.logs if l.kind == 'hit'
           and l.detail.get('src') == '芬' and l.detail.get('tgt') == '猎狗pro']
    gou = [l.frame for l in b.logs if l.kind == 'hit'
           and l.detail.get('src') == '芬' and l.detail.get('tgt') == '猎狗']
    blk = [l.frame for l in b.logs if l.kind == 'block']
    a, h, m, _ = score(b)
    print(f'--- {title}')
    print(f'    猎狗pro {pro}   标定 221/253/285/317')
    print(f'    猎狗    {gou}   标定 432')
    print(f'    阻挡    {blk}   标定 236/443    伤害平均 {a:.2f} 最大 {m}')
