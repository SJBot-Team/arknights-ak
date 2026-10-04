# -*- coding: utf-8 -*-
"""analyze_spawn_frames.py — 从实机采样帧里自动定位「敌人首次出现在门口」的时刻。

目的（§7.49 的定案）：实机首漏 ≈44.3s（战斗时间）。若首只敌人的**出生时刻**不是模拟器的 5.0s，
那偏差在「波次时间表」而不是「移动速度/路径」。本脚本对指定区域做逐帧差分能量，
输出每个区域首次出现持续变化的时刻（= 有单位出现/开始移动）。

区域按列向标定 pitch_x=130, x0=97；行向用 pitch_y=86, y0=140 作粗定位（透视会带来误差，只用于开窗）。
用法：analyze_spawn_frames.py <帧目录> [起始战斗时间偏移秒]
"""
import os
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
FRAMES = sys.argv[1] if len(sys.argv) > 1 else r'C:\Users\23922\Documents\ds_harness\ak\.tmp\runframes'
OFFSET = float(sys.argv[2]) if len(sys.argv) > 2 else 11.5     # 采样 t → 战斗 t

# 采样间隔（run_drill_and_measure 用 2.0s，截图耗时让实际间隔略大）
H, W = 1080, 1920
PX, PY, X0, Y0 = 130.0, 86.0, 97.0, 140.0


def cell_box(row, col, w=1, h=1):
    """屏幕格（row 自顶向下）→ 像素框。"""
    x = X0 + col * PX
    y = Y0 + row * PY
    return int(x + PX * 0.15), int(y + PY * 0.15), int(x + PX * 0.85), int(y + PY * 0.85)


REGIONS = {
    '左门(1,0)': cell_box(7, 0),           # 内部 row1 → 屏幕 row 7
    '左门(2,0)': cell_box(6, 0),
    '左门(5,0)': cell_box(3, 0),
    '中门(1,5)': cell_box(7, 5),
    '中门(3,6)': cell_box(5, 6),
    '蓝门(8,8)': cell_box(0, 8),
    '蓝门(8,10)': cell_box(0, 10),
}


def main():
    files = sorted(f for f in os.listdir(FRAMES) if f.endswith('.png'))
    print(f'{len(files)} 帧')
    prev = None
    series = {k: [] for k in REGIONS}
    for i, fn in enumerate(files):
        img = cv2.imread(os.path.join(FRAMES, fn), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        if prev is not None:
            d = cv2.absdiff(img, prev)
            for k, (x0, y0, x1, y1) in REGIONS.items():
                roi = d[y0:y1, x0:x1]
                series[k].append((i * 2.0 - OFFSET, float(roi.mean())))
        prev = img

    print('\n=== 各区域「帧间差」时间线（数值=平均像素差；战斗时间）===')
    for k, s in series.items():
        vals = [v for _, v in s]
        if not vals:
            continue
        base = float(np.median(vals))
        thr = base + max(2.0, 3.0 * float(np.std(vals)))
        first = next((t for t, v in s if v > thr), None)
        print(f'  {k:<12} 基线 {base:5.2f} 阈值 {thr:5.2f}  '
              f'首次越阈 {"%.1fs" % first if first is not None else "无"}')
        top = sorted(s, key=lambda x: -x[1])[:4]
        print(f'      最大波动: ' + ', '.join(f'{t:.0f}s:{v:.1f}' for t, v in top))


if __name__ == '__main__':
    main()
