# -*- coding: utf-8 -*-
r"""t200_video_events.py — 从**已有录像**逐帧离线定位"敌人影子生成帧 / 血条变化帧"（T-200c 第 4 项）

思路（自研，prts+/MAA 无现成识别可抄）：
  1X 演习下 **1 视频帧 ≈ 1 逻辑帧**（30fps），所以录像本身就是"逐帧采样"。
  · **影子帧**：在敌人出生点 ROI 内做**相邻帧差分**，找"由静到动"的第一个显著变化；
  · **血条帧**：在单位血条 ROI 内做差分，找血条长度变化的帧。
用法：python t200_video_events.py <video> [--t0 5 --t1 25]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

# ROI（1920×1080）：敌人出生红框（画面中上）与左下红框（第一只怪的出生点）
ROI_SPAWN_TOP = (860, 40, 1080, 200)
ROI_SPAWN_LEFT = (110, 300, 330, 470)


def diffs(video: str, t0: float, t1: float, roi, thr: int = 18):
    cap = cv2.VideoCapture(video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    x0, y0, x1, y1 = roi
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t0 * fps))
    prev = None
    out = []
    f = int(t0 * fps)
    while True:
        ok, img = cap.read()
        if not ok:
            break
        t = f / fps
        if t > t1:
            break
        g = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY).astype(np.int16)
        if prev is not None:
            d = np.abs(g - prev)
            out.append({'frame': f, 't': round(t, 3),
                        'changed': int((d > thr).sum()), 'mean': round(float(g.mean()), 1)})
        prev = g
        f += 1
    cap.release()
    return fps, out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--t0', type=float, default=5.0)
    ap.add_argument('--t1', type=float, default=25.0)
    a = ap.parse_args()

    for name, roi in (('出生点-顶部', ROI_SPAWN_TOP), ('出生点-左侧', ROI_SPAWN_LEFT)):
        fps, rows = diffs(a.video, a.t0, a.t1, roi)
        print(f'=== {name} {roi}  fps={fps:.3f}  样本 {len(rows)} ===')
        # 找"由静到动"的第一个显著变化：连续 3 帧 changed 明显抬升
        base = np.median([r['changed'] for r in rows]) if rows else 0
        hit = None
        for i in range(2, len(rows)):
            if all(rows[i - k]['changed'] > max(200, base * 6) for k in range(3)):
                hit = rows[i - 2]
                break
        print(f'  静止基线(中位差异像素)={base:.0f}；首个显著变化帧 = {hit}')
        # 打印前后 8 帧的曲线
        if hit:
            hf = hit['frame'] - int(a.t0 * fps)
            for r in rows[max(0, hf - 5):hf + 9]:
                print(f"   帧 {r['frame']:>5} t={r['t']:>6.3f}  changed={r['changed']:>6}  mean={r['mean']}")
        out = os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\.tmp',
                           f't200_video_{name}.json')
        json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'  明细 → {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
