# -*- coding: utf-8 -*-
"""montage_roi.py — 顺序读取视频，在等间隔帧上裁剪同一 ROI 并按放大倍数拼图。

用途：确认 HUD/ROI 在整段视频中位置稳定、以及放大目视各元素（费用数字/费用条）。
性能要点：**一次顺序遍历**，不做 seek（seek 精度不足）。
"""
from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--roi', required=True, help='x0,y0,x1,y1')
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--end', type=int, default=-1)
    ap.add_argument('--n', type=int, default=24)
    ap.add_argument('--zoom', type=int, default=3)
    ap.add_argument('--cols', type=int, default=4)
    a = ap.parse_args()
    x0, y0, x1, y1 = (int(v) for v in a.roi.split(','))

    cap = cv2.VideoCapture(a.video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    end = total if a.end < 0 else min(a.end, total)
    step = max(1, (end - a.start) // a.n)
    targets = list(range(a.start, end, step))[:a.n]
    want = set(targets)
    last = max(targets)
    got: dict[int, np.ndarray] = {}
    i = 0
    while True:
        if not cap.grab():
            break
        if i in want:
            ok, fr = cap.retrieve()
            if ok and fr is not None:
                got[i] = fr[y0:y1, x0:x1].copy()
        if i >= last:
            break
        i += 1
    cap.release()
    ks = [t for t in targets if t in got]
    print('取到', len(ks), '帧')

    z = a.zoom
    th, tw = (y1 - y0) * z, (x1 - x0) * z
    cols = a.cols
    rows = (len(ks) + cols - 1) // cols
    sheet = np.zeros((rows * (th + 18), cols * tw, 3), np.uint8)
    for k, t in enumerate(ks):
        r, c = divmod(k, cols)
        y = r * (th + 18)
        cv2.putText(sheet, f'f{t}', (c * tw + 3, y + 13), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (0, 255, 0), 1, cv2.LINE_AA)
        sheet[y + 18:y + 18 + th, c * tw:(c + 1) * tw] = cv2.resize(
            got[t], (tw, th), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(a.out, sheet)
    print('已写出', a.out, sheet.shape)
    return 0


if __name__ == '__main__':
    sys.exit(main())
