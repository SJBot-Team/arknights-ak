# -*- coding: utf-8 -*-
"""test_locate_card.py — 验证"按名字直接定位卡片"（判别性扫描）。"""
from __future__ import annotations

import os
import sys

import cv2

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\code\vision')
sys.stdout.reconfigure(encoding='utf-8')

from plugins.recognize.operator_card import OperatorCardMatcher     # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
SQUAD = ['卡缇', '安赛尔', '芬', '泡普卡', '安德切尔', '月见夜',
         '斑点', '香草', '玫兰莎', '克洛丝', '史都华德']
CASES = [('row11.png', ['芬', '克洛丝', '月见夜', '泡普卡']),
         ('axisdep_D6.png', ['克洛丝', '月见夜', '卡缇', '史都华德'])]

m = OperatorCardMatcher(candidates=SQUAD)
for fn, names in CASES:
    img = cv2.imread(os.path.join(TMP, fn))
    print('--- ' + fn)
    for nm in names:
        r = m.locate_operator_card(img, nm)
        print('   {}: ok={} x={} half={} ncc_me={} ncc_other={} disc={}'.format(
            nm, r.get('ok'), r.get('cx'), r.get('half'),
            r.get('ncc_me'), r.get('ncc_other'), r.get('discriminative')))
