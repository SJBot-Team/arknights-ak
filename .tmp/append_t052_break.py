# -*- coding: utf-8 -*-
"""append_t052_break.py — ★记录"逐敌受击体积"突破：两个观测首次同时满足。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

parts = [
 '【第105轮】★★★★★★**★突破：L1-03/L2-03 的耦合被解开 ——「逐敌受击判定体积不同」，两个观测首次同时满足**：',
 '①**思路**：L1-03 一直表现为「敌人 #2 到达芬范围的时刻差 ~25 帧」，但移速与出生点均已排除；',
 '本轮转而怀疑**受击判定体积并非「所有敌人一律 0.1」** —— 客户端 prefab（`battle/enm_pfb_N.ab` 的 ',
 '`CircleCollider2D.m_Radius`）实测分布是 **0.1(2037)/0.5(124)/1.0(1028)/1.5(84)/2.0(313)/2.5(78)/3.0(36)**',
 '（`knowledge/04/16`）；',
 '②**引擎增强**：`ak_sim/engine.py` 新增 **`options[\'hit_radius_by_key\']`**（按敌人 key 覆盖受击半径，',
 '`__init__` 读入、`_spawn_enemy` 应用）—— 调试中发现首版**选项没接进引擎**导致覆盖无效，已修；',
 '③**★扫描结果（`sim/draft/sweep_hit_radius_by_key.py`）**：',
 '**`margin 0.1`（≈「进入阻挡者所在格」）+ 不吸附 + 「猎狗」受击半径 0.8** ⇒ ',
 '**阻挡帧 [232, 442]（标定 [236, 443]，偏差恒 −4/−1）✅ 且 伤害平均 2.44、≤6 帧 15、最大 7 ✅**',
 ' —— **两个观测首次同时满足**；',
 '（对照：旧默认 `margin 1.0`+吸附 伤害 2.19 但阻挡 −32/−31 ✗；',
 '`margin 0.1`+半径 0.1 阻挡 ✓ 但伤害 4.50/最大 25 ✗）',
 '半径序列 0.1→0.3→0.5→0.8→1.0 的伤害平均为 4.50→4.12→3.56→**2.44**→2.47 ⇒ **0.8 为最优**；',
 '④**⇒ 结论（修正既有认知）**：所谓「敌人 #2 到达偏晚」**其实是它的受击圆更大**，芬因此更早索敌',
 ' ⇒ **L1-03 不是路径问题**（该问题被大幅回收）；',
 '而旧默认的 `margin 1.0`+吸附之所以「伤害最优」，是靠**提前吸附掩盖了「体积一律 0.1」这一错误**',
 ' —— 这正是「用一个错误补偿另一个错误」的典型；',
 '⑤**文档更新**：`knowledge/04/60_问题登记_按工作层级.md` —— **L2-02 改为「已发现逐敌不同」',
 '（猎狗≈0.8 / 猎狗pro=0.1）**、**L2-03 改为「已定」（margin 0.1 + 不吸附）**、',
 '**L1-03 改为「⚠️ 已大幅回收」**、L1-07 同步；',
 '⑥**残留 OPEN**：客户端逐敌半径的**直接读取**（需 `UnityPy` 解析 `battle/enm_pfb_N.ab`，',
 '本机未装；报告 `collider_report.json` 中 `enm_pfb_0` 是**扁平碰撞体列表**、非逐敌）',
 ' ⇒ 下一步可装 `UnityPy` 或用等价解析器**直接确认 猎狗=0.8、猎狗pro=0.1**；',
 '⑦**合规**：纯本地模拟计算与只读本机资源；未登录、未消耗资源、未读改游戏文件/内存。 |',
]
entry = ''.join(parts)
lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
