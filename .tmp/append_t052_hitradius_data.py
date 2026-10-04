# -*- coding: utf-8 -*-
"""append_t052_hitradius_data.py — 记录"引擎接入客户端实测逐敌半径 + 缓存"。"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = io.open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
parts = [
 '【第118轮】★★★★**引擎接入"客户端实测逐敌受击半径"（含模块级缓存），语义②从此有实测底座**：',
 '①**`ak_sim/engine.py::_load_enemy_hit_radius()` 重写**：来源优先级 '
 '**①`data/derived/enemy_hit_radius.json`（人工/标定校正）> ②`data/derived/enemy_colliders.json`'
 '（客户端 prefab 实测，2123 个敌人）**；并加**模块级缓存**（首次 0.006s / 后续 0.000008s，'
 '避免每场战斗重复读 549KB JSON）；',
 '②**实测载入 2100 条逐敌半径**；1-1 的 `enemy_1000_gopro` 与 `enemy_1000_gopro_2` 均为 **0.1** ✅'
 '（与客户端数据一致 ⇒ 也再次确认"0.8 拟合值"是错的）；',
 '③**语义注释同步强化**：明确该半径是**受击判定体积**（`CircleCollider2D`, `is_trigger=True`），'
 '**不是碰撞体积**；阻挡判据用干员侧 `Consts.BLOCK_RADIUS = 0.7071`（见 `BLOCK_RADIUS_DEFAULT`）'
 '—— 两者分属文件头部对照表的 ② 与 ④，**不得混用**；',
 '④**回归（全绿，数值不变）**：`verify_semantics` A1~A9 ✅、`replay_verify5` 16/16、`replay_axis` 18/18；',
 '⑤**合规**：纯本地模拟计算与只读本机数据文件；未登录、未消耗资源、未读改游戏文件/内存。 |',
]
entry = ''.join(parts)
lines[i] = row[:-1] + entry
io.open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('第118轮已写入, len =', len(lines[i]))
