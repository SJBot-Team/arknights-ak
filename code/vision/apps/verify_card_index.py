# -*- coding: utf-8 -*-
"""verify_card_index.py — 离线验证"结构性选卡"与实机卡片行一致。

真值：`axisdep_D6.png`（1-1 演习，**芬已部署**）的卡片费用目视读数
      9 9 9 13 14 15 15 16 16 17
预期：`card_plan.json` 的 `order` 去掉已部署者后，其位次上的费用应与卡片费用逐项一致；
      且 `月见夜` 的位次应指向 **14 费**那张卡。
"""
from __future__ import annotations

import json
import os
import sys

import cv2

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer                     # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
PLAN = r'C:\Users\23922\Documents\ds_harness\ak\data\derived\card_plan.json'
OBSERVED = [9, 9, 9, 13, 14, 15, 15, 16, 16, 17]

plan = json.load(open(PLAN, encoding='utf-8'))
img = cv2.imread(os.path.join(TMP, 'axisdep_D6.png'))
cards = sorted(Deployer(None).find_cards(img=img) or [], key=lambda k: k['cx'])

print('卡段 x        :', [c['cx'] for c in cards])
print('实机目视费用  :', OBSERVED)
print('计划 order    :', plan['order'])
print('计划 costs    :', plan['costs_sorted'])

deployed = {'芬'}                       # 该截图里芬已部署
rest = [nm for nm in plan['order'] if nm not in deployed]
rest_costs = [plan['squad'][nm] for nm in rest]
print(f'\n去掉已部署 {deployed} 后的剩余顺序: {rest}')
print(f'对应费用: {rest_costs}')
ok = rest_costs == OBSERVED
print(('✅ 与实机卡片费用逐项一致' if ok else '⚠️ 不一致'))

for want in ('月见夜', '香草', '泡普卡'):
    if want in rest:
        i = rest.index(want)
        cx = cards[i]['cx'] if i < len(cards) else None
        print(f'  {want}: 位次 {i} → 卡片 x={cx}（该位次费用 {rest_costs[i]}）')
