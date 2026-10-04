# -*- coding: utf-8 -*-
"""instant_sample.py — 演习进战斗后**零延迟立即采样**，做相位↔墙钟精度验收

## 为什么必须"零延迟"
§7.89/§7.90 的教训：费用上限只有 20，进战斗时费用从 10 起涨，**10 秒就满**；
而"扫描部署"要花 30 秒以上（还会因无部署而判负）⇒ 必须**一进战斗就采**。
本脚本进入战斗后的第一件事就是采样，中途不做任何点击。

## 合规
只点「演习」与编队「开始行动」（演习模式不消耗理智）；结算画面只点"继续"。
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
TAP_DRILL = (1441, 983)
TAP_START_SQUAD = (1675, 792)
TAP_CONTINUE = (960, 988)


def tap(x, y):
    subprocess.run([ADB, '-s', DEV, 'shell', 'input', 'tap', str(int(x)), str(int(y))],
                   capture_output=True)


def main():
    cap = make_capture('adb')
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

    def fp(img):
        return cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')

    # ---- 导航：只轻轻推，进战斗立刻停 ----
    for step in range(8):
        img = grab()
        if in_battle(img):
            print(f'[{step}] 已在战斗 → 立即采样')
            break
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if float((g[450:660, 180:640] > 200).mean()) > 0.25:      # 「任务失败/行动结束」大白字（帧坐标实测）
            tap(*TAP_CONTINUE); print(f'[{step}] 结算 → 继续'); time.sleep(1.6); continue
        before = fp(img)
        tap(*TAP_DRILL); time.sleep(1.8)
        img2 = grab()
        if float(np.abs(fp(img2) - before).mean()) > 3.0:
            print(f'[{step}] 演习生效 → 编队'); 
            tap(*TAP_START_SQUAD); print('    点编队「开始行动」')
            for _ in range(16):
                im3 = grab()
                if in_battle(im3):
                    print('    战斗已开始 → 立即采样')
                    break
                time.sleep(0.5)
            else:
                print('    未进入战斗'); return 2
            break
        print(f'[{step}] 「演习」无效（合规约束：不试其它按钮）')
        return 3
    else:
        print('导航失败'); return 2

    # ---- 零延迟立即采样 ----
    S = []
    t_start = time.perf_counter()
    while time.perf_counter() - t_start < 10 and len(S) < 14:
        ta = time.perf_counter(); img = grab(); tb = time.perf_counter()
        mid = (ta + tb) / 2.0
        c, cf = cost(img)
        ph, fill = phase(img)
        S.append((mid, c, ph, fill))
        print(f'  采样{len(S)-1}: t={mid-t_start:5.2f} 费用={c} conf={cf:.2f} 填充={fill:>3}px 帧={ph}')
        time.sleep(0.2)

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
            print(f'  #{i}: 静止（封顶），跳过')
            continue
        e = frames - wall
        errs.append(abs(e))
        print(f'  #{i}: 费用 {a[1]}→{b[1]}(Δ{dc}) 相位 {a[2]}→{b[2]}(Δ{dph}) ⇒ 推得 {frames:>3} 帧 | '
              f'墙钟 {wall:6.2f} 帧 | 误差 {e:+6.2f}')
    if errs:
        errs.sort()
        print(f'\n有效样本 {len(errs)}；|误差| 中位 {errs[len(errs)//2]:.2f}、最大 {errs[-1]:.2f} 帧')
        print('判据 |误差| ≤ 2 帧：' + ('✅ 达标' if errs[len(errs)//2] <= 2 else '🟡 未达标'))
    else:
        print('\n无有效样本')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
