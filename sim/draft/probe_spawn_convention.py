# -*- coding: utf-8 -*-
"""probe_spawn_convention.py — ★检验"出生点坐标约定"（格中心 vs 路线起点的字面坐标）。

## 假设（D14 诊断中手算得到）
1-1 第 2 只（route4 起点 row6/col4）：
- 约定 A「格中心」= (4.5, 6.5)；
- 约定 B「字面坐标」= (4.0, 6.0) —— 相差 0.5 格 ⇒ 到达各节点的时刻整体提前约 16 帧。
手算：约定 B 下「进入芬所在格 (3,5)」≈ 帧 **443**，与标定「443 芬 阻挡 猎狗」**逐帧吻合**；
      约定 A 给出 459（晚 16 帧）。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score     # noqa: E402

CASES = [
    ('A 格中心 + margin1.0 + 吸附（默认）', {'spawn_at_route_point': False}),
    ('B 字面点 + margin1.0 + 吸附', {'spawn_at_route_point': True}),
    ('B 字面点 + margin0.0 + 无吸附', {'spawn_at_route_point': True,
                                       'block_cell_margin': 0.0, 'block_snap': False}),
    ('A 格中心 + margin0.0 + 无吸附', {'spawn_at_route_point': False,
                                       'block_cell_margin': 0.0, 'block_snap': False}),
]

print(f'{"配置":>30} {"阻挡帧":>14} {"平均":>6} {"≤6帧":>5} {"最大":>5}  芬命中猎狗')
for name, o in CASES:
    b = run(o)
    bl = [l.frame for l in b.logs if l.kind == 'block']
    a, h, m, _d = score(b)
    fh = [l.frame for l in b.logs if l.kind == 'hit' and l.detail['src'] == '芬'
          and l.detail['tgt'] == '猎狗']
    print(f'{name:>30} {str(bl):>14} {a:>6.2f} {h:>5} {m:>5}  {fh}')
print('标定：阻挡 [236, 443]；芬命中猎狗 432 / 击杀 464')
