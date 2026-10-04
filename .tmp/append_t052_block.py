# -*- coding: utf-8 -*-
"""append_t052_block.py — ★记录"采用知识库权威统一阻挡模型 + 多方核验"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

parts = [
 '【第108轮】★★★★★★**依用户指示改用「统一阻挡模型」（B站专栏 + 代码核验），并清理两处自造 drift；',
 '确认伤害缺口**不在阻挡侧****：',
 '①**用户指示（采纳）**：「**阻挡按玩家常识应当全部统一**，与 **b 站专栏学习结果相同**，'
 '**多方核验**确保**阻挡和阻挡偏移**建模可信」；',
 '②**★知识库本就有权威模型（我此前未采用）** —— `knowledge/04/37_阻挡与阻挡偏移_代码核验.md`（源：B站 cv25694535 + 反汇编）：',
 '**`Consts.BLOCK_RADIUS = 0.7071`（= 0.5√2）、`BLOCK_RADIUS_SQUARE = 0.49999037`；大号 0.8944（√0.8）**；',
 '**判定 = 角色类单位的「中点」与敌人的「中点」距离 ≤ 阻挡半径 ⇒ 可被阻挡；'
 '阻挡半径只存在于角色类单位身上、敌人没有 ⇒ 对全体统一，不存在逐敌差异**；',
 '**扫描节奏 `Character.FIND_BLOCKEE_TICK = 3`（每 3 帧）**，多个可阻挡时取**最近**者；',
 '③**→ 清理两处自造 drift**：**(a)** 把阻挡判据从"按格 margin/capture_distance"（我自造的近似）'
 '改为 **`block_rule=\'radius\'` + `block_radius=0.7071`（默认）**；'
 '**(b)** 把扫描从"**每帧**"（那是为"按格判定判窗过窄"打的补丁）**恢复为每 3 帧** —— '
 '改用半径 0.7071 的**圆盘**后，敌人以 0.95 格/秒穿过该盘约需 44 帧，**3 帧扫描不会再漏**'
 '（保留 `block_scan_every_frame` 作对照开关）；',
 '④**★多方核验结果（统一半径扫描，`sim/draft/sweep_block_radius.py`）**：',
 '**代码常量 0.7071 ⇒ 阻挡帧 [231, 447] vs 标定 [236, 443]，偏差 (−5, +4) ✅**'
 '（远优于此前的按格判定 (−32,−31) 与 margin 0.1 的 (−4,−1) 之外的其它规则）；',
 '扫描 0.5→1.0 的阻挡帧为 [235,459]→[229,446]→[226,442]→[220,434]，**随半径单调**，'
 '0.7071 落在这条**物理合理曲线**上（而非"卡到某个格边界"）⇒ 与专栏/代码结论一致 ✓；',
 '⑤**★关键判定：伤害缺口不在阻挡侧** —— 半径 0.5/0.6/0.65/0.7071/0.75/0.8 的**伤害平均恒为 4.50、最大恒为 25** '
 '⇒ **伤害缺口与阻挡规则无关**，必在**索敌/范围**侧（承接第107轮的 L1-08 与"芬有效范围"线索）；',
 '⑥**全量回归（新默认下全部通过）**：`verify_semantics` A1~A9 ✅（其中"默认阻挡规则"断言已从 '
 '`cell_3x3_round` 改为 **`radius`+0.7071**）、`replay_verify5` 16/16、`replay_axis` 18/18、'
 '`test_slice_fields`/`test_axis_io`/`test_spawn_random`/`test_harmless_enemy` ✅；',
 '⑦**待实现（下一步，用户明确要求）**：**阻挡偏移** —— `BlockBalancer.CalculateBlockOffset`（RVA 0x7C1050）'
 '四步算法（长度延长到 ≥0.5 → 按 0.1/0.4 分档累加修正向量 → 合成 CE 长 0.2 → 长度设回）+ '
 '**0.2s（6 帧）tween 到 F**、F 记为该敌人的「**稳定阻挡位置**」（后续阻挡他人时取 F 而非实时位置）；',
 '⑧**合规**：纯本地模拟计算与只读本机资源；未登录、未消耗资源、未读改游戏文件/内存。 |',
]
entry = ''.join(parts)
lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
