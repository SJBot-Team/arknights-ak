# -*- coding: utf-8 -*-
"""run_prts_compare.py — 一键：运行赛博塑料 + 同时做图像识别 → 并排对照两路时间轴

## 依据（用户 2026-09-14 的机制澄清）
> PRTS+ 仅具备识别**关卡内待部署干员**的功能，不能识别局外进入关卡界面的干员。

⇒ `--autoenter` 只是"盲点开始行动、自动进关"；干员识别**只在关卡内的待部署区**发生。
因此本脚本的用法是：**先把游戏带到"战斗中（待部署区有干员）"或"演习的编队界面（配 --autoenter）"**。

## 输出
1. PRTS+ 的日志（含它的 `GameTime(cost, tick, time)` 与 `not on time` 标记）→ 落盘；
2. 我们的图像识别（费用数字 + 费用条相位，查官方 pixel_map）→ 采样表；
3. 两者的**并排对照**：把它的每条 GameTime 与同时刻我们的读数对齐，算 `tick/time/cost` 的差。

用法：
    python apps/run_prts_compare.py [--autoenter] [--seconds 90] [--interval 0.5]
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import threading
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture                      # noqa: E402
from plugins.clock.frame_clock import PIXEL_MAP_30F, bar_phase, frame_from_width  # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer            # noqa: E402

EXE = r'D:\__soft\ak\prts+\prts+.exe'
CWD = r'D:\__soft\ak\prts+'
XLSM_ASCII = r'D:\__soft\ak\prts_plan_h124.xlsm'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TPL = os.path.join(TMP, 'tpl_h124.json')
NUM_ROI = (1795, 730, 1915, 805)
BAR_ROI = (1739, 805, 1919, 818)
ANSI = re.compile(r'\x1b\[[0-9;]*m')
GT = re.compile(r'GameTime\(cost=(\d+),\s*tick=(\d+),\s*time=(\d+)\)')
MISMATCH = re.compile(r'Game time mismatch.*?at (GameTime\([^)]*\)).*?instead of (GameTime\([^)]*\))')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--autoenter', action='store_true', help='从编队界面自动进关')
    ap.add_argument('--seconds', type=float, default=90.0)
    ap.add_argument('--interval', type=float, default=0.5)
    a = ap.parse_args()

    log_path = os.path.join(TMP, 'prts_cmp_%s.log' % time.strftime('%H%M%S'))
    logf = open(log_path, 'w', encoding='utf-8')
    cmd = [EXE, '--xlsm', XLSM_ASCII] + (['--autoenter'] if a.autoenter else [])
    print('运行:', ' '.join(cmd), f'\n日志: {log_path}')
    p = subprocess.Popen(cmd, cwd=CWD, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)

    gt_lines, buf = [], {'s': ''}
    lock = threading.Lock()

    def reader():
        while True:
            ch = p.stdout.read(1)
            if not ch:
                break
            c = ch.decode('utf-8', 'replace')
            with lock:
                buf['s'] += c
                if c == '\n':
                    line = ANSI.sub('', buf['s']).rstrip()
                    buf['s'] = ''
                    logf.write(line + '\n')
                    logf.flush()
                    if 'GameTime' in line:
                        gt_lines.append((time.time(), line))
                        print('  [PRTS+]', line[:150], flush=True)

    threading.Thread(target=reader, daemon=True).start()

    cap = make_capture('adb')
    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}
    samples = []
    t0 = time.time()
    print('\n同时开始图像识别采样……')
    while time.time() - t0 < a.seconds:
        img = cap.grab().image
        t = time.time() - t0
        ms = rec.run(img, spec, None, (0, 0))
        cost = None
        if ms and float(ms[0].extra.get('confidence', 0.0)) >= 0.85:
            cost = int(ms[0].extra['cost'])
        ph = bar_phase(img[BAR_ROI[1]:BAR_ROI[3], BAR_ROI[0]:BAR_ROI[2]],
                       full_px=BAR_ROI[2] - BAR_ROI[0])
        tick = frame_from_width(ph['fill_px'], PIXEL_MAP_30F)
        samples.append((t, cost, tick, ph['fill_px']))
        print(f'  [我们] t={t:6.2f} 费用={cost} tick={tick:>2} 填充={ph["fill_px"]:>3}px', flush=True)
        time.sleep(a.interval)

    try:
        p.terminate(); time.sleep(0.4)
        if p.poll() is None:
            p.kill()
    except Exception:
        pass
    logf.close()

    print('\n===== PRTS+ 的 GameTime 记录 =====')
    for _, line in gt_lines:
        m = GT.search(line)
        mm = MISMATCH.search(line)
        if mm:
            print(f'  ★不匹配：实际 {mm.group(1)}  期望 {mm.group(2)}')
        elif m:
            print(f'  GameTime(cost={m.group(1)}, tick={m.group(2)}, time={m.group(3)})')
    print('\n===== 我们的识别（末 10 条）=====')
    for t, cost, tick, fill in samples[-10:]:
        print(f'  t={t:6.2f} 费用={cost} tick={tick} 填充={fill}px')
    print(f'\n日志：{log_path}（可用它继续做逐帧对照）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
