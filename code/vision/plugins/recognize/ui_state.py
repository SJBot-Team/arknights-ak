# -*- coding: utf-8 -*-
"""ui_state.py — 用 **MAA 模板**做界面判定与按钮定位（替代亮度阈值+硬编坐标）

## 为什么
我此前用"右下角白色占比 > 0.10"之类判据判界面，反复误命中（把关卡地图判成结算、
把编队判成别的），并硬编"开始行动 = (1710,990)/(1675,792)"这种随界面变化的坐标。
用 MAA 的模板直接匹配，判据来自**游戏自己的图标**，既准又能直接给出**点击点**。

## 判定表（2026-09-14 用 8 张真实帧标定，阈值 0.75）
| 界面 | 命中锚点 | 分数 |
|---|---|---|
| 战斗 | `BattleFlag/BattleOfficiallyBegin` | **0.99**（另有 HpFlag 0.95、CostFlag 0.88、KillsFlag 0.87、OpersFlag 0.80） |
| 编队（含"开始行动"） | `StartButton/BattleStartNormal` / `BattleStartAdverse` | **0.99 / 0.98** |
| 关卡详情 / 关卡地图 / 收藏列表 | 仅 `ReturnButton/Return` | 0.99（需再用其它手段细分） |
| 任务失败结算 | 无命中 | —— |

## 用法
    ui = UiState()
    r = ui.classify(frame)
    r['state']            # 'battle' | 'squad' | 'viewport' | 'unknown'
    r['start_point']      # 编队界面里「开始行动」按钮的**实测**点击点（帧坐标）
"""
from __future__ import annotations

import os
import sys

import cv2

if __package__ in (None, ''):                 # 允许 `python plugins/recognize/ui_state.py` 直接跑自检
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from plugins.recognize.maa_anchor import MaaAnchor

BATTLE_MAIN = 'Battle/BattleFlag/BattleOfficiallyBegin.png'
BATTLE_AUX = ['Battle/BattleFlag/BattleHpFlag.png', 'Battle/BattleFlag/BattleCostFlag.png',
              'Battle/BattleFlag/BattleKillsFlag.png', 'Battle/BattleFlag/BattleOpersFlag.png']
START_BUTTONS = ['Battle/StartButton/BattleStartNormal.png',
                 'Battle/StartButton/BattleStartExercise.png',
                 'Battle/StartButton/BattleStartAdverse.png',
                 'Battle/StartButton/BattleStartRaid.png',
                 'Battle/StartButton/BattleStartTrials.png']
RETURN_BTN = 'ReturnButton/Return.png'


class UiState:
    def __init__(self, ma: MaaAnchor | None = None, thr: float = 0.80):
        self.ma = ma or MaaAnchor(thr=thr)
        self.thr = thr

    def classify(self, frame) -> dict:
        """返回 {state, hits, start_point, start_template}。

        state:
          battle   —— 战斗中（HUD 锚点命中）
          squad    —— 编队界面（开始行动按钮命中，start_point 可直接点）
          viewport —— 有关卡详情/地图/列表（有返回按钮但无战斗/编队特征）
          unknown  —— 都不匹配（可能是结算/加载/剧情等，需单独处理）
        """
        hits: dict[str, float] = {}
        h = self.ma.match(frame, BATTLE_MAIN, thr=self.thr)
        if h:
            hits['BattleOfficiallyBegin'] = h['score']
        for rel in BATTLE_AUX:
            hh = self.ma.match(frame, rel, thr=self.thr)
            if hh:
                hits[rel.split('/')[-1]] = hh['score']
        if hits:
            return {'state': 'battle', 'hits': hits, 'start_point': None, 'start_template': None}

        for rel in START_BUTTONS:
            hh = self.ma.match(frame, rel, thr=self.thr)
            if hh:
                hits[rel.split('/')[-1]] = hh['score']
                return {'state': 'squad', 'hits': hits,
                        'start_point': self.ma.click_point(hh), 'start_template': rel}

        hh = self.ma.match(frame, RETURN_BTN, thr=self.thr)
        if hh:
            hits['Return'] = hh['score']
            return {'state': 'viewport', 'hits': hits, 'start_point': None, 'start_template': None}

        return {'state': 'unknown', 'hits': hits, 'start_point': None, 'start_template': None}


def _selftest():
    import os
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    TMP = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'
    expect = {
        'battle_in.png': 'battle', 'battle_now.png': 'unknown',
        'battle_ready.png': 'squad',
        'detail.png': 'viewport', 'detail_check.png': 'viewport',
        'after_back.png': 'viewport', 'r45_state.png': 'viewport',
        'diag_battle_0.png': 'unknown',
    }
    ui = UiState()
    bad = 0
    for fn, exp in expect.items():
        p = os.path.join(TMP, fn)
        img = cv2.imread(p)
        if img is None:
            print(f'  {fn:<20} 读不到'); continue
        r = ui.classify(img)
        ok = (r['state'] == exp)
        bad += (not ok)
        sp = r['start_point']
        print(f'  {"OK " if ok else "BAD"} {fn:<20} → {r["state"]:<8} 期望 {exp:<8} '
              f'{("点击点" + str(sp)) if sp else ""} 证据={ {k: round(v,2) for k,v in r["hits"].items()} }')
    print(f'\n界面判定自检：{"全部通过" if bad == 0 else f"{bad} 项不符"}')


if __name__ == '__main__':
    _selftest()
