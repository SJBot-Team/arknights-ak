# -*- coding: utf-8 -*-
"""append_t052_semantics.py — 把「五语义分离」一轮的进展追加到 tasks_registry.md 的 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

Q1, Q2 = '\u300c', '\u300d'      # 「 」
entry = (
 "【第61轮】★★★★**依用户指示分离「体积/范围」的五个语义，并把它与事件显式关联**："
 "①**用户约束（原文要点）**：**(a)** 攻击索敌应为**方格范围**；**(b)** 索敌时需考虑**受击判定体积**；"
 "**(c)** 该体积**主要用于索敌**，**不是**用于判断是否被范围攻击命中；"
 "**(d)** 部分范围攻击判定「**目标中心是否位于选定格内**」⇒ 与体积无关；"
 "②**代码层面落地**（`sim/draft/ak_sim/`）：**(a)** `engine.py` 头部新增**五语义对照表**（语义→参数→**关联事件**→代码路径）；"
 "**(b)** 新增 `Battle.is_targetable` 实现 **索敌 = 方格范围 ∪ 受击圆∩范围格**（`point_to_cell_distance` 求点到格最短距离），"
 "并新增 `Battle.cell_square` / `point_to_cell_distance` / `aoe_targets` / `aoe_cells_around`；"
 "**(c)** 索敌成功写事件 **`target_select {unit,target,judge∈{grid,hit_volume,distance_legacy},hit_radius}`** ⇒ 事件与语义显式绑定；"
 "**(d)** `Unit` 新增 **`collider_radius`（①碰撞体积）/ `hit_radius` + `hit_offset`（②受击判定体积，含偏移以容纳胶囊体）**；"
 "**(e)** ④阻挡判定改用 **`block_capture_distance`（默认 1.0）** —— **不是**两个碰撞体积之和（语义不同）；"
 "**(f)** ⑤`_summon_aoe_tick` 改走 `aoe_targets`，**只看目标中心所在格**；"
 "③**新增回归测试 `verify_semantics.py`（6 组断言，全部通过）**：A1 改碰撞半径 5.0 ↛ 索敌/命中/范围不变；"
 "A2 改受击半径 0→1.0 ↛ 阻挡帧不变；A3 改受击半径 → 索敌/命中改变且存在「靠体积」的索敌；"
 "A4 改全体受击半径 3.0 ↛ **AoE 结果不变**（用户第 (d) 点）；A5 改体积 ↛ `cells_in_range` 不变；A6 缩短捕获距离 → 阻挡帧改变；"
 "④**★语义更正确但拟合变差（如实记录，未粉饰）**：新口径默认（`hit_volume_enemy=0.1`，客户端小怪实测）"
 " ⇒ **16/16、平均 4.56 帧、最大 18**；旧口径（中心距 ≤1.5，语义混用）⇒ **16/16、平均 1.81、最大 7**；"
 "细网格扫描 0.00~0.60（步长 0.05）显示**半径越大越差、最优是 0.0（纯方格 3.81）**"
 " ⇒ **「体积」不是当前 1-1 残差缺的那块拼图**；残余**只有 2 条**（帧 432 芬命中猎狗 +18、帧 464 芬击杀猎狗 +15），"
 "定性为「**芬打不到格 (4,4) 上的敌人**」（该格不在她朝左范围 {(3,5),(3,4)} 内；要命中需 `hit_radius ≥ 0.25`，"
 "但把半径提到 0.25 会让**第 1 只被过早索敌**）⇒ **单一全局半径无法同时满足两只敌人的几何**；"
 "**结论：需逐单位从 `enm_pfb_*.ab`/`charpack\\*.ab` 抽「判定体形状+偏移」填入 `hit_radius`/`hit_offset`**（已登记 D11）；"
 "⑤**开关（供用户选择）**：`options={'targeting_model':'legacy_center_distance','range_distance_tol':1.5}` 复现历史 16/16；"
 "`'grid_plus_hit_volume'`（★默认，语义正确）；`'grid_only'` 纯方格；"
 "⑥**副作用改善**：后半段击杀时刻对照的平均偏差由 18.7 帧降到 **13.4 帧**；`verify_skill_cost.py` 仍 −2/−4 帧、费用值一致；"
 "⑦**新增文档 `knowledge/04/56_体积与范围五语义_事件关联.md`**（用户原话 4 点、五语义对照表、三条硬约束、"
 "索敌精确定义、与旧口径的关系与实测对照、残余定位、**事件关联速查表**）；"
 "⑧**更新**：`55_工作前提与五项机制.md`（标准提取项扩到 **17 项**，新增 14~17 碰撞体积/受击体积/阻挡捕获/AoE中心格；清单 B 补 4 条坑）、"
 "`00_结论索引.md`（新增 **A16/A17、B23~B25、D11/D12** 与检索词）；"
 "⑨**新增脚本**：`ak/sim/draft/`：`verify_semantics.py`、`sweep_hit_volume.py`、`fine_sweep_hit_volume.py`、`diag_target_model.py`；"
 "⑩**合规**：仅本地模拟计算与用户提供的数据/客户端只读备份；**未触碰游戏文件/内存**。 |"
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
