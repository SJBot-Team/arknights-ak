# -*- coding: utf-8 -*-
"""append_t052_two_ranges.py — 追加"两阵营范围表示 + 阻挡重校准"一轮到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 "【第62轮】★★★★**依用户第二次澄清实现「两阵营范围表示不同」，并由此定位并修掉 1-1 的几何残差**："
 "①**用户约束**：**(A)** 我方（近战干员，如芬）索敌 = **方格范围**（芬 = **2 个方格**）；"
 "**无阻挡时，敌人的 0.1 圆进入该范围** ⇒ 干员索敌并**开始前摇**；"
 "**(B)** **远程敌人**的攻击范围通常是**一个确定半径的圆**（`rangeRadius`）；"
 "**干员的 0.25 圆处于该圆内** ⇒ 敌人开始攻击；"
 "②**实现**（`sim/draft/ak_sim/engine.py`）：**(a)** 新增 **`Battle.enemy_reach(e)`** —— 远程敌人有效触及 = "
 "`rangeRadius + ally_hit_radius(0.25)`（`enemy_range_mode='intersect'` 默认；`'contain'` 则为 `−0.25`）；"
 "**(b)** `operators_attackable_by` 按三类判据重写：`blocked` / 近战 `melee_adjacent`（切比雪夫≤1）/ 远程 `circle_*`；"
 "**(c)** 敌方索敌也写 **`target_select`** 事件（`side='ENEMY'`，含 `judge/range_radius/reach/ally_hit_radius`）；"
 "**(d)** 新增 `options`：`ally_hit_radius`、`enemy_range_mode`、`block_rule`、`block_cell_margin`；"
 "**(e)** 头部对照表补入「**两阵营范围表示不同**」的说明；"
 "③**数据层核对**（新增 `probe_enemy_range.py`）：`enemy_database` 有 `rangeRadius` + `applyWay`；"
 "1-1 的猎狗/猎狗pro/源石虫/暴徒/酸液源石虫均为 **MELEE(0)**，**`enemy_1028_mocock` = 1.75（RANGED）**；"
 "④**回归测试扩到 8 组（全通过）**：新增 **A7** 远程敌人触及 = `rangeRadius+干员0.25圆`（实测 1.75→2.00）、"
 "**A8** 近战敌人不走圆判据且敌方 `target_select` 带判据；"
 "⑤**★关键诊断（`diag_enemy2_approach.py`）**：新索敌语义下 1-1 只剩 2 条超标（帧 432 +18、帧 464 +15），"
 "逐帧追踪第 2 只猎狗发现 —— 帧 414 它在 (4.79,4.78)（到芬范围格 0.78）、帧 431 在 (4.87,4.25)（0.25）、"
 "**帧 432 被「距离 ≤ 1.0」挡下并吸附到 (3,4)**（0.00）⇒ 芬要到**帧 450** 才命中；"
 "而标定要求**帧 432 命中**（索敌帧 414，此时该敌人**尚未被阻挡**）⇒ **残差出在 ④阻挡判定，不是 ②索敌**；"
 "⑥**★重校准阻挡**：扫描 `capture_distance` 0.3~2.0 × 吸附开关 × 格规则（`sweep_block_rule.py`、"
 "`sweep_block_cell_margin.py`）：1.0→4.56/13/18；**1.5→2.56/15/7（新默认）**；`cell_3x3`（进入阻挡者格或其 8 邻格）→3.27/14/7；"
 "1.75→6.73；2.0→13.13 ⇒ **`BLOCK_CAPTURE_DISTANCE` 由 1.0 改为 1.5**（语义 = 阻挡者周围 3×3 邻域的径向近似；"
 "严格格版本以 `block_rule='cell_3x3'` 保留）；"
 "⑦**★结果（1-1 严格口径，语义正确的前提下）**：**16/16、|偏差|≤6 帧 15 条、平均 2.56 帧、最大 7 帧**"
 "（分布 `0,0,0,1,1,1,2,2,2,3,3,4,4,5,6,7`）；**帧 432 = +0、帧 464 = +1**（原 +18/+15）；"
 "**唯一 >6 帧仍是帧 367「出现影子」−7**（已定性为标注语义差）；"
 "⑧**遗留**：模拟器 `block` 仍偏早（201/414 vs 标定 236/443）⇒ 敌人的路径/起点或被挡规则待核（D12）；"
 "后半段击杀时刻平均差 ~17.8 帧（最大 46，H1/H2 待判）；逐单位判定体形状/偏移待从 prefab 抽取（D11）；"
 "⑨**文档**：`56_体积与范围五语义_事件关联.md` 增补「用户第二批澄清（两阵营范围表示）」、"
 "3.1/3.2 两侧判据、残余定位与阻挡重校准、**事件关联速查表 + A1~A8 断言表**；"
 "`55_工作前提与五项机制.md` 标准提取项扩到 **18 项**（②拆成我方体积/敌方远程范围，④改为 1.5），清单 B 补 3 条；"
 "`00_结论索引.md` 更新 **A16/A18、B24/B26、D12** 与检索词；"
 "⑩**新增脚本**：`probe_enemy_range.py`、`diag_enemy2_approach.py`、`sweep_block_rule.py`、`sweep_block_cell_margin.py`；"
 "⑪**合规**：仅本地模拟计算、用户提供的数据与客户端**只读**备份；**未触碰游戏文件/内存**。 |"
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
