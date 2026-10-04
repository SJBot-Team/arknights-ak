# -*- coding: utf-8 -*-
"""selflabel_cost_capture.py — 自标注式费用数字识别回归（实机，无需人工打标签）

原理：战斗开始后的**自由回费窗口**里 显示费用 = initialCost + floor(t)（h12-4：10 + t 秒数），
直到撞上限（20）。所以只要把「战斗开始时刻」定准，每帧的费用标签**由时间自己给出**，
不存在人工读错标签的问题。

流程：进演习 → 开打 → 以 ~10fps 连拍 → 用"首次出现费用数字"定 t=0 → 对每帧跑识别器 → 统计准确率。
输出：逐帧 (t, 标签, 识别值, 置信度) + 总体准确率 + 错例清单（错例帧落盘供人眼复核）。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.recognize.cost_number import CostNumberRecognizer   # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
LABELED = os.path.join(TMP, 'labeled_cost')
NUM_ROI = (1795, 730, 1915, 805)
INITIAL, CAP = 10, 20


def sh(*a):
    return subprocess.run([ADB, '-s', DEV, *a], capture_output=True)


def main():
    span = float(sys.argv[1]) if len(sys.argv) > 1 else 16.0
    rate = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    os.makedirs(LABELED, exist_ok=True)
    for f in os.listdir(LABELED):
        try:
            os.remove(os.path.join(LABELED, f))
        except Exception:
            pass

    for tap, wait in (((960, 540), 4), ((953, 812), 3), ((1441, 975), 5), ((1659, 766), 1)):
        sh('shell', 'input', 'tap', str(tap[0]), str(tap[1]))
        time.sleep(wait)

    from plugins.capture.emu_window import EmuWindowCapture
    cam = EmuWindowCapture().open()
    print(f'模拟器窗口客户区 = {cam.rect}（桌面坐标）；抓屏后端 = {cam.backend}')
    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': os.path.join(TMP, 'tpl_h124.json')}

    t_wall0 = time.perf_counter()
    samples = []          # (wall_since_launch, cost_or_None, conf, path)
    while time.perf_counter() - t_wall0 < 40:      # 先等在加载结束后出现费用数字
        img = cam.grab()
        if img is None:
            continue
        ms = rec.run(img, spec, None, (0, 0))
        if ms:
            break
        time.sleep(0.05)
    t_battle0 = time.perf_counter()
    if not ms:
        print('40s 内未读到费用数字 —— 大概率没进到战斗（导航需状态自适应），本次作废')
        return
    print(f'检测到战斗开始（首次读到费用数字 = {ms[0].extra["cost"]}）')

    t0 = time.perf_counter()
    while time.perf_counter() - t0 < span:
        img = cam.grab()
        if img is None:
            continue
        t = time.perf_counter() - t_battle0
        ms = rec.run(img, spec, None, (0, 0))
        got = int(ms[0].extra['cost']) if ms else None
        conf = float(ms[0].extra['confidence']) if ms else 0.0
        p = os.path.join(LABELED, f't{t:06.2f}_p{got}.png')
        cv2.imwrite(p, img[max(0, NUM_ROI[1] - 20):NUM_ROI[3] + 40,
                           max(0, NUM_ROI[0] - 40):NUM_ROI[2] + 20])
        samples.append((t, got, conf, p))
        time.sleep(max(0.0, 1.0 / rate - 0.02))

    print(f'\n连拍 {len(samples)} 帧 / {span:.0f}s')
    print('   t(s)   标签  识别  置信')
    ok = bad = 0
    misses = []
    for t, got, conf, p in samples:
        label = min(CAP, INITIAL + int(t))
        good = (got == label)
        ok += good
        bad += (not good)
        if not good:
            misses.append((round(t, 2), label, got, p))
        print(f'  {t:6.2f}  {label:>4}  {str(got):>4}  {conf:5.3f}  {"✓" if good else "✗"}')
    n = max(1, ok + bad)
    print(f'\n准确率 {ok}/{n} = {100.0 * ok / n:.1f}%')
    if misses:
        print('错例（已落盘可人眼复核）：')
        for t, lab, got, p in misses[:12]:
            print(f'   t={t} 标签={lab} 识别={got}  {os.path.basename(p)}')


if __name__ == '__main__':
    main()
