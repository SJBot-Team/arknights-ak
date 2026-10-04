# -*- coding: utf-8 -*-
"""validate_card_match2.py — ★修正几何模型后重验卡片头像匹配（离线，编队页有真值）。

## 修正的几何模型（由"卡面 vs 头像"对照图目视确认）
战斗/编队卡片的画法 = **头像按"高度铺满"缩放后水平居中裁切**：
    scale = card_h / av_h ;  av' = resize(av, (card_h, card_h)) ; 取中央 card_w 宽
⇒ 直接比对即可，**不需要滑窗**，也**不能把两者都压成正方形**（此前正是因此失败：2/11）。

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

mapping = json.load(open(os.path.join(PRTS, 'operator_mapping.json'), encoding='utf-8'))
AV = os.path.join(PRTS, 'avatar')


def project(av_bgr, w, h):
    """把头像按"高度铺满 + 水平居中裁切"投影到卡片尺寸。"""
    n = max(w, h)
    s = cv2.resize(av_bgr, (n, n), interpolation=cv2.INTER_AREA)
    x0 = (n - w) // 2
    return s[:, x0:x0 + w]


def zn(a):
    a = a.astype(np.float32)
    return (a - a.mean()) / (a.std() + 1e-6)


def main() -> int:
    lib = {}
    for nm in SQUAD:
        for cid in (mapping.get(nm) or []):
            p = os.path.join(AV, f'{cid}.png')
            if os.path.exists(p):
                lib[nm] = cv2.imread(p)
    print(f'候选 {len(lib)} 人')

    img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
    truth = SQUAD
    rows = [(x, 306) for x in XS] + [(x, 819) for x in XS[:5]]
    CW, CH = 210, 400
    TOP = 0.55                       # 只比上 55%（下方有蓝色横幅/费用/职业图标等叠加）
    hit = 0
    print(f'{"#":>2} {"真值":<6} {"识别":<6} {"分":>7} {"边际":>7}  判定  top3')
    for k, ((cx, cy), want) in enumerate(zip(rows, truth)):
        card = img[cy - CH // 2:cy + CH // 2, cx - CW // 2:cx + CW // 2]
        if card.shape[:2] != (CH, CW):
            continue
        ch = int(CH * TOP)
        q = zn(cv2.cvtColor(card[:ch], cv2.COLOR_BGR2GRAY))
        sc = []
        for nm, av in lib.items():
            pj = cv2.cvtColor(project(av, CW, CH), cv2.COLOR_BGR2GRAY)[:ch]
            sc.append((float((zn(pj) * q).mean()), nm))
        sc.sort(reverse=True)
        ok = sc[0][1] == want
        hit += ok
        print(f'{k:>2} {want:<6} {sc[0][1]:<6} {sc[0][0]:>7.4f} '
              f'{sc[0][0] - sc[1][0]:>7.4f}  {"✅" if ok else "✗ "}    '
              f'{[n for _, n in sc[:3]]}')
    print(f'\n命中 {hit}/{len(truth)} = {hit / len(truth):.0%}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
