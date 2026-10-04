# -*- coding: utf-8 -*-
"""locate_costbar_video.py — 在视频帧上精确定位「费用条」与「费用数字」的像素坐标。

方法（不依赖人肉试坐标）：
1. 顺序推进到目标帧（避免 seek 精度问题）；
2. 在给定大区域内做**白色像素**掩膜（低饱和 + 高亮度）；
3. 按行统计白色像素数 → 找出"长横条"所在的行（费用条）；
4. 在条所在行带内按列统计 → 给出条起止 x；
5. 同时给出"大号数字"的连通域包围盒（费用数字）。
"""
from __future__ import annotations

import argparse
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

VID = r'E:\MUMU共享文件夹\VideoRecords\1-1标定.mp4'


def grab(vid: str, f: int) -> np.ndarray | None:
    cap = cv2.VideoCapture(vid)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, f - 2))
    img = None
    cur = max(0, f - 2)
    while cur <= f:
        ok, fr = cap.read()
        if not ok:
            break
        if cur == f:
            img = fr
        cur += 1
    cap.release()
    return img


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--video', default=VID)
    ap.add_argument('--frames', default='800,1500,3000,6000')
    ap.add_argument('--zone', default='1600,700,1920,900', help='x0,y0,x1,y1')
    a = ap.parse_args()
    x0, y0, x1, y1 = (int(v) for v in a.zone.split(','))

    for f in (int(v) for v in a.frames.split(',')):
        img = grab(a.video, f)
        if img is None:
            print(f'帧 {f}: 读取失败')
            continue
        sub = img[y0:y1, x0:x1]
        hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
        white = ((hsv[:, :, 2] > 190) & (hsv[:, :, 1] < 80)).astype(np.uint8)
        rows = white.sum(axis=1)
        print(f'\n=== 帧 {f}  区域 {a.zone}  高度 {sub.shape[0]} ===')
        cand = [(int(r), int(v)) for r, v in enumerate(rows) if v >= 60]
        print('  长横条候选行（白像素≥60）:', cand[:20])
        if cand:
            r0 = min(c[0] for c in cand)
            r1 = max(c[0] for c in cand)
            band = white[r0:r1 + 1]
            cols = band.sum(axis=0)
            on = cols >= max(1, (r1 - r0 + 1) // 2)
            runs, s = [], None
            for i, v in enumerate(on):
                if v and s is None:
                    s = i
                elif not v and s is not None:
                    if i - s >= 4:
                        runs.append((x0 + s, x0 + i, i - s))
                    s = None
            if s is not None:
                runs.append((x0 + s, x0 + len(on), len(on) - s))
            print(f'  条带 y = {y0 + r0} ~ {y0 + r1}（高 {r1 - r0 + 1}）')
            print(f'  该带内白色横段 (x起, x止, 长): {runs}')
        # 数字连通域（在条带上方区域找）
        top = white[:max(1, (cand[0][0] - 4) if cand else white.shape[0])]
        n, lab, stats, cent = cv2.connectedComponentsWithStats(top, 8)
        boxes = [(int(stats[i, 0]) + x0, int(stats[i, 1]) + y0,
                  int(stats[i, 2]), int(stats[i, 3]), int(stats[i, 4]))
                 for i in range(1, n) if stats[i, 4] >= 30]
        boxes.sort(key=lambda b: -b[4])
        print('  上方连通域 (x, y, w, h, area) 前 8:', boxes[:8])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
