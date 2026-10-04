# -*- coding: utf-8 -*-
"""track_enemy_video.py — ★从视频里**直接量取敌人轨迹**（帧差法，无需模板）。

## 目的（D14 的决定性实验）
模拟器与标定在"第 2 只敌人的到达时刻"上差 ~25 帧；移速与出生点约定都已排除
⇒ 需要**实测轨迹**来判断是"路径形状"还是"速度"的问题。
第 2 只（game 360~464）的画面被干员详情面板/橙色遮罩遮挡，
⇒ 改用**第 4 只（route5，game 810 起）**：该时段地图清晰（已目视确认）。

## 方法
游戏在 RUN 段时，1 游戏帧 = 1 视频帧；地图本身静止，**只有单位在动**
⇒ 取 `frame(g+Δ) − frame(g)`（ROI=战场区），阈值化后取最大连通域质心 = 运动单位。
逐采样点输出屏幕坐标；用 `--px-per-cell`（默认 130，见打图插件实测）换算成格。

用法：
    python apps/track_enemy_video.py <axis.jsonl> <video> <g_start> <g_end> <step>
                                     [--roi x0,y0,x1,y1] [--delta 3] [--px-per-cell 130]
"""
from __future__ import annotations

import argparse
import json
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('axis')
    ap.add_argument('video')
    ap.add_argument('g_start', type=int)
    ap.add_argument('g_end', type=int)
    ap.add_argument('step', type=int, default=5)
    ap.add_argument('--roi', default='0,60,1920,470')
    ap.add_argument('--delta', type=int, default=3)
    ap.add_argument('--px-per-cell', type=float, default=130.0)
    ap.add_argument('--area', type=int, default=60)
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.axis, encoding='utf-8')]
    g2v = {int(round(r['B'])): r['f'] for r in rows}
    x0, y0, x1, y1 = (int(v) for v in a.roi.split(','))

    # 需要 (g, g+delta) 两个视频帧 ⇒ 一次顺序遍历，收集所需帧号
    need = set()
    for g in range(a.g_start, a.g_end + 1, a.step):
        for gg in (g, g + a.delta):
            if gg in g2v:
                need.add(g2v[gg])
    frames: dict[int, np.ndarray] = {}
    cap = cv2.VideoCapture(a.video)
    i, mx = 0, (max(need) if need else 0)
    while True:
        if not cap.grab():
            break
        if i in need:
            ok, fr = cap.retrieve()
            if ok and fr is not None:
                frames[i] = fr[y0:y1, x0:x1].copy()
        if i >= mx:
            break
        i += 1
    cap.release()

    print(f'{"游戏帧":>6} {"视频帧":>7} {"质心x":>7} {"质心y":>7} {"面积":>6}  Δ(格)')
    prev = None
    out = []
    for g in range(a.g_start, a.g_end + 1, a.step):
        v0, v1 = g2v.get(g), g2v.get(g + a.delta)
        if v0 is None or v1 is None or v0 not in frames or v1 not in frames:
            continue
        if v1 - v0 != a.delta:          # 跨了暂停/断帧 ⇒ 不可比
            continue
        d = cv2.absdiff(frames[v0], frames[v1])
        gray = cv2.cvtColor(d, cv2.COLOR_BGR2GRAY)
        _, m = cv2.threshold(gray, 35, 255, cv2.THRESH_BINARY)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab, stats, cent = cv2.connectedComponentsWithStats(m, 8)
        blobs = [(int(stats[k, 4]), float(cent[k][0]), float(cent[k][1]))
                 for k in range(1, n) if int(stats[k, 4]) >= a.area]
        if not blobs:
            continue
        area, cx, cy = max(blobs)
        step_txt = ''
        if prev is not None:
            dx = (cx - prev[0]) / a.px_per_cell
            dy = (cy - prev[1]) / a.px_per_cell
            step_txt = f'({dx:+.2f},{dy:+.2f}) |{np.hypot(dx, dy):.2f}|'
        prev = (cx, cy)
        out.append((g, cx, cy, area))
        print(f'{g:>6} {v0:>7} {cx:>7.1f} {cy:>7.1f} {area:>6}  {step_txt}')

    if len(out) >= 2:
        (g0, x0c, y0c, _), (g1, x1c, y1c, _) = out[0], out[-1]
        dg = g1 - g0
        dist = np.hypot(x1c - x0c, y1c - y0c) / a.px_per_cell
        print(f'\n★ 首末：game {g0}→{g1}（{dg} 帧 = {dg / 30:.2f}s）'
              f'  位移 {dist:.2f} 格 ⇒ **平均 {dist / (dg / 30):.3f} 格/秒**')
        print(f'   （参考：猎狗 moveSpeed 1.9 × moveMultiplier 0.5 = **0.950 格/秒**）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
