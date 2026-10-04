# -*- coding: utf-8 -*-
"""speed_probe.py — **流速检测 + 过帧标定**（用户指出的关键点）

## 依用户 2026-09-15 的说明
> 过帧功能需要明确当前游戏速度，区分二倍速、一倍速、子弹时间（正在拖动干员或已点选干员），
> 不同流速对应不同过帧宏。

**原理**：过帧宏（云迹方案的 R/T/Y = 12/33/166ms）用的是**真实时间**，
因此**同样的宏在不同游戏流速下推进的"游戏内帧数"不同**：
- **1 倍速**：33ms ≈ 1 帧（30fps）
- **2 倍速**：33ms ≈ 2 帧
- **子弹时间**（点选/拖动干员时游戏减速）：33ms < 1 帧

本脚本做两件事：
1. **`read_speed()`**：读右上角的倍速标识（1X / 2X）——用 OCR（Tesseract，`eng` 即可）识别；
2. **`calibrate()`**：在给定流速下反复过帧，测出**每次宏推进多少帧**
   （用费用条填充像素换算：180px = 30 帧 ⇒ 6px = 1 帧）。

用法：
    python apps/speed_probe.py            # 读流速 + 用 T 过帧 6 次，报每步帧数
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer            # noqa: E402
from plugins.action.win_input import WinInput         # noqa: E402
from plugins.capture.emu_window import make_capture   # noqa: E402

TESS = r'D:\__soft\ak\prts+\_internal\Tesseract-OCR\tesseract.exe'
TESSDATA = r'D:\__soft\ak\prts+\_internal\Tesseract-OCR\tessdata'
# 倍速标识所在区域（帧坐标，1920×1080）：右上角 "1X"/"2X"
SPEED_ROI = (1560, 30, 1720, 115)


def read_speed(img=None, cap=None):
    """读倍速标识，返回 '1X' / '2X' / None。"""
    if img is None:
        img = (cap or make_capture('adb')).grab().image
    x0, y0, x1, y1 = SPEED_ROI
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    crop = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1]
    tmp = os.path.join(r'C:\Users\23922\Documents\ds_harness\ak\.tmp', '_speed.png')
    cv2.imwrite(tmp, gray)
    try:
        p = subprocess.run([TESS, tmp, 'stdout', '-l', 'eng',
                            '--tessdata-dir', TESSDATA, '--psm', '7'],
                           capture_output=True, encoding='utf-8', errors='replace', timeout=20)
        t = ''.join((p.stdout or '').split()).upper()
    except Exception:
        return None
    for k in ('2X', '1X'):
        if k in t:
            return k
    return t or None


def is_unit_selected(img=None, cap=None):
    """是否处于"已点选/正在拖动干员"的子弹时间：用绿色可部署高亮格判断。"""
    d = Deployer(cap or make_capture('adb'))
    return len(d.find_green_cells(img)) > 0


def calibrate(key: str = 't', rounds: int = 6, gap: float = 1.0):
    """在**当前流速**下反复过帧，测每次宏推进的帧数。"""
    cap = make_capture('adb')
    d = Deployer(cap)
    wi = WinInput()
    ok, rd = d.ensure_paused()
    print(f'暂停确认: {ok}  {rd}')
    if not ok:
        return
    sp = read_speed(cap=cap)
    print(f'当前倍速标识: {sp}')
    prev = d.read_cost()
    print(f'起始: cost={prev["cost"]} tick={prev["tick"]} fill={prev["fill_px"]}px')
    deltas = []
    for i in range(rounds):
        wi.post_key(key)
        time.sleep(gap)
        cur = d.read_cost()
        dfill = None if (prev['fill_px'] is None or cur['fill_px'] is None) else cur['fill_px'] - prev['fill_px']
        dcost = None if (prev['cost'] is None or cur['cost'] is None) else cur['cost'] - prev['cost']
        frames = None if dfill is None else round(dfill / 6.0, 2)   # 6px = 1 帧
        if dcost:
            frames = (dcost * 30) + (frames or 0)
        print(f'  第{i+1}次 过帧[{key.upper()}] Δfill={dfill}px Δcost={dcost} ⇒ 约 {frames} 帧')
        if frames is not None:
            deltas.append(frames)
        prev = cur
    if deltas:
        print(f'⇒ 平均每次宏推进 ≈ {sum(deltas)/len(deltas):.2f} 帧（{len(deltas)} 次样本）')
        print('   注：6px = 1 帧（费用条 180px = 30 帧）')


if __name__ == '__main__':
    sys.argv += []
    calibrate(sys.argv[1] if len(sys.argv) > 1 else 't')
