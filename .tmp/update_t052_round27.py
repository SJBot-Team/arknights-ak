# -*- coding: utf-8 -*-
"""T-052 追加：第二十七轮（坐标变换再确认：合法判据胜出，接触判据有陷阱）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第二十七轮（坐标变换再确认）**：①新增"实战接触"判据 `check_transform_contact.py`'
    '（逐帧统计每格被敌人占据次数 → 各变换下干员攻击格的接触总量）：rc_colflip 合计 178663 帧 '
    'vs 现用 rc_rowflip 108739（1.64×），看似应换变换；'
    '②**但逐一检查非法地块后发现接触判据是陷阱**：rc_rowflip 仅 1 个非法（艾拉 G12 落近战位），'
    '而 rc_colflip 有 **16 个非法**，其中**令 C12 → tile_forbidden（禁区）、蕾缪安 G9 → 近战位**⇒ '
    '物理上不可能；接触判据偏向它只是因为错位后的格子落在敌人主干道上（流量大但根本不可部署）；'
    '③**结论：坐标变换仍为 rc_rowflip**（唯一异常是轴表里艾拉 G12，疑似作者笔误）；'
    '**判据选择教训**：涉及"能不能放下/打得到"，**合法性优先于流量统计**；'
    '④据此把上轮疑点收窄：令/弦惊攻击格的接触量其实不低（弦惊格 54578 帧 ≈ 总接触 70%），'
    '所以"召唤物 AoE 0 次"**不是位置问题**，下一步查"技能激活窗口内敌人是否恰在龙的四格内"'
    '以及 `_summon_aoe_tick` 的触发/累计逻辑。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第二十七轮（坐标变换再确认）' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
