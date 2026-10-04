# -*- coding: utf-8 -*-
"""fix_card_cost_roi.py — 标定"卡片费用数字"的 ROI 并验证（离线，有真值）。

## 真值（`axisdep_D6.png` 目视读数，卡片按费用升序）
    9 9 9 13 14 15 15 16 16 17
## 用途
费用可**唯一定人**（本编队里 芬=8、月见夜=14 均唯一）；对重复费用再用头像匹配在这 2~3 人里分辨，
边际会大幅提高。⇒ 这是"按轴表选对干员"的可行混合方案。
"""
from __future__ import annotations

import os
import sys

import cv2

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)
sys.stdout.reconfigure(encoding='utf-8')

from plugins.recognize.cost_number import CostNumberRecognizer      # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TPL = os.path.join(TMP, 'tpl_h124.json')
TRUTH_X = [89, 261, 432, 609, 764, 1130, 1277, 1458, 1665, 1830]
TRUTH_V = [9, 9, 9, 13, 14, 15, 15, 16, 16, 17]

img = cv2.imread(os.path.join(TMP, 'axisdep_D6.png'))
num = CostNumberRecognizer()
print('候选 ROI（卡片费用文字区）验证：真值 =', TRUTH_V)
best = None
for (y0, y1) in ((888, 934), (896, 942), (880, 926), (900, 946)):
    for hw in (26, 32, 40):
        got, ok = [], 0
        for cx, want in zip(TRUTH_X, TRUTH_V):
            spec = {'roi': [cx - hw, y0, cx + hw, y1]}
            if os.path.exists(TPL):
                spec['templates'] = TPL
            ms = num.run(img, spec, None, (0, 0))
            v = int(ms[0].extra['cost']) if ms else None
            got.append(v)
            ok += (v == want)
        tag = f'  ROI(cx±{hw}, y {y0}..{y1})'
        print(f'{tag}: 命中 {ok}/{len(TRUTH_V)}  读数={got}')
        if best is None or ok > best[0]:
            best = (ok, hw, y0, y1, got)
print(f'\n最佳：命中 {best[0]}/{len(TRUTH_V)}  ROI(cx±{best[1]}, y {best[2]}..{best[3]})  读数={best[4]}')
