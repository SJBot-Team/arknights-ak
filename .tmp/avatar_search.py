# -*- coding: utf-8 -*-
"""avatar_search.py — ★头像识别：**全尺度 + 全位移搜索**（此前只试过固定几何/局部滑窗）。

## 为什么重做
目视对照显示卡片画的是**同一位干员的同一张立绘**，但**取景不同**（卡片是"脸部特写"、
头像库是"半身"）⇒ 固定几何模型必然失败；必须让头像在卡片区域内**自由缩放+平移**去匹配。
本脚本以**卡片上部区域**为搜索图、**头像**为模板，在多种缩放尺度上做 `matchTemplate`
（`TM_CCOEFF_NORMED`，对亮度/对比度线性变化稳健），取最大响应为得分。

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
TOP = 0.78                     # 只搜卡片上部（下方有蓝色横幅/费用/图标）


def load_gray(cid):
    p = os.path.join(PRTS, 'avatar', f'{cid}.png')
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if im is None:
        return None, None
    bgr = im[:, :, :3]
    a = im[:, :, 3] if im.shape[2] == 4 else np.full(im.shape[:2], 255, np.uint8)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), a


def main() -> int:
    mapping = json.load(open(os.path.join(PRTS, 'operator_mapping.json'), encoding='utf-8'))
    lib = {}
    for nm in SQUAD:
        for cid in (mapping.get(nm) or []):
            g, a = load_gray(cid)
            if g is not None:
                lib[nm] = (g, a)
    print(f'候选 {len(lib)} 人；搜索尺度 = 卡片上部的 0.55~1.15 倍')

    img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
    rows = [(x, 306) for x in XS] + [(x, 819) for x in XS[:5]]
    hit = 0
    print(f'{"#":>2} {"真值":<6} {"识别":<6} {"分":>6} {"边际":>6}  top3')
    for k, ((cx, cy), want) in enumerate(zip(rows, SQUAD)):
        card = img[cy - CH // 2:cy + CH // 2, cx - CW // 2:cx + CW // 2]
        if card.shape[:2] != (CH, CW):
            continue
        region = cv2.cvtColor(card[:int(CH * TOP)], cv2.COLOR_BGR2GRAY)
        rh, rw = region.shape[:2]
        sc = []
        for nm, (g, a) in lib.items():
            best = -1.0
            for f in (0.28, 0.35, 0.42, 0.50, 0.60, 0.72, 0.85):
                th = int(rh * f)
                tw = th                      # 头像为正方形
                if th > rh or tw > rw or th < 24:
                    continue
                tpl = cv2.resize(g, (tw, th), interpolation=cv2.INTER_AREA)
                r = cv2.matchTemplate(region, tpl, cv2.TM_CCOEFF_NORMED)
                best = max(best, float(r.max()))
            sc.append((best, nm))
        sc.sort(reverse=True)
        rank = [n for _, n in sc].index(want) + 1
        hit += (rank == 1)
        print(f'{k:>2} {want:<6} {sc[0][1]:<6} {sc[0][0]:>6.3f} '
              f'{sc[0][0] - sc[1][0]:>6.3f}  {[n for _, n in sc[:3]]}'
              f'{"  ✅" if rank == 1 else f"  ✗(真值第{rank})"}')
    print(f'\n命中 {hit}/{len(SQUAD)} = {hit / len(SQUAD):.0%}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
