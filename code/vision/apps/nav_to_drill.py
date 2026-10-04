# -*- coding: utf-8 -*-
"""nav_to_drill.py — 自动导航到「1-1 演习战斗」，**每步用信号校验**（不盲点）。

## 状态判据（本机实测标定）
| 状态 | 判据 |
|---|---|
| **战斗中** | `BattleHudGate.in_battle` |
| **关卡详情页** | `btn_drill ≥ 170`（「演习」灰白按钮区域 1450..1570 × 950..1030 的均值亮度） |
| **编队页** | `110 ≤ btn_drill < 170` |
| **章节地图** | `btn_drill < 110` 且非以上 |
| **加载/结算** | 全图均值 < 60 ⇒ 点画面中央继续 |

## 动作
- 章节地图 → 点 1-1 节点 (919,520)
- 关卡详情页 → 点「演习」(1509,988)
- 编队页 → 点「开始行动」(1662,810)
- 加载/结算 → 点中央 (960,540)

最多 10 步；到达战斗即返回 0。**只做界面级点击与截图**。
"""
from __future__ import annotations

import os
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer                    # noqa: E402
from plugins.capture.emu_window import make_capture           # noqa: E402
from plugins.recognize.battle_hud import BattleHudGate        # noqa: E402

STAGE_NODE = (919, 520)
BTN_DRILL = (1509, 988)
BTN_START = (1662, 810)
CENTER = (960, 540)
TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'


def signals(img, gate):
    st = gate.check(img)
    drill = float(cv2.cvtColor(img[950:1030, 1450:1570], cv2.COLOR_BGR2GRAY).mean())
    return st['in_battle'], drill, float(img.mean())


def which(in_battle, drill, mean):
    if in_battle:
        return 'battle'
    if mean < 60:
        return 'loading'
    if drill >= 170:
        return 'stage'
    if drill >= 110:
        return 'squad'
    return 'map'


def main() -> int:
    cap = make_capture('adb')
    dep, gate = Deployer(cap), BattleHudGate()
    for step in range(1, 11):
        img = cap.grab().image
        ib, drill, mean = signals(img, gate)
        w = which(ib, drill, mean)
        print(f'  步骤 {step}: 状态={w:<8} (battle={ib} drill={drill:.0f} mean={mean:.0f})')
        if w == 'battle':
            print('✅ 已进入战斗')
            return 0
        tgt = {'map': STAGE_NODE, 'stage': BTN_DRILL,
               'squad': BTN_START, 'loading': CENTER}[w]
        dep.tap(*tgt)
        time.sleep(2.6 if w != 'loading' else 4.5)
    img = cap.grab().image
    cv2.imwrite(os.path.join(TMP, 'nav_fail.png'), img)
    print('⚠️ 10 步内未进入战斗；已存 nav_fail.png')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
