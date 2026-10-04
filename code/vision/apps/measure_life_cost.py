# -*- coding: utf-8 -*-
"""measure_life_cost.py — 实机采样「顶部 HUD（击杀/生命）」与「右下费用」，输出两条时间轴。

实验目的（§7.47/§7.49）：
  · 不部署任何干员，看**真实游戏里第一只敌人什么时候进点（生命 3→2）**，
    与模拟器的 37.3s / 39.8s / 43.7s 对比 ⇒ 直接校验敌人流速与寻路保真度；
  · 同时看费用上限（MAX 何时消失、数字何时突破 20）。

用法：measure_life_cost.py <总时长秒> [间隔秒]
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
ROI_TOP = (860, 0, 1420, 80)       # 击杀数 + 生命
ROI_COST = (1700, 700, 1920, 860)  # 费用 + MAX


def grab(dst):
    with open(dst, 'wb') as f:
        p = subprocess.run([ADB, '-s', DEV, 'exec-out', 'screencap', '-p'],
                           stdout=f, stderr=subprocess.DEVNULL)
    return p.returncode == 0 and os.path.getsize(dst) > 10000


def strip(tiles, path, scale=1.0):
    if not tiles:
        return
    h = max(t.shape[0] for t in tiles)
    w = max(t.shape[1] for t in tiles)
    canvas = np.full((len(tiles) * (h + 4), w, 3), 20, np.uint8)
    for k, t in enumerate(tiles):
        canvas[k * (h + 4):k * (h + 4) + t.shape[0], :t.shape[1]] = t
    if scale != 1.0:
        canvas = cv2.resize(canvas, (int(canvas.shape[1] * scale), int(canvas.shape[0] * scale)))
    cv2.imwrite(path, canvas)
    print('写出', path, canvas.shape)


def main():
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    step = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
    d = os.path.join(OUT, 'lcframes')
    os.makedirs(d, exist_ok=True)
    tops, costs = [], []
    t0 = time.time()
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
                            (255, 255, 255), 2, cv2.LINE_AA)
                store.append(c)
        i += 1
        time.sleep(max(0.0, step - 1.3))
    half = max(1, len(tops) // 2)
    for tag, chunk in (('a', tops[:half]), ('b', tops[half:])):
        strip(chunk, os.path.join(OUT, f'life_timeline_{tag}.png'), 1.0)
    for tag, chunk in (('a', costs[:half]), ('b', costs[half:])):
        strip(chunk, os.path.join(OUT, f'costcap_timeline_{tag}.png'), 1.0)
    print(f'采样 {len(tops)} 帧 / {total}s')


if __name__ == '__main__':
    main()
