# -*- coding: utf-8 -*-
"""fine_sweep_hit_volume.py — 细网格扫描"受击判定体积"（语义模型下的标定）。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score     # noqa: E402

print(f'{"hr":>6} {"平均":>6} {"<=6帧":>6} {"最大":>5}')
best = None
for i in range(0, 13):
    hr = round(i * 0.05, 2)
    b = run({'hit_volume_enemy': hr})
    a, h, m, _d = score(b)
    print(f'{hr:>6.2f} {a:>6.2f} {h:>6} {m:>5}')
    if best is None or (h, -a) > (best[1], -best[0]):
        best = (a, h, m, hr)
print(f'\n最优（以"≤6 帧条数"为先、平均为次）：hr={best[3]}  平均 {best[0]:.2f}  ≤6帧 {best[1]}  最大 {best[2]}')
