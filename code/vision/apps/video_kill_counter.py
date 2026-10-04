# -*- coding: utf-8 -*-
"""video_kill_counter.py — 读游戏原生 HUD 的「**击破数 x/总数**」计数器（★最强的击杀事件通道）

## 为什么用这个通道
游戏顶部 HUD 直接显示 `击破数 / 关卡敌人总数`（1-1 实测 **x/33**）。
- **分母 = 关卡敌人总数**：这是**硬地面真值**。1-1 的关卡 SPAWN 展开也是 **33**
  ⇒ 两者一致，同时验证了"关卡解析"与"图像识别"两条链；
- **分子单调 +1** ⇒ 给出**精确的击杀时刻序列**，是校验模拟器"击杀帧"的最佳通道。

## 实现（省算力）
计数器极少变化（整片 ~33 次），因此：
1. **一次顺序读完整段视频**，逐帧只把 ROI **二值化后**与上一帧比较（二值化可消除
   "暂停时 HUD 整体变暗"造成的假变化）；
2. 只把**变化帧**留给第 2 遍：对 ROI 整体跑一次 tesseract（`psm 7`，白名单 `0-9/`）；
3. 输出 `(视频帧, 游戏帧, 击破数原串)`。

⇒ 全片只需 ~1 分钟（逐帧 OCR 需 ~18 分钟）。

用法：
    python apps/video_kill_counter.py <video> <out.jsonl> [--axis axis.jsonl] [--roi ...]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import cv2
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

TESS = r'D:\__soft\ak\prts+\_internal\Tesseract-OCR\tesseract.exe'
TESSDATA = r'D:\__soft\ak\prts+\_internal\Tesseract-OCR\tessdata'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'

# 由 apps/frames_at_game.py + 放大图实测：顶部「N/33」（ENEMY 计数）所在区域
# ★曾用 (812,26,930,60) ⇒ **纵向截断**（字形只剩上半截，导致 3 被读成 2）。
#   实测文字实际范围 ≈ x 830~906、y 40~68，故取 (820,33,920,76) 留余量。
KC_ROI = (820, 33, 920, 76)


def binarize(cell: np.ndarray) -> np.ndarray:
    th = max(110, int(0.60 * float(cell.max())))
    return (cell > th).astype(np.uint8)


def ocr_string(cell: np.ndarray) -> str:
    big = cv2.resize(cell, None, fx=8, fy=8, interpolation=cv2.INTER_CUBIC)
    big = 255 - big                       # tesseract 偏好黑字白底
    big = cv2.copyMakeBorder(big, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=255)
    p = os.path.join(TMP, '_kcstr.png')
    cv2.imwrite(p, big)
    for psm in ('7', '6'):
        try:
            r = subprocess.run([TESS, p, 'stdout', '-l', 'eng', '--tessdata-dir', TESSDATA,
                                '--psm', psm, '-c', 'tessedit_char_whitelist=0123456789/'],
                               capture_output=True, encoding='utf-8', errors='replace',
                               timeout=20)
            t = ''.join((r.stdout or '').split())
            if t and all(ch in '0123456789/' for ch in t):
                return t
        except Exception:
            pass
    return '?'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('out')
    ap.add_argument('--start', type=int, default=0)
    ap.add_argument('--end', type=int, default=-1)
    ap.add_argument('--pix', type=int, default=12, help='二值掩膜差异像素数阈值')
    ap.add_argument('--axis', default=None)
    ap.add_argument('--roi', default='')
    ap.add_argument('--montage', default=None)
    a = ap.parse_args()

    roi = KC_ROI
    if a.roi:
        roi = tuple(int(v) for v in a.roi.split(','))
    x0, y0, x1, y1 = roi

    cap = cv2.VideoCapture(a.video)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    end = total if a.end < 0 else min(a.end, total)
    prev = None
    changes: list[int] = []
    f = 0
    while f < end:
        if not cap.grab():
            break
        if f >= a.start:
            ok, img = cap.retrieve()
            if ok and img is not None:
                g = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
                m = binarize(g)
                if prev is None or int(np.count_nonzero(m != prev)) >= a.pix:
                    changes.append(f)
                prev = m
        f += 1
    cap.release()
    print(f'遍历 {f} 帧；二值掩膜变化帧 {len(changes)} 个')

    want = set(changes)
    cap = cv2.VideoCapture(a.video)
    seq = []
    i = 0
    mx = max(want) if want else 0
    while True:
        if not cap.grab():
            break
        if i in want:
            ok, img = cap.retrieve()
            if ok and img is not None:
                g = cv2.cvtColor(img[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
                th = max(110, int(0.60 * float(g.max())))
                _, b = cv2.threshold(g, th, 255, cv2.THRESH_BINARY)
                seq.append((i, ocr_string(b)))
        if i >= mx:
            break
        i += 1
    cap.release()

    axis = {}
    if a.axis:
        for line in open(a.axis, encoding='utf-8'):
            r = json.loads(line)
            axis[r['f']] = r['B']

    print(f'\n{"视频帧":>7} {"游戏帧":>9}  击破数')
    rows = []
    prev_s = None
    for fr, s in seq:
        b = axis.get(fr)
        rows.append({'f': fr, 'raw': s, 'B': b})
        if s != prev_s:
            bs = f'{b:>9.1f}' if b is not None else '        -'
            print(f'{fr:>7} {bs}  {s}')
        prev_s = s

    with open(a.out, 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('已写出', a.out)

    vals = sorted({r['raw'] for r in rows})
    print('出现的原串:', vals)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
