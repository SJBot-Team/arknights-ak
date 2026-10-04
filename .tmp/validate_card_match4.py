# -*- coding: utf-8 -*-
"""validate_card_match4.py — ★用 **HSV 颜色直方图** 匹配卡片头像（对叠加/对齐不敏感）。

## 为什么换度量
历次"灰度/彩色互相关"均失败（2/11），但**目视对照已证明卡片裁切与头像文件是同一张图**
（`card_vs_avatar.png`：卡缇/芬/月见夜 三对全中）。
⇒ 问题在**度量**而非资产：卡片带**蓝色对角线横幅、费用、职业图标、渐变**等叠加，
   且头像带**透明通道**，逐像素相关很容易被这些非共有区域淹没。
⇒ 颜色直方图只统计**颜色分布**，对上述干扰天然不敏感。

## 真值（`live_03_squad.png` 编队页，已目视确认）
    行1: 卡缇 安赛尔 芬 泡普卡 安德切尔 月见夜
    行2: 斑点 香草 玫兰莎 克洛丝 史都华德
"""
from __future__ import annotations

import json
import os
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

PRTS = r'D:\__soft\ak\prts+\_internal\resource'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
SQUAD = ['卡缇', '安赛尔', '芬', '泡普卡', '安德切尔', '月见夜',
         '斑点', '香草', '玫兰莎', '克洛丝', '史都华德']
XS = [234, 468, 693, 918, 1144, 1369]
CW, CH = 210, 400
TOP = 0.58
BINS = (8, 8, 8)


def hist(bgr, mask=None):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1, 2], mask, BINS, [0, 180, 0, 256, 0, 256])
    h = cv2.normalize(h, h).flatten()
    return h


def load(cid):
    p = os.path.join(PRTS, 'avatar', f'{cid}.png')
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    if im.ndim == 3 and im.shape[2] == 4:
        return im[:, :, :3], im[:, :, 3]
    return im[:, :, :3], np.full(im.shape[:2], 255, np.uint8)


def main() -> int:
    mapping = json.load(open(os.path.join(PRTS, 'operator_mapping.json'), encoding='utf-8'))
    lib = {}
    for nm in SQUAD:
        for cid in (mapping.get(nm) or []):
            r = load(cid)
            if r:
                lib[nm] = r
    print(f'候选 {len(lib)} 人')
    img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
    ch = int(CH * TOP)
    rows = [(x, 306) for x in XS] + [(x, 819) for x in XS[:5]]
    hit = 0
    print(f'{"#":>2} {"真值":<6} {"识别":<6} {"分":>7} {"边际":>7}  判定  top3')
    for k, ((cx, cy), want) in enumerate(zip(rows, SQUAD)):
        card = img[cy - CH // 2:cy + CH // 2, cx - CW // 2:cx + CW // 2]
        if card.shape[:2] != (CH, CW):
            continue
        qh = hist(card[:ch])
        sc = []
        for nm, (b, a) in lib.items():
            pb = cv2.resize(b, (CW, CH), interpolation=cv2.INTER_AREA)
            pa = cv2.resize(a, (CW, CH), interpolation=cv2.INTER_AREA)
            m = (pa[:ch] > 32).astype(np.uint8) * 255
            sc.append((float(cv2.compareHist(qh, hist(pb[:ch], m), cv2.HISTCMP_CORREL)), nm))
        sc.sort(reverse=True)
        ok = sc[0][1] == want
        hit += ok
        print(f'{k:>2} {want:<6} {sc[0][1]:<6} {sc[0][0]:>7.4f} '
              f'{sc[0][0] - sc[1][0]:>7.4f}  {"✅" if ok else "✗ "}    {[n for _, n in sc[:3]]}')
    print(f'\n命中 {hit}/{len(SQUAD)} = {hit / len(SQUAD):.0%}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
