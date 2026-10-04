# -*- coding: utf-8 -*-
"""find_avatar_rect.py — ★在卡面内**搜索与头像文件完全一致的矩形**（alpha 掩膜 NCC）。

## 用户说明（2026-09-15）
> 「头像文件其实就是游戏本地读取、**显示到局内待部署区的图片**；
>    **排除头像透明区域和费用等干扰后应完全一致**」

⇒ 若如此，卡面内必存在一个矩形 R，使 `NCC(卡面[R], 头像[不透明区]) ≈ 1.0`。
本脚本在卡面内**粗到细搜索** R（位置 + 尺寸），报告最佳 NCC 与对应矩形。
若最佳值远小于 1，则说明还有别的变换（缩放/裁切）或资产并非同一张。
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
PRTS = r'D:\__soft\ak\prts+\_internal\resource'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
# 编队页卡面（实测中心）：第 3 张 = 芬
CX, CY = 693, 306
CARD = (CX - 130, CY - 230, CX + 130, CY + 230)      # 260×460 的卡面外框


def masked_ncc(a_bgr, a_mask, b_gray):
    """a=头像（含 alpha），b=卡面候选矩形（已缩放到 a 的尺寸）。"""
    ag = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    m = a_mask > 32
    if m.sum() < 200:
        return -1.0
    x = ag[m]
    y = b_gray[m]
    x = (x - x.mean()) / (x.std() + 1e-6)
    y = (y - y.mean()) / (y.std() + 1e-6)
    return float((x * y).mean())


def main() -> int:
    cid = sys.argv[1] if len(sys.argv) > 1 else 'char_123_fang'
    img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
    x0, y0, x1, y1 = CARD
    card = img[y0:y1, x0:x1]
    av = cv2.imread(os.path.join(PRTS, 'avatar', cid + '.png'), cv2.IMREAD_UNCHANGED)
    bgr, alpha = av[:, :, :3], (av[:, :, 3] if av.shape[2] == 4
                                else np.full(av.shape[:2], 255, np.uint8))
    print(f'头像 {cid} {av.shape}；卡面框 {CARD} → {card.shape}')

    best = (-9, None)
    # 粗搜：矩形宽 120~240、高 120~260，位置在卡面内滑动
    for w in range(120, 241, 20):
        for h in range(120, 261, 20):
            for yy in range(0, card.shape[0] - h + 1, 12):
                for xx in range(0, card.shape[1] - w + 1, 12):
                    sub = cv2.cvtColor(card[yy:yy + h, xx:xx + w], cv2.COLOR_BGR2GRAY)
                    sub = cv2.resize(sub, (alpha.shape[1], alpha.shape[0]),
                                     interpolation=cv2.INTER_AREA)
                    s = masked_ncc(bgr, alpha, sub)
                    if s > best[0]:
                        best = (s, (xx, yy, w, h))
    print(f'\n粗搜最佳 NCC = {best[0]:.4f}  矩形(卡面内) = {best[1]}')

    # 细搜（在最佳附近 ±16 / ±10）
    xx0, yy0, w0, h0 = best[1]
    for w in range(max(60, w0 - 20), w0 + 21, 4):
        for h in range(max(60, h0 - 20), h0 + 21, 4):
            for yy in range(max(0, yy0 - 16), min(card.shape[0] - h, yy0 + 16) + 1, 4):
                for xx in range(max(0, xx0 - 16), min(card.shape[1] - w, xx0 + 16) + 1, 4):
                    sub = cv2.cvtColor(card[yy:yy + h, xx:xx + w], cv2.COLOR_BGR2GRAY)
                    sub = cv2.resize(sub, (alpha.shape[1], alpha.shape[0]),
                                     interpolation=cv2.INTER_AREA)
                    s = masked_ncc(bgr, alpha, sub)
                    if s > best[0]:
                        best = (s, (xx, yy, w, h))
    print(f'细搜最佳 NCC = {best[0]:.4f}  矩形(卡面内) = {best[1]}')
    xx, yy, w, h = best[1]
    sub = card[yy:yy + h, xx:xx + w]
    cv2.imwrite(os.path.join(TMP, 'best_rect.png'),
                np.hstack([cv2.resize(sub, (180, 240)), cv2.resize(bgr, (180, 240))]))
    print('已输出 best_rect.png（左=卡面最佳矩形，右=头像）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
