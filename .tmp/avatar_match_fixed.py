# -*- coding: utf-8 -*-
"""avatar_match_fixed.py — ★按"已对齐的头像矩形"做卡片识别，并在编队页 11 人上验证。

## 对齐关系（本轮实测发现）
在编队页卡面上**搜索"与头像完全一致的矩形"**，最佳位置为**卡面相对 (60, 68)、尺寸 180×176**，
掩膜 NCC = **0.796**，目视对照（`best_rect.png`）显示**同一张画的同一构图**
⇒ 用户说明成立：**头像文件就是局内待部署区显示的那张图**；此前失败是**裁切未对准**。

## 做法
- 取卡片外框 `(cx−130, cy−230) .. (cx+130, cy+230)`（编队页实测）；
- 头像矩形 = 外框内 **(60, 68, 180, 176)**；
- 用**头像的 alpha 掩膜**做归一化互相关（**排除透明区**），并只在该掩膜内比较；
- 真值 = 编队页 11 人顺序。
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
RECT = (60, 68, 180, 176)          # 卡面内头像矩形 (x, y, w, h)


def load_avatar(cid):
    p = os.path.join(PRTS, 'avatar', f'{cid}.png')
    im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
    if im is None:
        return None, None
    bgr = im[:, :, :3]
    a = im[:, :, 3] if im.shape[2] == 4 else np.full(im.shape[:2], 255, np.uint8)
    return bgr, a


def ncc_masked(card_patch, av_bgr, av_alpha):
    """card_patch(已缩放到头像尺寸) vs 头像，仅在 alpha>32 的像素上做归一化互相关（灰度+彩色取平均）。"""
    g1 = cv2.cvtColor(card_patch, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g2 = cv2.cvtColor(av_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    m = av_alpha > 32
    if m.sum() < 200:
        return -1.0
    a = g1[m]
    b = g2[m]
    ncc_g = float((((a - a.mean()) / (a.std() + 1e-6)) *
                   ((b - b.mean()) / (b.std() + 1e-6))).mean())
    # 彩色通道平均
    ncc_c = []
    for ch in range(3):
        x = card_patch[:, :, ch][m].astype(np.float32)
        y = av_bgr[:, :, ch][m].astype(np.float32)
        ncc_c.append(float((((x - x.mean()) / (x.std() + 1e-6)) *
                            ((y - y.mean()) / (y.std() + 1e-6))).mean()))
    return 0.5 * ncc_g + 0.5 * float(np.mean(ncc_c))


def main() -> int:
    mapping = json.load(open(os.path.join(PRTS, 'operator_mapping.json'), encoding='utf-8'))
    lib = {}
    for nm in SQUAD:
        for cid in (mapping.get(nm) or []):
            b, a = load_avatar(cid)
            if b is not None:
                lib[nm] = (b, a)
    print(f'候选 {len(lib)} 人；矩形(卡面内) = {RECT}')
    img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
    rows = [(x, 306) for x in XS] + [(x, 819) for x in XS[:5]]
    hit = 0
    print(f'{"#":>2} {"真值":<6} {"识别":<6} {"分":>7} {"边际":>7}  判定  top3')
    for k, ((cx, cy), want) in enumerate(zip(rows, SQUAD)):
        x0, y0 = cx - CARD_W // 2, cy - CARD_H // 2
        rx, ry, rw, rh = RECT
        patch = img[y0 + ry:y0 + ry + rh, x0 + rx:x0 + rx + rw]
        if patch.size == 0:
            continue
        sc = []
        for nm, (b, a) in lib.items():
            p2 = cv2.resize(patch, (b.shape[1], b.shape[0]), interpolation=cv2.INTER_AREA)
            sc.append((ncc_masked(p2, b, a), nm))
        sc.sort(reverse=True)
        ok = sc[0][1] == want
        hit += ok
        print(f'{k:>2} {want:<6} {sc[0][1]:<6} {sc[0][0]:>7.4f} '
              f'{sc[0][0] - sc[1][0]:>7.4f}  {"✅" if ok else "✗ "}    {[n for _, n in sc[:3]]}')
    print(f'\n命中 {hit}/{len(SQUAD)} = {hit / len(SQUAD):.0%}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
