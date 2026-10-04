# -*- coding: utf-8 -*-
"""probe_block_model.py — ★检验 D14 的假设：**不吸附 + "进入阻挡者所在格"阻挡**。

## 假设来源（手算）
「进入阻挡者所在格」+ **不做吸附**时，对 1-1 第 1 只（猎狗pro，走 row3 从左向右）：
- 芬在 (3,5)，朝左范围 = {(3,5),(3,4)}；
- 敌人进入 **范围格 (3,4)** ⇒ x ≥ 3.9 ⇒ 约 3.4 格行程 ⇒ 帧 ≈ 90 + 111 = **201**
  ⇒ 芬索敌 201、命中 201+18 = **219**（标定：207 起前摇 / **221 命中**）
- 敌人进入 **芬所在格 (3,5)** ⇒ x ≥ 5.0 ⇒ 约 4.5 格行程 ⇒ 帧 ≈ 90 + 146 = **236**
  ⇒ **与标定的「236 芬 阻挡」逐帧吻合**

⇒ 故本脚本对比四组：{吸附 on/off} × {阻挡规则 margin 0.0 / 1.0}。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from sweep_hit_volume import run, score     # noqa: E402

CASES = [
    ('margin1.0 + 吸附（当前默认）', {'block_cell_margin': 1.0, 'block_snap': True}),
    ('margin1.0 + 无吸附', {'block_cell_margin': 1.0, 'block_snap': False}),
    ('margin0.0 + 无吸附 ★假设', {'block_cell_margin': 0.0, 'block_snap': False}),
    ('margin0.0 + 吸附', {'block_cell_margin': 0.0, 'block_snap': True}),
]

print(f'{"配置":>26} {"阻挡帧":>14} {"平均":>6} {"≤6帧":>5} {"最大":>5}  芬首个/次个命中')
for name, o in CASES:
    b = run(o)
    bl = [l.frame for l in b.logs if l.kind == 'block']
    a, h, m, _d = score(b)
    fh = [l.frame for l in b.logs if l.kind == 'hit' and l.detail['src'] == '芬'
          and l.detail['tgt'] in ('猎狗pro', '猎狗')]
    print(f'{name:>26} {str(bl):>14} {a:>6.2f} {h:>5} {m:>5}  {fh[:4]}')
print('标定：阻挡 [236, 443]；芬命中猎狗pro 221 / 命中猎狗 432 / 击杀 464')
