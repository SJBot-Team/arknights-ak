# -*- coding: utf-8 -*-
"""enter_drill.py — 状态自适应地进到「演习战斗内」，并录一段带时间戳的帧序列

为什么需要状态自适应：之前写死了"关掉结算 → 点 H12-4 → 演习 → 开始行动"的固定序列，
一旦游戏停在别的界面（编队/结算/关卡地图）就会点空，最后表现为"40s 内读不到费用数字"。

本脚本每步都**先看画面再决定**：
  1) 已在战斗（费用数字 ROI 读得出值）→ 直接开始录制；
  2) 看到「开始行动」按钮（编队界面）→ 点它；
  3) 看到「演习」按钮（关卡详情）→ 点它；
  4) 否则当作关卡地图 → 点 H12-4 节点。
每一步都会打印判定依据，失败会明确报出来（不再静默）。

录制：`plugins.capture.emu_window.EmuWindowCapture`（只抓模拟器窗口客户区，与 adb 帧缓冲逐像素对齐），
按 ~15fps 存帧 + 存时间戳 csv，供后续离线标定 ROI / 验证帧级时钟。
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture               # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer     # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
NUM_ROI = (1795, 730, 1915, 805)
TPL = os.path.join(TMP, 'tpl_h124.json')

# 已标定的界面坐标（adb 帧缓冲坐标 = 窗口客户区坐标）
TAP_H124 = (953, 812)
TAP_DRILL = (1441, 975)
TAP_START = (1659, 766)          # 编队界面「开始行动」
TAP_DISMISS = (960, 540)


def sh(*a):
    return subprocess.run([ADB, '-s', DEV, *a], capture_output=True)


def tap_window(cam, x, y):
    """把帧缓冲坐标换成桌面坐标后用 adb 点（adb 点的是模拟器内部坐标，直接可用）。"""
    sh('shell', 'input', 'tap', str(int(x)), str(int(y)))


def bright_ratio(img, roi, thr=200):
    x0, y0, x1, y1 = roi
    g = img[y0:y1, x0:x1]
    g = g[..., :3].mean(axis=2) if g.ndim == 3 else g
    return float((g > thr).mean())


def main():
    span = float(sys.argv[1]) if len(sys.argv) > 1 else 15.0
    fps = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
    cam = make_capture('adb')          # adb display 通道：遮挡无关、真画面（§7.64）
    print(f'采集器 = {type(cam).__name__}（adb display {cam.display}）')
    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}

    MIN_CONF = 0.85      # ⚠ 置信度阈值：低置信度误判是本轮踩到的坑（§7.66）

    def read_cost():
        """只在**高置信度**下才认账。

        §7.66 教训：编队界面「开始行动」按钮上的白色笔画会被字形切分当成数字，
        置信度只有 0.328（正确帧 0.962）⇒ 不加阈值就会把"停在编队界面"误判成"已在战斗"，
        于是后续 tap 全不执行，整段采样只会读到"恒定 9"。
        """
        img = cam.grab().image
        ms = rec.run(img, spec, None, (0, 0))
        if not ms:
            return None
        conf = float(ms[0].extra.get('confidence', 0.0))
        return int(ms[0].extra['cost']) if conf >= MIN_CONF else None

    def state():
        img = cam.grab().image
        c = read_cost()
        if c is not None:
            return 'battle', img
        # 右下角「开始行动」区域很亮（蓝底白字按钮）
        if bright_ratio(img, (1540, 610, 1760, 900)) > 0.02:
            return 'squad', img
        if bright_ratio(img, (1370, 930, 1510, 1020)) > 0.02:
            return 'detail', img
        return 'map', img

    for step in range(12):
        st, _ = state()
        print(f'  [{step}] 当前界面判定 = {st}')
        if st == 'battle':
            break
        if st == 'squad':
            tap_window(cam, *TAP_START)
            time.sleep(1.0)
        elif st == 'detail':
            tap_window(cam, *TAP_DRILL)
            time.sleep(1.2)
        else:
            tap_window(cam, *TAP_H124)
            time.sleep(1.2)
    else:
        print('12 步内没能进到战斗，放弃（并保持游戏原状）')
        return 2

    # 等战斗真正开始（能读到费用数字）
    t_launch = time.perf_counter()
    while time.perf_counter() - t_launch < 40:
        if read_cost() is not None:
            break
        time.sleep(0.1)
    t0 = time.perf_counter()
    print(f'战斗已开始（t0 记在此刻）；开始录制 {span:.0f}s @ {fps:.0f}fps')

    outdir = os.path.join(TMP, 'battle_frames')
    os.makedirs(outdir, exist_ok=True)
    for f in os.listdir(outdir):
        try:
            os.remove(os.path.join(outdir, f))
        except Exception:
            pass
    rows = []
    i = 0
    while time.perf_counter() - t0 < span:
        img = cam.grab().image
        t = time.perf_counter() - t0
        name = f'f{i:04d}.png'
        cv2.imwrite(os.path.join(outdir, name), img)
        c = None
        ms = rec.run(img, spec, None, (0, 0))
        c = int(ms[0].extra['cost']) if ms else None
        rows.append((round(t, 4), name, c if c is not None else ''))
        i += 1
        time.sleep(max(0.0, 1.0 / fps - 0.02))
    with open(os.path.join(outdir, 'timestamps.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['t_sec', 'file', 'cost_read'])
        w.writerows(rows)
    print(f'录制 {len(rows)} 帧 → {outdir}')
    got = [r[2] for r in rows if r[2] != '']
    print(f'  其中读到费用数字 {len(got)} 帧，取值范围 {min(got) if got else None}~{max(got) if got else None}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
