# -*- coding: utf-8 -*-
"""sweep_tol_circum.py — ★稳健性检验：扫描索敌半径 tol，看"由范围表导出的 1.5811"是否落在数据最优区。

## 为什么重要
第115轮给出 `range_circumradius`（R = √(1.5²+0.5²) = **1.5811**，由 2 格范围的**最远角**导出）。
若 1.5811 只是"凑巧能过"，则附近的 tol 应同样甚至更好、或曲线平坦无特征。
本脚本扫描 tol ∈ [1.0, 2.2]，对每个值给出**两条链的偏差**与**整体伤害统计**，
用来看 1.5811 是否处于**数据自身的极值/拐点**（若是 ⇒ 该值有物理意义）。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score        # noqa: E402

CAL_PRO = [221, 253, 285, 317]
print(f'{"tol":>6} {"猎狗pro首4":>22} {"pro偏差":>14} {"猎狗首击":>8} {"猎狗偏差":>8} '
      f'{"伤害平均":>8} {"最大":>5}')
for tol in (1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.5811, 1.62, 1.7, 1.8, 2.0, 2.2):
    b = run({'targeting_model': 'legacy_center_distance', 'range_distance_tol': tol})
    pro = [l.frame for l in b.logs if l.kind == 'hit'
           and l.detail.get('src') == '芬' and l.detail.get('tgt') == '猎狗pro'][:4]
    gou = [l.frame for l in b.logs if l.kind == 'hit'
           and l.detail.get('src') == '芬' and l.detail.get('tgt') == '猎狗']
    dv = [p - c for p, c in zip(pro, CAL_PRO)] if len(pro) == 4 else None
    a, h, m, _ = score(b)
    star = ' ★导出值' if abs(tol - 1.5811) < 1e-9 else ''
    print(f'{tol:>6} {str(pro):>22} {str(dv):>14} {str(gou[:1]):>8} '
          f'{str([g - 432 for g in gou[:1]]):>8} {a:>8.2f} {m:>5}{star}')
print(f'\n标定：猎狗pro {CAL_PRO}；猎狗首击 432')
