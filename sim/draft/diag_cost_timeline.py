# -*- coding: utf-8 -*-
"""diag_cost_timeline.py — 费用/上限时间线 + 装置何时被谁打掉 + 首次弦惊落地的费用缺口。

关键问题：h12-4 的 rune 把费用上限压到 20，而弦惊要 23 费 ⇒
**不先打掉一个「街头应急储备」（+5 上限）就永远放不下弦惊**，轴表第 5 条（29.0s 落龙）会一直顺延。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S               # noqa: E402
from ak_sim.axis import parse_cyberplastic           # noqa: E402
from ak_sim.engine import Battle                     # noqa: E402

FPS = 30


def main():
    ax = parse_cyberplastic(S.XLSM)
    ops = []
    for o in ax.ops:
        d = o.to_dict()
        d['char'] = S.NAME_MAP.get(o.unit, o.unit)
        for k, v in S.UNIT_CONFIG.get(d['char'], {}).items():
            d.setdefault(k, v)
        ops.append(d)
    plan = ax.resolve_frames(initial_cost=10.0, unit_costs={}, timebase='abs-seconds')

    b = Battle(S.LEVEL, seed=0, record=False)
    b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
               max_frames=30 * 400, continue_after_fail=False,
               retry_on_cost=True, retry_on_sp=False,
               schedule=[int(p['frame']) for p in plan])

    print('=== 装置相关事件 ===')
    for l in b.logs:
        if l.kind in ('device_spawn', 'device_killed', 'device_destroyed', 'cost_cap_up'):
            print(f'  {l.frame:>5}f {l.frame/FPS:6.1f}s {l.kind:<18} {l.detail}')

    print('\n=== 我方对装置的命中 ===')
    dev_hits = [l for l in b.logs if l.kind == 'hit' and str(l.detail.get('tgt', '')).startswith('街头')]
    for l in dev_hits[:20]:
        print(f'  {l.frame:>5}f {l.frame/FPS:6.1f}s ← {l.detail.get("src")} dmg={l.detail.get("dmg")} '
              f'hp_after={l.detail.get("hp_after")}')
    print(f'  合计 {len(dev_hits)} 次命中装置')

    print('\n=== 弦惊落地尝试（每次失败的原因）===')
    fails = [l for l in b.logs if l.kind == 'deploy_failed'
             and 'soul3' in str(l.detail.get('unit') or l.detail.get('key') or '')]
    print(f'  相关 deploy_failed {len(fails)} 条；前 10 条：')
    for l in fails[:10]:
        print(f'  {l.frame:>5}f {l.frame/FPS:6.1f}s {l.detail}')

    print('\n=== 各干员部署时的费用/上限 ===')
    for l in b.logs:
        if l.kind == 'deploy':
            print(f'  {l.frame:>5}f {l.frame/FPS:6.1f}s {l.detail}')
    print(f'\n最终上限 {b.cost_max:.0f} 费用 {b.cost:.1f} 战果 {b.result} 生命 {b.life} '
          f'帧 {b.frame}（{b.frame/FPS:.1f}s）')


if __name__ == '__main__':
    main()
