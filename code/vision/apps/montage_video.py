# -*- coding: utf-8 -*-
"""montage_video.py — 把视频按等间隔抽帧拼成一张大图，用于人工/模型快速浏览全局。

用法:
    python montage_video.py <video> <out.png> [--start 0] [--end N] [--n 36]
                            [--scale 0.25] [--cols 6]

设计要点（★性能/正确性）:
- **必须顺序读取**：`cap.set(CAP_PROP_POS_FRAMES)` 的 seek 精度不足
  （此前实测：连续 seek 会导致像素恒为 0、费用跳变）。
  故本脚本只做**一次顺序遍历**，在目标帧号处取帧，读完即止。
- 每个小格左上角烧录**真实帧号**（从顺序计数得到，而不是估计）。
- 输出图不缩放原始分辨率之外的任何东西，按 `--scale` 逐帧缩放后拼接。
"""
from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--end', type=int, default=-1, help='不含；-1 = 到结尾')
    ap.add_argument('--n', type=int, default=36, help='抽取帧数')
    ap.add_argument('--scale', type=float, default=0.25)
    ap.add_argument('--cols', type=int, default=6)
    a = ap.parse_args()

    cap = cv2.VideoCapture(a.video)
    if not cap.isOpened():
        print('无法打开视频', a.video)
        return 2
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    start = a.start
    end = total if a.end < 0 else min(a.end, total)
    if end <= start:
        print('区间为空')
        return 2

    span = end - start
    step = max(1, span // a.n)
    targets = list(range(start, end, step))[:a.n]
    want = set(targets)

    frames: dict[int, np.ndarray] = {}
    i = 0
    last = max(targets)
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i in want:
            ok2, fr = cap.retrieve()
            if ok2 and fr is not None:
                frames[i] = fr
        if i >= last:
            break
        i += 1
    cap.release()

    got = [t for t in targets if t in frames]
    print(f'总帧 {total} fps {fps:.3f}；目标 {len(targets)} 帧，实取 {len(got)} 帧')
    if not got:
        return 2

    h, w = frames[got[0]].shape[:2]
    tw, th = int(w * a.scale), int(h * a.scale)
    cols = a.cols
    rows = (len(got) + cols - 1) // cols
    sheet = np.zeros((rows * th, cols * tw, 3), np.uint8)
    for k, t in enumerate(got):
        r, c = divmod(k, cols)
        small = cv2.resize(frames[t], (tw, th), interpolation=cv2.INTER_AREA)
        cv2.rectangle(small, (0, 0), (tw - 1, th - 1), (60, 60, 60), 1)
        label = f'f{t} t{t / fps:.1f}s'
        cv2.rectangle(small, (0, 0), (len(label) * 8 + 6, 16), (0, 0, 0), -1)
        cv2.putText(small, label, (3, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (0, 255, 0), 1, cv2.LINE_AA)
        sheet[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = small
    cv2.imwrite(a.out, sheet)
    print('已写出', a.out, sheet.shape)
    return 0


if __name__ == '__main__':
    sys.exit(main())
