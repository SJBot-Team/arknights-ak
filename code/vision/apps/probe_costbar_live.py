# -*- coding: utf-8 -*-
"""probe_costbar_live.py — 用**实机截图**核对费用条识别器与实测几何是否一致。

背景：实机 HUD 上 `CostBarRecognizer` 默认 spec 报 `frame=30`（满），
但直接量测该处填充仅约 45%% ⇒ 需要拿到实机 ROI 并核验映射。
本脚本对若干候选 ROI 跑识别器，并**直接按亮度量填充长度**作对照。
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.recognize.cost_bar import CostBarRecognizer      # noqa: E402

IMG = os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\.tmp', 'live_11_final.png')
img = cv2.imread(IMG)
print('图:', os.path.basename(IMG), img.shape)

print('\n--- 识别器（带候选 ROI）---')
for roi in ([1740, 805, 1875, 821], [1734, 810, 1914, 824], [1700, 800, 1920, 830], None):
    spec = {} if roi is None else {'roi': roi}
    try:
        ms = CostBarRecognizer().run(img, spec, None, (0, 0))
    except Exception as ex:                                    # noqa: BLE001
        print('  roi=%-26s 异常 %r' % (roi, ex))
        continue
    if ms:
        e = ms[0].extra
        print('  roi=%-26s frame=%s fill_px=%s total=%s'
              % (roi, e.get('frame'), e.get('fill_px'), e.get('total_frames')))
    else:
        print('  roi=%-26s 无匹配' % (roi,))

print('\n--- 直接量亮填充（对照）---')
sub = cv2.cvtColor(img[805:821, 1740:1880], cv2.COLOR_BGR2GRAY).astype(float)
col = sub.mean(axis=0)
thr = col.max() * 0.55
n = int((col > thr).sum())
print('  轨道 140px 内，亮列数 = %d ⇒ 填充比 ≈ %.0f%%' % (n, 100 * n / len(col)))
print('  若"满条"= 132px（实测轨道长），则当前 ≈ %.0f%%' % (100 * n / 132))
