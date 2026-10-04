# -*- coding: utf-8 -*-
"""sweep_block_cell_margin.py — 在"格 3×3"阻挡规则下扫描边界余量。

目的：找出**既语义干净（格判定）又精度最好**的阻挡规则。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score     # noqa: E402

print(f'{"规则":>18} {"余量":>6} {"平均":>6} {"≤6帧":>5} {"最大":>5}  block 帧')
for mg in (1.0, 1.1, 1.2, 1.3, 1.414, 1.5):
    opts = {'block_rule': 'cell_3x3_round', 'block_cell_margin': mg}
    b = run(opts)
    a, h, m, _d = score(b)
    blk = [l.frame for l in b.logs if l.kind == 'block']
    print(f'{"cell_3x3_round":>18} {mg:>6.3f} {a:>6.2f} {h:>5} {m:>5}  {blk}')
for cd in (1.4, 1.45, 1.5, 1.55, 1.6):
    opts = {'block_capture_distance': cd}
    b = run(opts)
    a, h, m, _d = score(b)
    blk = [l.frame for l in b.logs if l.kind == 'block']
    print(f'{"capture_distance":>18} {cd:>6.2f} {a:>6.2f} {h:>5} {m:>5}  {blk}')
