# -*- coding: utf-8 -*-
"""diag_pair.py — 最直接的判定：卡面 vs 头像，缩到同一尺寸后**并排输出 + 打印相关系数**。

若"目视像"而"相关≈0"，说明两者是**同一角色但取景不同**（视觉相似≠像素可匹配），
则须改用更强的描述子（颜色/形状/特征点），而不是继续调模板匹配参数。
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
PRTS = r'D:\__soft\ak\prts+\_internal\resource'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
CW, CH = 210, 400
PANELS = [((234, 306), 'char_209_ardign', '卡缇'),
          ((693, 306), 'char_123_fang', '芬'),
          ((1369, 306), 'char_283_midn', '月见夜')]

img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
out = []
for (cx, cy), cid, nm in PANELS:
    card = img[cy - CH // 2:cy + CH // 2, cx - CW // 2:cx + CW // 2]
    av = cv2.imread(os.path.join(PRTS, 'avatar', cid + '.png'), cv2.IMREAD_UNCHANGED)[:, :, :3]
    a = cv2.resize(card, (180, 300), interpolation=cv2.INTER_AREA)
    b = cv2.resize(av, (180, 300), interpolation=cv2.INTER_AREA)
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY).astype(np.float32)
    za = (ga - ga.mean()) / (ga.std() + 1e-6)
    zb = (gb - gb.mean()) / (gb.std() + 1e-6)
    ncc = float((za * zb).mean())
    # 只取上部 60%
    h = int(300 * 0.6)
    pa = (ga[:h] - ga[:h].mean()) / (ga[:h].std() + 1e-6)
    pb = (gb[:h] - gb[:h].mean()) / (gb[:h].std() + 1e-6)
    ncc_top = float((pa * pb).mean())
    print(f'{nm:<5} 全长 NCC={ncc:+.3f}  上部60% NCC={ncc_top:+.3f}')
    out += [a, b]

sheet = np.hstack([cv2.resize(x, (180, 300)) for x in out])
cv2.imwrite(os.path.join(TMP, 'diag_pair.png'), sheet)
print('\n已输出 diag_pair.png（成对：卡面 | 头像；共 3 对）')
