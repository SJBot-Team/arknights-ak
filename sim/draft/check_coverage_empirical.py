# -*- coding: utf-8 -*-
"""用「敌人实际走过的格子」评估坐标变换与射程覆盖（比路线检查点采样可靠得多）

做法：跑一局模拟（轴表驱动），逐帧记录所有敌人占据的格子 → 得到真实经过格集合；
再对 4 种坐标变换，统计令/蕾缪安的射程覆盖到多少「敌人实际经过格」。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S          # noqa: E402
from ak_sim.axis import coord_to_rc, parse_cyberplastic  # noqa: E402
from ak_sim.data import get_operator, get_range          # noqa: E402
from ak_sim.engine import Battle               # noqa: E402

LEVEL = 'obt/hard/level_hard_12-04'
DIRS = {'右': (1, 0), '左': (-1, 0), '上': (0, 1), '下': (0, -1)}
TF = ['rc_normal', 'rc_rowflip', 'rc_colflip', 'rc_bothflip']

b = Battle(LEVEL, seed=0, record=False)
H, W = b.map.height, b.map.width

# 逐帧记录敌人占据格
visited = set()
orig_tick = b.tick


def tick_and_record():
    orig_tick()
    for u in list(b.units.values()):
        if u.side == 'ENEMY' and u.alive:
            visited.add(u.grid())


b.tick = tick_and_record
while b.frame < 30 * 120:
    b.tick()
print(f'敌人实际经过格 = {len(visited)} 格（前 120s 模拟）')

ax = parse_cyberplastic(S.XLSM)


def cells_of(range_id, row, col, direction):
    rg = get_range(range_id)
    dx, dy = DIRS.get(direction, (1, 0))
    out = set()
    for g in rg:
        c, r = (g[0], g[1]) if isinstance(g, (list, tuple)) else (g.get('col', 0), g.get('row', 0))
        if dx == 1:
            out.add((row + r, col + c))
        elif dx == -1:
            out.add((row - r, col - c))
        elif dy == 1:
            out.add((row + c, col - r))
        else:
            out.add((row - c, col + r))
    return out


print(f'\n{"变换":<13} {"合法率":>6} {"令覆盖":>6} {"蕾缪安覆盖":>8} {"合计":>5}')
for tf in TF:
    legal = tot = 0
    cov = {'令': 0, '蕾缪安': 0}
    for o in ax.ops:
        if o.op != 'deploy' or not o.coord:
            continue
        cid = S.NAME_MAP.get(o.unit, o.unit)
        try:
            spec = get_operator(cid, elite=2, level=90, potential=6, trust=200)
        except Exception:
            continue
        r, c = coord_to_rc(o.coord, H, W, tf)
        tot += 1
        if b.map.can_deploy(r, c, melee=spec.get('position') != 'RANGED'):
            legal += 1
        if o.unit in cov:
            cells = cells_of(spec.get('rangeId') or '1-1', r, c, o.dir or '右')
            # 取该干员所有部署点里的最大覆盖（他会被多次部署）
            cov[o.unit] = max(cov[o.unit], len(cells & visited))
    print(f'{tf:<13} {legal/max(1,tot):>6.0%} {cov["令"]:>6} {cov["蕾缪安"]:>8} '
          f'{cov["令"]+cov["蕾缪安"]:>5}')
