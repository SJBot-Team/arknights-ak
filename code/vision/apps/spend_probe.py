# -*- coding: utf-8 -*-
"""spend_probe.py — 进战斗 → 选干员卡 → **扫描候选格直到部署成功**（费用下降）→ 立即采样

## 为什么用"扫描"而不是"精确算格"
目的只有一个：**消耗费用**，让费用条重新跳动（用户方法一）。
精确算格子需要 battle_area 标定（列向已标定：pitch_x≈130、x0≈97；行向未标定），
而"选中干员后点击地图"是**安全操作**（不合法格只提示、不会误触其它 UI），
所以直接按估计网格扫描，命中即止，最省事也最稳。

## 流程
1. 渲染前置（§7.72）+ adb display 采集（抗遮挡，§7.64）
2. 若不在战斗：用已实测校准的坐标导航（12-4 → 演习 → 开始行动）
3. 依次：点卡片 → 扫描候选格 → 每次读费用；费用下降 = 部署成功
4. 成功后**立即**密集采样，做 相位↔墙钟 精度比对（目标 |误差| ≤ 2 帧）
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture                        # noqa: E402
from plugins.clock.frame_clock import PIXEL_MAP_30F, bar_phase, frame_from_width  # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer              # noqa: E402
from plugins.recognize.maa_anchor import MaaAnchor                          # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
TPL = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\tpl_h124.json'
NUM_ROI = (1795, 730, 1915, 805)
BAR_ROI = (1739, 805, 1919, 818)
MIN_CONF = 0.85

TAP_H124, TAP_DRILL, TAP_START_DETAIL, TAP_START_SQUAD = (1734, 460), (1441, 983), (1710, 990), (1675, 792)
TAP_CONTINUE = (960, 988)
CARD_X = [76, 233, 390, 547, 704, 861]           # 底部卡片栏（帧坐标）
GRID_X = [200, 460, 720, 980, 1240, 1500]
GRID_Y = [250, 400, 550, 700]


def tap(x, y):
    subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True)


def main():
    cap = make_capture('adb')
    ma = MaaAnchor(thr=0.80)
    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}

    def grab():
        return cap.grab().image

    def cost(img):
        ms = rec.run(img, spec, None, (0, 0))
        if not ms:
            return None
        c = float(ms[0].extra.get('confidence', 0.0))
        return int(ms[0].extra['cost']) if c >= MIN_CONF else None

    def phase(img):
        p = bar_phase(img[BAR_ROI[1]:BAR_ROI[3], BAR_ROI[0]:BAR_ROI[2]],
                      full_px=BAR_ROI[2] - BAR_ROI[0])
        return frame_from_width(p['fill_px'], PIXEL_MAP_30F), p['fill_px']

    def in_battle(img):
        return ma.match(img, ma.BATTLE_OFFICIAL_BEGIN, thr=0.85) is not None

    # ---- 导航（若不在战斗）----
    for step in range(10):
        img = grab()
        if in_battle(img):
            print(f'[{step}] 已在战斗，费用 {cost(img)}')
            break
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        br = lambda roi: float((g[roi[1]:roi[3], roi[0]:roi[2]] > 200).mean())
        if float((g[250:400, 300:700] > 200).mean()) > 0.30:
            tap(*TAP_CONTINUE); print(f'[{step}] 结算 → 继续')
        elif br((1500, 900, 1920, 1080)) > 0.10:
            tap(*TAP_START_SQUAD); print(f'[{step}] 编队 → 开始行动')
        elif br((1370, 930, 1510, 1020)) > 0.10:
            tap(*TAP_DRILL); print(f'[{step}] 详情 → 演习')
        else:
            tap(*TAP_H124); print(f'[{step}] 地图 → 12-4')
        time.sleep(1.8)
    else:
        print('导航失败'); return 2
    time.sleep(1.0)

    base = cost(grab())
    print(f'基准费用 = {base}')

    # ---- 扫描部署 ----
    ok_deploy = False
    for ci, cx in enumerate(CARD_X[:4]):
        tap(cx, 967)
        time.sleep(0.7)
        for gy in GRID_Y:
            for gx in GRID_X:
                tap(gx, gy)
                time.sleep(0.55)
                c = cost(grab())
                if c is not None and base is not None and c < base:
                    print(f'  ✅ 部署成功：卡{ci}(x={cx}) → 格({gx},{gy})，费用 {base} → {c}')
                    ok_deploy = True
                    break
            if ok_deploy:
                break
        if ok_deploy:
            break
        print(f'  卡{ci}(x={cx}) 扫描完未成功')
    if not ok_deploy:
        print('  ✗ 扫描完未找到可部署格（可能要拖拽部署，或网格估计偏差过大）')
        return 3

    # ---- 立即采样 ----
    S = []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 9 and len(S) < 12:
        t_a = time.perf_counter(); img = grab(); t_b = time.perf_counter()
        mid = (t_a + t_b) / 2
        c = cost(img); ph, fill = phase(img)
        S.append((mid, c, ph, fill))
        print(f'  采样{len(S)-1}: t={mid-t0:5.2f} 费用={c} 填充={fill}px → 帧={ph}')
        time.sleep(0.25)

    print('\n逐对比较（相位↔墙钟）')
    errs = []
    for i in range(1, len(S)):
        a, b = S[i - 1], S[i]
        if a[1] is None or b[1] is None:
            continue
        dc, dph = b[1] - a[1], (b[2] - a[2]) % 30
        wall = (b[0] - a[0]) * 30.0
        frames = dc * 30 + dph
        e = frames - wall
        if dc == 0 and dph == 0:
            print(f'  #{i}: 静止（封顶/未消耗），跳过')
            continue
        errs.append(abs(e))
        print(f'  #{i}: 费用 {a[1]}→{b[1]}(Δ{dc}) 相位 {a[2]}→{b[2]}(Δ{dph}) ⇒ 推得 {frames} 帧 | '
              f'墙钟 {wall:5.2f} | 误差 {e:+5.2f}')
    if errs:
        errs.sort()
        print(f'\n有效样本 {len(errs)}；|误差| 中位 {errs[len(errs)//2]:.2f}、最大 {errs[-1]:.2f} 帧')
        print('判据 ≤2 帧：' + ('✅ 达标' if errs[len(errs)//2] <= 2 else '🟡 未达标'))
    else:
        print('\n仍无有效样本')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
