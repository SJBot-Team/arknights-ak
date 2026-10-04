# -*- coding: utf-8 -*-
"""probe_spend_sample.py — 演习进战斗 → 扫描部署消耗费用 → 立即采样 → 相位↔墙钟比对

## 合规保护（硬约束）
**只点「演习」按钮，绝不点「开始行动」**（后者会消耗理智）：
轮询导航里若"演习"点击无效（画面无变化），就**直接放弃退出**，不去试其它可能消耗理智的按钮。

## 为什么扫描部署
目的只有一个：消耗费用让费用条重新跳动（用户方法一）。选中干员后点击地图是**安全操作**
（不合法格只提示），所以按估计网格扫描、命中即止，无需 battle_area 行向标定。
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

TAP_DRILL = (1441, 983)        # 关卡详情「演习」
TAP_START_SQUAD = (1675, 792)  # 编队「开始行动」（演习模式下不消耗理智）
CARD_Y = 967
CARD_X = [76, 233, 390, 547, 704, 861]
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
    fp_cache = {}

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

    def fp(img):
        return cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')

    img = grab()
    if in_battle(img):
        print('已在战斗')
    else:
        # 只点「演习」；无效就退出（合规）
        before = fp(img)
        tap(*TAP_DRILL)
        time.sleep(2.0)
        img = grab()
        d = float(np.abs(fp(img) - before).mean())
        print(f'点「演习」画面变化 {d:.1f}')
        if d < 3.0:
            print('「演习」点击无效 ⇒ 按合规约束退出，不去试可能消耗理智的按钮')
            return 2
        tap(*TAP_START_SQUAD)
        print('点编队「开始行动」')
        for i in range(14):
            img = grab()
            if in_battle(img):
                print('  战斗已开始')
                break
            time.sleep(1.5)
        else:
            print('  未进入战斗'); return 2
    time.sleep(0.8)

    base = cost(grab())
    print(f'战斗内基准费用 = {base}')

    ok = False
    for ci, cx in enumerate(CARD_X[:3]):
        tap(cx, CARD_Y)
        time.sleep(0.6)
        for gy in GRID_Y:
            for gx in GRID_X:
                tap(gx, gy)
                time.sleep(0.5)
                c = cost(grab())
                if c is not None and base is not None and c < base:
                    print(f'  ✅ 部署成功：卡{ci}(x={cx}) → 格({gx},{gy})，费用 {base} → {c}')
                    ok = True
                    break
            if ok:
                break
        if ok:
            break
        print(f'  卡{ci} 扫描完未成功')
    if not ok:
        print('  ✗ 未能部署（网格估计可能偏差过大）')
        return 3

    S = []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 9 and len(S) < 12:
        ta = time.perf_counter(); img = grab(); tb = time.perf_counter()
        mid = (ta + tb) / 2
        c = cost(img); ph, fill = phase(img)
        S.append((mid, c, ph, fill))
        print(f'  采样{len(S)-1}: t={mid-t0:5.2f} 费用={c} 填充={fill}px 帧={ph}')
        time.sleep(0.25)

    print('\n逐对比较（相位↔墙钟）')
    errs = []
    for i in range(1, len(S)):
        a, b = S[i - 1], S[i]
        if a[1] is None or b[1] is None:
            continue
        dc, dph = b[1] - a[1], (b[2] - a[2]) % 30
        if dc == 0 and dph == 0:
            print(f'  #{i}: 静止（封顶），跳过')
            continue
        wall = (b[0] - a[0]) * 30.0
        frames = dc * 30 + dph
        e = frames - wall
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
