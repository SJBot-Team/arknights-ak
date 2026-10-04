# -*- coding: utf-8 -*-
"""timer_scan.py — ★逐帧读取游戏内计时器，建立"视频帧 → 游戏时间"映射表

## 背景（上轮发现）
1-1 标定视频右下角，游戏自身显示：
- **「⌛ 00:00:00」计时器**（ROI ≈ 帧坐标 x1570~1710, y802~838）
- **「/30」相位** 与 白色填充条
- **费用数字**
⇒ 计时器是游戏自写的数值，是"帧级识别"的**最强通道**（避开"费用条满与下一费 0 帧混同"的问题）。

## 本脚本
逐帧 OCR 计时器，输出 `(视频帧, 计时器原文, 解析出的秒/帧)`；
据此可求出**视频帧 ↔ 游戏帧的偏移与倍率**，并定位"游戏开始（第 0 帧）"。

用法：
    python apps/timer_scan.py <video> [start] [end] [step]
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

TESS = r'D:\__soft\ak\prts+\_internal\Tesseract-OCR\tesseract.exe'
TESSDATA = r'D:\__soft\ak\prts+\_internal\Tesseract-OCR\tessdata'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
# 计时器 ROI（帧坐标）——★由 `apps/locate_hud.py` 的**连通域自动定位**得到：
#   数字串 "00:00:10" 的绝对框 = x **1591~1659**、y **807~822**（w68×h15）
#   （此前人肉反推为 1604~1670，**偏右 13px**，故二值化图几乎全黑）
TIMER_ROI = (1588, 804, 1662, 826)
# 另一个候选数字串（x1708~1796, y808~823，w88×h15，亮px616）＝费用数字/相位一带
COST_ROI = (1705, 805, 1800, 826)


def read_timer(img, roi=TIMER_ROI):
    x0, y0, x1, y1 = roi
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # 字为灰白（亮度 ~140-220），背景暗 ⇒ 阈值 110 并做放大
    _, bw = cv2.threshold(gray, 110, 255, cv2.THRESH_BINARY)
    bw = cv2.resize(bw, None, fx=8, fy=8, interpolation=cv2.INTER_CUBIC)
    bw = cv2.copyMakeBorder(bw, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=0)
    p = os.path.join(TMP, '_timer.png')
    cv2.imwrite(p, bw)
    for psm in ('7', '8', '6'):
        try:
            r = subprocess.run(
                [TESS, p, 'stdout', '-l', 'eng', '--tessdata-dir', TESSDATA,
                 '--psm', psm, '-c', 'tessedit_char_whitelist=0123456789:'],
                capture_output=True, encoding='utf-8', errors='replace', timeout=15)
            t = ''.join((r.stdout or '').split())
            if t and re.search(r'\d', t):
                return t
        except Exception:
            continue
    return None


def parse_timer(t):
    """把 '00:00:10' 解析为 (数字组)。格式待定（时:分:秒 或 分:秒:帧）。"""
    if not t:
        return None
    nums = re.findall(r'\d+', t)
    if len(nums) == 3:
        return tuple(int(x) for x in nums)
    return None


def main():
    vid = sys.argv[1] if len(sys.argv) > 1 else r'E:\MUMU共享文件夹\VideoRecords\1-1标定.mp4'
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 560
    end = int(sys.argv[3]) if len(sys.argv) > 3 else 900
    step = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    cap = cv2.VideoCapture(vid)
    if not cap.isOpened():
        print('打不开视频')
        return 1
    print(f'扫描 {os.path.basename(vid)}  帧 {start}~{end} 步长 {step}')
    rows = []
    f = start
    while f < end:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, img = cap.read()
        if not ok:
            break
        t = read_timer(img)
        rows.append((f, t, parse_timer(t)))
        f += step
    cap.release()

    print(f'\n共 {len(rows)} 个采样点（每 {step} 帧一次）：')
    prev = None
    for (f, t, p) in rows:
        mark = ''
        if p is not None and prev is not None and p != prev:
            mark = '   ← 变化'
        print(f'  视频帧 {f:>5}: {t}  {p}{mark}')
        prev = p if p is not None else prev

    out = os.path.join(TMP, 'timer_scan_1-1.json')
    json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n明细已存 {out}')

    # 估算倍率：由相邻两次"秒变化"之间的视频帧数
    secs = [(f, p) for (f, t, p) in rows if p is not None]
    if len(secs) >= 2:
        print('\n== 时间戳（可能为 时:分:秒 或 分:秒:帧）==')
        for (f, p) in secs[:20]:
            print(f'  视频帧 {f:>5} ⇒ {p}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
