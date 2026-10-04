# -*- coding: utf-8 -*-
"""append_t052_harmless.py — 追加"无害标记核实"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]
add = (
 '【第65轮·补】**`isUnharmfulAndAlwaysCountAsKilled` 核实：又一个「其实早就实现了」的例子**：'
 'h12-4 的 14 条带标记出怪**key 全是 `enemy_1313_wdfmr`「诺伯特平民」**；'
 '而本库**早已有平民分支**（依据 `enemy_skills.json` 的 `wdfmr_cost`）：到达终点**不扣生命**、'
 '**费用上限 +2**（`civilian_arrived` 事件）；实跑 260s 验证 **14/14 到达、rune 基数 20 → 最终 48、未扣生命**；'
 '本轮另加**通用兜底分支 `escape_harmless`**（供"非平民"的无害单位使用）；'
 '新增 `probe_harmless.py`、`test_harmless_enemy.py`；**1-1 无回归（16/16、平均 2.19 帧）**；'
 '⇒ 再次印证"先摸底"：**该标记在本项目对应的就是平民，其语义已由既有分支承担**。 |'
)
lines[i] = row[:-1] + add
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
