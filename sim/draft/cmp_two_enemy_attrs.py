# -*- coding: utf-8 -*-
"""cmp_two_enemy_attrs.py — ★对比 1-1 两种敌人的**全部属性**（找索敌差异的根因）。

关键线索：标定表显示 `猎狗` 在帧 **418** 就命中了芬（标注者漏标），
说明它在 1.37 格外就能打到芬 ⇒ 其 `rangeRadius` 可能非 0；
而 `猎狗pro` 是纯近战 ⇒ `rangeRadius ≈ 0`。
若两者 `rangeRadius` 确有此差异，则可解释"两敌要求相反的索敌修正"。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D          # noqa: E402

for k in ('enemy_1000_gopro', 'enemy_1000_gopro_2', 'enemy_1000_gopro_3'):
    try:
        e = D.get_enemy(k, level=0)
    except Exception as ex:                                   # noqa: BLE001
        print(f'{k}: 取数失败 {ex!r}')
        continue
    print(f"=== {k}  ({e['name']}) ===")
    for f in ('moveSpeed', 'rangeRadius', 'applyWay', 'motion', 'atk', 'maxHp',
              'def', 'magicResistance', 'blockCnt', 'weight', 'baseAttackTime',
              'attackSpeed', 'lifePointReduce'):
        print(f'    {f:<16} = {e.get(f)}')
