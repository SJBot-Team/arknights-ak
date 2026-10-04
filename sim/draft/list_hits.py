# -*- coding: utf-8 -*-
"""list_hits.py — 列出全部 hit 事件（正确字段名 src/tgt），核对芬是否命中猎狗。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run        # noqa: E402

b = run({})
print('=== 全部 hit 事件 ===')
for l in b.logs:
    if l.kind == 'hit':
        print(f"  {l.frame:>4}  {l.detail['src']:>6} -> {l.detail['tgt']:<6} dmg={l.detail['dmg']}")
print('\n=== kill ===')
for l in b.logs:
    if l.kind == 'kill':
        print(f"  {l.frame:>4}  {l.detail}")
print('\n=== 芬 对 猎狗 的索敌 ===')
for l in b.logs:
    if l.kind == 'target_select' and l.detail.get('unit') == '芬' \
            and l.detail.get('target') == '猎狗':
        print(f"  {l.frame:>4}  judge={l.detail.get('judge')}")
