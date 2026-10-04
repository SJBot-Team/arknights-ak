# -*- coding: utf-8 -*-
"""find_costbar.py — 在视频帧中自动定位费用条（偏黄/白色水平条 + 锯齿时序特征）"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import cv2
import numpy as np

FR = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\frames'
img = cv2.imread(os.path.join(FR, 'frame_040s.png'))
H, W = img.shape[:2]
b, g, r = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
# 黄色/亮色掩码：R,G 高且 B 明显低（费用条为金色渐变）
yellow = ((r > 120) & (g > 100) & (b < 120) & (r > b + 40)).astype(np.uint8)
rowsum = yellow.sum(axis=1)
print('=== 偏黄像素最多的行（前 15）===')
for y in np.argsort(-rowsum)[:15]:
    print(f'  y={y:<4} 黄色像素 {rowsum[y]:<5} 占比 {rowsum[y]/W:.2%}')
# 白色亮条掩码
bright = ((r > 200) & (g > 200) & (b > 200)).astype(np.uint8)
browsum = bright.sum(axis=1)
print('=== 亮白像素最多的行（前 10）===')
for y in np.argsort(-browsum)[:10]:
    print(f'  y={y:<4} 亮白像素 {browsum[y]:<5} 占比 {browsum[y]/W:.2%}')
# 保存掩码可视化
vis = (yellow * 255).astype(np.uint8)
cv2.imwrite(os.path.join(FR, 'mask_yellow.png'), vis)
print('掩码已存 mask_yellow.png')
# 逐列分析：检查中部区域是否存在短横条（费用条候选）
for y0, y1 in ((30, 90), (90, 200), (380, 470), (470, 520), (520, 590)):
    band = yellow[y0:y1].sum()
    print(f'  区域 y {y0}-{y1}: 黄色像素 {band}')
