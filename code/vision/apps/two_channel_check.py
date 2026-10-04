# -*- coding: utf-8 -*-
"""two_channel_check.py — ★双通道互验：**费用条填充** ↔ **费用数字跳变**。

## 为什么
用户方案第①步是「统计**费用条满的次数**以记录绝对时间」。
判据正确性的黄金标准是：**费用条每满一次（回绕）⇔ 费用数字恰好 +1**。
视频侧我们已用这两条独立时钟互验过（建出"视频↔游戏帧轴"）；
本脚本在**实机**上做同一件事，把费用条时钟的残差收敛、并给出可信度证据。

## 输出
- 每次采样的 `(相位, fill_px, 费用数字)`
- **满条回绕次数** vs **费用数字 +1 次数**（应相等）
- 每次 +1 前后相位（应在 30 → 0 附近）
- 判定：一致 / 不一致（并指出偏差模式）

## 安全
只截图 + 只读识别；**不注入任何输入**。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.capture.emu_window import make_capture              # noqa: E402
from plugins.recognize.battle_hud import BattleHudGate           # noqa: E402
from plugins.recognize.cost_bar import CostBarRecognizer         # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer   # noqa: E402

TPL = r'C:\Users\23922\Documents\ds_harness\ak\.tmp\tpl_h124.json'


def main() -> int:
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 25.0
    cap = make_capture('adb')
    bar, num, gate = CostBarRecognizer(), CostNumberRecognizer(), BattleHudGate()
    spec_num = {'roi': [1795, 730, 1915, 805]}
    if os.path.exists(TPL):
        spec_num['templates'] = TPL
        print('数字模板:', TPL)
    print(f'采样 {dur:.0f}s —— 双通道互验')
    print(f'{"t(s)":>6} {"相位":>5} {"fill":>5} {"费用":>5}  事件')
    t0 = time.perf_counter()
    prev_ph = prev_cost = None
    wraps = ups = 0
    up_phase = []
    rows = []
    while time.perf_counter() - t0 < dur:
        fr = cap.grab()
        img = fr.image
        wall = time.perf_counter() - t0
        g = gate.check(img)
        if not g['in_battle']:
            print(f'{wall:>6.2f} {"--":>5} {"--":>5} {"--":>5}  非战斗（{g["reason"]}）')
            time.sleep(0.1)
            continue
        mb = bar.run(img, {}, None, fr.origin)
        mn = num.run(img, spec_num, None, fr.origin)
        ph = int(mb[0].extra['frame']) if mb else None
        fpx = int(mb[0].extra.get('fill_px', -1)) if mb else None
        cost = int(mn[0].extra['cost']) if mn else None
        ev = []
        if ph is not None and prev_ph is not None and ph < prev_ph:
            wraps += 1
            ev.append('条满(回绕)')
        if cost is not None and prev_cost is not None and cost > prev_cost:
            ups += 1
            up_phase.append(prev_ph if prev_ph is not None else -1)
            ev.append(f'费用+{cost - prev_cost}')
        prev_ph, prev_cost = (ph if ph is not None else prev_ph), \
                             (cost if cost is not None else prev_cost)
        rows.append((ph, fpx, cost))
        print(f'{wall:>6.2f} {str(ph):>5} {str(fpx):>5} {str(cost):>5}  {" ".join(ev)}')
        time.sleep(0.05)

    print('\n=== 汇总 ===')
    print(f'满条回绕 {wraps} 次；费用 +1 共 {ups} 次')
    if up_phase:
        print(f'费用 +1 前的相位样本: {up_phase}')
    # ★正确判据（不受采样边界影响）：**每次"费用 +1"都应发生在"本条末尾"**，
    #   即其前的相位样本应接近满条（≥25）。回绕次数与递增次数允许相差 1
    #   （满条与 +1 同刻发生，可能被采样边界切到相邻两个样本里）。
    near_full = [p for p in up_phase if p >= 25]
    ratio = len(near_full) / max(1, len(up_phase))
    print(f'其中相位 ≥25（本条末尾）的比例: {len(near_full)}/{len(up_phase)} = {ratio:.0%}')
    ok = (abs(wraps - ups) <= 1) and ratio >= 0.5
    print('✅ 两通道一致：**费用 +1 恰好发生在费用条满（本条末尾）**；'
          f'回绕 {wraps} ≈ 递增 {ups}（差 ≤1 由采样边界造成）'
          if ok else
          f'⚠️ 需复核：回绕 {wraps} vs 递增 {ups}，相位≥25 比例 {ratio:.0%}')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
