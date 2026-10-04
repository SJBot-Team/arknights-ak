# -*- coding: utf-8 -*-
"""match_card_ms.py — ★多尺度模板匹配识别卡片干员（标准做法，替代固定几何模型）。

## 为什么
固定几何模型（直接拉伸 / 高铺满居中裁 / 宽铺满顶对齐）实测相关分≈0
⇒ 卡片与头像**不是固定几何关系** ⇒ 必须**搜索对齐**。
本脚本：以**卡面上部中央的脸部框**为模板，在**头像的多个缩放尺度**上做 `cv2.matchTemplate`
（`TM_CCOEFF_NORMED`），每位候选取其最大值 ⇒ 排名。

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


def load_gray(cid, scale):
    im = cv2.imread(os.path.join(PRTS, 'avatar', f'{cid}.png'), cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    g = cv2.cvtColor(im[:, :, :3], cv2.COLOR_BGR2GRAY)
    h, w = g.shape[:2]
    return cv2.resize(g, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)


def main() -> int:
    mapping = json.load(open(os.path.join(PRTS, 'operator_mapping.json'), encoding='utf-8'))
    ids = {nm: (mapping.get(nm) or [None])[0] for nm in SQUAD}
    img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
    scales = [0.8, 1.0, 1.2, 1.5, 1.8, 2.2, 2.6, 3.0]
    cache = {(nm, s): load_gray(cid, s) for nm, cid in ids.items() if cid for s in scales}

    rows = [(x, 306) for x in XS] + [(x, 819) for x in XS[:5]]
    # 模板 = 卡面上部中央的脸部框（相对卡面：x 中央 110px、y 从 8% 到 45%）
    TX, TY0, TY1 = 110, 0.08, 0.45
    hit = 0
    print(f'{"#":>2} {"真值":<6} {"识别":<6} {"分":>6} {"边际":>6}  判定  top3')
    for k, ((cx, cy), want) in enumerate(zip(rows, SQUAD)):
        card = img[cy - CH // 2:cy + CH // 2, cx - CW // 2:cx + CW // 2]
        if card.shape[:2] != (CH, CW):
            continue
        y0, y1 = int(CH * TY0), int(CH * TY1)
        tpl = cv2.cvtColor(card[y0:y1, CW // 2 - TX // 2:CW // 2 + TX // 2],
                           cv2.COLOR_BGR2GRAY)
        sc = []
        for nm in ids:
            best = -1.0
            for s in scales:
                g = cache.get((nm, s))
                if g is None or g.shape[0] < tpl.shape[0] or g.shape[1] < tpl.shape[1]:
                    continue
                r = cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED)
                best = max(best, float(r.max()))
            sc.append((best, nm))
        sc.sort(reverse=True)
        ok = sc[0][1] == want
        hit += ok
        print(f'{k:>2} {want:<6} {sc[0][1]:<6} {sc[0][0]:>6.3f} '
              f'{sc[0][0] - sc[1][0]:>6.3f}  {"✅" if ok else "✗ "}    {[n for _, n in sc[:3]]}')
    print(f'\n命中 {hit}/{len(SQUAD)} = {hit / len(SQUAD):.0%}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
