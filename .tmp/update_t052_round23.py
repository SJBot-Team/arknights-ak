# -*- coding: utf-8 -*-
"""T-052 追加：第二十三轮（修复：地面敌人不能触及高台单位 —— 本轮最重要保真度修正）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第二十三轮（高台规则修复，重大保真度修正）**：①上一轮定位到"令 21.2s 阵亡"，'
    '本轮查明根因：我们的敌人攻击/阻挡判定**只按格距、不区分高台与地面** ⇒ 站在高台上的'
    '令/蕾缪安被地面近战敌人打死；②修复：新增 `Battle._enemy_can_reach(e, o)`——地面敌人'
    '**既不能攻击也不能阻挡高台单位**，`operators_attackable_by` 与 `_block_tick` 都接入；'
    '③**效果**：令 存活 592 帧→**11955 帧**（活到 400s 结束）、出手 1 次→**63 次**；'
    '蕾缪安 2540 帧→**9037 帧**（活到结束）、有目标帧 162→**521**；'
    '④这条修正把"打不到人→没伤害→没SP→技能放不出"的因果链**从根上解开**，'
    '此前所有伤害/SP/生存类结论需在新规则下重跑；'
    '⑤下一层：叠加 `enemy_attribute_mul` rune（{atk:1.2, def:1.2, max_hp:1.2}）与 '
    '`enemyDbRefs.overwrittenData`（逐字段 m_defined 覆盖）→ 再核敌人出场/移动时序 → 最后重跑三类对齐；'
    '⑥技能自检 4/4、案例测试 PASS、1-7 冒烟正常。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第二十三轮（高台规则修复' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
