# -*- coding: utf-8 -*-
"""probe_video.py — h12-4 视频属性与抽帧（用于费用尺离线校准）"""
import io, sys, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import cv2

VID = r'E:\MUMU共享文件夹\VideoRecords\H12-4\双\2025-11-15 12-48-09.mkv'
cap = cv2.VideoCapture(VID)
fps = cap.get(cv2.CAP_PROP_FPS)
n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f'视频: {os.path.basename(VID)}')
print(f'  分辨率 {w}x{h}  fps={fps:.3f}  帧数={n}  时长≈{n/max(1e-9,fps):.1f}s')
out = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\frames'
os.makedirs(out, exist_ok=True)
# 抽取若干时刻的帧
for t in (5, 20, 40, 60, 90, 120):
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, img = cap.read()
    if ok:
        p = os.path.join(out, f'frame_{t:03d}s.png')
        cv2.imwrite(p, img)
        print(f'  抽出 {t}s → {p}')
cap.release()
