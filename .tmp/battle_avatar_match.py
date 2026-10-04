# -*- coding: utf-8 -*-
"""battle_avatar_match.py — ★战斗待部署区**头像识别**（用"费用顺序"当真值做交叉验证）。

## 关键测量（`battle_cards.png` 2× 放大目视）
- **战斗卡片头像 = 脸部特写，与 `avatar/char_*.png` 同构图**，仅**底部被屏幕裁掉**
  ⇒ 比编队页更好匹配（无需缩放对齐到半身）；
- **卡片真实中心 x ≈ 230 + 182·i**（10 张时）；`find_cards` 给出的 89 偏左约 140px；
- 单卡头像区：**x = 中心 ± 85**、**y ≈ 912..1078**（下缘被裁）。

## 真值（交叉验证）
`axisdep_D6.png` 时**芬已部署** ⇒ 卡片行应为「剩余费用升序」：
    克洛丝(9) 安德切尔(9) 香草(9) 玫兰莎(13) 月见夜(14) 安赛尔(15) 斑点(15)
    卡缇(16) 史都华德(16) 泡普卡(17)
（该顺序由 `card_plan.json` 独立给出，与图像识别**互为独立的通道**）
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
EXPECT = ['克洛丝', '安德切尔', '香草', '玫兰莎', '月见夜', '安赛尔',
          '斑点', '卡缇', '史都华德', '泡普卡']
X_LEFT, X_RIGHT = 139.0, 1959.0
Y0, Y1 = 912, 1078
HALF = 85


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
    plan = json.load(open(r'C:\Users\23922\Documents\ds_harness\ak\data\derived\card_plan.json',
                          encoding='utf-8'))
    pool = {}
    for nm in set(EXPECT) | set(plan['order']):
        for cid in (mapping.get(nm) or []):
            b, a = load(cid)
            if b is not None:
                pool[nm] = (b, a)
    img = cv2.imread(os.path.join(TMP, 'axisdep_D6.png'))
    n = len(EXPECT)
    pitch = (X_RIGHT - X_LEFT) / n
    print(f'候选 {len(pool)} 人；卡片 {n} 张，pitch={pitch:.1f}')
    hit = 0
    print(f'{"#":>2} {"真值(费用顺序)":<12} {"识别":<8} {"分":>7} {"边际":>7}  判定  top3')
    for i, want in enumerate(EXPECT):
        cx = X_LEFT + pitch * (i + 0.5)
        best = (-9, None, 0, 0)
        for dcx in range(-48, 49, 4):        # ★每卡 x 局部搜索（吸收步距累积误差）
            for dy in range(-8, 9, 4):
                for dx in range(-8, 9, 4):
                    cxi = int(cx) + dcx
                    patch = img[Y0 + dy:Y1 + dy, cxi - HALF + dx:cxi + HALF + dx]
                    if patch.shape[0] < 40 or patch.shape[1] < 40:
                        continue
                    sc = []
                    for nm, (b, a) in pool.items():
                        p2 = cv2.resize(patch, (b.shape[1], b.shape[0]),
                                        interpolation=cv2.INTER_AREA)
                        sc.append((ncc(p2, b, a), nm))
                    sc.sort(reverse=True)
                    if sc[0][0] > best[0]:
                        best = (sc[0][0], sc, dcx, dy)
        _, sc, dx, dy = best
        ok = sc[0][1] == want
        hit += ok
        print(f'{i:>2} {want:<12} {sc[0][1]:<8} {sc[0][0]:>7.4f} '
              f'{sc[0][0] - sc[1][0]:>7.4f}  {"✅" if ok else "✗ "}    {[n for _, n in sc[:3]]}')
    print(f'\n命中 {hit}/{n} = {hit / n:.0%}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
