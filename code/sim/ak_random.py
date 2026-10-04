#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ak_random.py —— 明日方舟局内随机数发生器的精确复刻

结论来源（见 knowledge/04/29、34）：
  BattleController.RANDOM_ALGORITHM = 0 (DEFAULT)
    → RandomFactory.Create(seed, 0) 进入默认分支 (RVA 0x5526E70 / 0x5527065)
    → new LegacyRandom(seed)         (RVA 0x52FAB60)
  LegacyRandom 的字段是 MBIG=2147483647 / MSEED=161803398 / MZ=0 / SeedArray / inext / inextp，
  且 Sample() 的反汇编为：
      inc inext; cmp 56; cmovge→1
      inc inextp; cmp 56; cmovge→1
      retVal = SeedArray[inext] - SeedArray[inextp]
      lea eax,[rcx+0x7fffffff]; cmovns      → if (retVal < 0) retVal += MBIG
      SeedArray[inext] = retVal
      mulSd xmm0, 1/2147483647
  这正是 .NET Framework 的 System.Random（Knuth 减法法）。

验证：与 Windows PowerShell 5.1（.NET Framework）的 System.Random 逐值比对。
用法：
  python ak_random.py <seed> [count]      # 打印前 count 个 Next()
"""
import sys

sys.stdout.reconfigure(encoding="utf-8")


class LegacyRandom:
    """.NET Framework System.Random 的逐位等价实现（AK 用作局内主随机源）。"""

    MBIG = 2147483647          # int.MaxValue
    MSEED = 161803398
    MZ = 0
    SEED_ARRAY_SIZE = 56
    INT_MIN = -2147483648

    def __init__(self, seed: int):
        self.SeedArray = [0] * self.SEED_ARRAY_SIZE
        ii = 0
        subtraction = self.MBIG if seed == self.INT_MIN else abs(seed)
        mj = self.MSEED - subtraction
        self.SeedArray[55] = mj
        mk = 1
        for i in range(1, 55):
            ii = (21 * i) % 55
            self.SeedArray[ii] = mk
            mk = mj - mk
            if mk < 0:
                mk += self.MBIG
            mj = self.SeedArray[ii]
        for _k in range(1, 5):
            for i in range(1, 56):
                self.SeedArray[i] -= self.SeedArray[1 + (i + 30) % 55]
                if self.SeedArray[i] < 0:
                    self.SeedArray[i] += self.MBIG
        self.inext = 0
        self.inextp = 21

    def _internal_sample(self) -> int:
        loc_inext = self.inext + 1
        if loc_inext >= self.SEED_ARRAY_SIZE:
            loc_inext = 1
        loc_inextp = self.inextp + 1
        if loc_inextp >= self.SEED_ARRAY_SIZE:
            loc_inextp = 1
        ret_val = self.SeedArray[loc_inext] - self.SeedArray[loc_inextp]
        if ret_val == self.MBIG:
            ret_val -= 1
        if ret_val < 0:
            ret_val += self.MBIG
        self.SeedArray[loc_inext] = ret_val
        self.inext = loc_inext
        self.inextp = loc_inextp
        return ret_val

    # --- 与 C# System.Random 对应的公开接口 ---
    def Sample(self) -> float:
        return self._internal_sample() * (1.0 / self.MBIG)

    def Next(self) -> int:
        return self._internal_sample()

    def NextMax(self, max_value: int) -> int:
        if max_value < 0:
            raise ValueError("maxValue must be >= 0")
        return int(self.Sample() * max_value)

    def NextRange(self, min_value: int, max_value: int) -> int:
        if min_value > max_value:
            raise ValueError("minValue > maxValue")
        rng = max_value - min_value
        if rng <= self.MBIG:
            return int(self.Sample() * rng) + min_value
        # 大区间：C# 用 long 运算后取模（此处按 .NET Framework 原实现）
        while True:
            d = self.Sample() * rng
            if d < rng:
                return int(d) + min_value

    def NextDouble(self) -> float:
        return self.Sample()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    seed = int(sys.argv[1])
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    r = LegacyRandom(seed)
    print(" ".join(str(r.Next()) for _ in range(count)))
