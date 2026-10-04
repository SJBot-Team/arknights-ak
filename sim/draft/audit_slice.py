# -*- coding: utf-8 -*-
"""audit_slice.py — ★逐帧切片**完整性审计**（目标①要求：操作/血量/坐标/攻速/移速/随机判定）。

## 目标①原文
> 「…逐帧**完整切片**（**操作 / 血量 / 坐标 / 攻速 / 移速 / 随机判定**）」

本脚本对一场 1-1 复刻的切片逐项核对：
| 项 | 期望字段 |
|---|---|
| 操作 | 本帧的部署/技能/撤退等命令 |
| 血量 | 每个单位的 HP（含上限） |
| 坐标 | 每个单位的世界坐标 |
| 攻速 | 攻击间隔 / 前摇 / 下次可攻击时刻 |
| 移速 | 当前速度向量（惯性） |
| 随机判定 | 本帧发生的随机决策（出怪组抽签等） |

输出「有/缺」与字段名，缺项即为下一步要补的内容。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim.engine import Battle              # noqa: E402
from ak_sim.scenario import Scenario          # noqa: E402


def main() -> int:
    sc = Scenario('1-1')
    b = Battle(sc.stage_code, seed=0, record=True, record_every=1, max_frames=300)
    for _ in range(300):
        b.tick()
        if b.frame == 10:
            b.deploy('char_123_fang', 3, 5, direction='左', elite=1, level=55,
                     potential=6, trust=200, skill_index=0, skill_level=7, cost=8)

    print(f'切片类型={type(b.frames).__name__} 数量={len(b.frames)}')
    s = b.frames[120]
    print('\n单帧切片顶层键:', sorted(s.keys()))
    print('\n样例（截断）:', json.dumps(s, ensure_ascii=False)[:1200])

    print('\n' + '=' * 70)
    print('逐项审计')
    print('=' * 70)
    # 汇总所有切片里出现过的键
    allkeys = {}
    for f in b.frames:
        for k in f:
            allkeys[k] = allkeys.get(k, 0) + 1
    print('全部出现过的键（出现帧数 / 总帧数）:')
    for k in sorted(allkeys):
        print(f'   {k:<24} {allkeys[k]:>4} / {len(b.frames)}')

    # 单位级字段
    ukeys = {}
    for f in b.frames:
        for u in (f.get('units') or []):
            for k in u:
                ukeys[k] = ukeys.get(k, 0) + 1
    if ukeys:
        print('\n单位级字段:')
        for k in sorted(ukeys):
            print(f'   {k:<24} {ukeys[k]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
