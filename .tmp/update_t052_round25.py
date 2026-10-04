# -*- coding: utf-8 -*-
"""T-052 追加：第二十五轮（敌人属性乘区 + 回归事故修复）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第二十五轮（敌人属性乘区 + 一次回归事故）**：①实现 `enemy_attribute_mul` rune '
    '（h12-4 = atk/def/max_hp ×1.2，平民除外）于敌人出场时叠加——实测岗哨密探长 '
    'atk 800→960 / def 200→240 / HP 6500→7800 ✓；②**发现并修复一次回归**：上一轮按用户更正'
    '「敌人不攻击储备」改动 `operators_attackable_by` 时，**连带删掉了其后的 `_enemy_can_reach` 高台判定**，'
    '导致地面近战敌人又能打到高台上的令（令 20.9s 被 822×2 打死）；已补回并加注「勿删」；'
    '③修复后实测：令 存活 11955 帧（活到结束、出手 62 次）、蕾缪安 9248 帧（8 次）、'
    'U-Official 有目标帧 72%（12 次）⇒ 我方终于能正常打人；'
    '④时间线（已含全部机制）：弦惊 33.0/56.0/83.0/129.5/130.2/173.0s，作者记录 66.1/86.4/153.3s；'
    '储备被摧毁于 24.7s/27.3s（现由我方攻击触发），费用上限最终 58（2×储备+5 与 14×平民+2）；'
    '⑤技能自检 4/4、案例测试 PASS、1-7 冒烟正常。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第二十五轮（敌人属性乘区' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
