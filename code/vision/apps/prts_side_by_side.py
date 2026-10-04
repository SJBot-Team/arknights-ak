# -*- coding: utf-8 -*-
"""prts_side_by_side.py — 进关→第一秒内暂停→局内启动 PRTS+(--debug)→同时逐帧识别→对齐对照

## 目的（用户 2026-09-14 的两条纠正之后）
1. "0 帧暂停"不必严格 0 帧，**只要在第一秒内暂停**（它按费用条相对长度定位秒内帧）；
2. 启动逻辑要选**局内开始**（不加 `--autoenter`）。

于是本脚本：① 若在战斗中先等它结束；② 走演习进关并**立刻暂停**；
③ 以 `--debug` 局内启动 PRTS+（日志落盘、按时间戳记录）；
④ 同时用费用尺逐帧识别（费用数字 + 相位，查官方 pixel_map）；
⑤ 结束后**按时间戳把两路对齐**，输出并排对照表。

用法：python apps/prts_side_by_side.py [采样秒数]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture, EmuWindowCapture        # noqa: E402
from plugins.clock.frame_clock import PIXEL_MAP_30F, bar_phase, frame_from_width  # noqa: E402
from plugins.nav.auto_enter import AutoEnter                                 # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer               # noqa: E402
from plugins.recognize.maa_anchor import MaaAnchor                           # noqa: E402
from plugins.recognize.ui_state import UiState                               # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
EXE = r'D:\__soft\ak\prts+\prts+.exe'
XLSM = r'D:\__soft\ak\prts_plan_h124.xlsm'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TPL = os.path.join(TMP, 'tpl_h124.json')
NUM_ROI = (1795, 730, 1915, 805)
BAR_ROI = (1739, 805, 1919, 818)
TAP_PAUSE = (1877, 76)
ANSI = re.compile(r'\x1b\[[0-9;]*m')
KEY = re.compile(r'(Setting initial tick to \d+|Getting current action at row \d+|'
                 r'Performing action:.*?oper=.(\S+?).,|Too much time.*|'
                 r'Game time mismatch.*|Error occurred:.*|Performed action:.*?oper=.(\S+?).,)')


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 70.0
    cap = make_capture('adb')
    EmuWindowCapture().open().bring_to_front()
    time.sleep(0.4)
    ui, ma = UiState(), MaaAnchor(thr=0.85)

    def tap(x, y):
        subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                       capture_output=True)

    def fp(img):
        return cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')

    # ① 若在战斗中，先等它结束
    t0 = time.time()
    while time.time() - t0 < 95 and ui.classify(cap.grab().image)['state'] == 'battle':
        time.sleep(2.0)
    # ② 进关 + 第一秒内暂停
    ae = AutoEnter(cap, tap, ui, ma=ma, wait_battle_sleep=0.2)
    if not ae.enter():
        print('进关失败'); return 2
    img0 = cap.grab().image
    tap(*TAP_PAUSE)
    time.sleep(0.8)
    a, b = cap.grab().image, None
    time.sleep(1.0)
    b = cap.grab().image
    paused = float(np.abs(fp(a) - fp(b)).mean()) < 0.005
    print(f'进关并暂停：两次点后差异 {float(np.abs(fp(a)-fp(b)).mean()):.4f} ⇒ '
          f'{"已暂停" if paused else "未确认暂停"}')

    # ③ 局内启动 PRTS+（--debug），日志按时间戳记录
    log_path = os.path.join(TMP, 'prts_side_%s.log' % time.strftime('%H%M%S'))
    logf = open(log_path, 'w', encoding='utf-8')
    p = subprocess.Popen([EXE, '--xlsm', XLSM, '--debug'], stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    t_start = time.time()
    log_lines, buf, lock = [], {'s': ''}, threading.Lock()

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
                    logf.write(line + '\n'); logf.flush()
                    if any(k in line for k in ('tick to', 'current action', 'Performing action',
                                               'Too much time', 'mismatch', 'Error occurred',
                                               'Performed action', 'resetting', 'bullet')):
                        log_lines.append((time.time() - t_start, line))

    threading.Thread(target=reader, daemon=True).start()

    # ④ 同时逐帧识别
    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}
    samples = []
    print('同时开始逐帧识别……')
    t1 = time.time()
    while time.time() - t1 < seconds:
        img = cap.grab().image
        t = time.time() - t1
        ms = rec.run(img, spec, None, (0, 0))
        cost = None
        if ms and float(ms[0].extra.get('confidence', 0.0)) >= 0.85:
            cost = int(ms[0].extra['cost'])
        ph = bar_phase(img[BAR_ROI[1]:BAR_ROI[3], BAR_ROI[0]:BAR_ROI[2]],
                       full_px=BAR_ROI[2] - BAR_ROI[0])
        samples.append((t, cost, frame_from_width(ph['fill_px'], PIXEL_MAP_30F), ph['fill_px']))
        time.sleep(0.5)

    try:
        p.terminate(); time.sleep(0.4)
        if p.poll() is None:
            p.kill()
    except Exception:
        pass
    logf.close()

    # ⑤ 对齐输出
    print(f'\n===== 并排对照（PRTS+ 的事件 → 我们最接近的一次识别）=====')
    print(f'{"PRTS+时刻":>9}  {"PRTS+ 事件":<58} {"我方时刻":>7} {"费用":>4} {"tick":>4}')
    for lt, line in log_lines:
        nearest = min(samples, key=lambda s: abs(s[0] - lt)) if samples else None
        short = line.split(' - ', 2)[-1][:56]
        if nearest:
            print(f'{lt:9.2f}  {short:<58} {nearest[0]:7.1f} {str(nearest[1]):>4} {nearest[2]:>4}')
        else:
            print(f'{lt:9.2f}  {short:<58}')
    print(f'\n我方识别采样 {len(samples)} 条；日志 {log_path}')
    if samples:
        costs = [s[1] for s in samples if s[1] is not None]
        print(f'我方费用范围 {min(costs) if costs else None}~{max(costs) if costs else None}；'
              f'tick 取值集合 {sorted(set(s[2] for s in samples))[:12]}……')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
