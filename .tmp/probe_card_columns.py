# -*- coding: utf-8 -*-
"""probe_card_columns.py — 验证"自动检测卡片列"在各种卡数下是否正确。

对已存实机截图跑 `detect_card_columns`，与目视卡数/费用序列对照：
- `axisdep_D6.png`（10 张，费用 9,9,9,13,14,15,15,16,16,17）
"""
from __future__ import annotations

import os
import sys

import cv2

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)
sys.stdout.reconfigure(encoding='utf-8')

from plugins.recognize.operator_card import OperatorCardMatcher       # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
SQUAD = ['卡缇', '安赛尔', '芬', '泡普卡', '安德切尔', '月见夜',
         '斑点', '香草', '玫兰莎', '克洛丝', '史都华德']

m = OperatorCardMatcher(candidates=SQUAD)
for fn in (sys.argv[1:] or ['axisdep_D6.png']):
    p = os.path.join(TMP, fn)
    if not os.path.exists(p):
        print('缺', fn)
        continue
    img = cv2.imread(p)
    cols = m.detect_card_columns(img)
    print(f'--- {fn} --- 检测到 {len(cols)} 列')
    for c in cols:
        print(f"    x {c['x0']:>4}..{c['x1']:<4} w={c['w']:>3} 中心={c['cx']}")
