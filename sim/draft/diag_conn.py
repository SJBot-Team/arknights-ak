# -*- coding: utf-8 -*-
"""diag_conn.py — 打印地块类型全图 + 连通分量，检查「地面可通行」判定是否过严。"""
import os
import sys
from collections import Counter, deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import scenario_h124 as S            # noqa: E402
from ak_sim.engine import Battle                  # noqa: E402


def main():
    b = Battle(S.LEVEL, seed=0, record=False)
    m = b.map
    H, W = m.height, m.width
    print('=== 每格 tileKey / height / mask / gpass ===')
    keys = Counter()
    for r in range(H):
        line = []
        for c in range(W):
            t = m.tile(r, c)
            keys[(t.key, t.height_type, t.passable_mask, t.is_ground_passable)] += 1
            line.append(f'{t.key.replace("tile_","")[:5]:>5}{"H" if t.height_type=="HIGHLAND" else "L"}'
                        f'{t.passable_mask[:4]:>4}{"+" if t.is_ground_passable else "-"}')
        print(f'{r:>2} ' + ' '.join(line))
    print('\n=== 地块类型统计 ===')
    for k, v in keys.most_common():
        print(f'  {k} × {v}')

    print('\n=== 地面可通行连通分量（4 邻）===')
    seen = set()
    comps = []
    for r in range(H):
        for c in range(W):
            if (r, c) in seen or not m.is_passable(r, c):
                continue
            q = deque([(r, c)])
            seen.add((r, c))
            comp = []
            while q:
                cur = q.popleft()
                comp.append(cur)
                for dr, dc in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                    nxt = (cur[0] + dr, cur[1] + dc)
                    if nxt in seen or not m.in_bounds(*nxt):
                        continue
                    if m.is_passable(nxt[0], nxt[1]):
                        seen.add(nxt)
                        q.append(nxt)
            comps.append(comp)
    comps.sort(key=len, reverse=True)
    for i, comp in enumerate(comps):
        print(f'  分量{i}: {len(comp)} 格  {sorted(comp)[:40]}')
    print('\n出生门:', sorted(m.door_tiles))
    for rt in (b.level.get('routes') or []):
        if not rt:
            continue
        sp = rt.get('startPosition') or {}
        ep = rt.get('endPosition') or {}
        g = (int(sp.get('row', -1)), int(sp.get('col', -1)))
        e = (int(ep.get('row', -1)), int(ep.get('col', -1)))
        ci = next((i for i, comp in enumerate(comps) if g in comp), None)
        ce = next((i for i, comp in enumerate(comps) if e in comp), None)
        if ci != ce:
            print(f'  ⚠ route {rt.get("motionMode")} start{g} 分量{ci} → end{e} 分量{ce} 不连通')


if __name__ == '__main__':
    main()
