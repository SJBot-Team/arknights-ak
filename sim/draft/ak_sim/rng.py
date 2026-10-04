# -*- coding: utf-8 -*-
"""
rng.py — 局内随机数（复刻 .NET Framework System.Random = LegacyRandom）

依据：knowledge/04/34（随机数与确定性复刻，T1 已逐值验证）
实现复用 ak_random.py（code/sim/）。
用途：闪避/概率判定/召唤/掉落等；支持种子固定与状态快照（逐帧记录、可复现）。
"""
from __future__ import annotations

import os
import sys

_SIM_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))), 'code', 'sim')
if _SIM_DIR not in sys.path:
    sys.path.insert(0, _SIM_DIR)

from ak_random import LegacyRandom  # noqa: E402


class AKRandom:
    """包装 LegacyRandom，提供常用取样与状态快照。"""

    def __init__(self, seed: int):
        self.seed = seed
        self._r = LegacyRandom(seed)
        self.draws = 0

    # ---- 取样 ----
    def sample(self) -> float:
        """[0,1) 浮点（等价 Random.NextDouble 的 Sample）。"""
        self.draws += 1
        return self._r.Sample()

    def next_int(self, n: int) -> int:
        self.draws += 1
        return int(self.sample() * n)

    def chance(self, p: float) -> bool:
        """概率 p 成功（p 为 0~1）。"""
        return self.sample() < p

    # ---- 状态 ----
    def state_snapshot(self) -> dict:
        """快照（用于逐帧切片记录；SeedArray 摘要化以控体积）。"""
        return {
            'seed': self.seed,
            'draws': self.draws,
            'inext': getattr(self._r, 'inext', None),
            'inextp': getattr(self._r, 'inextp', None),
            'sa_hash': hash(tuple(getattr(self._r, 'SeedArray', [])[:8])),
        }


if __name__ == '__main__':
    import sys as _s
    _s.stdout.reconfigure(encoding='utf-8')
    r1 = AKRandom(12345)
    r2 = AKRandom(12345)
    a = [round(r1.sample(), 6) for _ in range(5)]
    b = [round(r2.sample(), 6) for _ in range(5)]
    print('序列一致:', a == b, a)
    print('快照:', r1.state_snapshot())
