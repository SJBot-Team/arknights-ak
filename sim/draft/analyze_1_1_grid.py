# -*- coding: utf-8 -*-
"""analyze_1_1_grid.py — 分析 1-1 的"近战可部署格"布局，用于实机绿格↔地图格匹配。

实机 `find_green_cells`（cell_px=130）测得 7 个绿格单元：
    一行 6 连：(807,502) (932,502) (1057,502) (1181,502) (1306,502) (1431,502)   x 步长≈124.5
    另一格   ：(1057,364)  ⇒ 恰好是"左起第 3 个的上方一行"（dx=+2 格、dy=-138）
本脚本据此在地图数据里找候选 (行, 列) 与朝向关系。
"""
from __future__ import annotations

import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

LV = r'E:\__file\ak_kb\gamedata\levels\obt\main\level_main_01-01.json'
lv = json.load(open(LV, encoding='utf-8'))
m = lv['mapData']['map']
tiles = lv['mapData']['tiles']


def kind(v):
    t = tiles[v]
    b = t.get('buildableType')
    if b == 'MELEE':
        return 'R'
    if b == 'RANGED':
        return '^'
    return '.'


print('近战可部署(R=road/MELEE) 高台(^) 其它(.)   —— 行号 = mapData 行')
for r, row in enumerate(m):
    print('  r{}: '.format(r) + ' '.join(kind(v) for v in row))

print()
print('★候选：6 连排 + “上方一行偏移 +2 列”')
for R in range(7):
    for C in range(0, 4):
        if all(kind(m[R][C + i]) == 'R' for i in range(6)):
            up = kind(m[R + 1][C + 2]) if R + 1 < 7 else '?'
            extra = '  ←★匹配(上方为R)' if up == 'R' else ''
            print('  r{} c{}..c{}  六连排；上方(c{})={}{}'.format(R, C, C + 5, C + 2, up, extra))
