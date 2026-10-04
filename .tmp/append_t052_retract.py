# -*- coding: utf-8 -*-
"""append_t052_retract.py — 记录"猎狗半径 0.8 撤销 + 客户端数据源打通 + 新 OPEN L1-08"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

parts = [
 '【第107轮】★★★★★★**用户否决"猎狗 0.8"并索要可信数据源 → 打通客户端 prefab 读取：',
 '实测猎狗半径就是 0.1，拟合值已撤销；张力回归为真正的 OPEN（L1-08）**：',
 '①**用户意见（采纳）**：「**存在受击半径不同的单位符合玩家认知，但猎狗 0.8 半径的范围与玩家游戏常识不符，'
 '请给出可信的数据来源**」；',
 '②**★打通可信数据源**：新增 **`ak/scripts/read_enemy_colliders.py`** —— '
 '**UnityPy 1.25.3 + 本仓库的 LZ4AK 解压器**（`from ak_lz4ak import decompress_lz4ak` 后注册到 '
 '`CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM]`；'
 '否则报 `Custom compression or unimplemented LZHAM`）直接读客户端 AB；',
 '**实测结果（`E:\\__file\\ak_kb\\client_res\\enm_pfb\\enm_pfb_0.ab`）**：',
 '**`enemy_1000_gopro`（猎狗）= 0.1、`enemy_1000_gopro_2`（猎狗pro）= 0.1、`enemy_1000_gopro_3` = 0.1** '
 '（均为 `CircleCollider2D`，offset (0,0)）⇒ **用户直觉正确，0.8 与客户端数据矛盾**；',
 '③**★撤销拟合值**：`ak/data/derived/enemy_hit_radius.json` 已把三项改为 **0.1**，'
 '并在文件内写明**数据来源（方法/脚本/bundle）**与**撤销说明**：'
 '「0.8 是从**单条标定事件反推的拟合值**，不符常识与实测 ⇒ 撤销；其"改善"属于**用一个错误补偿另一个错误**」；',
 '④**撤销后的诚实状态（无任何拟合参数）**：'
 '`replay_axis` **18/18、≤6 帧 15、平均 4.28、最大 25**；'
 '`replay_verify5` **16/16、≤6 帧 13、平均 4.50、最大 25**；'
 '`verify_semantics` A1~A9 ✅（未受影响）；',
 '⑤**⇒ 张力回归为真正的 OPEN（新增 L1-08）**：在数据可信前提下（受击半径一律 0.1）——',
 '`margin 0.1`（≈"进入阻挡者所在格"）⇒ **阻挡 ✓（[232,442] vs 标定 [236,443]，偏差恒 −4/−1）但伤害 ✗（4.50、最大 25）**；',
 '`margin 1.0 + 吸附` ⇒ 伤害 ✓（2.19）但**阻挡 ✗（−32/−31）**；**必有机制缺失**；',
 '**定量线索（本轮新算）**：真实芬**在真阻挡(443)前约 29 帧（414）就已索敌**猎狗 ⇒ '
 '那一刻敌人在 (x≈4.77, y≈4.87)，**距我方建模的范围格区域（(3,5)+(3,4)）约 0.87 格**'
 ' ⇒ **芬的"有效范围区域"很可能比 2 格更大**（候选：`cells_in_range` 里 range 表的行/列朝向或布局被我们理解错了）；',
 '⑥**分层登记更新（`knowledge/04/60`）**：**L2-02 → ✅ 客户端实测**（猎狗/猎狗pro 均 0.1）；',
 '**L2-03 → ⚠️ 规则已定但与伤害观测冲突**；**新增 L1-08「两观测仍不能同时满足」❌ OPEN**'
 '（候选方向：敌人真实路径/航点、芬的有效范围、阻挡后停位、标定表标注完整性——该表已被证实漏标过一次）；',
 '⑦**合规**：仅只读本机客户端 AB 备份与本地计算；未登录、未消耗资源、未读改运行中游戏的文件或内存。 |',
]
entry = ''.join(parts)
lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
