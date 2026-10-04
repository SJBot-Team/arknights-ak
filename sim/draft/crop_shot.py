# -*- coding: utf-8 -*-
"""crop_shot.py — 把实机截图切成九宫格放大，便于逐个格子读地形/门位。"""
import os
import sys

try:
    import cv2
except Exception as e:
    print('need cv2:', e)
    raise

SRC = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\23922\Documents\ds_harness\ak\.tmp\grid_overlay.png'
OUT = sys.argv[2] if len(sys.argv) > 2 else r'C:\Users\23922\Documents\ds_harness\ak\.tmp\crop'
os.makedirs(OUT, exist_ok=True)
img = cv2.imread(SRC)
h, w = img.shape[:2]
print('src', w, 'x', h)
for i, (name, y0, y1, x0, x1) in enumerate([
        ('TL', 0, h // 2, 0, w // 2), ('TR', 0, h // 2, w // 2, w),
        ('BL', h // 2, h, 0, w // 2), ('BR', h // 2, h, w // 2, w)]):
    crop = img[y0:y1, x0:x1]
    crop = cv2.resize(crop, (crop.shape[1] * 2, crop.shape[0] * 2), interpolation=cv2.INTER_CUBIC)
    p = os.path.join(OUT, f'{name}.png')
    cv2.imwrite(p, crop)
    print('  ->', p, crop.shape[1], 'x', crop.shape[0])
