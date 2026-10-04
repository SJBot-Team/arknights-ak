# -*- coding: utf-8 -*-
"""calibrate_battle_area.py — 从实机战斗截图标定「9×13 格 → 屏幕像素」映射（需求 2.6 的 TODO）。

做法（比自相关稳）：
  1. 在若干水平/垂直窄带里做梯度投影，找出瓦片接缝的周期与相位；
  2. 用已知地块（h12-4 的两个「街头应急储备」在 (5,6)/(5,7)）交叉验证列间距；
  3. 输出 battle_area = (x0, y0, pitch_x, pitch_y) 与 9×13 的中心像素表，
     并给「屏幕格(row,col)」的换算函数（屏幕 row 0 = 屏幕最上方 = 关卡 row 8）。

用法：calibrate_battle_area.py <png> [--dump]
"""
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
ROWS, COLS = 9, 13


def seams(sig: np.ndarray, lo: int, hi: int):
    """在 [lo,hi] 里找最强周期与其相位（缝的位置）。返回 (period, phase, score)。"""
    s = sig - sig.mean()
    ac = np.correlate(s, s, mode='full')[len(s) - 1:]
    ac = ac / (ac[0] + 1e-9)
    seg = ac[lo:hi]
    p = lo + int(np.argmax(seg))
    ph = np.zeros(p)
    for i, v in enumerate(s):
        ph[i % p] += max(0.0, v)
    return p, int(np.argmax(ph)), float(ac[p])


def main():
    png = sys.argv[1]
    img = cv2.imread(png)
    h, w = img.shape[:2]
    print(f'图像 {w}×{h}')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype('float32')

    # 竖缝：取地图中部横向带（避开上下 UI）
    res_x = []
    for y0, y1 in ((300, 380), (500, 580), (620, 700), (760, 840)):
        band = gray[y0:y1, 60:1800]
        gx = np.abs(cv2.Sobel(band, cv2.CV_32F, 1, 0, ksize=3)).mean(axis=0)
        p, ph, sc = seams(gx, 90, 200)
        res_x.append((p, ph + 60, sc, (y0, y1)))
    print('\n横向（列）候选：')
    for p, ph, sc, band in res_x:
        print(f'  带 {band}: 周期 {p}px 相位 {ph} 置信 {sc:.3f}  → 13 列宽 {p*COLS}px 起点 {ph}')
    px, phx, scx, _ = max(res_x, key=lambda t: t[2])

    res_y = []
    for x0, x1 in ((150, 600), (700, 1150), (1250, 1700)):
        band = gray[100:960, x0:x1]
        gy = np.abs(cv2.Sobel(band, cv2.CV_32F, 0, 1, ksize=3)).mean(axis=1)
        p, ph, sc = seams(gy, 60, 160)
        res_y.append((p, ph + 100, sc, (x0, x1)))
    print('\n纵向（行）候选：')
    for p, ph, sc, band in res_y:
        print(f'  带 {band}: 周期 {p}px 相位 {ph} 置信 {sc:.3f}  → 9 行高 {p*ROWS}px 起点 {ph}')
    py, phy, scy, _ = max(res_y, key=lambda t: t[2])

    print(f'\n>>> 推定 pitch=({px},{py})  origin=({phx},{phy})  '
          f'13 列 {px*COLS}px / 9 行 {py*ROWS}px')
    print('    屏幕格 (row,col) 中心像素：')
    for r in range(ROWS):
        row = []
        for c in range(COLS):
            cx = int(phx + (c + 0.5) * px)
            cy = int(phy + (r + 0.5) * py)
            row.append(f'{cx:>4}')
        print(f'   r{r}: ' + ' '.join(row))
    print('    行的 y 中心：', [int(phy + (r + 0.5) * py) for r in range(ROWS)])
    # 参考点：h12-4 两个应急储备在关卡 (5,6)/(5,7) = 屏幕行 3
    sr = ROWS - 1 - 5
    print(f'    交叉验证：储备(5,6)/(5,7) → 屏幕行 {sr}，'
          f'列 6/7 中心 x = {int(phx+(6+0.5)*px)} / {int(phx+(7+0.5)*px)}，'
          f'y = {int(phy+(sr+0.5)*py)}')


if __name__ == '__main__':
    main()
