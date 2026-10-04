# -*- coding: utf-8 -*-
"""h12-4 录像速查：分辨率/时长 + 费用数字区域拼图（用于判定录像是否为同一令+蕾缪安解）"""
import os
import sys
import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
D = r'E:\MUMU共享文件夹\VideoRecords\H12-4'
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\video_probe'
os.makedirs(OUT, exist_ok=True)

VIDS = []
for root, _, files in os.walk(D):
    for f in files:
        if f.lower().endswith(('.mp4', '.mkv')):
            VIDS.append(os.path.join(root, f))

print(f'共 {len(VIDS)} 个视频')
info = []
for v in VIDS:
    cap = cv2.VideoCapture(v)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    dur = n / fps if fps else 0
    info.append((v, w, h, fps, n, dur))
    print(f'  {os.path.relpath(v, D):<46} {w}x{h} {fps:.0f}fps {n:>6}帧 {dur:>7.1f}s')

# 对每个视频取固定时刻的费用区拼图（右下角费用数字 + 顶部击杀数）
TIMES = [20, 25, 30, 35, 40, 45, 50, 55]
for (v, w, h, fps, n, dur) in info:
    cap = cv2.VideoCapture(v)
    tiles = []
    for t in TIMES:
        idx = int(t * fps)
        if idx >= n:
            tiles.append(np.zeros((60, 200, 3), np.uint8))
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, fr = cap.read()
        if not ok:
            tiles.append(np.zeros((60, 200, 3), np.uint8))
            continue
        # 右下角（费用数字所在带）
        crop = fr[int(h * 0.63):int(h * 0.70), int(w * 0.78):int(w * 0.92)]
        crop = cv2.resize(crop, (200, 60), interpolation=cv2.INTER_NEAREST)
        cv2.putText(crop, f'{t}s', (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        tiles.append(crop)
    cap.release()
    rows = [np.hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]
    sheet = np.vstack(rows)
    name = 'v%02d' % VIDS.index(v)
    p = os.path.join(OUT, f'cost_{name}.png')
    cv2.imwrite(p, sheet)
    print('拼图 →', p)
