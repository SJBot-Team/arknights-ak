# -*- coding: utf-8 -*-
"""verify_card_grid.py — 验证"均匀网格补全"能否把漏检的卡片位次还原正确。

实测：`axisdep_D6.png` 的卡片行**实为 10 张**、目视费用 9 9 9 13 14 15 15 16 16 17，
但 `find_cards` 只检出 7 段 ⇒ 直接取"第 idx 段"会错位。
本脚本用 `fit_card_grid(检测x, n=10)` 还原 10 个中心，并检查 **月见夜(14 费) 位次 4**
是否落在"14 费那张卡"的真实位置附近（目视：10 张卡中第 5 张 ≈ x 945）。
"""
from __future__ import annotations

import json
import os
import sys

import cv2

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
APPS = os.path.join(VISION, 'apps')
sys.path.insert(0, VISION)
sys.path.insert(0, APPS)
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer                     # noqa: E402
from axis_deploy_live import fit_card_grid, card_index_for     # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
plan = json.load(open(r'C:\Users\23922\Documents\ds_harness\ak\data\derived\card_plan.json',
                      encoding='utf-8'))
img = cv2.imread(os.path.join(TMP, 'axisdep_D6.png'))
det = sorted(c['cx'] for c in (Deployer(None).find_cards(img=img) or []))
print('检测到的卡段 x:', det, f'（{len(det)} 段，实际应有 10 张）')

centers = fit_card_grid(det, 10)
print('网格补全后的 10 个中心:', centers)
print('相邻间距:', [centers[i + 1] - centers[i] for i in range(len(centers) - 1)])

deployed = {'芬'}
rest = [nm for nm in plan['order'] if nm not in deployed]
rest_costs = [plan['squad'][nm] for nm in rest]
print('\n剩余顺序:', rest)
print('对应费用:', rest_costs)
i = card_index_for(plan, '月见夜', deployed)
print(f'\n月见夜 位次 = {i} ⇒ 网格 x = {centers[i]}（该位次费用 {rest_costs[i]}）')
print('参照：实机 10 张卡的 14 费卡位于第 5 张；目视其中心 ≈ x 940~960')
print('✅ 合理' if 880 <= centers[i] <= 1010 else '⚠️ 偏离较大，需再校准网格参数')
