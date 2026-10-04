# -*- coding: utf-8 -*-
"""T-052 追加：第十七轮（实机发现费用上限 20 + 模拟器 rune 叠加）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第十七轮（实机发现：h12-4 费用上限被 rune 压到 20）**：①实机在 MuMu 进 h12-4 后，'
    '右下角费用**长期停在 20 并显示 MAX**（连测 28s 不变）⇒ 上限不是 99；'
    '②查关卡数据证实：`options.maxCost=99` 但 `runes` 里有 `cbuff_max_cost`（`max_cost=20`、'
    '`max_cost_ceil=99`）；关卡文本亦写明「我方费用上限大幅降低」「<街头应急储备>被摧毁后获得一定费用及费用上限」；'
    '③**含义**：此前模拟器直接用 99、未叠加 runes ⇒ h12-4 费用动力学错误；弦惊需 **23 > 20** ⇒ '
    '**只能在储备物被摧毁、上限抬升之后才可能落地** —— 这也解释了作者时间线（解析模型 43.0/66.0s 与作者 66.1s 吻合到 0.1s，'
    '说明 43s 前上限已被抬升过）；④**已修**：`ak_sim/engine.py` 载入关卡时叠加 runes（`max_cost`/`max_cost_ceil`），'
    '新增 `add_cost_cap(delta)` 供储备物机制抬升上限（实测：20 → +10 → 30 → +70 → 99 ✓）；'
    '⑤**新增缺口 F（优先级高）**：「街头应急储备」等可摧毁物未建模，需从其位置/耐久数据 + 摧毁时调用 `add_cost_cap`；'
    '在此之前模拟器无法复现弦惊落地（实测被推迟到 88.8s/148.8s…），案例测试已把该项降级为信息项；'
    '⑥`test_skills.py` 的静默战斗显式抬高上限以隔离变量；全量回归通过。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第十七轮（实机发现' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
