# -*- coding: utf-8 -*-
"""find_active_frames.py — 扫描视频亮度找未暂停片段，并定位候选费用条"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import cv2
import numpy as np

VID = r'E:\MUMU共享文件夹\VideoRecords\H12-4\双\2025-11-15 12-48-09.mkv'
cap = cv2.VideoCapture(VID)
fps = cap.get(cv2.CAP_PROP_FPS)
res = []
i = 0
while True:
    ok = cap.grab()
    if not ok:
        break
    if i % 30 == 0:
        ok, img = cap.retrieve()
        if ok:
            m = float(img.mean())
            res.append((i, m))
    i += 1
cap.release()
arr = np.array([(f, m) for f, m in res])
print(f'采样 {len(arr)} 点（每 30 帧一个）')
bright = arr[arr[:, 1] > np.percentile(arr[:, 1], 70)]
print('亮度较高（可能未暂停）的帧号样例:', bright[:20, 0].astype(int).tolist())
print('亮度范围: %.1f ~ %.1f' % (arr[:, 1].min(), arr[:, 1].max()))
# 抽取若干高亮点
out = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\frames'
cap = cv2.VideoCapture(VID)
for fno in bright[:6, 0].astype(int):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(fno))
    ok, img = cap.read()
    if ok:
        cv2.imwrite(os.path.join(out, f'act_{fno:05d}.png'), img)
        print('  抽出活跃帧', fno)
cap.release()
