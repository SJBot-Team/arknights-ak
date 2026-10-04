# -*- coding: utf-8 -*-
"""battle_hud.py — ★「是否处于战斗 HUD」门控（供费用条/费用数字等帧识别器前置使用）。

## 为什么必须门控（实机教训，2026-09-15）
在实机上直接跑 `CostBarRecognizer` 时，**相位恒为 `30/30`（判定为"满条"）**；
截图定位发现当时画面已是**「任务失败 MISSION FAILED / 行动结束」结算页**
⇒ **非战斗画面上识别器会把模糊背景读成满条**。
若把它当作绝对时间基准（"满条次数×30+相位"），时钟会被彻底污染。

⇒ 任何以 HUD 为依据的帧识别，**必须先判定"确实在战斗中"**。

## 判据（三路信号，可组合）
| 信号 | 取法 | 战斗内 | 非战斗 |
|---|---|---|---|
| **A 卡片行** | `Deployer.find_cards(img, y_band=(940,1075))` 的分段数 | ≈11 张 | 0~少量（菜单/结算） |
| **B 费用数字** | 费用 ROI 的**亮字形像素占比** | 有 | 无 |
| **C 敌人计数** | 顶部 `ENEMY x/N` ROI 的亮像素 | 有 | 无 |

**判定规则**：`A 成立` 且 `(B 或 C) 成立` ⇒ 在战斗中。
（A 作为必要条件最稳：待部署卡片行是战斗独有；B/C 排除"编队页也有卡片"的误判。）

用法：
```python
gate = BattleHudGate()
st = gate.check(img)          # {'in_battle': bool, 'cards': int, 'cost': float, 'enemy': float, ...}
```
"""
from __future__ import annotations

import cv2
import numpy as np

# ROI（1920×1080；来自本机实测）
COST_ROI = (1795, 730, 1915, 805)      # 费用数字
ENEMY_ROI = (820, 35, 925, 75)         # 顶部 ENEMY x/N
CARD_BAND = (940, 1075)                # 底部待部署卡片行
HOLD_ROI = (690, 266, 774, 342)        # ★「点击取消」按钮（拖出干员悬停时出现，**仅战斗中**）


class BattleHudGate:
    def __init__(self, min_cards: int = 7, bright_thr: int = 200,
                 card_band=CARD_BAND, cost_roi=COST_ROI, enemy_roi=ENEMY_ROI):
        self.min_cards = int(min_cards)
        self.bright_thr = int(bright_thr)
        self.card_band = card_band
        self.cost_roi = cost_roi
        self.enemy_roi = enemy_roi
        self._dep = None

    # ---------------- 单路信号 ----------------
    def _cards(self, img) -> int:
        if self._dep is None:
            from plugins.action.deploy import Deployer
            self._dep = Deployer(None)
        try:
            segs = self._dep.find_cards(img=img, y_band=self.card_band)
            return len(segs or [])
        except Exception:                                        # noqa: BLE001
            return 0

    def _bright_frac(self, img, roi) -> float:
        x0, y0, x1, y1 = roi
        sub = img[y0:y1, x0:x1]
        if sub.size == 0:
            return 0.0
        g = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
        return float((g > self.bright_thr).mean())

    def _hold_frac(self, img) -> float:
        """「点击取消」红色按钮占比 —— 拖出干员悬停态（**只可能在战斗中**出现）。

        ★为什么需要：实机发现**拖出干员时底部卡片行会隐藏** ⇒ 只看卡片行会把
        "正在操作中的战斗"误判为非战斗，导致时钟/探针在关键时刻**停止采样**。
        """
        x0, y0, x1, y1 = HOLD_ROI
        sub = img[y0:y1, x0:x1]
        if sub.size == 0:
            return 0.0
        hsv = cv2.cvtColor(sub, cv2.COLOR_BGR2HSV)
        red = ((hsv[:, :, 0] < 10) | (hsv[:, :, 0] > 170)) & \
              (hsv[:, :, 1] > 120) & (hsv[:, :, 2] > 120)
        return float(red.mean())

    # ---------------- 组合判定 ----------------
    def check(self, img) -> dict:
        cards = self._cards(img)
        cost = self._bright_frac(img, self.cost_roi)
        enemy = self._bright_frac(img, self.enemy_roi)
        hold = self._hold_frac(img)
        has_cards = cards >= self.min_cards
        has_cost = cost >= 0.02
        has_enemy = enemy >= 0.01
        has_hold = hold >= 0.40
        # ★两条件之一即可判"在战斗中"：
        #   (A) 常规 HUD：卡片行 + 费用数字 + 敌人计数 **三者全需**（最严，已验证 9/9 样本）；
        #   (B) **悬停态**：出现「点击取消」⇒ 必在战斗中（此时卡片行隐藏，A 会失效）。
        in_battle = bool((has_cards and has_cost and has_enemy) or has_hold)
        miss = [n for n, ok in (('卡片行', has_cards), ('费用数字', has_cost),
                                ('敌人计数', has_enemy)) if not ok]
        reason = '战斗中（悬停操作态）' if (has_hold and not (has_cards and has_cost and has_enemy)) \
            else ('战斗中' if in_battle else f'非战斗（缺：{"、".join(miss)}）')
        return {
            'in_battle': in_battle,
            'cards': cards, 'cost_frac': round(cost, 4), 'enemy_frac': round(enemy, 4),
            'hold_frac': round(hold, 4),
            'has_cards': has_cards, 'has_cost': has_cost, 'has_enemy': has_enemy,
            'has_hold': has_hold, 'reason': reason,
        }


def in_battle(img, **kw) -> bool:
    return BattleHudGate(**kw).check(img)['in_battle']
