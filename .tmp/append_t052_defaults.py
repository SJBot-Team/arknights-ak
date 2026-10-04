# -*- coding: utf-8 -*-
"""append_t052_defaults.py — ★记录"新默认配置固化 + 18/18 全部 ≤7 帧"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

parts = [
 '【第106轮】★★★★★★**把突破固化为默认：`replay_axis` 由 18/18（含 −31/−32 两条阻挡）改善为 '
 '「18/18 且**全部 ≤7 帧**」**：',
 '①**默认值修正（`ak_sim/engine.py`）**：',
 '**(a)** `BLOCK_CELL_MARGIN_DEFAULT` **1.0 → 0.1**（附实测依据注释：margin 1.0 偏差恒 −32/−31；'
 'margin 0.1 偏差恒 −4/−1）；',
 '**(b)** `block_snap` 默认 **True → False**（吸附属"用错误补偿错误"，应去掉）；',
 '**(c)** 新增 **`ak/data/derived/enemy_hit_radius.json`（逐敌受击判定半径表）**：'
 '1-1 的 `enemy_1000_gopro`(**猎狗**) = **0.8**、`enemy_1000_gopro_2`(**猎狗pro**) = 0.1；'
 '引擎启动时由 `_load_enemy_hit_radius()` 读入；',
 '**(d)** 优先级明确为 **显式全局 `hit_radius`/`hit_volume_enemy`（诊断覆盖）> 逐敌表 > 默认 0.1**；',
 '②**过程中自查出并修正的两个"遮蔽"缺陷**：',
 '**(i)** 首版 `hit_radius_by_key` **根本没接进引擎**（`self.hit_radius_by_key` 未被赋值）⇒ '
 '扫描显示"半径完全无影响"；',
 '**(ii)** 接进后**逐敌表遮蔽了全局诊断键** ⇒ `verify_semantics` 的 A3「受击半径影响索敌时刻」失败；'
 '且全局键有**两个历史别名**（`hit_radius` 与 `hit_volume_enemy`），需都认；已修 → A1~A9 全部通过；',
 '③**★新默认下的全量结果**：',
 '**`replay_axis`：18/18 可对齐、≤6 帧 **17** 条、平均 **2.44**、最大 **7**（偏差分布 '
 '0,0,1,1,1,1,1,2,2,2,2,3,3,4,4,4,6,7）** —— **此前两条阻挡事件 −31/−32 的离群已消失**；',
 '**`replay_verify5`：16/16、≤6 帧 15、平均 2.44、最大 7**；',
 '`verify_semantics` A1~A9 ✅、`test_slice_fields` ✅、`test_axis_io` ✅、`test_spawn_random` ✅、'
 '`test_harmless_enemy` ✅；打图侧（暂停中）`test_axis_runner` ✅、`test_same_frame` ✅（未受影响）；',
 '④**⇒ 分层登记的对应变化**：**L2-03（阻挡判据）✅ 已定**、**L2-02（受击体积）⚠️ 已发现逐敌不同**、',
 '**L1-03（敌人路径）⚠️ 已大幅回收**（原判"校验停在此处"不再成立）；',
 '⑤**残留 OPEN**：逐敌半径表的**客户端来源校正**（需 `UnityPy` 解析 `battle/enm_pfb_N.ab` 的 '
 '`CircleCollider2D.m_Radius`）；以及 L1-05/06、L2-07、L3-01/05、L4-02/04、L5-02、L6-02；',
 '⑥**合规**：纯本地模拟计算与只读本机资源；未登录、未消耗资源、未读改游戏文件/内存。 |',
]
entry = ''.join(parts)
lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
