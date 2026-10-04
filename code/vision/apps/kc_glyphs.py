# -*- coding: utf-8 -*-
"""kc_glyphs.py — 把「击破数」计数器的字形聚成少量簇并输出**放大拼图**，便于人工一次定标。

背景：tesseract 在本游戏字体上会**系统性误读**（实测 `0→6`、`5→6`、顶部小字 `3→2`），
因此本工具不依赖 OCR，而是：
1. 只对"ROI 变化帧"提取连通域字形；
2. 归一化后按汉明距离聚类；
3. 输出放大拼图（标注簇号 + 出现次数）⇒ **人工看一次即可固化整张字体表**。

用法：
    python apps/kc_glyphs.py <video> <kc.jsonl> <out.png> [--roi x0,y0,x1,y1]
"""
from __future__ import annotations

import argparse
import json
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

KC_ROI = (812, 26, 930, 60)
GLYPH_W, GLYPH_H = 16, 22
TOL_BITS = 20


def _vec(crop: np.ndarray) -> np.ndarray:
    small = cv2.resize(crop, (GLYPH_W, GLYPH_H), interpolation=cv2.INTER_AREA)
    return (small > 110).astype(np.uint8).ravel()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('kc')
    ap.add_argument('out')
    ap.add_argument('--roi', default='')
    ap.add_argument('--hmin', type=int, default=12)
    ap.add_argument('--hmax', type=int, default=34)
    ap.add_argument('--order', default=None, help='额外的"顺序帧"列表（逗号分隔）')
    a = ap.parse_args()
    roi = tuple(int(v) for v in a.roi.split(',')) if a.roi else KC_ROI
    x0, y0, x1, y1 = roi

    frames = [json.loads(l)['f'] for l in open(a.kc, encoding='utf-8')]
    want = set(frames)
    if a.order:
        want |= {int(v) for v in a.order.split(',') if v.strip()}

    vecs: list[np.ndarray] = []
    crops: list[np.ndarray] = []
    counts: list[int] = []
    cap = cv2.VideoCapture(a.video)
    i = 0
    mx = max(want)
    while True:
        if not cap.grab():
            break
        if i in want:
            ok, img = cap.retrieve()
            if ok and img is not None:
                g = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
                th = max(110, int(0.60 * float(g.max())))
                _, b = cv2.threshold(g, th, 255, cv2.THRESH_BINARY)
                n, _l, stats, _c = cv2.connectedComponentsWithStats(b, 8)
                for k in range(1, n):
                    x, y, w, h, area = (int(stats[k, 0]), int(stats[k, 1]), int(stats[k, 2]),
                                        int(stats[k, 3]), int(stats[k, 4]))
                    if not (a.hmin <= h <= a.hmax and 2 <= w <= 30 and area >= 15):
                        continue
                    c = b[y:y + h, x:x + w].copy()
                    v = _vec(c)
                    best, bd = -1, 10 ** 9
                    for j, u in enumerate(vecs):
                        d = int(np.count_nonzero(u != v))
                        if d < bd:
                            best, bd = j, d
                    if best >= 0 and bd <= TOL_BITS:
                        counts[best] += 1
                    else:
                        vecs.append(v)
                        crops.append(c)
                        counts.append(1)
        if i >= mx:
            break
        i += 1
    cap.release()

    print(f'字形簇 {len(vecs)} 个')
    order = sorted(range(len(vecs)), key=lambda j: -counts[j])
    for j in order:
        print(f'  簇{j:>3} n={counts[j]}')
    cw, ch, cols = 90, 110, 8
    rr = (len(order) + cols - 1) // cols
    sheet = np.zeros((max(1, rr) * (ch + 20), cols * cw, 3), np.uint8)
    for pos, j in enumerate(order):
        r0, c0 = divmod(pos, cols)
        yy = r0 * (ch + 20)
        cv2.putText(sheet, f'#{j} n={counts[j]}', (c0 * cw + 4, yy + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1, cv2.LINE_AA)
        im = cv2.cvtColor(crops[j], cv2.COLOR_GRAY2BGR)
        im = cv2.resize(im, (im.shape[1] * 4, im.shape[0] * 4), interpolation=cv2.INTER_NEAREST)
        h2, w2 = im.shape[:2]
        sheet[yy + 20:yy + 20 + min(h2, ch + 10), c0 * cw + 4:c0 * cw + 4 + min(w2, cw - 8)] = \
            im[:min(h2, ch + 10), :min(w2, cw - 8)]
    cv2.imwrite(a.out, sheet)
    print('拼图已写出', a.out, sheet.shape)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
