# -*- coding: utf-8 -*-
"""probe_ceiling_events.py — 定位"费用上限提升/费用重新流动"的**精确帧**（用户 2026-09-14 指正）

## 为什么要它
费用账本（"费用条满过几次 + 当前条长"）在**封顶期间会丢失时间**——条不动，账本无法计数。
用户指出：应通过**定位费用上限突破、即费用重新开始流动的精确时刻**来锚定时间轴，
而该时刻对应两个**可观测事件**：
  ① **<街头应急储备> 被摧毁**（上限 +5，并附带一定费用）；
  ② **平民进入目标点**（上限 +2）。
⇒ 这两个事件在模拟器里都能给出**精确帧**，在实机里也都能用图像识别定位。

## 本脚本做两件事
1. 跑 h12-4（可指定是否有我方操作），列出**所有 log 种类**，找出与"装置被摧毁/平民进点/上限变化"相关的事件；
2. 输出**费用上限随时间的变化时间线**（逐帧采样 cost_max / cost），即"费用何时重新开始流动"。
"""
from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S            # noqa: E402
from ak_sim.axis import parse_cyberplastic        # noqa: E402
from ak_sim.engine import Battle                  # noqa: E402

FPS = 30


def main():
    use_axis = '--axis' in sys.argv
    # 先空跑一局（不部署），最容易看清"上限提升"事件
    b = Battle(S.LEVEL, seed=0, record=False)
    ops = []
    if use_axis:
        ax = parse_cyberplastic(S.XLSM)
        for o in ax.ops:
            d = o.to_dict()
            d['char'] = S.NAME_MAP.get(o.unit, o.unit)
            d['frame'] = int(round(float(d['abs_seconds']) * FPS))
            for k, v in S.UNIT_CONFIG.get(d['char'], {}).items():
                d.setdefault(k, v)
            ops.append(d)
        ops.sort(key=lambda x: x['frame'])
    fired = b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
                       max_frames=30 * 400, continue_after_fail=False,
                       retry_on_cost=True, retry_on_sp=False,
                       schedule=[o['frame'] for o in ops])
    kinds = Counter(l.kind for l in b.logs)
    print(f'结果={b.result} 生命{b.life}/{b.life_max} 帧{b.frame}({b.frame/FPS:.1f}s) 上限={b.cost_max:.0f}')
    print('log 种类统计:', dict(kinds))

    # ★ 全部非 spawn 事件（含 cost_cap_up / civilian_arrived / device_killed / escape）
    print('\n全部非 spawn 事件（费用上限时间轴的锚点）：')
    for l in b.logs:
        if l.kind == 'spawn':
            continue
        print(f'  帧{l.frame:>5} ({l.frame/FPS:6.2f}s)  {l.kind:<18} detail={l.detail}')

    # 费用上限时间线：逐帧重建（用日志里的费用相关事件推断，若无则打印费用极值）
    print('\n费用相关字段：', {k: getattr(b, k, None) for k in
                            ('cost', 'cost_max', 'cost_cap_ceil', 'initial_cost') if hasattr(b, k)})
    devs = [(getattr(u, 'name', '?'), getattr(u, 'hp', None), getattr(u, 'max_hp', None))
            for u in b.units.values() if getattr(u, 'side', '') == 'DEVICE']
    print('预置装置状态：')
    for nm, hp, mhp in devs:
        print(f'  {nm:<24} hp={hp}/{mhp}')
    kills = [l for l in b.logs if l.kind == 'device_killed']
    print(f'\n装置被摧毁事件 {len(kills)} 条：')
    for l in kills:
        print(f'  帧{l.frame}({l.frame/FPS:.2f}s) detail={l.detail}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
