# -*- coding: utf-8 -*-
"""诊断：打印费用 ROI 内每个字形的 (x, w, h, 墨密度, 宽高比)，用于区分费用图标与数字"""
import sys
import cv2
import numpy as np

sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\code\vision\apps')
sys.stdout.reconfigure(encoding='utf-8')
from video_cost_timeline import lock_roi, frame_at

V = r'E:\MUMU共享文件夹\VideoRecords\H12-4\双\明日方舟(128).mp4'
cap = cv2.VideoCapture(V)
fps = cap.get(cv2.CAP_PROP_FPS)
roi = lock_roi(cap, fps)[:4]
print('ROI =', roi)
x0, y0, x1, y1 = roi
for t in (2, 5, 8, 14, 20, 23, 32, 41, 44, 62):
    fr = frame_at(cap, fps, t)
    g = cv2.cvtColor(fr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    ink = (g > 195).astype(np.uint8)
    cols = ink.sum(axis=0)
    groups, start = [], None
    for i, c in enumerate(cols):
        if c > 0 and start is None:
            start = i
        elif c == 0 and start is not None:
            groups.append((start, i))
            start = None
    if start is not None:
        groups.append((start, len(cols)))
    print(f'--- t={t}s ---')
    for (a, b) in groups:
        sub = ink[:, a:b]
        rows = np.where(sub.sum(axis=1) > 0)[0]
        if len(rows) == 0:
            continue
        top, bot = rows[0], rows[-1] + 1
        h = bot - top
        w = b - a
        dens = sub[top:bot].mean()
        print(f'   x={x0+a:>5}..{x0+b:<5} w={w:<3} h={h:<3} 密度={dens:.2f} 宽高比={w/max(1,h):.2f}')
cap.release()
