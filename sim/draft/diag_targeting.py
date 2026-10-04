# -*- coding: utf-8 -*-
"""诊断：我方干员「有多少帧有目标可打 / 存活多久」，定位打不到人的原因"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S            # noqa: E402
from ak_sim.axis import parse_cyberplastic        # noqa: E402
from ak_sim.engine import Battle                  # noqa: E402

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
stats = Counter()
life = {}
deploy_at = {}
orig = b._operator_tick


def patched(u):
    stats[(u.name, 'frames')] += 1
    try:
        if b.pick_operator_target(u) is not None:
            stats[(u.name, 'has_target')] += 1
    except Exception:
        pass
    life[u.name] = max(life.get(u.name, 0), b.frame)
    return orig(u)


b._operator_tick = patched
orig_make = b.deploy


def deploy_patched(char_id, *a, **kw):
    u = orig_make(char_id, *a, **kw)
    if u is not None:
        deploy_at.setdefault(u.name, b.frame)
    return u


b.deploy = deploy_patched
b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM, max_frames=30 * 400,
           continue_after_fail=True, retry_on_cost=True, retry_on_sp=False,
           schedule=[int(p['frame']) for p in plan])

print(f'{"单位":<10} {"部署帧":>7} {"存活帧数":>8} {"有目标帧":>8} {"占比":>6}  末次存活')
for (name, kind), _ in sorted(stats.items()):
    if kind != 'frames':
        continue
    fr = stats[(name, 'frames')]
    ht = stats[(name, 'has_target')]
    print(f'{name:<10} {deploy_at.get(name, -1):>7} {fr:>8} {ht:>8} {ht/max(1,fr):>6.0%}  '
          f'{life.get(name,0)/30:.1f}s')
print('\n我方 hit:', dict(Counter(l.detail.get('src') for l in b.logs if l.kind == 'hit')))
