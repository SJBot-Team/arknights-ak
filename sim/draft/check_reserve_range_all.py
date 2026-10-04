# -*- coding: utf-8 -*-
"""枚举轴表里所有部署点，看谁的射程覆盖「街头应急储备」(5,6)/(5,7)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S          # noqa: E402
from ak_sim.axis import coord_to_rc, parse_cyberplastic  # noqa: E402
from ak_sim.data import get_operator, get_range          # noqa: E402
from ak_sim.engine import Battle               # noqa: E402

LEVEL = 'obt/hard/level_hard_12-04'
RESERVES = [(5, 6), (5, 7)]
DIRS = {'右': (1, 0), '左': (-1, 0), '上': (0, 1), '下': (0, -1)}

b = Battle(LEVEL, seed=0)
H, W = b.map.height, b.map.width
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


print(f'{"操作":<6} {"单位":<10} {"坐标":<5} {"朝向":<4} {"→(r,c)":<9} {"射程":<6} 覆盖储备')
seen = set()
for o in ax.ops:
    if o.op != 'deploy' or not o.coord:
        continue
    key = (o.unit, o.coord)
    if key in seen:
        continue
    seen.add(key)
    cid = S.NAME_MAP.get(o.unit, o.unit)
    r, c = coord_to_rc(o.coord, H, W, S.COORD_TRANSFORM)
    try:
        spec = get_operator(cid, elite=2, level=90, potential=6, trust=200)
    except Exception:
        continue
    rid = spec.get('rangeId') or '1-1'
    cells = cells_of(rid, r, c, o.dir or '右')
    hits = [t for t in RESERVES if t in cells]
    print(f'{o.op:<6} {o.unit:<10} {o.coord:<5} {o.dir or "-":<4} ({r},{c}){"":<3} {rid:<6} '
          f'{hits if hits else "-"}')
