# -*- coding: utf-8 -*-
"""dump_start_end.py — 打印 1-1 的 tile_start / tile_end 格（出怪与终点），用于**格子映射反解**。"""
from __future__ import annotations

import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

LV = r'E:\__file\ak_kb\gamedata\levels\obt\main\level_main_01-01.json'
lv = json.load(open(LV, encoding='utf-8'))
md = lv['mapData']
m, tiles = md['map'], md['tiles']
rows, cols = len(m), len(m[0])

print('tile_start / tile_end 格:')
for r in range(rows):
    for c in range(cols):
        t = tiles[m[r][c]]
        k = str(t.get('tileKey'))
        if 'start' in k or 'end' in k:
            print(f'   ({r},{c})  {k}  height={t.get("heightType")}  '
                  f'isStart={t.get("isStart")} isEnd={t.get("isEnd")}')

print('\nROAD（近战可部署）格:')
road = [(r, c) for r in range(rows) for c in range(cols)
        if tiles[m[r][c]].get('buildableType') == 'MELEE']
print('  ', road)
print('\n高台格:')
hl = [(r, c) for r in range(rows) for c in range(cols)
      if tiles[m[r][c]].get('buildableType') == 'RANGED']
print('  ', hl)
