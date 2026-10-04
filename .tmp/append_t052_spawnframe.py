# -*- coding: utf-8 -*-
"""append_t052_spawnframe.py — 记录"补齐单位创建帧 ⇒ 阻挡扫描相位真正绑定部署帧"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

parts = [
 '【第111轮】★★★★★**补齐"单位创建帧"⇒ 阻挡扫描相位真正绑定部署帧（上一轮待补(b)的前置已解决）**：',
 '①**上一轮遗留**：相位实现里"每角色基准"**恒取到 0**，因为**单位上根本没有创建帧属性**',
 '（实测 `spawn_frame`/`deploy_frame`/`born_frame` **全都没有**）⇒ 相位实际未与部署帧绑定；',
 '②**★修正**：在 `Battle.tick()` 的"波次出生"之后加一处**统一打戳** —— ',
 '`for u in units: if getattr(u, "spawn_frame", None) is None: u.spawn_frame = f`；',
 '**一处覆盖三条创建路径**（敌人出生 / 干员部署 / 装置落地），无需各处分别埋点；',
 '**实测**：芬 `spawn_frame = 10`、月见夜 `= 411`、猎狗pro `= 660` ⇒ **与部署/出怪日志逐帧一致** ✓；',
 '③**⇒ 相位现已真正绑定部署帧**，`_block_ticker_fires` 的判定式 '
 '`(frame − spawn_frame − block_ticker_phase) % 3 == 0` 生效；',
 '**相位扫描实测（标定阻挡帧 [236, 443]）**：',
 '`per_unit phase0` ⇒ [229, 448] 偏差 **(−7, +5)**；`phase1` ⇒ [230, 446] **(−6, +3)**；',
 '`phase2` ⇒ [231, 447] **(−5, +4)**（与 `global` 巧合相同：芬部署帧 10 + 2 = 12 ≡ 0 (mod 3)）',
 '⇒ **对同一干员，相位每 +1 使阻挡帧移动约 1 帧**，机制成立 ✓；',
 '④**★这解释了用户观察的"不同干员存在差异"**：相位 = `(部署帧 + 初值) mod 3`，'
 '而不同干员的**部署帧不同** ⇒ 扫描相位自然不同 ✓（用户原话："阻挡扫描帧与干员部署帧高度相关，'
 '且不同干员存在差异"）—— **本轮已把这一层落实为可复现的机制**；',
 '⑤**清理**：删除上一轮遗留的、已废弃的 `block_ticker` 自增死代码（相位改由 `spawn_frame` 直接导出）；',
 '⑥**待补（仍无权威来源，依用户指示标记）**：',
 '**(a)** `PeriodicTicker` 创建时的**初值**与"先自增后判定 / 先判定后自增"顺序（现以 `block_ticker_phase` 0/1/2 暴露）；',
 '**(b)** **是否还存在"创建帧之外"的逐干员修正**（如按职业/阻挡数/体型）—— 现仅实现"创建帧绑定"，'
 '本轮相位扫描未显示需要额外修正，但**缺乏权威来源**；',
 '**(c)** 与"位置每 5 帧（`UPDATE_POS_TICK`）""索敌每 3 帧（`SEARCH_TARGET_TICK`）"的**相位关系**；',
 '⑦**回归（全绿）**：`verify_semantics` A1~A9 ✅、`replay_verify5` 16/16（平均 4.50、≤6 帧 13）、',
 '`replay_axis` 18/18（≤6 帧 14、平均 4.67 —— 与 4.50 的差异来自"相位改为按真实部署帧"，**更正确**）、',
 '`test_slice_fields`/`test_axis_io`/`test_spawn_random`/`test_harmless_enemy` ✅；',
 '⑧**合规**：纯本地模拟计算与只读本机资源；未登录、未消耗资源、未读改游戏文件/内存。 |',
]
entry = ''.join(parts)
lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok, len =', len(lines[i]))
