# -*- coding: utf-8 -*-
"""T-052 追加：第十八轮（储备物建模 + 暴露"谁摧毁它"规则未对）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第十八轮（储备物建模）**：①从关卡 `predefines.tokenInsts` 取到 **trap_111_wdfarm = 街头应急储备**'
    '（profession TRAP，**HP 8000/def 100/block 5**），h12-4 共 **2 个**，位置 (5,6)/(5,7)；'
    'character_table 天赋黑板 `{max_cost:5, cost:5}`，描述「被击败后恢复 5 点费用上限及费用」；'
    '②**闭合关系**：rune 上限 20 → 摧毁 1 个 → **25 ≥ 23** ⇒ 弦惊才可落地（2 个都摧毁 → 30）；'
    '③已实现：载入关卡生成 `side=DEVICE` 装置、摧毁时 `add_cost_cap(+5)` 与 `cost += 5`、'
    '干员无敌人时改打射程内装置、装置不参与清场/漏怪统计；实测载入后上限 20、场上 2 个装置（各 8000 HP）；'
    '④**本轮暴露的关键问题**：跑完整轴后**装置并未被摧毁**（无 `device_destroyed` 日志）⇒ 上限仍 20、'
    '弦惊仍落在 88.8s/148.8s。说明**「谁在何时摧毁储备」的规则还没对上**（作者时间线要求 ~43s 前已摧毁至少一个），'
    '候选规则：干员即便有敌人也优先打装置 / 召唤物 AoE 也能命中装置 / 敌人会摧毁它 / 轴表隐含攻击装置的操作；'
    '⑤案例测试保持信息项口径，解析预测与作者记录对照仍 PASS。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第十八轮（储备物建模）' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
