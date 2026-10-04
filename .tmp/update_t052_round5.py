# -*- coding: utf-8 -*-
"""T-052 追加：第五轮（技能/增益系统 + 时基 SP 判据）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第五轮（技能/增益系统 + 时基的独立判据）**：①按客户端表实现技能系统——SP 充能'
    '（spData：initSp/spCost/spType/increment）、**释放门槛**（SP 不满即拒绝）、技能时长（duration→帧）、'
    'blackboard 属性增益（atk/def/attack_speed→`eff_atk/eff_def/eff_attack_speed`，攻击间隔随之重算）、'
    '弹药型技能（蕾缪安 S1 6 发）、召唤物发放（S1 开启时/S3 结束时）、**召唤物 AoE**'
    '（令 S3：每 0.5s 周围四格 0.2×令攻击力 法术伤害）、**令天赋**（召唤物被撤退/击倒 → +4 SP、攻击力 +3%/层上限 5）；'
    '②`ak_sim/test_skills.py` **4/4 通过**（SP 充满帧 795 = 理论值；atk/def ×2；AoE 3 次/1.6s 且 232.8 = 0.2×1164；'
    '蕾缪安 2.1× 与 6 发弹药）；③**新增时基独立判据** `sim/draft/check_axis_sp_legality.py`：用「技能必须 SP 足够」'
    '这一与费用无关的约束检验两种时基 → `cost-relative` **4/21 合法**、`abs-seconds` **12/21 合法** ⇒ '
    '**表内「绝对时间」列明显更接近真实时间轴**，并说明此前 §7.3 的"±2 帧内 16/50"存在自洽性假象；'
    '④**仍未决**：两种时基下首批召唤物（23 费）都落在费用不足时刻（21s→DP1 / 29s→DP9），'
    'SP 与费用两条约束无法同时满足 ⇒ 实机复跑（费用尺 + 逐帧记录）为第一优先验证项。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第五轮（技能/增益系统' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
