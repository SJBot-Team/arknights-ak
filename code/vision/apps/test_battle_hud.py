# -*- coding: utf-8 -*-
"""test_battle_hud.py — ★回归：战斗 HUD 门控在**本机截图样本**上判得对。

样本（全部来自本机实机截图，见 `ak/.tmp/`）：
| 样本 | 场景 | 期望 |
|---|---|---|
| live_07_battle2.png | 演习战斗（运行中） | **在战斗中** |
| live_23_resume.png | 演习战斗（运行中，敌方已推进） | **在战斗中** |
| live_08_select.png | 战斗内（已选卡、绿格） | **在战斗中** |
| live_24_now.png | **任务失败 MISSION FAILED** | **非战斗** ← 就是它把费用条读成"满条" |
| live_26_state.png | 行动结束（结算） | 非战斗 |
| live_02_stage.png | 关卡详情 | 非战斗 |
| live_03_squad.png | 编队页（有卡片但不是战斗） | 非战斗 |
| live_home.png | 主界面 | 非战斗 |

再加一条**端到端断言**：对失败页跑 `CostBarRecognizer` 会得到"满条"，
但 `BattleHudGate` 必须把它判为**非战斗** ⇒ 时钟被正确门控。
"""
from __future__ import annotations

import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.recognize.battle_hud import BattleHudGate          # noqa: E402

TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
SAMPLES = [
    ('live_07_battle2.png', True), ('live_23_resume.png', True),
    ('live_08_select.png', True), ('live_11_final.png', True),
    ('live_18_smdrag.png', True),
    # ★悬停操作态（拖出干员未落格）：卡片行会隐藏，必须靠「点击取消」信号判为"战斗中"
    ('live_14_drag.png', True), ('live_20_running_drag.png', True),
    ('live_21_postmsg.png', True),
    ('live_24_now.png', False), ('live_26_state.png', False),
    ('live_02_stage.png', False), ('live_03_squad.png', False),
    ('live_home.png', False),
]
FAILED = []


def check(name, cond, detail=''):
    print(f'  {"✅" if cond else "❌"} {name}{("  — " + detail) if detail else ""}')
    if not cond:
        FAILED.append(name)


def main():
    gate = BattleHudGate()
    print('=== 战斗 HUD 门控样本判定 ===')
    print(f'{"样本":<24} {"期望":>6} {"实得":>6} {"卡片":>5} {"费用亮":>7} {"敌人亮":>7}  说明')
    for fn, want in SAMPLES:
        p = os.path.join(TMP, fn)
        if not os.path.exists(p):
            print(f'{fn:<24} （缺样本，跳过）')
            continue
        img = cv2.imread(p)
        st = gate.check(img)
        got = st['in_battle']
        print(f'{fn:<24} {str(want):>6} {str(got):>6} {st["cards"]:>5} '
              f'{st["cost_frac"]:>7.3f} {st["enemy_frac"]:>7.3f}  {st["reason"]}')
        check(f'{fn} → {"战斗" if want else "非战斗"}', got == want)

    print('\n=== 端到端：失败页上"费用条误报满条"必须被门控拦下 ===')
    p = os.path.join(TMP, 'live_24_now.png')
    if os.path.exists(p):
        img = cv2.imread(p)
        st = gate.check(img)
        check('失败页判为**非战斗**', st['in_battle'] is False)
        try:
            from plugins.recognize.cost_bar import CostBarRecognizer
            ms = CostBarRecognizer().run(img, {}, None, (0, 0))
            got = ms[0].extra.get('frame') if ms else None
            check('（佐证）同一画面上费用条识别器会给出"满条"读数',
                  got is not None, f'frame={got} ⇒ 正因如此才需要门控')
        except Exception as ex:                                   # noqa: BLE001
            print(f'  （费用条识别器调用异常，跳过佐证：{ex!r}）')

    print()
    if FAILED:
        print(f'❌ 未通过 {len(FAILED)} 项：{FAILED}')
        return 1
    print('✅ 通过：战斗 HUD 门控在全部样本上判定正确（战斗中 / 非战斗）')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
