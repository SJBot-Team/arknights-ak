# -*- coding: utf-8 -*-
"""检查 h12-4 的「街头应急储备」(5,6)/(5,7) 是否落在令(C12)/蕾缪安(G9)的射程内

用途：判定「谁摧毁储备」这条规则——若在射程内，则"干员会攻击装置"是可行解释；
      若不在，则应另有机制（敌人摧毁 / 召唤物 AoE / 轴表隐含操作）。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S          # noqa: E402
from ak_sim.axis import coord_to_rc            # noqa: E402
from ak_sim.data import get_operator, get_range  # noqa: E402
from ak_sim.engine import Battle               # noqa: E402

LEVEL = 'obt/hard/level_hard_12-04'
RESERVES = [(5, 6), (5, 7)]
UNITS = [('令', 'char_2023_ling', 2, 'C12', '上'),
         ('蕾缪安', 'char_4193_lemuen', 0, 'G9', '下'),
         ('弦惊', 'token_10020_ling_soul3', 0, 'D11', '左')]

b = Battle(LEVEL, seed=0)
H, W = b.map.height, b.map.width
print(f'地图 {H} 行 x {W} 列；储备位置 {RESERVES}')


def cells_of(range_id, row, col, direction):
    rg = get_range(range_id)
    dx, dy = {'右': (1, 0), '左': (-1, 0), '上': (0, 1), '下': (0, -1)}[direction]
    out = set()
    for g in rg:
        c, r = (g[0], g[1]) if isinstance(g, (list, tuple)) else (g.get('col', 0), g.get('row', 0))
        fwd, lat = c, r
        if dx == 1:
            out.add((row + lat, col + fwd))
        elif dx == -1:
            out.add((row - lat, col - fwd))
        elif dy == 1:
            out.add((row + fwd, col - lat))
        else:
            out.add((row - fwd, col + lat))
    return out


print('\n各干员射程覆盖情况：')
for name, cid, sk, coord, direction in UNITS:
    r, c = coord_to_rc(coord, H, W, S.COORD_TRANSFORM)
    try:
        spec = get_operator(cid, elite=2, level=90, potential=6, trust=200, skill_index=sk)
    except Exception as ex:
        print(f'  {name}: 取数据失败 {ex!r}')
        continue
    rid = spec.get('rangeId') or '1-1'
    cells = cells_of(rid, r, c, direction)
    hits = [t for t in RESERVES if t in cells]
    print(f'  {name:<6} {coord} → (r{r},c{c}) 朝向{direction} range={rid} 覆盖格数={len(cells)} '
          f'→ 命中储备 {hits if hits else "无"}')
    # 距储备的最近距离（切比雪夫）
    for t in RESERVES:
        d = max(abs(t[0] - r), abs(t[1] - c))
        print(f'        距储备{t} 切比雪夫距离 = {d} 格')

print('\n结论提示：若三者都不覆盖储备，则"谁摧毁它"另有机制（敌方/召唤物AoE/轴隐含操作）。')
