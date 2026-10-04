# -*- coding: utf-8 -*-
"""dump_keymap.py — 只读解析 MuMu 键鼠方案，找出「划火柴」/鼠标类动作（为下一轮宏路径做准备）。

用法：python dump_keymap.py "<keymap.json 路径>"
"""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

p = sys.argv[1]
d = json.load(open(p, encoding='utf-8'))
print('文件:', os.path.basename(p))
print('顶层键:', list(d.keys()))
kms = d.get('keymaps') or []
print('keymaps 组数:', len(kms))
for gi, g in enumerate(kms):
    print('--- 组 {}: {} 条 ---'.format(gi, len(g) if hasattr(g, '__len__') else '?'))
    if gi == 0:
        print('   结构样例:', json.dumps(g, ensure_ascii=False)[:500])
    for e in (g if isinstance(g, list) else []):
        if not isinstance(e, dict):
            print('   (非字典项)', str(e)[:120])
            continue
        k = e.get('key') or {}
        acts = e.get('press_actions') or e.get('pressActions') or []
        txt = k.get('text')
        print('  键={!r:<8} scan={:<5} 动作={}'.format(
            txt, k.get('scan_code'), ' | '.join(str(x) for x in acts)[:190]))
        rel = e.get('release_actions') or e.get('releaseActions')
        if rel:
            print('        抬起={}'.format(' | '.join(str(x) for x in rel)[:170]))
