# -*- coding: utf-8 -*-
"""consume_and_sample.py — 进战斗 → **故意部署消耗费用** → 在"费用条跳动"窗口采样 → 相位精度比对

## 为什么必须消耗（§7.86 实测）
H12-4 演习里**准备阶段费用就已回满到上限 20**，战斗开始后若不消耗，费用恒为 20 ⇒
费用条**填满静止**（相位恒 29、比例 1.000），相位就不可用。
按用户方法一："当费用快满时，消耗它，使费用条保持跳动" ⇒ 本脚本部署一个干员把费用拉下来，
制造约 10 秒的"条在跳动"窗口再采样。

## 流程
1. 置前台 → 渲染校验（§7.72 规程）
2. 状态自适应导航到战斗（坐标均已实测校准，见 §7.85）
3. **点干员卡 → 检测地图上的绿色可部署高亮 → 点击部署**（消耗费用）
4. 立刻密集采样 N 帧：读费用数字 + 用官方 pixel_map 查表得条内精确帧
5. 逐对比较 `推得逻辑帧 = Δ费用×30 + Δ相位` 与 `墙钟Δt×30`，输出 |误差| 分布
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

from plugins.capture.emu_window import EmuWindowCapture                      # noqa: E402
from plugins.clock.frame_clock import PIXEL_MAP_30F, bar_phase, frame_from_width  # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer                # noqa: E402
from plugins.recognize.maa_anchor import MaaAnchor                            # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TPL = os.path.join(TMP, 'tpl_h124.json')
NUM_ROI = (1795, 730, 1915, 805)
BAR_ROI = (1739, 805, 1919, 818)          # 官方标定：条宽 180px、左端 1739（§7.78）
MIN_CONF = 0.85

# 实测校准坐标（§7.85）
TAP_CONTINUE = (960, 988)
TAP_H124 = (1734, 460)
TAP_DRILL = (1441, 983)
TAP_START = (1710, 990)                   # MAA BattleStartPre ROI → (1710,990)
CARD_CANDIDATES = [(1647, 985), (1830, 985), (1647, 1010), (1830, 1010)]


def adb_tap(x, y):
    subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True)


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    cam = EmuWindowCapture().open()
    cam.bring_to_front()
    ma = MaaAnchor(thr=0.85)
    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}

    def grab():
        return cam.grab().image

    def read_cost(img):
        ms = rec.run(img, spec, None, (0, 0))
        if not ms:
            return None, 0.0
        c = float(ms[0].extra.get('confidence', 0.0))
        return (int(ms[0].extra['cost']) if c >= MIN_CONF else None), c

    def phase(img):
        band = img[BAR_ROI[1]:BAR_ROI[3], BAR_ROI[0]:BAR_ROI[2]]
        ph = bar_phase(band, full_px=BAR_ROI[2] - BAR_ROI[0])
        return frame_from_width(ph['fill_px'], PIXEL_MAP_30F), ph['fill_px']

    def in_battle(img):
        return ma.match(img, MaaAnchor.BATTLE_OFFICIAL_BEGIN, thr=0.85) is not None

    # ---- 1) 渲染校验 ----
    prev, ok_r = None, False
    for _ in range(5):
        img = grab()
        fp = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')
        if prev is not None and float(np.abs(fp - prev).mean()) > 0.005:
            ok_r = True
            break
        prev = fp
        time.sleep(0.4)
    print(f'渲染校验: {"通过" if ok_r else "★未通过"}')
    if not ok_r:
        return 4

    # ---- 2) 导航到战斗 ----
    for step in range(10):
        img = grab()
        if in_battle(img):
            c, _ = read_cost(img)
            print(f'[{step}] 已在战斗（费用 {c}）')
            break
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        bright = lambda roi: float((g[roi[1]:roi[3], roi[0]:roi[2]] > 200).mean())
        dark = float((g < 50).mean())
        if float((g[250:400, 300:700] > 200).mean()) > 0.25:     # 结算
            adb_tap(*TAP_CONTINUE); print(f'[{step}] 结算 → 继续')
        elif bright((1500, 900, 1920, 1080)) > 0.10:             # 编队「开始行动」
            adb_tap(*TAP_START); print(f'[{step}] 编队 → 开始行动')
            tw = time.perf_counter()
            while time.perf_counter() - tw < 30:
                im2 = grab()
                if in_battle(im2):
                    print('   → 战斗已开始')
                    break
                time.sleep(0.4)
        elif bright((1370, 930, 1510, 1020)) > 0.10:             # 关卡详情「演习」
            adb_tap(*TAP_DRILL); print(f'[{step}] 详情 → 演习')
        else:
            adb_tap(*TAP_H124); print(f'[{step}] 地图 → 12-4')
        time.sleep(1.5)
    else:
        print('导航失败'); return 2

    # ---- 3) 故意消耗：点干员卡 → 检测绿色可部署格 → 点击 ----
    c0 = None
    for i, card in enumerate(CARD_CANDIDATES):
        img = grab()
        c_before, _ = read_cost(img)
        adb_tap(*card)
        time.sleep(0.8)
        img2 = grab()
        b = img2[..., 0].astype('int16'); g2 = img2[..., 1].astype('int16'); r2 = img2[..., 2].astype('int16')
        mask = ((g2 > r2 + 15) & (g2 > b + 10) & (g2 > 110)).astype('uint8')
        # 排除右下部署栏与顶部 HUD
        mask[:100, :] = 0
        mask[880:, :] = 0
        n_pix = int(mask.sum())
        print(f'  卡候选{i} {card}: 选卡后绿色高亮像素 {n_pix}')
        if n_pix < 500:
            continue
        ys, xs = np.nonzero(mask)
        # 取最大连通块的质心
        num, lab, stats, cent = cv2.connectedComponentsWithStats(mask, 8)
        if num <= 1:
            continue
        idx = 1 + int(np.argmax(stats[1:, 4]))
        cx, cy = cent[idx]
        print(f'   → 绿格中心 ({cx:.0f},{cy:.0f}) 面积 {stats[idx,4]}；点击部署')
        adb_tap(cx, cy)
        time.sleep(1.2)
        img3 = grab()
        c_after, _ = read_cost(img3)
        print(f'   → 部署前费用 {c_before} / 部署后 {c_after}')
        if c_before is not None and c_after is not None and c_after < c_before:
            print('   ✅ 费用已下降（消耗成功）→ 进入跳动窗口')
            c0 = c_after
            break
        else:
            print('   ✗ 费用未下降，换下一张卡')

    # ---- 4) 采样 ----
    samples = []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 12 and len(samples) < n:
        img = grab()
        t = time.perf_counter() - t0
        c, conf = read_cost(img)
        ph, fill = phase(img)
        samples.append((t, c, conf, ph, fill))
        print(f'  采样{len(samples)-1}: t={t:5.2f} 费用={c} conf={conf:.3f} 相位={ph:>2} 填充={fill}px')
        time.sleep(0.3)

    # ---- 5) 精度比对 ----
    print('\n逐对比较：推得逻辑帧(Δ费用×30+Δ相位) vs 墙钟Δt×30')
    errs = []
    for i in range(1, len(samples)):
        t0_, c0_, _, p0_, _ = samples[i - 1]
        t1_, c1_, _, p1_, _ = samples[i]
        if c0_ is None or c1_ is None:
            continue
        dc = c1_ - c0_
        dph = (p1_ - p0_) % 30
        cap = (c0_ >= 20 and c1_ >= 20)
        if cap and dph == 0:
            print(f'  #{i}: {c0_}→{c1_} 相位 {p0_}→{p1_} ⇒ 封顶静止，跳过')
            continue
        frames = dc * 30 + dph
        wall = (t1_ - t0_) * 30.0
        e = frames - wall
        errs.append(e)
        print(f'  #{i}: 费用 {c0_}→{c1_}(Δ{dc}) 相位 {p0_}→{p1_}(Δ{dph}) ⇒ 推得 {frames:>3} 帧 | '
              f'墙钟 {wall:6.2f} 帧 | 误差 {e:+6.2f} 帧')
    if errs:
        a = sorted(abs(e) for e in errs)
        med = a[len(a) // 2]
        print(f'\n有效样本 {len(errs)}；|误差| 中位 {med:.2f} 帧、最大 {a[-1]:.2f} 帧')
        print('判据 |误差| ≤ 2 帧 ⇒ 方法一可用于帧级对齐：' + ('✅ 达标' if med <= 2 else '🟡 未达标'))
    else:
        print('\n没有有效样本（可能仍被封顶或未消耗成功）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
