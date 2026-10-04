# -*- coding: utf-8 -*-
"""fit_row11.py — 用**已知位次**的干员头像定位，解出 11 张卡行几何 (x0, pitch)。

已知位次（按费用升序，11 人在场）：芬=#0、月见夜=#5、泡普卡=#10（17 费，唯一最大）。
对每位在整行扫描其头像的最佳 NCC 位置，再用最小二乘拟合 `x = x0 + pitch·i`。
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)
sys.stdout.reconfigure(encoding='utf-8')

from plugins.recognize.operator_card import OperatorCardMatcher, _ncc   # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
SQUAD = ['卡缇', '安赛尔', '芬', '泡普卡', '安德切尔', '月见夜',
         '斑点', '香草', '玫兰莎', '克洛丝', '史都华德']
TARGETS = [('芬', 0), ('玫兰莎', 4), ('月见夜', 5), ('泡普卡', 10)]

img = cv2.imread(os.path.join(TMP, 'row11.png'))
m = OperatorCardMatcher(candidates=SQUAD)
HALF, Y0, H = 90, 905, 170
print(f'扫描参数：half={HALF} y0={Y0} h={H}')
pts = []
for nm, idx in TARGETS:
    av, al = m.lib[nm]
    best = (-9, None)
    for cx in range(100, 1901, 4):
        patch = img[Y0:Y0 + H, cx - HALF:cx + HALF]
        if patch.shape[0] < 100:
            continue
        p2 = cv2.resize(patch, (av.shape[1], av.shape[0]), interpolation=cv2.INTER_AREA)
        s = _ncc(p2, av, al)
        if s > best[0]:
            best = (s, cx)
    print(f'  {nm:<5} 位次{idx:>3} → 最佳 x={best[1]:>5}  NCC={best[0]:.4f}')
    pts.append((idx, best[1], best[0]))

good = [(i, x) for i, x, s in pts if s > 0.35]
if len(good) >= 2:
    A = np.array([[i, 1.0] for i, _ in good], float)
    b = np.array([x for _, x in good], float)
    pitch, x0 = np.linalg.lstsq(A, b, rcond=None)[0]
    print(f'\n★拟合：x = {x0:.1f} + {pitch:.1f}·i   （卡#0 中心 {x0:.0f}，'
          f'卡#10 中心 {x0 + 10 * pitch:.0f}）')
    for i, x in good:
        print(f'   #{i}: 实测 {x} vs 拟合 {x0 + pitch * i:.1f}  残差 {x - (x0 + pitch * i):+.1f}')
else:
    print('\n可信点不足，无法拟合')
