# -*- coding: utf-8 -*-
"""append_t052_phase.py — 记录"阻挡扫描相位 = 每角色 ticker（随部署帧）"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

parts = [
 '【第110轮】★★★★★**用户提醒的"阻挡扫描相位随部署帧、且因干员而异"已查明机制并实现；无权威来源处标记待补**：',
 '①**用户提醒（采纳）**：「**阻挡扫描帧与干员部署帧高度相关，且不同干员存在差异**。我不了解具体是为什么，'
 '你可以尝试查找，**找不到数据权威来源标记待补**」；',
 '②**★找到机制依据（知识库已有，非我臆测）**：`knowledge/04/33_cpp层战斗类结构与字段速查.md` 记载 —— ',
 '**`m_findBlockeeTicker` 是 `Character` 上的 `PeriodicTicker` 字段（偏移 0x380）**，'
 '配 `FIND_BLOCKEE_TICK = 3`（`knowledge/04/37` §二、`36` 第 6 条）',
 '⇒ **阻挡扫描的计时器属于"每个角色自己"**，相位由其**被创建（部署/出生）的时刻**决定，',
 '**不是全局帧时钟** ⇒ 全局 `frame % 3` 只在"部署帧 ≡ 0 (mod 3)"时才巧合相等，',
 '且**不同干员必然相位不同** —— 与用户观察**完全一致**；',
 '③**实现**（`ak_sim/engine.py`）：新增 `_block_ticker_fires(blocker)`，'
 '`options[\'block_scan_phase\'] ∈ {\'per_unit\'(默认), \'global\'(旧行为,对照)}` 与 '
 '`options[\'block_ticker_phase\'] ∈ {0,1,2}`；判定式 `(frame − 该角色创建帧 − phase) % 3 == 0`；',
 '④**★过程中发现并修正一个真实缺陷**：上一轮为"按格判定判窗过窄"加在**敌人侧的外层全局门**，'
 '与新的**每角色相位**形成**双重门控** ⇒ 实测 `phase=1/2` **永不成立、完全无阻挡**（`[]`）'
 '⇒ 外层门**仅在 `global` 模式保留**，`per_unit` 模式改为每帧调用、由各阻挡者自己的相位决定；',
 '⑤**相位扫描实测（`sim/draft/sweep_block_phase.py`；标定阻挡帧 [236, 443]）**：',
 '`global`/`per_unit phase0` ⇒ [231, 447] 偏差 **(−5, +4)**；`phase1` ⇒ [229, 448] **(−7, +5)**；'
 '`phase2` ⇒ [230, 446] **(−6, +3)** ⇒ **相位确实使阻挡帧移动 ±1~2 帧**，机制成立；'
 '⑥**⇒ 标记待补（依用户指示，无权威来源）**：',
 '**(a)** `PeriodicTicker` 在角色创建时的**初值**、以及"先自增后判定 / 先判定后自增"的顺序 —— '
 '反汇编仅给出字段/偏移与 tick 值，**未见初始化处的证据** ⇒ 以 `block_ticker_phase` 暴露 0/1/2 供后续标定；',
 '**(b)** **"不同干员差异"的成因**（是"创建帧不同"就够，还是存在**职业/阻挡数/体型**等额外修正）'
 ' —— 暂无权威来源；本轮已按"创建帧绑定"实现，但**尚未核实干员的创建帧是否已写入单位属性**'
 '（实测相位基准取到 0 ⇒ 疑似未记录）⇒ **待补**；',
 '**(c)** 与"**位置每 5 帧**（`Enemy.UPDATE_POS_TICK`）""索敌每 3 帧（`SEARCH_TARGET_TICK`）"的**相位关系**'
 '（是否同源或各自独立）—— 待补；',
 '⑦**回归**：`verify_semantics` A1~A9 ✅、`replay_verify5` 16/16、`replay_axis` 18/18（数值同第109轮）；',
 '⑧**合规**：纯本地模拟计算与只读本机资源；未登录、未消耗资源、未读改游戏文件/内存。 |',
]
entry = ''.join(parts)
lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok, len =', len(lines[i]))
