# -*- coding: utf-8 -*-
"""card_cost_scale.py — ★复用现成数字模板读**卡片小号费用**（放大后同字体匹配）。

## 思路（省去重新自举模板）
卡片费用数字与右下**大费用数字同字体**，仅字号不同（小 ≈22~26px，大 ≈40~50px）
⇒ 把卡片费用的小裁切**放大 ~1.8×** 后，直接复用既有 `tpl_h124.json` 模板即可识别。

## 真值（`axisdep_D6.png` 目视读数，卡片按费用升序）
    x = 89,261,432,609,764,1130,1277,1458,1665,1830  →  9 9 9 13 14 15 15 16 16 17
"""
from __future__ import annotations

import os
import sys

import cv2

VISION = r'C:\Users\23922\Documents\ds_harness\ak\code\vision'
sys.path.insert(0, VISION)
sys.stdout.reconfigure(encoding='utf-8')

from plugins.recognize.cost_number import CostNumberRecognizer       # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TPL = os.path.join(TMP, 'tpl_h124.json')
XS = [89, 261, 432, 609, 764, 1130, 1277, 1458, 1665, 1830]
TRUTH = [9, 9, 9, 13, 14, 15, 15, 16, 16, 17]


def read_small(img, cx, y0=884, y1=940, hw=30, scale=1.8):
    crop = img[y0:y1, max(0, cx - hw):cx + hw]
    if crop.size == 0:
        return None
    big = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    spec = {'roi': [0, 0, big.shape[1], big.shape[0]]}
    if os.path.exists(TPL):
        spec['templates'] = TPL
    ms = CostNumberRecognizer().run(big, spec, None, (0, 0))
    return int(ms[0].extra['cost']) if ms else None


def main() -> int:
    img = cv2.imread(os.path.join(TMP, 'axisdep_D6.png'))
    print('真值 =', TRUTH)
    best = None
    for (y0, y1) in ((884, 940), (890, 934), (878, 946), (896, 942)):
        for sc in (1.5, 1.8, 2.1):
            got = [read_small(img, cx, y0, y1, 30, sc) for cx in XS]
            ok = sum(1 for a, b in zip(got, TRUTH) if a == b)
            print(f'  y {y0}..{y1} ×{sc}: 命中 {ok}/{len(TRUTH)}  读数={got}')
            if best is None or ok > best[0]:
                best = (ok, y0, y1, sc, got)
    print(f'\n最佳 命中 {best[0]}/{len(TRUTH)}  y {best[1]}..{best[2]} ×{best[3]}  读数={best[4]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
