# -*- coding: utf-8 -*-
"""analyze_block_offset.py — 检查"模拟器阻挡帧 vs 标定阻挡帧"的偏差是否**恒定**。

## 为什么关键
若偏差随路径/敌人而变 ⇒ 是**物理/规则**问题（阻挡判据或寻路）；
若偏差对两个敌人**恒定** ⇒ 更像**标注语义差**（标定的「动画层=芬 阻挡」记录的是动画层切换，
未必是物理上"被挡下"的那一帧），或"判定整晚/早一个步长"。

标定：236（猎狗pro）、443（猎狗）。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run     # noqa: E402

CALIB = [236, 443]
CASES = [
    ('默认（margin1.0+吸附）', {}),
    ('margin0.0+无吸附', {'block_cell_margin': 0.0, 'block_snap': False}),
    ('margin0.1', {'block_cell_margin': 0.1}),
    ('capture1.0', {'block_rule': 'capture_distance', 'block_capture_distance': 1.0}),
    ('capture0.5', {'block_rule': 'capture_distance', 'block_capture_distance': 0.5}),
    ('navmap', {'straight_path': False}),
]

print(f'{"配置":>22} {"阻挡帧":>14} {"偏差":>16} {"偏差是否恒定":>12}')
for name, o in CASES:
    b = run(o)
    bl = [l.frame for l in b.logs if l.kind == 'block']
    if len(bl) < 2:
        print(f'{name:>22} {str(bl):>14} {"（不足两次）":>16}')
        continue
    d = [bl[i] - CALIB[i] for i in range(2)]
    print(f'{name:>22} {str(bl):>14} {str(d):>16} {"★恒定" if abs(d[0] - d[1]) <= 3 else "随敌人变":>12}')
print('\n读法：偏差**恒定** ⇒ 更像"标注语义差"或"整体早/晚一个步长"；')
print('      偏差**随敌人变** ⇒ 阻挡判据或寻路存在真实差异。')
