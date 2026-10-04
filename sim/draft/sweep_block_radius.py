# -*- coding: utf-8 -*-
"""sweep_block_radius.py — ★按**知识库权威模型**扫描统一阻挡半径（0.7071 附近）。

## 依据（用户 2026-09-15「阻挡按玩家常识应当全部统一，与 b 站专栏学习结果相同」）
`knowledge/04/37_阻挡与阻挡偏移_代码核验.md`：
- `Consts.BLOCK_RADIUS = 0.7071`（= 0.5√2）、大号 0.8944；
- **判定：角色类单位的中点与敌人中点距离 ≤ 阻挡半径**；半径**只在角色类单位身上、敌人没有** ⇒ **统一**；
- 扫描节奏 `FIND_BLOCKEE_TICK = 3`（每 3 帧）。

## 本脚本
在 `block_rule='radius'` 下扫描半径（0.5 / 0.6 / 0.7071 / 0.8 / 1.0），
对每个值同时给出**阻挡帧**与**伤害偏差**（两个观测）。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score     # noqa: E402

CAL = [236, 443]
print(f'{"阻挡半径":>8} {"阻挡帧":>12} {"阻挡偏差":>10} {"伤害平均":>8} {"≤6帧":>5} {"最大":>5}')
for r in (0.5, 0.6, 0.65, 0.7071, 0.75, 0.8, 0.9, 1.0):
    b = run({'block_rule': 'radius', 'block_radius': r, 'block_snap': False})
    bl = [l.frame for l in b.logs if l.kind == 'block']
    a, h, m, _ = score(b)
    dv = (bl[0] - CAL[0], bl[1] - CAL[1]) if len(bl) >= 2 else None
    star = ' ★' if abs(dv[0]) <= 6 and abs(dv[1]) <= 6 and a <= 2.6 else ''
    print(f'{r:>8} {str(bl):>12} {str(dv):>10} {a:>8.2f} {h:>5} {m:>5}{star}')
print(f'\n标定阻挡帧 = {CAL}；目标：阻挡偏差 ≤6 且伤害平均 ≤2.6')
print('代码常量：BLOCK_RADIUS = 0.7071（√0.5×1=0.5√2）、BLOCK_RADIUS_LARGE = 0.8944')
