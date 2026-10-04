# -*- coding: utf-8 -*-
"""grid_calib.py — 从战斗截图估计地图格点（9×13）→ 像素的线性映射

做法：地图区域内的**瓦片接缝**在 x/y 方向形成周期性强边缘：
  1. 取地图区域（排除上下 UI）；
  2. 计算列方向梯度能量（竖缝）与行方向梯度能量（横缝）；
  3. 用自相关估计周期 pitch，用相位找第一条缝的位置；
  4. 输出 battle_area = (x0, y0, x0 + cols*pitch_x, y0 + rows*pitch_y)，并给出置信度（自相关峰高）。
"""
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
IMG = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\23922\Documents\ds_harness\ak\.tmp\shot_mumu_5.png'
ROWS, COLS = 9, 13
Y0, Y1 = 140, 880          # 地图纵向范围（避开顶部 HUD 与底部卡槽）
X0, X1 = 0, 1580           # 地图横向范围（避开右侧费用区）

img = cv2.imread(IMG)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype('float32')
roi = gray[Y0:Y1, X0:X1]

# 竖缝：x 方向梯度
gx = np.abs(cv2.Sobel(roi, cv2.CV_32F, 1, 0, ksize=3)).mean(axis=0)
gy = np.abs(cv2.Sobel(roi, cv2.CV_32F, 0, 1, ksize=3)).mean(axis=1)


def period(sig, lo, hi):
    """在 [lo,hi] 像素范围内用自相关找周期，并返回相位（第一条缝的位置）。"""
    s = sig - sig.mean()
    ac = np.correlate(s, s, mode='full')[len(s) - 1:]
    ac = ac / (ac[0] + 1e-9)
    seg = ac[lo:hi]
    p = lo + int(np.argmax(seg))
    # 相位：把信号按周期折叠，取能量最大的相位
    ph = np.zeros(p, dtype='float32')
    for i, v in enumerate(sig):
        ph[i % p] += max(0.0, v)
    phase = int(np.argmax(ph))
    return p, phase, float(ac[p])


px, phx, confx = period(gx, 90, 260)
py, phy, confy = period(gy, 60, 200)
print(f'横向：周期 {px}px 相位 {phx} 置信 {confx:.3f} → 13 列宽 {px*COLS}px')
print(f'纵向：周期 {py}px 相位 {phy} 置信 {confy:.3f} → 9 行高 {py*ROWS}px')

# 以相位为瓦片边界起点（相位是“缝”的偏移）
bx0 = X0 + phx
by0 = Y0 + phy
print(f'推定 battle_area = ({bx0}, {by0}, {bx0 + px*COLS}, {by0 + py*ROWS})')

# 叠加可视化：按推定格点画线
vis = img.copy()
for i in range(COLS + 1):
    x = int(bx0 + i * px)
    cv2.line(vis, (x, by0), (x, by0 + py * ROWS), (0, 255, 0), 2)
for j in range(ROWS + 1):
    y = int(by0 + j * py)
    cv2.line(vis, (bx0, y), (bx0 + px * COLS, y), (0, 255, 0), 2)
out = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\grid_overlay.png'
cv2.imwrite(out, cv2.resize(vis, (960, 540)))
print('叠加图 →', out)
