# -*- coding: utf-8 -*-
"""用「射程覆盖敌人路线」判别 h12-4 轴表的坐标变换（比"部署合法性"更强的判据）

思路：正确的部署位置，其射程应当覆盖敌人的行进路线（否则干员一辈子打不到人 —— 
实机对局里令/蕾缪安是主力输出）。对 4 种候选变换分别计算：
  · 部署合法性（原有判据）
  · 射程覆盖到的**路线格数**（越接近路线越可能正确）
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

b = Battle(LEVEL, seed=0)
H, W = b.map.height, b.map.width
ax = parse_cyberplastic(S.XLSM)

# 敌人路线经过的格子集合（用路线上的检查点/终点近似）
route_cells = set()
for rt in b.routes:
    for cp in (getattr(rt, 'checkpoints', None) or []):
        if isinstance(cp, dict):
            if 'row' in cp and 'col' in cp:
                route_cells.add((int(cp['row']), int(cp['col'])))
            elif 'position' in cp and isinstance(cp['position'], dict):
                p = cp['position']
                route_cells.add((int(p.get('row', 0)), int(p.get('col', 0))))
        elif isinstance(cp, (tuple, list)) and len(cp) >= 2:
            route_cells.add((int(cp[1]), int(cp[0])))
    for attr in ('start', 'end'):
        v = getattr(rt, attr, None)
        if isinstance(v, (tuple, list)) and len(v) == 2:
            route_cells.add((int(v[1]), int(v[0])))
print(f'路线格样本数 = {len(route_cells)}')


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


print(f'\n{"变换":<13} {"合法率":>6} {"覆盖路线格":>8}  说明')
for tf in TF:
    legal = tot = cover = 0
    detail = []
    for o in ax.ops:
        if o.op != 'deploy' or not o.coord:
            continue
        cid = S.NAME_MAP.get(o.unit, o.unit)
        try:
            spec = get_operator(cid, elite=2, level=90, potential=6, trust=200)
        except Exception:
            continue
        r, c = coord_to_rc(o.coord, H, W, tf)
        melee = spec.get('position') != 'RANGED'
        tot += 1
        if b.map.can_deploy(r, c, melee=melee):
            legal += 1
        if o.unit in ('令', '蕾缪安', '弦惊'):
            cells = cells_of(spec.get('rangeId') or '1-1', r, c, o.dir or '右')
            cv = len(cells & route_cells)
            cover += cv
            detail.append(f'{o.unit}@{o.coord}({r},{c}) 覆盖{cv}')
    print(f'{tf:<13} {legal/max(1,tot):>6.0%} {cover:>8}  ' + '; '.join(detail[:4]))
