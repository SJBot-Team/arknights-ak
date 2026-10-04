# -*- coding: utf-8 -*-
"""T-052 追加：第二十六轮（案例基线 + 召唤物绑定修复）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第二十六轮（案例基线 + 召唤物绑定修复）**：①新增 `sim/draft/case_summary.py`（一次跑完整轴输出'
    '结果/击杀/漏怪/出手/事件/时间线）；②**修复**：轴表「部署 弦惊」此前**未被识别为召唤物**'
    '（`_exec_axis_op` 未传 is_token/token_owner）⇒ owner 为空、召唤者技能期间的 AoE 永不触发；'
    '现已由 `character_table` 的 `overrideTokenKey` 反查建 `token_owner_map`、部署时传 owner 并统一换算为 uid'
    '（实测 11 个存活 token 的 owner=7=令的 uid ✓）；③**当前基线（机制齐备后首次）**：50/50 触发、成功 32；'
    '结果 WIN/生命 1；**击杀 4 / 漏怪 61**（共 75 怪、出怪到 173s 全部出完）；我方出手 82 次'
    '（令 62/蕾缪安 8/U-Official 12）；**召唤物 AoE 0 次**；部署失败 328、技能被拒 14；'
    '费用上限 20→30→**58**；弦惊 33.0/56.0/83.0/129.5/130.2/173.0s（作者 66.1/86.4/153.3s）；'
    '④**结论**：机制层（上限/储备/平民/乘区/高台）已对齐，**差距集中在输出**——召唤物 AoE 在案例中一次未命中'
    '（单元测试是 PASS，机制本身正常）⇒ 我们模拟里「龙的落点与敌人路径几乎不接触」；'
    '下一轮从"龙的位置 vs 敌人路径/坐标变换"或"敌人移动保真度"入手。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第二十六轮（案例基线' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
