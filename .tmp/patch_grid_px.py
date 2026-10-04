# -*- coding: utf-8 -*-
"""patch_grid_px.py — 把各脚本里硬编码的格点像素改为引用 `plugins/action/grid_px`。"""
from __future__ import annotations

import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = r'C:\Users\23922\Documents\ds_harness\ak\code\vision\apps'

PATCH = {
    'deploy_two_step.py': [
        ('CARD, D6 = (63, 949), (934, 502)',
         'CARD = (63, 949)\n'
         'from plugins.action.grid_px import coord_to_px as _c2p\n'
         'D6 = _c2p("D6")          # ★修正后 = (1182, 502)'),
        ('DIR_LEFT_AXIS = (1182, 502)      # 轴表"朝左"对应的格 (3,4)',
         'DIR_LEFT_AXIS = _c2p("D4")   # 轴表"朝左"= 屏幕向左 = col 4（(row3,col4)）'),
    ],
    'test_deploy_channels.py': [
        ('D4, DIR_UP = (1182, 502), (1182, 364)',
         'from plugins.action.grid_px import coord_to_px as _c2p, cell_to_px as _cell2px\n'
         'D4 = _c2p("D4")                # (932, 502)\n'
         'DIR_UP = _cell2px(2, 3)        # 朝上 = row−1'),
    ],
    'bullet_time_probe.py': [
        ("CELL_D6 = (934, 502)      # D6（本机标定：x=1556−124.5·col, y=502+138·(row−3)）",
         'from plugins.action.grid_px import coord_to_px as _c2p\n'
         'CELL_D6 = _c2p("D6")       # ★唯一真源 plugins/action/grid_px（= (1182,502)）'),
    ],
    'enemy_track_live.py': [
        ('COL0_X, COL_PX = 1556.0, 124.5',
         'COL0_X, COL_PX = 559.0, 124.5      # ★修正：x 随 col 递增（原 1556 为镜像误值）'),
        ('col = (COL0_X - x) / COL_PX',
         'col = (x - COL0_X) / COL_PX'),
    ],
}

for fn, subs in PATCH.items():
    p = os.path.join(ROOT, fn)
    if not os.path.exists(p):
        print(f'  跳过（不存在）: {fn}')
        continue
    s = io.open(p, encoding='utf-8').read()
    n = 0
    for old, new in subs:
        if old in s:
            s = s.replace(old, new)
            n += 1
        else:
            print(f'  ⚠️ {fn}: 未找到片段 {old[:46]!r}')
    io.open(p, 'w', encoding='utf-8').write(s)
    print(f'  ✅ {fn}: 替换 {n}/{len(subs)} 处')

# 语法检查
import ast
for fn in PATCH:
    p = os.path.join(ROOT, fn)
    try:
        ast.parse(io.open(p, encoding='utf-8').read())
        print(f'  语法 OK: {fn}')
    except Exception as ex:                                       # noqa: BLE001
        print(f'  ❌ 语法错误 {fn}: {ex!r}')
