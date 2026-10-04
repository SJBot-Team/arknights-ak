# -*- coding: utf-8 -*-
"""probe_video_costbar.py — 确认 1-1 标定视频里"费用条"的位置与形态

## 目的（依用户第 3 点）
用户指出：前 10 秒"费用条满的第 29 帧"与"下一费的第 0 帧"混同、难以区分 ⇒
本脚本不用 OCR 数字，改为**直接读费用条的填充像素**（本方已在实机验证过的通道）。

## 已知（实机验证过的 ROI）
- 费用条：**y 811~817、x 1739~1919（宽 180px = 30 帧 ⇒ 6px = 1 帧）**
- 但视频可能因录制裁剪/缩放而不同 ⇒ 本脚本先**抽样定位**。
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

VID = r'E:\MUMU共享文件夹\VideoRecords\1-1标定.mp4'
OUT = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
SAMPLES = [0, 60, 200, 400, 620, 640, 700, 760, 900, 1100]


def main():
    cap = cv2.VideoCapture(VID)
    if not cap.isOpened():
        print('打不开视频')
        return 1
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f'视频 {w}x{h}')
    for f in SAMPLES:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, img = cap.read()
        if not ok:
            print(f'  帧 {f}: 读失败')
            continue
        # 已知 ROI 附近区域（右下角一带）放大保存，便于目视
        y0, y1 = 780, 860
        x0, x1 = 1650, 1920
        crop = img[y0:y1, x0:x1]
        p = os.path.join(OUT, f'costroi_{f:05d}.png')
        cv2.imwrite(p, cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST))
        # 在整条水平线上找"高亮段"（费用条是亮蓝/白色）
        strip = img[808:820, 1500:1920]
        hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)
        # 亮且低饱和（白/浅蓝）
        bright = ((hsv[:, :, 2] > 150)).sum(axis=0)
        runs = []
        s = None
        for i, v in enumerate(bright > 6):
            if v and s is None:
                s = i
            elif not v and s is not None:
                if i - s >= 5:
                    runs.append((1500 + s, 1500 + i))
                s = None
        if s is not None:
            runs.append((1500 + s, 1920))
        print(f'  帧 {f:>4}: 亮段 {runs[:4]}')
    cap.release()
    print(f'\nROI 小图已存 {OUT}\\costroi_*.png')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
