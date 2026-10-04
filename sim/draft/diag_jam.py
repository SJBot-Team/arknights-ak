# -*- coding: utf-8 -*-
"""diag_jam.py — 打印若干时间点的「敌人格点分布图」，定位拥堵/卡死。"""
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S            # noqa: E402
from ak_sim.axis import parse_cyberplastic        # noqa: E402
from ak_sim.engine import Battle                  # noqa: E402

FPS = 30
AT = [300, 900, 1800, 3600, 7200, 10800, 12000]


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
    snaps = {}
    orig = Battle.tick

    def tick(self):
        orig(self)
        if self.frame in AT:
            cnt = Counter()
            for u in self.units.values():
                if u.side == 'ENEMY' and u.alive:
                    cnt[u.grid()] += 1
            snaps[self.frame] = cnt

    Battle.tick = tick
    b.run_axis(ops, name_map=S.NAME_MAP, coord_transform=S.COORD_TRANSFORM,
               max_frames=30 * 400, continue_after_fail=False,
               retry_on_cost=True, retry_on_sp=False,
               schedule=[int(p['frame']) for p in plan])
    Battle.tick = orig

    m = b.map
    H, W = m.height, m.width
    for f in AT:
        cnt = snaps.get(f)
        if cnt is None:
            continue
        print(f'\n=== {f}f ({f/FPS:.0f}s) 存活 {sum(cnt.values())} 只，'
              f'占格 {len(cnt)} 个 ===')
        for r in range(H):
            row = ''
            for c in range(W):
                n = cnt.get((r, c), 0)
                if n:
                    row += f'{min(9,n):>3}'
                else:
                    t = m.tile(r, c)
                    ch = '#' if not t.is_ground_passable else ('D' if (r, c) in m.device_blocked else '.')
                    row += f'  {ch}'
            print(f'{r:>2} {row}')
    # 卡住最久的敌人
    print('\n=== 存活敌人明细（前 25）===')
    live = [u for u in b.units.values() if u.side == 'ENEMY' and u.alive]
    live.sort(key=lambda u: u.created_frame)
    for u in live[:25]:
        cp = u.checkpoints[u.checkpoint_idx] if (u.checkpoints and u.checkpoint_idx < len(u.checkpoints)) else None
        print(f'  {u.name:<22} uid={u.uid} grid={u.grid()} 创建 {u.created_frame}f '
              f'({u.created_frame/FPS:.0f}s) 检查点 {u.checkpoint_idx}/{len(u.checkpoints or [])} '
              f'next={ (cp or {}).get("position") } route_end={u.route_end} state={u.state}')


if __name__ == '__main__':
    main()
