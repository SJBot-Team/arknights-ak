# -*- coding: utf-8 -*-
"""measure_cost_cap.py — 实机采样右下角费用区，测「费用上限随时间的变化」。

用途（§7.47 的定案实验）：h12-4 上限 = 20 + 5×被拆储备 + 2×到达平民。
作者作战记录说 29.0s 就落了第一条弦惊（23 费）⇒ 上限必须在那之前抬到 ≥23。
本脚本每 N 秒截一帧，裁出费用区并拼成一张时间轴图，直接看：
  · 数字何时突破 20（= 上限抬升过）
  · 「MAX」标记何时消失（= 当前费用低于上限）

用法：measure_cost_cap.py <总时长秒> [间隔秒]
"""
import os
import subprocess
import sys
import time

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
# 费用数字 + MAX 标记（MuMu12 1920x1080 实测）
ROI = (1700, 700, 1920, 860)


def grab(dst: str) -> bool:
    with open(dst, 'wb') as f:
        p = subprocess.run([ADB, '-s', DEV, 'exec-out', 'screencap', '-p'],
                           stdout=f, stderr=subprocess.DEVNULL)
    return p.returncode == 0 and os.path.getsize(dst) > 10000


def main():
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    step = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
    os.makedirs(os.path.join(OUT, 'capframes'), exist_ok=True)
    tiles = []
    t0 = time.time()
    i = 0
    while time.time() - t0 < total:
        p = os.path.join(OUT, 'capframes', f'f{i:03d}.png')
        if grab(p):
            img = cv2.imread(p)
            x0, y0, x1, y1 = ROI
            crop = img[y0:y1, x0:x1]
            crop = cv2.resize(crop, (crop.shape[1] * 2, crop.shape[0] * 2),
                              interpolation=cv2.INTER_CUBIC)
            lab = f'{time.time()-t0:5.1f}s'
            cv2.putText(crop, lab, (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(crop, lab, (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (255, 255, 255), 2, cv2.LINE_AA)
            tiles.append(crop)
        i += 1
        time.sleep(max(0.0, step - 1.2))     # 截图本身约 1.2s
    if tiles:
        h = max(t.shape[0] for t in tiles)
        w = max(t.shape[1] for t in tiles)
        canvas = np.full((h * len(tiles) + 4 * len(tiles), w, 3), 30, np.uint8)
        for k, t in enumerate(tiles):
            canvas[k * (h + 4):k * (h + 4) + t.shape[0], :t.shape[1]] = t
        # 太长则分两张
        half = max(1, len(tiles) // 2)
        for part, chunk in enumerate((tiles[:half], tiles[half:])):
            if not chunk:
                continue
            hh = max(t.shape[0] for t in chunk)
            cc = np.full((hh * len(chunk) + 4 * len(chunk), w, 3), 30, np.uint8)
            for k, t in enumerate(chunk):
                cc[k * (hh + 4):k * (hh + 4) + t.shape[0], :t.shape[1]] = t
            wp = os.path.join(OUT, f'cap_timeline_{part}.png')
            cv2.imwrite(wp, cv2.resize(cc, (cc.shape[1] // 2, cc.shape[0] // 2)))
            print('写出', wp, cc.shape)
    print(f'采样 {len(tiles)} 帧 / {total}s')


if __name__ == '__main__':
    main()
