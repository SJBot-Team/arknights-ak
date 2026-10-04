# -*- coding: utf-8 -*-
"""validate_card_match3.py — ★带 alpha 掩膜的卡片头像匹配（修正"透明背景噪声"这一真因）。

## 历次失败原因（已定位）
1. 初版：把 210×400 卡面与 180×180 头像**都压成正方形** ⇒ 形变不同；
2. 二版：几何虽修正，但 **`cv2.imread` 忽略 alpha** ⇒ 头像透明区域变成**黑白噪声**，
   直接把互相关淹没（对照图里可肉眼看到噪声背景）。
**⇒ 本版：`IMREAD_UNCHANGED` 读取 RGBA，只用 `alpha>0` 的像素做掩膜归一化互相关。**

## 真值（`live_03_squad.png` 编队页）
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
TOP = 0.62


def load_rgba(cid):
    p = os.path.join(PRTS, 'avatar', f'{cid}.png')
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    if im.ndim == 3 and im.shape[2] == 4:
        bgr, a = im[:, :, :3], im[:, :, 3]
    else:
        bgr, a = im[:, :, :3], np.full(im.shape[:2], 255, np.uint8)
    return bgr, a


def project(bgr, alpha, w, h):
    n = max(w, h)
    b = cv2.resize(bgr, (n, n), interpolation=cv2.INTER_AREA)
    a = cv2.resize(alpha, (n, n), interpolation=cv2.INTER_AREA)
    x0 = (n - w) // 2
    return b[:, x0:x0 + w], a[:, x0:x0 + w]


def masked_corr(q_gray, q_mask, p_gray, p_mask):
    m = (q_mask > 32) & (p_mask > 32)
    if m.sum() < 200:
        return -1.0
    a = q_gray[m].astype(np.float32)
    b = p_gray[m].astype(np.float32)
    a = (a - a.mean()) / (a.std() + 1e-6)
    b = (b - b.mean()) / (b.std() + 1e-6)
    return float((a * b).mean())


def main() -> int:
    mapping = json.load(open(os.path.join(PRTS, 'operator_mapping.json'), encoding='utf-8'))
    lib = {}
    for nm in SQUAD:
        for cid in (mapping.get(nm) or []):
            r = load_rgba(cid)
            if r:
                lib[nm] = r
    print(f'候选 {len(lib)} 人（带 alpha）')
    img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
    rows = [(x, 306) for x in XS] + [(x, 819) for x in XS[:5]]
    ch = int(CH * TOP)
    hit = 0
    print(f'{"#":>2} {"真值":<6} {"识别":<6} {"分":>7} {"边际":>7}  判定  top3')
    for k, ((cx, cy), want) in enumerate(zip(rows, SQUAD)):
        card = img[cy - CH // 2:cy + CH // 2, cx - CW // 2:cx + CW // 2]
        if card.shape[:2] != (CH, CW):
            continue
        cg = cv2.cvtColor(card[:ch], cv2.COLOR_BGR2GRAY)
        cm = np.full(cg.shape, 255, np.uint8)
        sc = []
        for nm, (b, a) in lib.items():
            pb, pa = project(b, a, CW, CH)
            pg = cv2.cvtColor(pb[:ch], cv2.COLOR_BGR2GRAY)
            sc.append((masked_corr(cg, cm, pg, pa[:ch]), nm))
        sc.sort(reverse=True)
        ok = sc[0][1] == want
        hit += ok
        print(f'{k:>2} {want:<6} {sc[0][1]:<6} {sc[0][0]:>7.4f} '
              f'{sc[0][0] - sc[1][0]:>7.4f}  {"✅" if ok else "✗ "}    {[n for _, n in sc[:3]]}')
    print(f'\n命中 {hit}/{len(SQUAD)} = {hit / len(SQUAD):.0%}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
