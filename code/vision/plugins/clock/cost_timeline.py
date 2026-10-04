# -*- coding: utf-8 -*-
"""cost_timeline.py — 费用时间轴：**相位（1 秒内精度）+ 上限锚点（跨越封顶）**

## 由来（用户 2026-09-14 的两次指正 + 检验结论）
1. 费用条每满一次 = **30 帧**（非封顶时精确，§7.124 实测）；
2. 但本关费用**不可避免会满**，封顶期间条静止 ⇒ **账本无法计时**；
3. 上限突破事件（**平民进点 / 箱子被摧毁**）是"费用重新流动"的**精确锚点**（§7.120）；
4. 锚点之后**相位会被重置**（实测锚点后首个 +1 间隔是 26 帧而非 30，§7.124）⇒ 必须**按新原点重新起算**；
5. 帧数公式是 `Δ费用×30 + Δ相位`，其中 Δ相位**规范到 [-15,15)**（§7.133 修正，不能 mod 30）。

## 用法
    tl = CostTimeline()
    tl.observe(cost=12, phase=21)                 # 每帧/每次采样喂入
    est, stalled = tl.observe(cost=12, phase=23)  # 未封顶 ⇒ est 为相对帧数
    tl.add_anchor(frame=1469, cost_max=22, source='civilian')   # 观测到上限突破
"""
from __future__ import annotations

from dataclasses import dataclass, field

from plugins.clock.frame_clock import frames_between, signed_phase_delta


@dataclass
class Anchor:
    frame: int
    cost_max: float = 0.0
    source: str = ''


@dataclass
class CostTimeline:
    modulus: int = 30
    anchors: list = field(default_factory=list)
    _last: tuple | None = None          # (cost, phase, frame_est)
    _base: int = 0                      # 当前原点的估算帧
    stalled_reads: int = 0

    # ---------------- 锚点 ----------------
    def add_anchor(self, frame: int, cost_max: float = 0.0, source: str = '') -> Anchor:
        """登记一次**上限突破**（费用重新流动）。锚点后**重置基准**，按新原点重新起算。"""
        a = Anchor(int(frame), float(cost_max), source)
        self.anchors.append(a)
        self._base = int(frame)
        self._last = None               # ★ 关键：锚点后必须丢弃旧相位基准
        return a

    # ---------------- 观测 ----------------
    def observe(self, cost, phase, wall_t=None):
        """喂入一次读数，返回 (相对帧数估计, stalled)。

        - 未封顶：估计 = 上一次估计 + `Δ费用×30 + Δ相位`（Δ相位规范到 [-15,15)）；
        - **封顶（费用与相位都不动）**：返回 `(None, True)` —— **绝不由账本外推**。
        """
        if cost is None or phase is None:
            return None, True
        if self._last is None:
            self._last = (cost, phase, self._base)
            return self._base, False
        c0, p0, e0 = self._last
        if cost == c0 and phase == p0:
            self.stalled_reads += 1
            return None, True
        est = e0 + frames_between(c0, p0, cost, phase, self.modulus)
        self._last = (cost, phase, est)
        return est, False

    # ---------------- 查询 ----------------
    def last_estimate(self):
        return None if self._last is None else self._last[2]

    def stalled(self) -> bool:
        """上一次读数是否处于封顶（条静止）。"""
        return self.stalled_reads > 0 and self._last is not None

    def anchor_summary(self) -> list:
        return [(a.frame, a.cost_max, a.source) for a in self.anchors]


def phase_from_frame(frame: int, modulus: int = 30) -> int:
    """辅助：由"绝对帧号"推费用条相位（仅离线/自测用，实机由图像给出）。"""
    return int(frame) % modulus
