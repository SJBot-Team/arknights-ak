# -*- coding: utf-8 -*-
"""validate_card_match.py — ★用**已知顺序的编队截图**验证卡片头像匹配（离线，有真值）。

## 真值
`live_03_squad.png` 是 1-1 编队页，卡片顺序（截图已目视确认）：
    第 1 行：卡缇 安赛尔 芬 泡普卡 安德切尔 月见夜
    第 2 行：斑点 香草 玫兰莎 克洛丝 史都华德

## 做法
1. 用 PRTS+ 的 `operator_mapping.json` + `avatar/char_*.png`（720 张）建库；
2. **候选集限制到编队 11 人**；
3. 卡片裁切 → **彩色三通道**零均值归一化互相关 + **立绘内多尺度滑窗**（因卡片是脸部特写、立绘是半身）；
4. 报告**命中率**（top1 是否等于真值）与**边际**，用于判断方案是否可用。
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)
sys.stdout.reconfigure(encoding='utf-8')

PRTS = r'D:\__soft\ak\prts+\_internal\resource'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
SQUAD = ['卡缇', '安赛尔', '芬', '泡普卡', '安德切尔', '月见夜',
         '斑点', '香草', '玫兰莎', '克洛丝', '史都华德']
import json                                                        # noqa: E402

mapping = json.load(open(os.path.join(PRTS, 'operator_mapping.json'), encoding='utf-8'))
AV = os.path.join(PRTS, 'avatar')


def load(cid, sz=96):
    p = os.path.join(AV, f'{cid}.png')
    im = cv2.imread(p)
    if im is None:
        return None
    return cv2.resize(im, (sz, sz), interpolation=cv2.INTER_AREA).astype(np.float32)


def zn(a):
    a = a - a.reshape(-1, a.shape[-1]).mean(axis=0, keepdims=True)
    a = a / (a.reshape(-1, a.shape[-1]).std(axis=0, keepdims=True) + 1e-6)
    return a


def best_window(av, q, fracs=(0.40, 0.50, 0.62, 0.75, 0.90, 1.00)):
    n = av.shape[0]
    best = -1.0
    for f in fracs:
        w = max(16, int(n * f))
        step = max(2, w // 4)
        for y in range(0, n - w + 1, step):
            for x in range(0, n - w + 1, step):
                sub = av[y:y + w, x:x + w]
                s = float((zn(cv2.resize(sub, q.shape[:2], interpolation=cv2.INTER_AREA)) * q).mean())
                if s > best:
                    best = s
    return best


def main() -> int:
    ids = {}
    for nm in SQUAD:
        for cid in (mapping.get(nm) or []):
            a = load(cid)
            if a is not None:
                ids[nm] = a
    print(f'候选 {len(ids)} 人；库中头像 {len(os.listdir(AV))} 张')

    img = cv2.imread(os.path.join(TMP, 'live_03_squad.png'))
    if img is None:
        print('缺 live_03_squad.png')
        return 1
    # 编队页两行卡片：**按实机截图实测**（预览 1066×600 → ×1.801）
    #   行1: 6 张，卡面中心 x≈234/468/693/918/1144/1369，y≈306
    #   行2: 5 张，同 x（前 5 个），y≈819
    XS = [234, 468, 693, 918, 1144, 1369]
    rows = [(x, 306) for x in XS] + [(x, 819) for x in XS[:5]]
    truth = SQUAD
    hit = 0
    print(f'{"#":>2} {"裁切中心":>12} {"真值":<6} {"识别":<6} {"分":>6} {"边际":>6}  判定')
    for k, ((cx, cy), want) in enumerate(zip(rows, truth)):
        crop = img[cy - 200:cy + 200, cx - 105:cx + 105]      # 卡面（含脸部）
        if crop.size == 0:
            continue
        q = zn(cv2.resize(crop, (96, 96), interpolation=cv2.INTER_AREA).astype(np.float32))
        sc = sorted(((best_window(a, q), nm) for nm, a in ids.items()), reverse=True)
        top, margin = sc[0][0], sc[0][0] - sc[1][0]
        ok = sc[0][1] == want
        hit += ok
        print(f'{k:>2} {str((cx, cy)):>12} {want:<6} {sc[0][1]:<6} {top:>6.3f} '
              f'{margin:>6.3f}  {"✅" if ok else "✗"}')
    print(f'\n命中 {hit}/{len(truth)} = {hit / len(truth):.0%}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
