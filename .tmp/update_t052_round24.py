# -*- coding: utf-8 -*-
"""T-052 追加：第二十四轮（用户更正的三条机制 + 关卡单位完整提取）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第二十四轮（用户更正机制 + 关卡单位完整提取）**：用户指出 ①应急储备**不会被敌人攻击**、'
    '②但**影响敌人寻路**、③**我方可以攻击它获取费用**；④另有**平民**被查明身份后进入目标点提升上限，'
    '需辨明是否附带回费。**数据核实**：储备 `trap_111_wdfarm` 天赋黑板 `{max_cost:5, cost:5}` ⇒ '
    '**上限+5 且费用+5**；平民 `enemy_1313_wdfmr` 的技能 `wdfmr_cost` tooltip：「鉴定完成后自身获得不可阻挡；'
    '到达路径终点时，我方**费用上限+2**」⇒ **仅上限、无回费**（已辨明）。'
    '**已实现**：①敌人索敌移除 DEVICE（保留高台规则）；②储备占格进 `map.device_blocked`，'
    '`build_navmap` 当障碍 ⇒ 影响寻路；③我方无敌人时打装置换费用（实测 25.2/28.5s 各 +5/+5）；'
    '④平民到达终点 `add_cost_cap(2)`、不扣生命不回费。**实测**：`device_destroyed×2`、'
    '**`civilian_arrived×14`**、上限 20→30→**58**、战果 WIN。'
    '**新增（用户明示要求）**：`sim/draft/level_units.py` —— 读取关卡时**一次性提取全部关联单位与机制**'
    '（runes / 预置单位及天赋黑板 / 敌人实例覆盖字段 / 平民机制），供模拟与打图两端共用。'
    '**待办**：叠加 `enemy_attribute_mul`（atk/def/max_hp ×1.2）。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第二十四轮（用户更正机制' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
