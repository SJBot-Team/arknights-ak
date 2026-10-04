# -*- coding: utf-8 -*-
"""读某录像右下角「费用数字」区域，按时间拼图（用于判定回费/消耗轨迹）"""
import os
import sys
import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
V = sys.argv[1]
T0, T1, STEP = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
OUT = sys.argv[5]
cap = cv2.VideoCapture(V)
fps = cap.get(cv2.CAP_PROP_FPS)
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
# 费用数字：右下角（据 1600x900 全帧定位 ≈ (1511,636)）
x0, x1 = int(w * 0.895), int(w * 0.985)
y0, y1 = int(h * 0.675), int(h * 0.725)
tiles = []
t = T0
while t <= T1:
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
    ok, fr = cap.read()
    if ok:
        crop = fr[y0:y1, x0:x1]
        crop = cv2.resize(crop, (180, 56), interpolation=cv2.INTER_CUBIC)
        cv2.putText(crop, f'{t:.0f}', (3, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        tiles.append(crop)
    t += STEP
cap.release()
rows = []
for i in range(0, len(tiles), 5):
    chunk = tiles[i:i + 5]
    while len(chunk) < 5:                      # 补齐末行，保证宽度一致
        chunk.append(np.zeros_like(chunk[0]))
    rows.append(np.hstack(chunk))
sheet = np.vstack(rows)
cv2.imwrite(OUT, sheet)
print('写入', OUT, sheet.shape)
