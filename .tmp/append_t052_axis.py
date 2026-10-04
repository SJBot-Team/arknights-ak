# -*- coding: utf-8 -*-
"""append_t052_axis.py — 追加"共用轴表落地"一轮到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第67轮】★★★★**落地「与模拟共用易读易改的轴表」（模拟器 / 打图端 / 校验器三方同一份）**：'
 '①**用户需求对应**：目标②要求「与模拟**共用易读易改的轴表**」，目标③要求"以事件精确帧为判定口径"；'
 '本轮把两者合并为一个可执行产物；'
 '②**新建 `ak/axis/1-1.yaml`（唯一事实来源）**：段 = `stage` / `level`（初始费用·费用间隔·moveMultiplier·'
 'maxLife·charLimit·randomSeed）/ `squad`（含练度与 `cost_override`，如芬 8 费）/ '
 '**`deploys`（执行序列：`at:{frame|sec}` + `op` + `cell`(标定记法 D6→(3,5)) + `dir` + `cost`）** / '
 '**`expect`（校验用期望事件：`kind∈spawn|dmg|kill|block` + `victim` + `src` + 可选显式 `n`）** / '
 '**`video_axis`（视频帧↔游戏帧：来源、逐帧表路径、4 个硬锚点）**；'
 '并附 `ak/axis/README.md`（格式说明 + 三方用法 + 新增轴表步骤）；'
 '③**新建 `sim/draft/axis_io.py`**：`load_axis` / `at_to_frame`（frame|sec）/ `cells_letter_to_rc` / '
 '`axis_to_deploy_plan`（→模拟器与打图端共用的部署计划）/ `axis_expect_table`（★支持**显式 `n`**，'
 '处理"该组更早还有未标注事件"，如 1-1 帧 461 实为第 1 次）/ `video_to_game`（锚点或逐帧查表）/ '
 '**`axis_to_runner_ops` + `axis_to_derived`（→打图端执行器格式）**；'
 '④**新建 `sim/draft/replay_axis.py`**：**按轴表复刻并逐条校验**（不再把部署与对应表硬编码在脚本里），'
 '并把 `block` 事件纳入索引（`extract_events` 不含，改从 `Battle.logs` 取）；'
 '**结果：18/18 可对齐**，其中 16 条伤害/出生/击杀与 `replay_verify5` **完全一致**（平均 2.19、≤6帧 15、最大 7），'
 '2 条 `block` 偏差 −31/−32（★恒定偏移，即 D14）；'
 '⑤**新建 `sim/draft/axis_to_runner.py`（打图端桥接）**：YAML → `ak/data/derived/axis_1-1.json`，'
 '结构 `{level,timebase,seed,meta,ops}` 与打图端既有派生轴表'
 '（`data/derived/axis_h12-4_cyberplastic.json`）**同构**，'
 '`ops` 项 = `{op,unit,coord,dir,cost,frame,abs_seconds}` ⇒ '
 '**打图端只需把 `configs/axis_*.json` 的 `axis_runner.axis` 指过去，即可跑与模拟器同一份轴**；'
 '⑥**新增 `sim/draft/test_axis_io.py`（20 项断言，全通过）**：载入与字段齐全、部署计划与标定逐项一致'
 '（帧10 芬@(3,5)左8费 / 帧411 月见夜@(3,3)上14费）、18 条期望事件且类别覆盖四类、'
 '**显式 `n` 生效**、4 个视频锚点还原正确、**两次载入计划一致（同一事实来源）**、打图端桥接字段齐全且 `abs_seconds=frame/30`；'
 '⑦**同步回归**：`replay_verify5` 仍 16/16、平均 2.19；`verify_semantics` A1~A9 全通过；'
 '`test_spawn_random` / `test_harmless_enemy` 全通过；效率 149× 实时；'
 '⑧**文档**：`00_结论索引.md` 新增 **B29/B30** 与检索词；`outputs_inventory.md` 登记"共用轴表"成果；'
 '⑨**合规**：仅本地文件读写与模拟计算；**未触碰游戏文件/内存**，未执行任何实机注入。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
