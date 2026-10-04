# -*- coding: utf-8 -*-
"""measure_row2.py — ★用"各自头像"在编队页**宽域搜索**，定位两行卡片的真实中心。

## 为什么
上一轮逐卡对齐后**第 1 行 6/6**，但**第 2 行的对齐总是顶到搜索边界** ⇒ 说明我给的第 2 行 y 坐标
（`y=819`）偏差 > 44px。本脚本对第 2 行 5 张卡做 **(x, y) 宽域搜索**（以"与本人头像的掩膜 NCC"为准则），
直接量出**真实中心**，并同时验证"头像匹配"在该行的可用性。
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
ROW2 = ['斑点', '香草', '玫兰莎', '克洛丝', '史都华德']
XS = [234, 468, 693, 918, 1144]
RECT = (60, 68, 180, 176)


def load(cid):
    im = cv2.imread(os.path.join(PRTS, 'avatar', f'{cid}.png'), cv2.IMREAD_UNCHANGED)
    if im is None:
        return None, None
    return im[:, :, :3], (im[:, :, 3] if im.shape[2] == 4
                          else np.full(im.shape[:2], 255, np.uint8))


def ncc(patch, av, alpha):
    g1 = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(av, cv2.COLOR_BGR2GRAY).astype(np.float32)
    m = alpha > 32
    if m.sum() < 200:
        return -1.0
    a, b = g1[m], g2[m]
    return float((((a - a.mean()) / (a.std() + 1e-6)) *
                  ((b - b.mean()) / (b.std() + 1e-6))).mean())


def main() -> int:
    mapping = json.load(open(os.path.join(PRTS, 'operator_mapping.json'), encoding='utf-8'))
    img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
    print(f'{"干员":<6} {"最佳中心":>12} {"NCC":>7}   搜索范围 x=中心±70, y=600..1060')
    for nm, cx0 in zip(ROW2, XS):
        cid = (mapping.get(nm) or [None])[0]
        av, al = load(cid)
        if av is None:
            continue
        best = (-9, None)
        for cy in range(600, 1061, 6):
            for dx in range(-70, 71, 6):
                x0, y0 = cx0 + dx - 130, cy - 230
                rx, ry, rw, rh = RECT
                patch = img[max(0, y0 + ry):y0 + ry + rh, max(0, x0 + rx):x0 + rx + rw]
                if patch.shape[0] < 20 or patch.shape[1] < 20:
                    continue
                p2 = cv2.resize(patch, (av.shape[1], av.shape[0]),
                                interpolation=cv2.INTER_AREA)
                s = ncc(p2, av, al)
                if s > best[0]:
                    best = (s, (cx0 + dx, cy))
        print(f'{nm:<6} {str(best[1]):>12} {best[0]:>7.4f}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
