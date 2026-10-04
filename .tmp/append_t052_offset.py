# -*- coding: utf-8 -*-
"""append_t052_offset.py — 记录"阻挡偏移实现 + 环境变更登记"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')

# --- 1) 任务台账 ---
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

parts = [
 '【第109轮】★★★★★**实现文档化「阻挡偏移」（`CalculateBlockOffset`）并修正两处接线缺陷**：',
 '①**实现**（`ak_sim/engine.py`）：新增 `_block_offset()`（逐字对应 `knowledge/04/37` §三 四步算法：',
 '①长度延长到 ≥0.5 →②按 `d<0.1`（取 `rot90CW(A→D)`）/`0.1≤d<0.4`（取 `(0.4−d)×50×normalize(D−C)`）',
 '分档累加修正向量 →③`CE=normalize(corr)×0.2`、`AF=normalize(AE)×|AC|` →④`F=A+AF`）、',
 '`_start_block_tween()`（**0.2s = 6 帧**强制移动到 F，F 记为该敌人的**稳定阻挡位置** `stable_block_pos`）、',
 '`_step_block_tween()`（逐帧推进）；',
 '**常量**：`BLOCK_OFFSET_MIN_DIST=1e-5`（中点重合则不偏移）、`BLOCK_OFFSET_MIN_LEN=0.5`、`BLOCK_TWEEN_FRAMES=6`；',
 '**模式**：`block_offset_mode` 默认 **`\'code\'`**（文档化），`\'cell_center\'` 保留旧自造"吸附到相邻格中心"作对照；',
 '②**修正两处接线缺陷**：**(a)** `block_offset_mode` **没接进实例**（`getattr(self,…)` 恒取默认 ⇒ '
 '三种模式跑同一条路径）；**(b)** tween 期间**提前 `return` 会跳过攻击冷却递减**，'
 '实测使伤害偏差由 4.50 漂到 4.62 ⇒ 改为"接管位置但不跳过本帧其余结算"；',
 '③**1-1 实测（`sim/draft/test_block_offset.py`）**：`code` 模式记录 **`block_offset` 事件（dist = 0.0）** —— '
 '**这是算法的正确结果**：单一阻挡者、`|AB| ≈ 0.7071 ≥ 0.5` 且无"同被 A 阻挡的其它敌人"拥挤时，',
 '算法**只改方向、不改距离** ⇒ **F = B、偏移为 0**；⇒ **偏移的可见效应出现在"多敌挤位"场景**，1-1 不产生差异；',
 '④**回归（全绿）**：`verify_semantics` A1~A9 ✅、`replay_verify5` 16/16（平均 4.50、≤6 帧 13、最大 25）、',
 '`replay_axis` 18/18（≤6 帧 15、最大 25）；**阻挡帧 [231,447] 偏差 (−5,+4)** 维持权威规则结果；',
 '⑤**结论**：**伤害缺口（4.50/最大 25）确在索敌/范围侧**，与阻挡判据、阻挡偏移均无关'
 '（半径 0.5~0.8 伤害恒 4.50；三种偏移模式伤害恒 4.50）⇒ 下一轮转向 **L1-08：芬的有效范围/范围表朝向**；',
 '⑥**环境变更（按管理规则登记）**：本会话新装 **`UnityPy 1.25.3`**（用于只读解析客户端 AB；',
 '配合本仓库 `scripts/ak_lz4ak.py` 的 LZ4AK 解压器）⇒ 已登记 `management/environment_change_log.md`；',
 '⑦**合规**：纯本地模拟计算与只读本机资源；未登录、未消耗资源、未读改游戏文件/内存。 |',
]
entry = ''.join(parts)
lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('tasks_registry ok, len =', len(lines[i]))

# --- 2) 环境变更日志 ---
p2 = r'C:\Users\23922\Documents\ds_harness\management\environment_change_log.md'
try:
    s2 = open(p2, encoding='utf-8').read()
except FileNotFoundError:
    s2 = '# 环境变更日志\n\n| 时间 | 变更前 | 变更后 | 原因 | 验证 |\n|---|---|---|---|---|\n'
line = ('| 2026-09-15 | 无 UnityPy（默认 python 与 vision venv 均无） | '
        '**UnityPy 1.25.3**（默认 python，`pip install UnityPy`） | '
        '只读解析客户端 AB（`enm_pfb_N.ab`）以取得**逐敌碰撞半径**这一可信数据源 | '
        '`scripts/read_enemy_colliders.py` 成功读出 `enemy_1000_gopro*` 半径=0.1 |')
if 'UnityPy 1.25.3' not in s2:
    s2 = s2.rstrip('\n') + '\n' + line + '\n'
    open(p2, 'w', encoding='utf-8').write(s2)
    print('environment_change_log ok')
else:
    print('environment_change_log 已含该条，跳过')
