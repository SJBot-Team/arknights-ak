# -*- coding: utf-8 -*-
"""diag_traffic.py — 敌人流量热力图 vs 轴表坐标（判定坐标变换是否把召唤物放到了敌人走位上）。

只做一件事：统计每个格子被敌人占用的帧数，然后看轴表里的坐标在 8 种变换下
落在多热的格子上。热 = 敌人真的会经过。召唤物放在冷格子上 → AoE 永远不触发。
"""
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S                     # noqa: E402
from ak_sim.axis import parse_cyberplastic, coord_to_rc, COORD_TRANSFORMS  # noqa: E402
from ak_sim.engine import Battle                          # noqa: E402

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
    heat = Counter()
    destroy_heat = Counter()
    orig = Battle.tick

    def tick(self):
        orig(self)
        if self.frame % 6 == 0:                 # 每 6 帧采样，降噪
            for u in self.units.values():
                if u.side == 'ENEMY' and u.alive:
                    heat[u.grid()] += 6
                elif u.side == 'DEVICE' and not u.dead:
                    destroy_heat[u.grid()] += 6

    Battle.tick = tick
    b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
               max_frames=30 * 400, continue_after_fail=True,
               retry_on_cost=True, retry_on_sp=False,
               schedule=[int(p['frame']) for p in plan])
    Battle.tick = orig

    H, W = b.map.height, b.map.width
    print(f'地图 {H} 行 × {W} 列；采样帧数 {sum(heat.values())//6}')
    print('\n=== 敌人占用热力图（数字=占用秒数，. = 0，B=可部署地面，H=高台）===')
    maxv = max(heat.values()) / FPS if heat else 1
    hdr = '     ' + ''.join(f'{c:>4}' for c in range(W))
    print(hdr)
    for r in range(H):
        cells = []
        for c in range(W):
            v = heat.get((r, c), 0) / FPS
            if v <= 0:
                try:
                    g = b.map.tile(r, c).height_type
                    cells.append('  H ' if g == 'HIGHLAND' else '  . ')
                except Exception:
                    cells.append('  x ')
            else:
                cells.append(f'{v:4.0f}' if v < 1000 else f'{v/1000:3.0f}k')
        print(f'{r:>4} ' + ''.join(cells))

    # 占领/经过最多的格子
    top = [(v / FPS, rc) for rc, v in heat.most_common(25)]
    print('\n=== 最热格子 Top25（秒, (row,col)）===')
    print('  ' + ', '.join(f'{rc}={s:.0f}s' for s, rc in top))

    print('\n=== 轴表 deploy 坐标在 8 种变换下的热度（召唤物用 token，其余为干员）===')
    tot = defaultdict(float)
    n_tok = defaultdict(int)
    for o in ops:
        if o.get('op') != 'deploy' or not o.get('coord'):
            continue
        tok = str(o.get('unit', '')).startswith('token_')
        for name in S.COORD_TRANSFORMS:
            try:
                r, c = coord_to_rc(o['coord'], H, W, name)
            except Exception:
                continue
            tot[name] += heat.get((r, c), 0) / FPS
            if tok:
                n_tok[name] += 1
    for name in sorted(COORD_TRANSFORMS, key=lambda n: -tot[n]):
        print(f'  {name:<12} 全部部署点累计热度 {tot[name]:8.0f}s')

    print('\n=== 逐条 deploy：各变换落点热度（只看召唤物 与 令/蕾缪安）===')
    for o in ops:
        if o.get('op') != 'deploy' or not o.get('coord'):
            continue
        u = o.get('char') or o.get('unit') or ''
        if not (u.startswith('token_') or u in ('令', '蕾缪安')):
            continue
        row = []
        for name in S.COORD_TRANSFORMS:
            try:
                r, c = coord_to_rc(o['coord'], H, W, name)
                s = heat.get((r, c), 0) / FPS
                row.append(f'{name}={s:.0f}s{(r,c)}')
            except Exception:
                row.append(f'{name}=ERR')
        print(f'  {u:<28} {o["coord"]:<4} ' + ' | '.join(row))


if __name__ == '__main__':
    main()
