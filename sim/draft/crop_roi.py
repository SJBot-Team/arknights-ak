# -*- coding: utf-8 -*-
"""crop_roi.py — 按 ROI 裁剪并放大（查看实机截图局部细节）。

用法：crop_roi.py <src> <name> <x0> <y0> <x1> <y1> [scale]
"""
import os
import sys

import cv2

sys.stdout.reconfigure(encoding='utf-8')
src = sys.argv[1]
name = sys.argv[2]
x0, y0, x1, y1 = (int(v) for v in sys.argv[3:7])
scale = float(sys.argv[7]) if len(sys.argv) > 7 else 2.0
img = cv2.imread(src)
print('src', img.shape[1], 'x', img.shape[0])
crop = img[y0:y1, x0:x1]
crop = cv2.resize(crop, (int(crop.shape[1] * scale), int(crop.shape[0] * scale)),
                  interpolation=cv2.INTER_CUBIC)
out = os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\.tmp', f'roi_{name}.png')
cv2.imwrite(out, crop)
print('->', out, crop.shape[1], 'x', crop.shape[0])
