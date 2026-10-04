# -*- coding: utf-8 -*-
"""diag_card_geom.py — ★数值诊断：卡面与头像的**几何关系**到底是哪种模型。

## 目视已证明"卡片裁切 == 头像文件"（同一张画），故只要几何模型对，逐像素相关必然显著。
本脚本对同一张卡（编队页 (693,306) = **芬**）比较三种投影模型下、对 11 位候选的相关分：
  **A 直接拉伸**：头像 resize 到 (W,H)
  **B 高度铺满+水平居中裁切**：resize 到 (H,H) 后取中央 W 宽
  **C 宽度铺满+顶部对齐**：resize 到 (W,W) 后置于 (W,H) 画布顶部
并只比较**上部区域**（避开蓝色横幅/费用/职业图标等叠加）。
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
CW, CH = 210, 400
CX, CY = 693, 306          # 编队页第 3 张卡 = 芬
TRUTH = '芬'


def load(cid):
    im = cv2.imread(os.path.join(PRTS, 'avatar', f'{cid}.png'), cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    if im.ndim == 3 and im.shape[2] == 4:
        return im[:, :, :3]
    return im


def modelA(av):
    return cv2.resize(av, (CW, CH), interpolation=cv2.INTER_AREA)


def modelB(av):
    n = max(CW, CH)
    s = cv2.resize(av, (n, n), interpolation=cv2.INTER_AREA)
    x0 = (n - CW) // 2
    return s[:, x0:x0 + CW]


def modelC(av):
    s = cv2.resize(av, (CW, CW), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((CH, CW, 3), np.uint8)
    canvas[:CW] = s
    return canvas


def zn(g):
    g = g.astype(np.float32)
    return (g - g.mean()) / (g.std() + 1e-6)


def main() -> int:
    mapping = json.load(open(os.path.join(PRTS, 'operator_mapping.json'), encoding='utf-8'))
    lib = {}
    for nm in SQUAD:
        for cid in (mapping.get(nm) or []):
            a = load(cid)
            if a is not None:
                lib[nm] = a
    img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
    card = img[CY - CH // 2:CY + CH // 2, CX - CW // 2:CX + CW // 2]
    print(f'卡中心=({CX},{CY}) 期望={TRUTH}  卡面={card.shape}')

    for top in (0.40, 0.55, 0.70, 1.00):
        h = int(CH * top)
        q = zn(cv2.cvtColor(card[:h], cv2.COLOR_BGR2GRAY))
        print(f'\n--- 只比上 {top:.0%}（{h}px）---')
        for name, fn in (('A 直接拉伸', modelA), ('B 高铺满+居中裁', modelB), ('C 宽铺满+顶对齐', modelC)):
            sc = []
            for nm, av in lib.items():
                g = cv2.cvtColor(fn(av)[:h], cv2.COLOR_BGR2GRAY)
                sc.append((float((zn(g) * q).mean()), nm))
            sc.sort(reverse=True)
            rank = [n for _, n in sc].index(TRUTH) + 1
            print(f'  {name:<14} top1={sc[0][1]:<5} 分={sc[0][0]:>6.3f} '
                  f'| {TRUTH} 的排名={rank} 分={dict((n, round(s,3)) for s,n in sc)[TRUTH]:>6.3f} '
                  f'| top3={[n for _, n in sc[:3]]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
