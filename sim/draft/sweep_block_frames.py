# -*- coding: utf-8 -*-
"""sweep_block_frames.py — ★用"阻挡事件帧"本身作为判据扫描 ④阻挡规则。

## 为什么换判据
此前只用"伤害事件帧"打分，导致阻挡规则**被当成可自由拟合的参数**（1.0 → 1.5），
而**标定表本身就标了两个阻挡事件**：

| 标定帧 | 说明 |
|---|---|
| **236** | 芬 阻挡 猎狗pro |
| **443** | 芬 阻挡 猎狗 |

模拟器当前（cell_3x3_round）：`block = [204, 412]` ⇒ 比标定**早 ~31 帧**。
⇒ 本脚本同时报：**(a) 阻挡帧误差**、**(b) 伤害事件帧误差**，找两者都好的规则。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score     # noqa: E402

CALIB_BLOCK = [236, 443]


def blocks(b) -> list[int]:
    return [l.frame for l in b.logs if l.kind == 'block']


def berr(b) -> float:
    bl = blocks(b)
    if len(bl) < len(CALIB_BLOCK):
        return 999.0
    return sum(abs(bl[i] - CALIB_BLOCK[i]) for i in range(len(CALIB_BLOCK))) / len(CALIB_BLOCK)


rows = []
CASES = [
    ('cell_3x3_round', {'block_cell_margin': 1.0}),
    ('cell_3x3_round', {'block_cell_margin': 0.75}),
    ('cell_3x3_round', {'block_cell_margin': 0.5}),
    ('cell_3x3_round', {'block_cell_margin': 0.25}),
    ('cell_3x3_round', {'block_cell_margin': 0.1}),
    ('cell_3x3_round', {'block_cell_margin': 0.0}),
    ('cell_3x3', {}),
    ('capture_distance', {'block_capture_distance': 1.0}),
    ('capture_distance', {'block_capture_distance': 0.75}),
    ('capture_distance', {'block_capture_distance': 0.5}),
    ('capture_distance', {'block_capture_distance': 0.35}),
    ('capture_distance', {'block_capture_distance': 0.25}),
    ('collision_pair', {}),
]

print(f'{"规则":>18} {"参数":>16} {"阻挡帧":>14} {"阻挡误差":>8} {"平均":>6} {"≤6帧":>5} {"最大":>5}')
for rule, extra in CASES:
    opts = {'block_rule': rule}
    opts.update(extra)
    b = run(opts)
    a, h, m, _d = score(b)
    param = ','.join(f'{k.split("_")[-1]}={v}' for k, v in extra.items()) or '—'
    print(f'{rule:>18} {param:>16} {str(blocks(b)):>14} {berr(b):>8.1f} {a:>6.2f} {h:>5} {m:>5}')
    rows.append((rule, param, blocks(b), berr(b), a))
print(f'\n标定阻挡帧 = {CALIB_BLOCK}')
best = min(rows, key=lambda r: r[3])
print(f'阻挡帧误差最小：{best[0]} {best[1]} → {best[2]}（误差 {best[3]:.1f}）；其伤害平均 {best[4]:.2f}')
