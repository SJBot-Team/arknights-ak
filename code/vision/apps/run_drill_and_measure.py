# -*- coding: utf-8 -*-
"""run_drill_and_measure.py — 点「开始行动」后立刻开始采样，用**费用数字当锚**测出绝对时间线。

锚点原理：费用从 initialCost 10 开始按 1/s 上涨，直到撞上限（h12-4 = 20）。
因此只要截到「费用 < 20」的帧，就有 战斗时间 t = 费用 − 10（1s 精度），
据此可以把「生命 3→2 的漏怪时刻」换算成**绝对战斗时间**，与模拟器的 37.3s/39.8s/43.7s 对比。

用法：run_drill_and_measure.py <开始行动x> <开始行动y> [总时长] [间隔]
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
ROI_TOP = (860, 0, 1420, 80)
ROI_COST = (1740, 690, 1920, 860)


def sh(*args):
    return subprocess.run([ADB, '-s', DEV, *args], capture_output=True)


def grab(dst):
    with open(dst, 'wb') as f:
        p = subprocess.run([ADB, '-s', DEV, 'exec-out', 'screencap', '-p'],
                           stdout=f, stderr=subprocess.DEVNULL)
    return p.returncode == 0 and os.path.getsize(dst) > 10000


def strip(tiles, path):
    if not tiles:
        return
    h = max(t.shape[0] for t in tiles)
    w = max(t.shape[1] for t in tiles)
    canvas = np.full((len(tiles) * (h + 4), w, 3), 20, np.uint8)
    for k, t in enumerate(tiles):
        canvas[k * (h + 4):k * (h + 4) + t.shape[0], :t.shape[1]] = t
    cv2.imwrite(path, canvas)
    print('写出', path, canvas.shape)


def main():
    x, y = int(sys.argv[1]), int(sys.argv[2])
    total = int(sys.argv[3]) if len(sys.argv) > 3 else 70
    step = float(sys.argv[4]) if len(sys.argv) > 4 else 2.0
    d = os.path.join(OUT, 'runframes')
    os.makedirs(d, exist_ok=True)
    sh('shell', 'input', 'tap', str(x), str(y))
    t0 = time.time()
    tops, costs = [], []
    i = 0
    while time.time() - t0 < total:
        p = os.path.join(d, f'f{i:03d}.png')
        el = time.time() - t0
        if grab(p):
            img = cv2.imread(p)
            for roi, store in ((ROI_TOP, tops), (ROI_COST, costs)):
                x0, y0, x1, y1 = roi
                c = img[y0:y1, x0:x1].copy()
                cv2.putText(c, f'{el:5.1f}s', (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                            (0, 0, 0), 4, cv2.LINE_AA)
                cv2.putText(c, f'{el:5.1f}s', (6, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                            (255, 255, 0), 2, cv2.LINE_AA)
                store.append(c)
        i += 1
        time.sleep(max(0.0, step - 1.2))
    strip(tops, os.path.join(OUT, 'run_life.png'))
    strip(costs, os.path.join(OUT, 'run_cost.png'))
    print(f'采样 {len(tops)} 帧 / {total}s（t0 = 点击「开始行动」）')


if __name__ == '__main__':
    main()
