# -*- coding: utf-8 -*-
"""card_order_by_cost.py — ★用**费用**确定卡片顺序（**不需要图像识别**），并用实机读数验证。

## 原理
1. 战斗卡片行**按费用升序**（本项目多次实测一致）；
2. 干员**部署费用可由数据算出** —— 直接复用模拟器的数据层
   （`get_operator(...)['attrs']['cost']`，即属性关键帧里的 cost），
   再减去**天赋/潜能的费用减免**（本编队内芬有「轻量化 −1」）。

⇒ **卡片序号 = 目标干员费用在"编队费用升序"中的位次**，可直接推出。

## 验证
`axisdep_D6.png`（此时**芬已部署**）的卡片费用目视读数为
    **9 9 9 13 14 15 15 16 16 17**
若"芬(8) 之外的 10 人"按数据算出的费用排序与之吻合 ⇒ 方法成立。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D      # noqa: E402

SQUAD = [('卡缇', 'char_209_ardign'), ('安赛尔', 'char_212_ansel'),
         ('芬', 'char_123_fang'), ('泡普卡', 'char_281_popka'),
         ('安德切尔', 'char_211_adnach'), ('月见夜', 'char_283_midn'),
         ('斑点', 'char_284_spot'), ('香草', 'char_240_wyvern'),
         ('玫兰莎', 'char_208_melan'), ('克洛丝', 'char_124_kroos'),
         ('史都华德', 'char_210_stward')]
OBSERVED_10 = [9, 9, 9, 13, 14, 15, 15, 16, 16, 17]     # 芬(8) 已部署后的卡片
TALENT_COST = {'芬': 1}                                   # 「轻量化」−1

rows = []
for nm, cid in SQUAD:
    try:
        op = D.get_operator(cid, elite=1, level=55, potential=6, trust=200)
        base = int(round(float(op['attrs']['cost'])))
    except Exception as ex:                                # noqa: BLE001
        print(f'  {nm}: 取数失败 {ex!r}')
        continue
    eff = base - TALENT_COST.get(nm, 0)
    rows.append((eff, base, nm, cid))

print(f'{"干员":<6} {"数据cost":>8} {"天赋减免":>8} {"实机费用":>8}  char_id')
for eff, base, nm, cid in sorted(rows):
    print(f'{nm:<6} {base:>8} {TALENT_COST.get(nm, 0):>8} {eff:>8}  {cid}')

sorted_costs = [eff for eff, _, _, _ in sorted(rows)]
print('\n按数据算出的费用升序:', sorted_costs)
print('实机卡片费用（芬已部署）:', OBSERVED_10)
rest = [c for c in sorted_costs if c != 8]
print('去掉芬(8) 后:', rest)
print('✅ 与实机一致' if rest == OBSERVED_10 else '⚠️ 与实机不一致，需核对')
