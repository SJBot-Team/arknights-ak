# -*- coding: utf-8 -*-
"""probe_block_combo.py — 组合测试：寻路模型 × 阻挡规则 × 吸附，对两个观测同时打分。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score     # noqa: E402

CASES = [
    ('navmap+collision+吸附', {'straight_path': False, 'block_rule': 'collision_pair'}),
    ('navmap+collision+无吸附', {'straight_path': False, 'block_rule': 'collision_pair',
                                 'block_snap': False}),
    ('直线+collision+无吸附', {'straight_path': True, 'block_rule': 'collision_pair',
                               'block_snap': False}),
    ('navmap+m0.1+无吸附', {'straight_path': False, 'block_cell_margin': 0.1,
                            'block_snap': False}),
    ('navmap+cap1.0+无吸附', {'straight_path': False, 'block_rule': 'capture_distance',
                              'block_capture_distance': 1.0, 'block_snap': False}),
    ('navmap+m1.0+无吸附', {'straight_path': False, 'block_cell_margin': 1.0,
                            'block_snap': False}),
    ('直线+m1.0+无吸附', {'straight_path': True, 'block_cell_margin': 1.0,
                          'block_snap': False}),
]

print(f'{"配置":>26} {"阻挡帧":>16} {"平均":>6} {"<=6帧":>5} {"最大":>5}')
for name, o in CASES:
    b = run(o)
    bl = [l.frame for l in b.logs if l.kind == 'block']
    a, h, m, _d = score(b)
    print(f'{name:>26} {str(bl):>16} {a:>6.2f} {h:>5} {m:>5}')
print('标定阻挡 = [236, 443]；标定命中 432/464')
