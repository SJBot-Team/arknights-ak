# -*- coding: utf-8 -*-
"""frames_at_game.py — 按**游戏帧**取视频帧（用 video_axis.py 产出的轴表反查）

用法：
    python apps/frames_at_game.py <axis.jsonl> <video> <out.png> <g1,g2,...>
                                  [--roi x0,y0,x1,y1] [--zoom 1] [--cols 3] [--tol 3]

要点：
- 轴表每行 `{f, px, g, A, B, cost}`，`B` 即游戏帧（回费计数时钟）。
- 反查：取 `|B - 目标|` 最小的视频帧（可加 `--tol` 限制）。
- **顺序读取**视频（不做连续 seek）。
"""
from __future__ import annotations

import argparse
import json
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('axis')
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('targets', help='逗号分隔的游戏帧')
    ap.add_argument('--roi', default='')
    ap.add_argument('--zoom', type=float, default=1.0)
    ap.add_argument('--cols', type=int, default=2)
    ap.add_argument('--tol', type=float, default=8.0)
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.axis, encoding='utf-8')]
    B = np.array([r['B'] for r in rows], dtype=float)
    F = np.array([r['f'] for r in rows], dtype=int)
    targets = [float(v) for v in a.targets.split(',') if v.strip()]
    picks = []
    for g in targets:
        i = int(np.argmin(np.abs(B - g)))
        ok = abs(B[i] - g) <= a.tol
        picks.append((g, int(F[i]), float(B[i]), ok))
        print(f'游戏帧 {g:>7.1f} → 视频帧 {int(F[i]):>6} (轴值 {B[i]:.1f}'
              f'{"  OK" if ok else "  ★超出容差"})')

    want = {p[1] for p in picks}
    mx = max(want)
    got: dict[int, np.ndarray] = {}
    cap = cv2.VideoCapture(a.video)
    i = 0
    while True:
        if not cap.grab():
            break
        if i in want:
            ok, fr = cap.retrieve()
            if ok and fr is not None:
                got[i] = fr.copy()
        if i >= mx:
            break
        i += 1
    cap.release()

    if a.roi:
        x0, y0, x1, y1 = (int(v) for v in a.roi.split(','))
    else:
        x0 = y0 = 0
        y1, x1 = got[picks[0][1]].shape[:2] if picks[0][1] in got else (1080, 1920)

    z = a.zoom
    cells = []
    for g, f, b, ok in picks:
        img = got.get(f)
        if img is None:
            continue
        crop = img[y0:y1, x0:x1]
        crop = cv2.resize(crop, None, fx=z, fy=z, interpolation=cv2.INTER_AREA)
        label = f'game {g:.0f} / video f{f} (axis {b:.1f})'
        h = crop.shape[0]
        cv2.rectangle(crop, (0, h - 22), (len(label) * 9 + 8, h), (0, 0, 0), -1)
        cv2.putText(crop, label, (4, h - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1,
                    cv2.LINE_AA)
        cells.append(crop)
    if not cells:
        print('未取到帧')
        return 2
    cols = a.cols
    ch, cw = cells[0].shape[:2]
    rr = (len(cells) + cols - 1) // cols
    sheet = np.zeros((rr * ch, cols * cw, 3), np.uint8)
    for k, c in enumerate(cells):
        r0, c0 = divmod(k, cols)
        sheet[r0 * ch:r0 * ch + c.shape[0], c0 * cw:c0 * cw + c.shape[1]] = c
    cv2.imwrite(a.out, sheet)
    print('已写出', a.out, sheet.shape)
    return 0


if __name__ == '__main__':
    sys.exit(main())
