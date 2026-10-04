# -*- coding: utf-8 -*-
"""probe_enemy_range.py — 查敌人的**攻击范围表示**（近战 / 远程圆半径 / 攻击方式）。

用户 2026-09-15 指出：
- **近战干员（如芬）索敌** = **2 个方格**；无阻挡时，**敌人的 0.1 圆进入该范围** ⇒ 干员索敌并起前摇；
- **远程敌人**的攻击范围通常是**一个确定半径的圆**；**干员的 0.25 圆**处于该圆内 ⇒ 敌人开始攻击。

本脚本核对数据层字段：`rangeRadius`（敌人攻击范围半径）、`applyWay`、`motion`、`attack@` 等。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D          # noqa: E402

KEYS = sys.argv[1:] or ['enemy_1000_gopro', 'enemy_1000_gopro_2', 'enemy_1007_slime_2',
                        'enemy_1027_mob', 'enemy_1028_mocock', 'enemy_1030_wteeth',
                        'enemy_1105_tyokai', 'enemy_1007_slime']

print(f'{"敌人 key":<26} {"rangeRadius":>12} {"applyWay":>12} {"motion":>10} '
      f'{"atk":>5} {"bat":>6}')
for k in KEYS:
    try:
        d = D.get_enemy(k, 0)
    except KeyError:
        print(f'{k:<26} （库中无）')
        continue
    a = d.get('attrs') or d.get('attributes') or {}
    rr = d.get('rangeRadius', a.get('rangeRadius'))
    print(f'{k:<26} {str(rr):>12} {str(d.get("applyWay")):>12} {str(d.get("motion")):>10} '
          f'{str(a.get("atk") or a.get("atk")):>5} {str(a.get("baseAttackTime")):>6}')

print('\n（`rangeRadius = 0/None` ⇒ 近战；`> 0` ⇒ 远程，攻击范围 = 以自身为心、该半径的**圆**）')
