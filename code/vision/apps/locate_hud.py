# -*- coding: utf-8 -*-
"""locate_hud.py — ★自动定位 HUD 元素（计时器 / 费用数字 / 相位），不靠人肉反推坐标

## 背景（上轮教训）
计时器 ROI 经 3 次人肉反推均失败（二值化图几乎全黑）⇒ 说明"由放大图目测反推坐标"不可靠。
本脚本改用**连通域**自动找 HUD 上的"数字串"。

## 算法
1. 取右下角大区域（默认 x 1500~1920、y 770~870）；
2. 灰度 + 阈值二值化（HUD 文字为浅色，背景暗）；
3. 形态学**水平连接**（把小字符连成"数字串"）；
4. 找连通域，按"宽高比 / 高度"筛选出候选数字串；
5. 输出候选框（含在原帧中的绝对坐标），并把这些区域**放大存图**供目视确认。

用法：
    python apps/locate_hud.py <video> [frame]
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
ZONE = (1500, 770, 1920, 870)      # 大区域（x0,y0,x1,y1）帧坐标


def find_text_runs(img, zone=ZONE, thr=100, min_h=8, max_h=26, min_w=14):
    x0, y0, x1, y1 = zone
    roi = img[y0:y1, x0:x1]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY)
    # 水平连接：把小字符连成数字串
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 3))
    closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, k)
    cnts, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        if not (min_h <= h <= max_h):
            continue
        if w < min_w:
            continue
        if w / max(1, h) < 1.2:        # 数字串应显著宽于高
            continue
        out.append({'abs': (x0 + x, y0 + y, x0 + x + w, y0 + y + h),
                    'rel': (x, y, w, h),
                    'ratio': round(w / max(1, h), 2),
                    'px': int((bw[y:y + h, x:x + w] > 0).sum())})
    out.sort(key=lambda z: -z['px'])
    return out, gray, bw


def main():
    vid = sys.argv[1] if len(sys.argv) > 1 else r'E:\MUMU共享文件夹\VideoRecords\1-1标定.mp4'
    frames = [int(x) for x in sys.argv[2:]] or [640, 700, 900, 1100]
    cap = cv2.VideoCapture(vid)
    if not cap.isOpened():
        print('打不开视频')
        return 1
    for f in frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, img = cap.read()
        if not ok:
            continue
        cands, gray, bw = find_text_runs(img)
        print(f'\n=== 视频帧 {f}：候选数字串 {len(cands)} 个 ===')
        for c in cands[:6]:
            print(f"   绝对框 x{c['abs'][0]}~{c['abs'][2]}, y{c['abs'][1]}~{c['abs'][3]}"
                  f"  (w{c['rel'][2]}×h{c['rel'][3]}, 宽高比{c['ratio']}, 亮px{c['px']})")
        # 把整区放大存图
        x0, y0, x1, y1 = ZONE
        cv2.imwrite(os.path.join(TMP, f'hud_{f:05d}.png'),
                    cv2.resize(img[y0:y1, x0:x1], None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC))
        cv2.imwrite(os.path.join(TMP, f'hudbw_{f:05d}.png'), bw)
    cap.release()
    print(f'\n放大图与二值图已存 {TMP}\\hud_*.png / hudbw_*.png')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
