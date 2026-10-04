# -*- coding: utf-8 -*-
"""test_block_offset.py — 验证**阻挡偏移**（文档化算法）并对比旧"吸附"模式。

对照：`block_offset_mode='code'`（默认，`CalculateBlockOffset`）
      vs `'cell_center'` + `block_snap`（旧自造"吸附到相邻格中心"）
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score       # noqa: E402

CASES = [
    ('code（文档化阻挡偏移）', {'block_offset_mode': 'code'}),
    ('cell_center + snap', {'block_offset_mode': 'cell_center', 'block_snap': True}),
    ('cell_center 不吸附', {'block_offset_mode': 'cell_center', 'block_snap': False}),
]
for title, extra in CASES:
    opts = {'block_rule': 'radius', 'block_radius': 0.7071}
    opts.update(extra)
    b = run(opts)
    bl = [l.frame for l in b.logs if l.kind == 'block']
    off = [(l.frame, l.detail['dist']) for l in b.logs if l.kind == 'block_offset']
    a, h, m, _ = score(b)
    print(f'--- {title} ---')
    print(f'    阻挡帧 {bl}  偏差 ({bl[0]-236},{bl[1]-443})')
    print(f'    阻挡偏移事件 {off}')
    print(f'    伤害 平均 {a:.2f}  ≤6帧 {h}  最大 {m}')
