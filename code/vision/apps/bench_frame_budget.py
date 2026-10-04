# -*- coding: utf-8 -*-
"""bench_frame_budget.py — 帧级执行的时延预算实测（33.3ms/帧 能不能做到）

需求背景（用户 2026-09-14）："游戏中操作的精度需要精确到帧，对识别和响应的要求很高"。
本脚本把**端到端一次帧级操作**拆成若干段逐段计时，回答三个问题：
  1. 采集（窗口抓屏 vs adb screencap）各自多少 ms？够不够 30fps？
  2. 识别（费用条相位 / 费用数字）多少 ms？
  3. 注入（Windows 点击 vs adb tap）多少 ms？
并给出「同帧多操作」的可行批量 N（= 该帧剩余预算 / 单次操作耗时）。

用法：bench_frame_budget.py [--n 30] [--device 127.0.0.1:16384] [--window MuMu]
"""
from __future__ import annotations

import argparse
import os
import statistics
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
FRAME_MS = 1000.0 / 30.0


def timeit(fn, n=30, warmup=3):
    for _ in range(warmup):
        try:
            fn()
        except Exception:
            pass
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        try:
            fn()
        except Exception as e:
            return None, f'{type(e).__name__}: {e}'
        ts.append((time.perf_counter() - t0) * 1000.0)
    return (statistics.median(ts), statistics.mean(ts), min(ts), max(ts)), None


def fmt(label, res, err=None):
    if res is None:
        print(f'  {label:<28} 不可用（{err}）')
        return None
    med, mean, lo, hi = res
    print(f'  {label:<28} 中位 {med:7.2f}ms  均值 {mean:7.2f}  min {lo:6.2f}  max {hi:7.2f}')
    return med


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=30)
    ap.add_argument('--device', default='127.0.0.1:16384')
    ap.add_argument('--window', default='MuMu')
    args = ap.parse_args()

    print(f'帧预算 = {FRAME_MS:.1f}ms / 帧（30fps 逻辑帧）\n')
    print('== 1) 采集 ==')
    cap_win = None
    # 窗口/桌面抓屏（帧级执行的唯一可行路线）
    for mod, cls in (('plugins.capture.dxgi_backend', 'BetterCamCapture'),
                     ('plugins.capture.dxgi_backend', 'DxcamCapture'),
                     ('plugins.capture.mss_backend', None)):
        try:
            m = __import__(mod, fromlist=['*'])
            if cls:
                backend = getattr(m, cls)()
            else:
                names = [n for n in dir(m) if n.endswith('Capture') and n != 'BaseCapture']
                if not names:
                    continue
                backend = getattr(m, names[0])()
            try:
                backend.open()
            except Exception:
                pass
            cap_win = fmt(f'{cls or mod.split(".")[-1]} 抓屏', timeit(lambda: backend.grab(), args.n)[0])
            if cap_win is not None:
                break
        except Exception as e:
            print(f'  {cls or mod} 不可用（{type(e).__name__}: {e}）')

    def adb_shot():
        p = subprocess.run([ADB, '-s', args.device, 'exec-out', 'screencap', '-p'],
                           capture_output=True)
        return len(p.stdout)
    cap_adb = fmt('adb screencap（含 PNG 编码）', timeit(adb_shot, max(5, args.n // 3))[0])

    print('\n== 2) 识别 ==')
    from plugins.clock.frame_clock import bar_phase, render_cost_bar
    img = render_cost_bar(17, width=240)
    rec_bar = fmt('费用条相位（bar_phase 240px）', timeit(lambda: bar_phase(img), args.n)[0])

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    rec_num = None
    try:
        from plugins.recognize.cost_number import CostNumberRecognizer
        import cv2
        shot = cv2.imread(r'C:\Users\23922\Documents\ds_harness\ak\.tmp\now7.png')
        if shot is not None:
            spec = {'roi': [1795, 730, 1915, 805],
                    'templates': r'C:\Users\23922\Documents\ds_harness\ak\.tmp\tpl_h124.json'}
            r = CostNumberRecognizer()
            rec_num = fmt('费用数字（模板匹配）',
                          timeit(lambda: r.run(shot, spec, None, (0, 0)), args.n)[0])
    except Exception as e:
        print(f'  费用数字识别不可用（{type(e).__name__}: {e}）')

    print('\n== 3) 注入 ==')
    def adb_tap():
        subprocess.run([ADB, '-s', args.device, 'shell', 'input', 'tap', '5', '5'],
                       capture_output=True)
    inj_adb = fmt('adb input tap（往返）', timeit(adb_tap, max(5, args.n // 3))[0])

    inj_win = None
    for mod, cls in (('plugins.action.backends', 'SendInputBackend'),
                     ('plugins.action.backends', 'DirectInputBackend')):
        try:
            m = __import__(mod, fromlist=['*'])
            backend = getattr(m, cls)()
            inj_win = fmt(f'{cls} 点击注入', timeit(lambda: backend.click(5, 5), args.n)[0])
            if inj_win is not None:
                break
        except Exception as e:
            print(f'  {cls} 不可用（{type(e).__name__}: {e}）')

    print('\n== 4) 端到端「识别→注入」一次帧级操作 ==')
    cap = cap_win if cap_win else cap_adb
    rec = rec_bar if rec_bar else 0.0
    inj = inj_win if inj_win else inj_adb
    if cap and inj:
        total = cap + rec + inj
        print(f'  采集 {cap:.1f} + 识别 {rec:.1f} + 注入 {inj:.1f} = {total:.1f}ms'
              f'  （{total / FRAME_MS:.2f} 帧）')
        slack = FRAME_MS - total
        print(f'  单帧预算剩余 {slack:+.1f}ms'
              + (' ⇒ 可以做到单帧内闭环' if slack > 0 else ' ⇒ **超出 1 帧**，必须用「暂停批处理」或降低识别频率'))
        if slack > 0:
            print(f'  同帧可叠加操作数 ≈ {int(slack / inj) + 1} 次（注入 {inj:.1f}ms/次）')
    print('\n注：adb 采集/注入是「截图→编码→传输」链路，天然是秒级；'
          '帧级执行必须走**窗口抓屏 + 本机注入**（PRTS+ 也是这个路线：MuMu12 + 键鼠方案）。')


if __name__ == '__main__':
    main()
