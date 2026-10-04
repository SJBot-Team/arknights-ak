# -*- coding: utf-8 -*-
"""check_transform_contact.py — 用**实战接触次数**选坐标变换（最贴近真实的判据）

做法：跑一局模拟，逐帧累计**每个格子被敌人占据的次数**（contact[cell]）。
再对 4 种坐标变换，把轴表里每个部署点换算成格子，累计该干员"攻击格"的接触次数：
  · 近战/召唤物：周围四格（含自身）
  · 远程：其 rangeId 覆盖的全部格
接触次数最多者，最可能是真实坐标变换（因为实机里这些人确实在输出）。
"""
import os
import sys
from collections import Counter

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
contact = Counter()
orig = b.tick


def tick_rec():
    orig()
    for u in list(b.units.values()):
        if u.side == 'ENEMY' and u.alive:
            contact[u.grid()] += 1


b.tick = tick_rec
while b.frame < 30 * 200:
    b.tick()
print(f'敌人接触格 {len(contact)} 个，总接触帧 {sum(contact.values())}')

ax = parse_cyberplastic(S.XLSM)


def cells(range_id, row, col, direction, melee_cross=False):
    if melee_cross:
        return {(row, col), (row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)}
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


print(f'\n{"变换":<13} {"合法率":>6} {"令接触":>7} {"蕾缪安接触":>9} {"弦惊接触":>8} {"合计":>7}')
best = None
for tf in TF:
    legal = tot = 0
    cov = Counter()
    for o in ax.ops:
        if o.op != 'deploy' or not o.coord:
            continue
        cid = S.NAME_MAP.get(o.unit, o.unit)
        try:
            spec = get_operator(cid, elite=2, level=90, potential=6, trust=200)
        except Exception:
            continue
        r, c = coord_to_rc(o.coord, H_ := b.map.height, W_ := b.map.width, tf)
        tot += 1
        if b.map.can_deploy(r, c, melee=spec.get('position') != 'RANGED'):
            legal += 1
        melee = str(cid).startswith('token_') or spec.get('position') != 'RANGED'
        cs = cells(spec.get('rangeId') or '1-1', r, c, o.dir or '右', melee_cross=melee)
        cov[o.unit] += sum(contact.get(x, 0) for x in cs)
    total = sum(cov.values())
    print(f'{tf:<13} {legal/max(1,tot):>6.0%} {cov["令"]:>7} {cov["蕾缪安"]:>9} {cov["弦惊"]:>8} {total:>7}')
    if best is None or total > best[0]:
        best = (total, tf)
print(f'\n按实战接触次数 → 最佳变换 = {best[1]}（接触 {best[0]} 帧）')
