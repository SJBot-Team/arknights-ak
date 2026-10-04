# -*- coding: utf-8 -*-
"""临时：从 h12-4 双人解视频抽帧，用于定位 UI 区域（费用数字/费用条）"""
import os
import sys
import cv2

VID = r'E:\MUMU共享文件夹\VideoRecords\H12-4\双\2025-11-15 12-48-09.mkv'
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\frames'
os.makedirs(OUT, exist_ok=True)

cap = cv2.VideoCapture(VID)
fps = cap.get(cv2.CAP_PROP_FPS)
n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(f'视频 {w}x{h} fps={fps} frames={n} 时长={n/fps:.1f}s')

times = [float(x) for x in (sys.argv[1:] or ['100', '135.67', '149.67', '150.2'])]
for t in times:
    idx = int(round(t * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ok, fr = cap.read()
    p = os.path.join(OUT, f'v_{t:07.2f}s_f{idx}.png')
    cv2.imwrite(p, fr)
    print('写入', p, ok)
cap.release()
