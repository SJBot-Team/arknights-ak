# -*- coding: utf-8 -*-
"""sweep_path_model.py — 在"惯性 + 格判定阻挡"基础上，比较**寻路模型**：
  `straight_path=True`（直线优先，当前默认） vs `False`（navmap 逐格导航）。

## 动机（本轮诊断）
- `collision_pair`（碰撞体积相触，0.25+0.1=0.35）对**第 1 只**给出阻挡帧 **240**（标定 236 ✓），
  但**第 2 只永不触发** —— 因为"格中心→格中心"的直线**最接近芬 0.5 格**，够不到 0.35。
- 而标定显示第 2 只**确实被阻挡（443）**且在阻挡前就能被芬打到（432）
  ⇒ **第 2 只的真实路径应当更靠近芬**（很可能经过芬所在格或相邻格）。
⇒ 本脚本同时报：阻挡帧误差（标定 236/443）与伤害帧误差。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score     # noqa: E402
from sweep_block_frames import CALIB_BLOCK  # noqa: E402

CASES = [
    ('直线优先（默认）', {'straight_path': True, 'block_cell_margin': 1.0}),
    ('直线优先', {'straight_path': True, 'block_cell_margin': 0.1}),
    ('直线优先+collision', {'straight_path': True, 'block_rule': 'collision_pair'}),
    ('navmap 逐格', {'straight_path': False, 'block_cell_margin': 1.0}),
    ('navmap 逐格', {'straight_path': False, 'block_cell_margin': 0.1}),
    ('navmap 逐格+collision', {'straight_path': False, 'block_rule': 'collision_pair'}),
    ('navmap 逐格+strict_wp', {'straight_path': False, 'strict_waypoints': True,
                               'block_cell_margin': 0.1}),
]

print(f'{"模型":>22} {"阻挡帧":>14} {"阻挡误差":>8} {"平均":>6} {"≤6帧":>5} {"最大":>5}')
for name, opts in CASES:
    b = run(opts)
    bl = [l.frame for l in b.logs if l.kind == 'block']
    err = 999.0 if len(bl) < 2 else sum(abs(bl[i] - CALIB_BLOCK[i]) for i in range(2)) / 2
    a, h, m, _d = score(b)
    print(f'{name:>22} {str(bl):>14} {err:>8.1f} {a:>6.2f} {h:>5} {m:>5}')
print(f'\n标定阻挡帧 = {CALIB_BLOCK}')
