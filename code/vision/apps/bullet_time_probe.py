# -*- coding: utf-8 -*-
"""bullet_time_probe.py — ★验证"子弹时间"：**拖出干员（悬停不落格）后游戏是否真的减速**。

## 依据（用户 2026-09-15 给出的 PRTS+ 方案第②步）
> 「到大约**操作前一秒**进入**子弹时间**，**操作前 5 帧**开始**子弹时间过帧**」

若子弹时间成立，则"过帧"才有意义（1X 下 1 帧 = 33ms，靠外部注入根本追不上；
减速后单帧窗口被拉长，才能逐帧精确操作）。

## 判据
用**费用条相位推进速率**当"游戏时间流速"的度量：
- **基线**（正常运行）：应为 **~30 帧/秒**（1X）；
- **悬停干员**（`Deployer.motion` 拖出但不落格 ⇒ 干员保持 held，画面出现「点击取消」）：
  若显著低于 30 帧/秒（例如 2~8），则**子弹时间成立**，并给出实测倍率。

## 安全
只做**界面级拖拽**（不落格、随后取消），不消耗资源；仅截图 + 只读识别。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer                       # noqa: E402
from plugins.capture.emu_window import make_capture              # noqa: E402
from plugins.recognize.battle_hud import BattleHudGate           # noqa: E402
from plugins.recognize.cost_bar import CostBarRecognizer         # noqa: E402

CARD = (63, 949)          # 芬卡片（实机实测：费用升序首张）
from plugins.action.grid_px import coord_to_px as _c2p
CELL_D6 = _c2p("D6")       # ★唯一真源 plugins/action/grid_px（= (1182,502)）


def rate(cap, bar, gate, dur: float, tag: str):
    """采样 dur 秒，返回 (帧/秒, 满条次数, 样本数)。"""
    rec = CostBarRecognizer()
    t0 = time.perf_counter()
    prev, wraps, n = None, 0, 0
    first = None
    while time.perf_counter() - t0 < dur:
        fr = cap.grab()
        if not gate.check(fr.image)['in_battle']:
            time.sleep(0.1)
            continue
        ms = rec.run(fr.image, {}, None, fr.origin)
        if not ms:
            time.sleep(0.05)
            continue
        ph = int(ms[0].extra['frame'])
        if prev is not None and ph < prev:
            wraps += 1
        prev = ph
        n += 1
        if first is None:
            first = (time.perf_counter() - t0, ph)
        time.sleep(0.02)
    span = (time.perf_counter() - t0) - (first[0] if first else 0)
    adv = wraps * 30 + (prev or 0) - (first[1] if first else 0)
    fps = adv / span if span > 0 else 0.0
    print(f'  [{tag}] {span:.2f}s 内推进 {adv} 帧 ⇒ **{fps:.1f} 帧/秒**'
          f'（满条 {wraps} 次，样本 {n}）')
    return fps, wraps, n


def main() -> int:
    cap = make_capture('adb')
    bar, gate = CostBarRecognizer(), BattleHudGate()
    dep = Deployer(cap)

    print('=== ① 基线（正常运行）===')
    base, _, base_s = rate(cap, bar, gate, 8.0, '基线')

    print('\n=== ② 拖出干员（悬停不落格）→ 期望减速 ===')
    dep.motion([CARD, (500, 750), CELL_D6], hold_ms=200, between_ms=180)
    time.sleep(0.4)
    held, _, held_s = rate(cap, bar, gate, 8.0, '悬停')

    print('\n=== ③ 取消悬停 ===')
    dep.tap(732, 304)          # 「点击取消」
    time.sleep(1.0)

    print('\n=== 汇总 ===')
    print(f'基线 {base:.1f} 帧/秒 → 悬停 {held:.1f} 帧/秒')
    if base_s == 0 or held_s == 0:
        print('⚠️ **测量失败**（悬停段样本数为 0）⇒ 不能据此判定减速；'
              '常见原因：拖出干员时卡片行隐藏导致门控误判（已在 `BattleHudGate` 加「点击取消」悬停信号修复）')
        return 1
    if base > 0:
        print(f'**减速比 ≈ {base / max(0.01, held):.1f}×**')
    if held < base * 0.6:
        print('✅ **子弹时间成立**：拖出干员后游戏时间流速显著下降 ⇒ "过帧"具备逐帧窗口')
    else:
        print('⚠️ 未观察到显著减速：悬停可能未保持，或该版本子弹时间不作用于费用条计时')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
