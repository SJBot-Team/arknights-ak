# -*- coding: utf-8 -*-
"""self_read_hud.py — ★**自主识别游戏画面本身**（不读费用尺的叠加读数）

## 为什么（用户 2026-09-15 澄清）
> 「你识别到的计时器为**外部费用尺**，基于图像识别，有不可避免的延迟；
>   暂停于某一帧一段时间后，读取的帧才与费用条完全相同。
>   你可以借用费用尺的识别，**自行对游戏某帧的画面识别**，而不是识别已经存延迟的费用尺。」

⇒ 因此：
- 屏幕右下角那个「⌛ 00:00:10」是**费用尺工具叠加显示**的，**运行中滞后**，**不可用于对轴**；
- 应**自己识别游戏原生 HUD**：**费用数字**（大号白字）与**费用条填充**（相位）。

## 本脚本做三件事
1. **自动定位费用数字**（在大区域里找"最大、最右的数字串"）；
2. **读费用条填充像素**（180px = 30 帧 ⇒ 6px = 1 帧）；
3. 输出 `(视频帧, 费用数字, 相位填充px, 相位比例)`，并可批量扫描。

用法：
    python apps/self_read_hud.py <video> [start] [end] [step]
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

# 游戏原生 HUD（由 `costzone_*.png` 5× 放大图逐一确认，★自主识别，不读费用尺）
#   费用图标「♢C」: x 1744~1792, y 760~803   ← 注意：这是图标，**不是**数字
#   ★费用数字     : x 1820~1880, y 750~806   （大号白字，在图标右侧）
#   费用条         : x 1733~1900（总宽≈167px≈180px）, y 813~823
COST_NUM_ROI = (1815, 748, 1888, 808)
COST_BAR_X = (1731, 1902)
COST_BAR_Y = (812, 824)
ZONE_ALL = (1700, 740, 1920, 880)


def read_cost_number(img, roi=COST_NUM_ROI):
    """读**费用数字**（游戏原生大号白字）。"""
    x0, y0, x1, y1 = roi
    crop = img[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, b = cv2.threshold(g, 170, 255, cv2.THRESH_BINARY)
    b = cv2.resize(b, None, fx=8, fy=8, interpolation=cv2.INTER_CUBIC)
    b = cv2.copyMakeBorder(b, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=0)
    p = os.path.join(TMP, '_costnum.png')
    cv2.imwrite(p, b)
    try:
        r = subprocess.run([TESS, p, 'stdout', '-l', 'eng', '--tessdata-dir', TESSDATA,
                            '--psm', '7', '-c', 'tessedit_char_whitelist=0123456789'],
                           capture_output=True, encoding='utf-8', errors='replace', timeout=15)
        t = ''.join((r.stdout or '').split())
        return int(t) if t.isdigit() else None
    except Exception:
        return None


def read_cost_bar(img, xr=COST_BAR_X, yr=COST_BAR_Y, total_px: int = 167):
    """读费用条**白色填充**长度 ⇒ 相位。

    ★总宽固定为 **167px**（实测：条从 x≈1733 到 x≈1900）。
    此前用"非背景水平跨度"估计会受 HUD 其他元素干扰而跳变（53~171px），故改为常量。
    相位 tick = `填充px / total_px × 30`（180px↔30帧、167px↔30帧的实测口径）。
    """
    xs, xe = xr
    y0, y1 = yr
    sub = img[y0:y1, xs:xe]
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    white = ((hsv[:, :, 2] > 185) & (hsv[:, :, 1] < 70)).astype(np.uint8)
    cols = white.sum(axis=0)
    on = cols >= max(2, (y1 - y0) // 3)
    best_len, s = 0, None
    for i, v in enumerate(on):
        if v and s is None:
            s = i
        elif not v and s is not None:
            best_len = max(best_len, i - s)
            s = None
    if s is not None:
        best_len = max(best_len, len(on) - s)
    ratio = best_len / float(total_px)
    return best_len, total_px, round(ratio, 4), round(ratio * 30, 2)


def main():
    vid = sys.argv[1] if len(sys.argv) > 1 else r'E:\MUMU共享文件夹\VideoRecords\1-1标定.mp4'
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    end = int(sys.argv[3]) if len(sys.argv) > 3 else 700
    step = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    cap = cv2.VideoCapture(vid)
    if not cap.isOpened():
        print('打不开视频')
        return 1
    print(f'自主识别（游戏原生 HUD）扫描 {os.path.basename(vid)} 帧 {start}~{end} 步长 {step}')
    rows = []
    # ★必须**顺序读取**：连续 `cap.set(POS_FRAMES)` 的 seek 精度不足，
    #   实测会导致取到错误帧（填充px 恒为 0、费用数字跳变）。
    #   先跳到 start 一次，之后用 read() 连续推进。
    if start > 0:
        cap.set(cv2.CAP_PROP_POS_FRAMES, start)
        cap.read()
    f = start
    while f < end:
        ok, img = cap.read()
        if not ok:
            break
        if (f - start) % step == 0:
            num = read_cost_number(img)
            fill, total, ratio, tick = read_cost_bar(img)
            rows.append({'f': f, 'cost': num, 'fill_px': fill,
                         'total_px': total, 'ratio': ratio, 'tick': tick})
        f += 1
    cap.release()
    print(f'\n{"视频帧":>7} {"费用":>5} {"填充px":>7} {"相位tick":>8}  备注')
    prev = None
    events = []
    for r in rows:
        note = ''
        if prev is not None:
            pc, pt = prev.get('cost'), prev.get('tick')
            if r['cost'] is not None and pc is not None and r['cost'] != pc:
                dc = r['cost'] - pc
                note += f'  ★费用 {pc}→{r["cost"]}（{dc:+d}）'
                events.append({'f': r['f'], 'kind': 'cost_change', 'from': pc, 'to': r['cost']})
            if pt is not None and r['tick'] is not None:
                if abs(r['tick'] - pt) < 0.5:
                    note += '  [相位不动⇒暂停]'
                elif r['tick'] < pt - 5:
                    note += '  [相位归零⇒跨秒]'
        print(f'{r["f"]:>7} {str(r["cost"]):>5} {r["fill_px"]:>7} {r["tick"]:>8} {note}')
        prev = r
    out = os.path.join(TMP, 'self_hud_scan.json')
    json.dump({'rows': rows, 'events': events}, open(out, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'\n检出事件 {len(events)} 条；明细已存 {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
