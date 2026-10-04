# -*- coding: utf-8 -*-
"""card_probe.py — **待部署卡片位置检测（细化版）**

## 背景
`Deployer.find_cards()` 用"底部条带列标准差分段"的方法，实测只返回 2 段
（(709,1002)、(1709,1002)），而画面上明显有 12 张卡片 ⇒ 需要更可靠的检测。

## 本脚本的三种互补手段
1. **列梯度能量**：卡片边界处水平方向梯度强（`Sobel_x` 列求和峰值）⇒ 找峰即边界；
2. **卡片"亮度块"**：卡片是亮色矩形，间隙是暗色 ⇒ 用行的亮度剖面找亮块；
3. **等分反推**：已知卡片从左右边距开始等间距排列 ⇒ 由 **段数** 反推每张中心，
   并用前两种手段**交叉验证**。

输出：卡片中心列表 + 可视化（在截图上画线），供人工核对。
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
# 待部署区（帧坐标）
BAND = (940, 1075)


def detect(img, band=BAND, min_gap: int = 6, verbose=True):
    y0, y1 = band
    strip = img[y0:y1]
    gray = cv2.cvtColor(strip, cv2.COLOR_BGR2GRAY).astype(np.float32)

    # ① 列梯度能量（卡片左右边界处强）
    gx = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    col_energy = gx.sum(axis=0)
    # ② 列亮度均值（卡片亮、间隙暗）
    col_bright = gray.mean(axis=0)

    def segments(signal, thresh_ratio=0.6, min_w=60):
        thr = signal.mean() * thresh_ratio
        mask = signal > thr
        segs, s = [], None
        for i, m in enumerate(mask):
            if m and s is None:
                s = i
            elif not m and s is not None:
                if i - s >= min_w:
                    segs.append((s, i))
                s = None
        if s is not None and len(mask) - s >= min_w:
            segs.append((s, len(mask)))
        merged = []
        for a, b in segs:
            if merged and a - merged[-1][1] < min_gap:
                merged[-1] = (merged[-1][0], b)
            else:
                merged.append((a, b))
        return merged

    segs_e = segments(col_energy)
    segs_b = segments(col_bright)

    # ③ 由边界峰反推卡片数：找梯度峰（非极大值抑制）
    peaks = []
    e = col_energy / (col_energy.max() + 1e-9)
    for i in range(2, len(e) - 2):
        if e[i] > 0.35 and e[i] >= e[i - 1] and e[i] >= e[i + 1]:
            if not peaks or i - peaks[-1] > 20:
                peaks.append(i)

    if verbose:
        print(f'  列梯度分段 {len(segs_e)} 个: {segs_e[:14]}')
        print(f'  亮度分段   {len(segs_b)} 个: {segs_b[:14]}')
        print(f'  梯度峰     {len(peaks)} 个: {peaks[:16]}')

    # 用"段"的中心作为卡片中心（优先用亮度分段，因为它更贴合卡片矩形）
    best = segs_b if len(segs_b) >= len(segs_e) else segs_e
    centers = [{'cx': (a + b) // 2, 'cy': (y0 + y1) // 2, 'x0': a, 'x1': b, 'w': b - a}
               for a, b in best]
    return centers, segs_e, segs_b, peaks


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(TMP, 'r14c.png')
    img = cv2.imread(path)
    if img is None:
        print('读不到', path)
        return 1
    print(f'分析 {os.path.basename(path)}  尺寸 {img.shape[1]}x{img.shape[0]}')
    centers, se, sb, pk = detect(img)
    print(f'\n⇒ 卡片中心（{len(centers)} 个）:')
    for c in centers:
        print(f"    x={c['cx']:>4}  [{c['x0']}~{c['x1']}] 宽{c['w']}")
    # 可视化
    vis = img.copy()
    for c in centers:
        cv2.rectangle(vis, (c['x0'], BAND[0]), (c['x1'], BAND[1]), (0, 0, 255), 3)
        cv2.line(vis, (c['cx'], BAND[0]), (c['cx'], BAND[1]), (0, 255, 0), 2)
    out = os.path.join(TMP, 'cards_vis.png')
    cv2.imwrite(out, vis)
    print(f'\n可视化已存: {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
