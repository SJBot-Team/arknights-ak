# -*- coding: utf-8 -*-
"""auto_sample_v2.py — 目标驱动导航（多界面分支）→ 进战斗**立即采样** → 相位↔墙钟验收

## 与上一版的差别
1. 支持更多界面分支：结算 / 关卡详情(演习) / 编队(开始行动) / 「清理人的收藏」列表 / 关卡地图；
2. **进战斗后立刻采样**（§7.94：任何额外点击/截图都会让费用涨满、甚至输棋）；
3. 每步打印判据数值，便于诊断卡在哪。

## 合规
只点「演习」与编队「开始行动」（演习不消耗理智）、结算"继续"；不点任何"开始行动"之外的消耗项。
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
from plugins.recognize.maa_anchor import MaaAnchor
from plugins.recognize.ui_state import UiState                          # noqa: E402

ADB = r'D:\__soft\MuMu Player 12\shell\adb.exe'
DEV = '127.0.0.1:16384'
TPL = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\tpl_h124.json'
NUM_ROI = (1795, 730, 1915, 805)
BAR_ROI = (1739, 805, 1919, 818)
MIN_CONF = 0.85

TAP_DRILL = (1441, 983)
TAP_START_SQUAD = (1675, 792)
TAP_CONTINUE = (960, 988)
TAP_H124_LIST = (1549, 819)      # 「清理人的收藏」列表里的 H12-4
TAP_H124_MAP = (1160, 667)       # 关卡地图上的 12-4（此前实测可用）


def tap(x, y, twice=False):
    for _ in range(2 if twice else 1):
        subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                       capture_output=True)
        if twice:
            time.sleep(0.12)


def main():
    cap = make_capture('adb')
    # ★ 渲染前置（§7.72）：MuMu 失去前台会**停止渲染并丢弃输入**（表现为判据全 0、点击全无效），
    #   必须先强制置前，否则后面每一轮都在对一张静止旧帧做判断。
    try:
        from plugins.capture.render_guard import ensure_foreground
        ensure_foreground()
        print('已置前台（保证渲染与输入生效）')
    except Exception as e:
        print('置前台失败:', e)
    # ★ 渲染闸门（§7.98）：渲染停止时 adb 帧缓冲精确冻结，一切画面判断都无意义 ⇒ 直接退出
    from plugins.capture.render_guard import assert_rendering
    if not assert_rendering(cap, tries=5, interval=0.4, thresh=0.005, quiet=True):
        print('★ 渲染仍停止（adb 帧缓冲冻结）—— 实机流程无法进行，需重启模拟器实例')
        return 4
    print('渲染校验通过（画面在变）')
    ma = MaaAnchor(thr=0.85)
    rec = CostNumberRecognizer()
    spec = {'roi': list(NUM_ROI), 'templates': TPL}

    def grab():
        return cap.grab().image

    def cost(img):
        ms = rec.run(img, spec, None, (0, 0))
        if not ms:
            return None, 0.0
        c = float(ms[0].extra.get('confidence', 0.0))
        return (int(ms[0].extra['cost']) if c >= MIN_CONF else None), c

    def phase(img):
        p = bar_phase(img[BAR_ROI[1]:BAR_ROI[3], BAR_ROI[0]:BAR_ROI[2]],
                      full_px=BAR_ROI[2] - BAR_ROI[0])
        return frame_from_width(p['fill_px'], PIXEL_MAP_30F), p['fill_px']

    def in_battle(img):
        return ma.match(img, ma.BATTLE_OFFICIAL_BEGIN, thr=0.85) is not None

    def classify(img):
        """改用 **MAA 模板界面判定**（§7.97），不再用"白色占比"这类脆弱判据。"""
        return ui.classify(img)

    ui = UiState()
    # ---------- 导航 ----------
    for step in range(10):
        img = grab()
        r = classify(img)
        st = r['state']
        print(f'[{step}] UiState={st} 证据={ {k: round(v, 2) for k, v in r["hits"].items()} }')
        if st == 'battle':
            print(f'[{step}] 已在战斗 → 立即采样')
            break
        if st == 'squad':
            pt = r['start_point'] or TAP_START_SQUAD
            tap(*pt); print(f'    编队 → 开始行动 @{pt}（模板定位）')
            for _ in range(16):
                if in_battle(grab()):
                    print('    战斗已开始 → 立即采样')
                    break
                time.sleep(0.4)
            else:
                print('    未进入战斗'); continue
            break
        if st == 'viewport':
            # 详情/地图/收藏列表：先试「演习」，无效再试节点
            before = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')
            tap(*TAP_DRILL); time.sleep(1.6)
            img2 = grab()
            after = cv2.resize(cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')
            if float(np.abs(after - before).mean()) > 3.0:
                print('    详情 → 演习（生效）')
                time.sleep(0.6)
                continue
            tap(*TAP_H124_LIST, twice=True); print('    地图/列表 → 双击 H12-4')
        else:
            tap(*TAP_CONTINUE); print('    结算/加载（unknown）→ 点继续')
        time.sleep(1.6)
    else:
        print('导航失败'); return 2

    # ---------- 立即采样 ----------
    S = []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 10 and len(S) < 16:
        ta = time.perf_counter(); img = grab(); tb = time.perf_counter()
        mid = (ta + tb) / 2.0
        c, cf = cost(img)
        ph, fill = phase(img)
        S.append((mid, c, ph, fill))
        print(f'  采样{len(S)-1}: t={mid-t0:5.2f} 费用={c} conf={cf:.2f} 填充={fill:>3}px 帧={ph}')
        time.sleep(0.18)

    print('\n逐对比较（相位↔墙钟）')
    errs = []
    for i in range(1, len(S)):
        a, b = S[i - 1], S[i]
        if a[1] is None or b[1] is None:
            continue
        dc, dph = b[1] - a[1], (b[2] - a[2]) % 30
        wall = (b[0] - a[0]) * 30.0
        frames = dc * 30 + dph
        if dc == 0 and dph == 0:
            print(f'  #{i}: 静止（封顶），跳过'); continue
        e = frames - wall
        errs.append(abs(e))
        print(f'  #{i}: 费用 {a[1]}→{b[1]}(Δ{dc}) 相位 {a[2]}→{b[2]}(Δ{dph}) ⇒ 推得 {frames:>3} 帧 | '
              f'墙钟 {wall:6.2f} | 误差 {e:+6.2f}')
    if errs:
        errs.sort()
        print(f'\n有效样本 {len(errs)}；|误差| 中位 {errs[len(errs)//2]:.2f}、最大 {errs[-1]:.2f} 帧')
        print('判据 |误差| ≤ 2 帧：' + ('✅ 达标' if errs[len(errs)//2] <= 2 else '🟡 未达标'))
    else:
        print('\n无有效样本')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
