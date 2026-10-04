# -*- coding: utf-8 -*-
"""test_deploy_channels.py — ★两段式部署的**通道对照实验**（判据 = 费用数字下降量）。

## 为什么关键
`axis_runner` 默认用 **ADB `motionevent`** 注入；上一轮已用**真实鼠标**验证两段式提交成功。
若 ADB 通道也能提交 ⇒ **轴表可全自动执行**；否则执行器须改用真实鼠标。

## 上一轮的两个 bug（已修）
1. `find_cards` 返回的是 **dict**（`{'cx','cy','x0','x1','w'}`），旧代码按 tuple 处理 ⇒ 回退到固定坐标；
2. 判据用"卡片段数"不可靠 ⇒ 改为**读费用数字**：部署 14 费的月见夜后费用应 **−14**。

## 做法
1. 确保在战斗中（否则自动导航）；
2. 读费用数字（`CostNumberRecognizer`）；
3. **ADB 通道**两段式部署 月见夜(第5张卡,≈(873,1007)) → D4(1182,502) 朝上(→(1182,364))；
4. 再读费用；若未变，换**真实鼠标**通道重试；
5. 打印各步费用与结论。

安全：仅界面级拖拽与截图；演习不消耗理智。
"""
from __future__ import annotations

import os
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.action.deploy import Deployer                     # noqa: E402
from plugins.capture.emu_window import make_capture            # noqa: E402
from plugins.recognize.battle_hud import BattleHudGate         # noqa: E402
from plugins.recognize.cost_number import CostNumberRecognizer  # noqa: E402
import nav_to_drill                                            # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
TPL = os.path.join(TMP, 'tpl_h124.json')
from plugins.action.grid_px import coord_to_px as _c2p, cell_to_px as _cell2px
D4 = _c2p("D4")                # (932, 502)
DIR_UP = _cell2px(2, 3)        # 朝上 = row−1
# 卡片行几何（本机实测：10 张卡，首卡中心 ≈153，间距 ≈180，y≈1007）
CARD0_X, CARD_DX, CARD_Y = 153, 180, 1007


def card_xy(i: int):
    return (CARD0_X + CARD_DX * i, CARD_Y)


def read_cost(cap, num):
    fr = cap.grab()
    spec = {'roi': [1795, 730, 1915, 805]}
    if os.path.exists(TPL):
        spec['templates'] = TPL
    ms = num.run(fr.image, spec, None, fr.origin)
    return (int(ms[0].extra['cost']) if ms else None), fr.image


def main() -> int:
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else 4       # 第 5 张（0 基）= 14 费
    cap = make_capture('adb')
    dep, gate, num = Deployer(cap), BattleHudGate(), CostNumberRecognizer()

    if not gate.check(cap.grab().image)['in_battle']:
        print('不在战斗 → 自动导航')
        if nav_to_drill.main() != 0:
            return 1

    c0, img = read_cost(cap, num)
    cv2.imwrite(os.path.join(TMP, 'chan_0.png'), img)
    print(f'起点费用 = {c0}（部署 14 费干员需要费用 ≥ 14，否则游戏拒绝部署）')

    # ★先攒够费用：确保运行态 → 轮询费用 → 够了就暂停
    from plugins.action.win_input import WinInput
    wi = WinInput()
    need = 16
    if c0 is None or c0 < need:
        print(f'费用不足 → 恢复运行攒费（目标 ≥ {need}）')
        wi.post_key('f')                       # 若暂停则恢复
        time.sleep(0.5)
        t0 = time.time()
        while time.time() - t0 < 90:
            c, img = read_cost(cap, num)
            if c is not None and c >= need:
                print(f'  费用已达 {c} ⇒ 暂停')
                wi.post_key('f')
                time.sleep(0.6)
                break
            time.sleep(0.2)
        c0, _ = read_cost(cap, num)
        print(f'  暂停后费用 = {c0}')

    print(f'目标卡（第 {idx + 1} 张）≈ {card_xy(idx)} → D4 {D4} 朝上 {DIR_UP}')

    for channel in ('adb', 'real'):
        print(f'\n--- 通道 {channel} ---')
        r = dep.deploy_two_step_px(card_xy(idx), D4, DIR_UP,
                                   use_real_mouse=(channel == 'real'))
        time.sleep(1.4)
        c1, img = read_cost(cap, num)
        cv2.imwrite(os.path.join(TMP, f'chan_{channel}.png'), img)
        print(f'  执行 {r}')
        print(f'  费用 {c0} → {c1}')
        if c0 is not None and c1 is not None and (c0 - c1) >= 8:
            print(f'  ✅ **{channel} 通道提交成功**（费用下降 {c0 - c1}）')
            return 0
        print('  ✗ 费用未按预期下降')
    print('\n两通道均未见费用下降 —— 请人工查看 chan_adb.png / chan_real.png')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
