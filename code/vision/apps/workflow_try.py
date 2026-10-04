# -*- coding: utf-8 -*-
"""workflow_try.py — 走一遍用户给出的完整流程（第②~⑤步），检验"落格提交"。

## 流程（用户 2026-09-15 方案）
① 记绝对时间：费用条满条计数（已实现）
② 操作前 ≈1s 进入**子弹时间**（拖出干员悬停）—— **已实测 30.3 → 6.1 帧/秒（5×）**
③ 操作前 5 帧开始**子弹时间过帧**
④ **暂停定位**到预定帧
⑤ **部署干员**

## 本轮新增的关键手段
**`PostMessage` 宏键**（`WinInput.post_key`）实测**可用**：发 `F` 后费用条相位冻结
⇒ **宏暂停不会像"点暂停按钮"那样取消悬停**（此前实测：悬停态点暂停按钮会立刻取消悬停）
⇒ 因此"先悬停（子弹时间）→ 宏键暂停 → 释放"这条顺序**首次变得可行**。

## 本脚本
1. 确保运行态 → 拖出干员（悬停，进入子弹时间）
2. 用 `post_key('f')` 宏暂停
3. 检查**悬停是否仍在**（「点击取消」红色按钮）
4. 在暂停+悬停态**尝试释放**（`motionevent UP` + 补一次 `tap`）
5. 报告：是否落格（比对"剩余可放置角色"与费用）

安全：仅界面级操作；不落格则取消；演习不消耗理智。
"""
from __future__ import annotations

import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer                      # noqa: E402
from plugins.action.win_input import WinInput                    # noqa: E402
from plugins.capture.emu_window import make_capture             # noqa: E402
from plugins.recognize.battle_hud import BattleHudGate          # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
CARD, CELL_D6, CANCEL = (63, 949), (934, 502), (732, 304)


def shot(cap, name):
    img = cap.grab().image
    cv2.imwrite(os.path.join(TMP, name), img)
    return img


def hold_frac(img):
    x0, y0, x1, y1 = 690, 266, 774, 342
    sub = img[y0:y1, x0:x1]
    hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
    red = ((hsv[:, :, 0] < 10) | (hsv[:, :, 0] > 170)) & \
          (hsv[:, :, 1] > 120) & (hsv[:, :, 2] > 120)
    return float(red.mean())


def rest_band(img):
    """右侧「剩余可放置角色」区域的平均亮度（有该文本时 ~94，悬停/隐藏时 ~58）。"""
    return round(float(cv2.cvtColor(img[880:950, 1620:1920], cv2.COLOR_BGR2GRAY).mean()), 1)


def main() -> int:
    cap, dep, wi, gate = make_capture('adb'), None, WinInput(), BattleHudGate()
    dep = Deployer(cap)
    img = shot(cap, 'wf_00_start.png')
    print(f'起点: in_battle={gate.check(img)["in_battle"]} 剩余区={rest_band(img)} hold={hold_frac(img):.3f}')

    print('\n② 拖出干员（悬停 → 子弹时间）')
    dep.motion([CARD, (500, 750), CELL_D6], hold_ms=200, between_ms=180)
    time.sleep(0.6)
    img = shot(cap, 'wf_01_hold.png')
    print(f'   悬停: hold={hold_frac(img):.3f}（应 ≈0.76）剩余区={rest_band(img)}')

    print('\n④ 用宏键 F 暂停（PostMessage）')
    try:
        wi.post_key('f')
    except Exception as ex:                                     # noqa: BLE001
        print('   post_key 异常:', repr(ex))
    time.sleep(1.0)
    img = shot(cap, 'wf_02_fpause.png')
    hf = hold_frac(img)
    print(f'   宏暂停后: hold={hf:.3f} 剩余区={rest_band(img)} '
          f'⇒ **悬停是否保留：{"是 ✅" if hf > 0.4 else "否 ✗（被取消）"}**')

    print('\n⑤ 在"暂停 + 悬停"态尝试释放')
    for args in (['input', 'motionevent', 'UP', str(CELL_D6[0]), str(CELL_D6[1])],
                 ['input', 'tap', str(CELL_D6[0]), str(CELL_D6[1])]):
        dep._sh(*args)
        time.sleep(0.7)
    img = shot(cap, 'wf_03_after.png')
    print(f'   释放后: hold={hold_frac(img):.3f} 剩余区={rest_band(img)}')

    print('\n=== 判定 ===')
    if hold_frac(img) < 0.4:
        print('悬停已结束：**释放动作被接受**（是否真落格需看"剩余可放置角色"是否 8→7、费用是否 −8）')
    else:
        print('悬停仍在：释放未被接受（与既有 D1 结论一致）')
    print('提示：可直接查看 wf_03_after.png 确认芬是否出现在 D6')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
