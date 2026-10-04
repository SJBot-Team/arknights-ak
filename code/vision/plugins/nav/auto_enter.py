# -*- coding: utf-8 -*-
"""auto_enter.py — 自动进关导航（可注入依赖、可离线测试）

## 为什么要抽出来
导航逻辑此前写在 `apps/auto_sample_v2.py` 的 `main()` 里，**无法离线测试**，
只能靠实机反复试错（而实机又常被渲染冻结/坐标失效打断）。
抽成类之后，可以用"真实帧序列 + 假采集器/假注入器"完整验证决策链。

## 判据
界面判定用 `UiState`（MAA 模板，§7.97）；点「开始行动」用**模板给出的位置**（不硬编坐标）。

## 合规约束（写死在逻辑里）
只点：关卡详情「演习」、编队「开始行动」、结算/加载的"继续"、关卡地图/列表的节点。
**不点任何可能消耗理智的按钮**（例如关卡详情里的「开始行动」）。
"""
from __future__ import annotations

import time

# 实测坐标（帧坐标）
TAP_DRILL = (1441, 983)        # 关卡详情「演习」
TAP_NODE = (1160, 667)         # 关卡地图上的目标节点
TAP_CONTINUE = (960, 988)      # 结算/加载"继续"
DEFAULT_START = (1675, 792)    # 编队「开始行动」兜底（模板给不出位置时用）


class AutoEnter:
    def __init__(self, cap, tap, ui, ma=None, log=print, max_steps: int = 10,
                 wait_battle_tries: int = 16, wait_battle_sleep: float = 0.4,
                 frame_diff_fn=None, change_thresh: float = 3.0):
        self.cap = cap
        self.tap = tap
        self.ui = ui
        self.ma = ma
        self.log = log
        self.max_steps = max_steps
        self.wait_battle_tries = wait_battle_tries
        self.wait_battle_sleep = wait_battle_sleep
        self.change_thresh = change_thresh
        self.trace: list[dict] = []
        self._frame_diff = frame_diff_fn or self._default_diff

    # ---------- 工具 ----------
    @staticmethod
    def _default_diff(a, b):
        import cv2
        import numpy as np
        fa = cv2.resize(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')
        fb = cv2.resize(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), (64, 36)).astype('float32')
        return float(np.abs(fa - fb).mean())

    def _grab(self):
        return self.cap.grab().image

    def _in_battle(self, img) -> bool:
        return self.ui.classify(img)['state'] == 'battle'

    def _wait_battle(self) -> bool:
        for _ in range(self.wait_battle_tries):
            if self._in_battle(self._grab()):
                return True
            time.sleep(self.wait_battle_sleep)
        return False

    # ---------- 主流程 ----------
    def enter(self) -> bool:
        """尽力进入战斗；成功返回 True（调用方随即开始采样，**不得再做额外点击**）。"""
        for step in range(self.max_steps):
            img = self._grab()
            r = self.ui.classify(img)
            st = r['state']
            self.trace.append({'step': step, 'state': st, 'hits': dict(r['hits'])})
            self.log(f'[{step}] UiState={st} 证据={ {k: round(v, 2) for k, v in r["hits"].items()} }')

            if st == 'battle':
                self.log(f'[{step}] 已在战斗 → 交由调用方立即采样')
                return True

            if st == 'squad':
                pt = r['start_point'] or DEFAULT_START
                self.tap(*pt)
                self.log(f'    编队 → 开始行动 @{pt}（模板定位）')
                if self._wait_battle():
                    self.log('    战斗已开始')
                    return True
                self.log('    未进入战斗，继续尝试')
                time.sleep(self.wait_battle_sleep)
                continue

            if st == 'viewport':
                self.tap(*TAP_DRILL)
                time.sleep(0.8)
                # ★ 生效判据用**界面类型变化**，不用帧间差异（§7.116）：
                #   关卡地图自身有视差/粒子动画，帧差会被误判成"点击生效"（实测踩到）。
                r2 = self.ui.classify(self._grab())
                if r2['state'] != 'viewport':
                    self.log(f'    详情 → 演习（界面已变为 {r2["state"]}）')
                    continue
                self.tap(*TAP_NODE)
                self.log('    地图/列表 → 点目标节点')
            else:
                self.tap(*TAP_CONTINUE)
                self.log('    结算/加载（unknown）→ 点继续')
            time.sleep(0.8)
        self.log('导航失败（步数用尽）')
        return False
