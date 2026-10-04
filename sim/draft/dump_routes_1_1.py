# -*- coding: utf-8 -*-
"""dump_routes_1_1.py — 打印 1-1 的**出怪路线格子**（用户要求的"按出怪格子重新映射"的基准）。

同时打印：
- `mapData.map` 的 tile 类型网格（R=近战可部署 road、^=高台、.=其它）
- 每条 route 的 `startPosition` / `endPosition` / checkpoints（mapData 行列）
- 关卡 `mapData.map` 的行序说明（AK 的 mapData 行 0 在**屏幕上方还是下方**）
"""
from __future__ import annotations

import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

LV = r'E:\__file\ak_kb\gamedata\levels\obt\main\level_main_01-01.json'
lv = json.load(open(LV, encoding='utf-8'))
md = lv.get('mapData') or {}
m, tiles = md.get('map') or [], md.get('tiles') or []
rows, cols = len(m), len(m[0]) if m else 0


def kind(v):
    t = tiles[v] if 0 <= v < len(tiles) else {}
    b = t.get('buildableType')
    return 'R' if b == 'MELEE' else ('^' if b == 'RANGED' else '.')


print(f'1-1 地图 {rows}×{cols}（mapData 行 0..{rows - 1}）')
for r in range(rows):
    print(f'  mapData r{r}: ' + ' '.join(kind(v) for v in m[r]))

print('\n路线（出怪格子）:')
for i, rt in enumerate(lv.get('routes') or []):
    s = rt.get('startPosition') or {}
    e = rt.get('endPosition') or {}
    cps = rt.get('checkpoints') or []
    print(f'  route{i}: start=(row {s.get("row")}, col {s.get("col")}) '
          f'→ end=(row {e.get("row")}, col {e.get("col")})  '
          f'allowDiagonal={rt.get("allowDiagonalMove")} checkpoints={len(cps)}')
    for cp in cps:
        p = cp.get('position') or {}
        print(f'        cp: (row {p.get("row")}, col {p.get("col")}) '
              f'reachOffset={cp.get("reachOffset")}')

print('\n出怪动作里用到的 routeIndex（前 12 条）:')
acts = []
for w in (lv.get('waves') or []):
    for fr in (w.get('fragments') or []):
        for a in (fr.get('actions') or []):
            if a.get('actionType') == 'SPAWN':
                acts.append((a.get('key'), a.get('routeIndex')))
for a in acts[:12]:
    print('   ', a)
