# -*- coding: utf-8 -*-
"""probe_rarity_cap.py — 核对★3 干员的**练度上限**（用户 2026-09-15 指出的"游戏数据基础常识"）。

用 `character_table.json` 的 `phases[].maxLevel` 验证：★3 干员最高只能到 **精英1**，
其满级为 **55** ⇒ 芬 / 月见夜 的"最高练度"就是 **E1 L55**，
**不是** 轴表早期误写的"精英2 / LV90"。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D     # noqa: E402

c = json.load(open(os.path.join(D.AKGD, 'character_table.json'), encoding='utf-8'))
KEYS = ['char_123_fang', 'char_283_midn']
print(f'{"干员":<8} {"稀有度":>5} {"阶段":>10} {"该阶段满级":>10}')
for k in KEYS:
    f = c[k]
    rarity = f.get('rarity')
    try:
        n_star = int(rarity) + 1 if not isinstance(rarity, str) else int(rarity) + 1
    except Exception:                                            # noqa: BLE001
        n_star = rarity
    for p in f.get('phases', []):
        print(f'{f["name"]:<8} {str(n_star) + "★":>5} {str(p.get("phase")):>10} '
              f'{str(p.get("maxLevel")):>10}')
print()
print('★通用常识（可据此判断"是否已达上限"）：')
print('  ★1/★2：仅精英0（上限 30）')
print('  ★3   ：精英0(上限 40) → 精英1(上限 55)      ← 芬/月见夜属此列，**最高 E1 L55**')
print('  ★4/★5：+ 精英2(上限 70/80)')
print('  ★6   ：精英2 上限 90')
