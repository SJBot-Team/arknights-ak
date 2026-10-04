# -*- coding: utf-8 -*-
"""avatar_match_aligned.py — ★先做**逐卡局部对齐**再做头像匹配（编队页 11 人验证）。

## 思路
上一版用**全局统一矩形**得 5/11（芬 0.796/边际 0.509 极强，但其余卡因几像素错位而崩）
⇒ 每张卡先在**期望矩形附近 ±16px 搜索最佳对齐**（以"对全部候选的最大响应"为目标），
再在该对齐下匹配头像 ⇒ 消除逐卡微小的排版/取整偏差。

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
CARD_W, CARD_H = 260, 460
RECT = (60, 68, 180, 176)
SEARCH = 24


def load(cid):
    im = cv2.imread(os.path.join(PRTS, 'avatar', f'{cid}.png'), cv2.IMREAD_UNCHANGED)
    if im is None:
        return None, None
    bgr = im[:, :, :3]
    a = im[:, :, 3] if im.shape[2] == 4 else np.full(im.shape[:2], 255, np.uint8)
    return bgr, a


def ncc(card_patch, av, alpha):
    g1 = cv2.cvtColor(card_patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(av, cv2.COLOR_BGR2GRAY).astype(np.float32)
    m = alpha > 32
    if m.sum() < 200:
        return -1.0
    a, b = g1[m], g2[m]
    return float((((a - a.mean()) / (a.std() + 1e-6)) *
                  ((b - b.mean()) / (b.std() + 1e-6))).mean())


def score_all(img, cx, cy, lib, dx, dy):
    x0, y0 = cx - CARD_W // 2, cy - CARD_H // 2
    rx, ry, rw, rh = RECT
    patch = img[y0 + ry + dy:y0 + ry + dy + rh, x0 + rx + dx:x0 + rx + dx + rw]
    if patch.size == 0:
        return None
    sc = []
    for nm, (b, a) in lib.items():
        p2 = cv2.resize(patch, (b.shape[1], b.shape[0]), interpolation=cv2.INTER_AREA)
        sc.append((ncc(p2, b, a), nm))
    sc.sort(reverse=True)
    return sc


def main() -> int:
    mapping = json.load(open(os.path.join(PRTS, 'operator_mapping.json'), encoding='utf-8'))
    lib = {}
    for nm in SQUAD:
        for cid in (mapping.get(nm) or []):
            b, a = load(cid)
            if b is not None:
                lib[nm] = (b, a)
    img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
    # ★第 2 行中心由 measure_row2.py 实测：y≈740（原 819 偏差 ~80px）
    rows = ([(x, 306) for x in XS]
            + [(236, 740), (458, 740), (701, 740), (932, 740), (1170, 740)])
    hit = 0
    print(f'{"#":>2} {"真值":<6} {"识别":<6} {"分":>7} {"边际":>7} {"对齐":>10}  判定  top3')
    for k, ((cx, cy), want) in enumerate(zip(rows, SQUAD)):
        best = None
        for dy in range(-SEARCH, SEARCH + 1, 4):
            for dx in range(-SEARCH, SEARCH + 1, 4):
                sc = score_all(img, cx, cy, lib, dx, dy)
                if sc and (best is None or sc[0][0] > best[0][0][0]):
                    best = (sc, dx, dy)
        if best is None:
            continue
        sc, dx, dy = best
        ok = sc[0][1] == want
        hit += ok
        print(f'{k:>2} {want:<6} {sc[0][1]:<6} {sc[0][0]:>7.4f} '
              f'{sc[0][0] - sc[1][0]:>7.4f} {f"({dx:+d},{dy:+d})":>10}  '
              f'{"✅" if ok else "✗ "}    {[n for _, n in sc[:3]]}')
    print(f'\n命中 {hit}/{len(SQUAD)} = {hit / len(SQUAD):.0%}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
