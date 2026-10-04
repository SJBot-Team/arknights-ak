# -*- coding: utf-8 -*-
"""append_round71.py — 第 71 轮：★实运行 PRTS+，现场验证"费用封顶使其计时器卡死"。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''
### 7.175 【★★★现场验证】实运行赛博塑料：**费用封顶使其计时器卡死 ⇒ 战斗失败**

用户切换好界面并授权后，我选择"让赛博塑料自己进关"（`--autoenter`），
用副本轴表 `D:\\__soft\\ak\\prts_plan_h124.xlsm` 运行（**当时游戏处于"演习"的编队界面**，
`BattleStartExercise` 匹配度 1.0 ⇒ 零理智风险）。

#### (1) 它的内部时间表示被完整读到
```
WARNING - Game time mismatch, performed action at GameTime(cost=11, tick=21, time=1)
          instead of GameTime(cost=11, tick=15, time=1)
WARNING - Performed action: Action(cost=11, tick=15, time=1, action_type=DEPLOY,
          oper='令', pos='C12', direction=UP, tile_pos=(11,6), ...) (not on time)
```
⇒ **它用 `GameTime(cost, tick, time)` 表示时刻**＝「**费用 + 费用条相位 tick + 秒 time**」，
**与我们的方法完全同构**（费用数字 + 相位）；
而且它**自带"时间不匹配"检测**：期望 `tick=15`、实际读到 `tick=21`（差 6 帧）并标记 `not on time`。

#### (2) ★现象：费用封顶 ⇒ 它卡死
- 它成功进关并**部署了令**（第 1 条）✓；
- 随后**卡在第 2 条**（蕾缪安要求 `time=20, tick=0`）；
- 而 H12-4 **上限仅 20，约 t=10s 费用即满** ⇒ 我们的图像识别同一时刻读到
  **费用 20、费用条填充恒 180px、tick 恒 29**（条完全静止）；
- ⇒ **它等不到 `tick=0`** ⇒ 计时停住、流程卡死 ⇒ 敌人漏光 ⇒ 画面出现
  **「任务失败 / MISSION FAILED」**；
- Excel 的 `中转站` 同时显示 `当前状态=停止中`、`当前操作=2`、
  `报错信息=错误：无法识别当前费用。`。

#### (3) 结论（对用户说法的现场印证）
> "费用满后费用跳停止跳动，游戏时间流逝，但赛博塑料计时器停止，直到费用下次开始流动。"

**本轮实运行完全复现了这句话**：封顶期间它的 `tick` 停住、流程停住，而游戏时间继续走
⇒ 在"费用必然封顶"的关卡（H12-4 上限 20）里，**它无法自行推进**。
这也解释了用户为何要专门研究"费用满"的计时问题 —— 以及**我们的方案（§7.120 的上限锚点）为何必要**：
用 `cost_cap_up`（箱子被摧毁 / 平民进点）的精确帧作锚点，才能在封顶后**重新对齐时间轴**。

#### (4) 附带确认的机制
- PRTS+ 抓的是 **render_wnd（7801904）**，与我们一致；
- 它把动作细节（含 `tile_pos`、`avatar_pos`、朝向）写进日志 ⇒ 可作为**它的"事件帧"来源**；
- 轴表的 `绝对时间/帧数` 列不会在运行时实时更新（本次运行后仍为计划值）⇒
  **要拿它的实时计时，读日志比读 Excel 更快**。

### 7.176 本次运行的合规说明
全程在**演习**中运行（编队界面 `BattleStartExercise` 1.0 证实），**未消耗理智**；
它在演习中把这一局打到判负，属演习的正常结果。
'''

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.174 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, SEC + '\n### 7.177 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.175/§7.176')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第七十一轮（★实运行 PRTS+：现场验证"费用封顶使其计时器卡死"）**：'
       '①用户授权后我选择"让它自己进关"（`--autoenter`），用副本轴表在**演习的编队界面**启动'
       '（`BattleStartExercise` 1.0 证实 ⇒ 零理智风险）；'
       '②**读到它的内部时间表示**：`GameTime(cost, tick, time)` = 「费用 + 费用条相位 + 秒」，'
       '**与我们的方法完全同构**；且它自带"时间不匹配"检测——日志报期望 `tick=15`、实际 `tick=21`（差 6 帧）并标 `not on time`；'
       '③**★现场验证用户说法**：它成功进关并**部署了令**，随后**卡在第 2 条**（蕾缪安要求 `time=20, tick=0`），'
       '而 H12-4 **上限仅 20、约 t=10s 费用即满** ⇒ 我方图像识别同时读到 **费用20/填充恒180px/tick 恒 29**（条静止）'
       '⇒ **它等不到 tick=0，计时停住、流程卡死** ⇒ 敌人漏光 ⇒ 画面 **「任务失败」**；'
       'Excel `中转站` 同时显示 `停止中 / 当前操作=2 / 错误：无法识别当前费用。`；'
       '⇒ **完全复现"费用满后条停跳、游戏时间流逝而它计时器停止"**，也解释了我们方案（§7.120 上限锚点）的必要性；'
       '④**附带确认**：它抓 **render_wnd(7801904)**（与我们一致）；动作细节（`tile_pos`/`avatar_pos`/朝向）写入日志 '
       '⇒ 可作"它的事件帧"来源；轴表的 `绝对时间/帧数` **运行时不会实时更新** ⇒ 要它的实时计时**读日志更快**；'
       '⑤**合规**：全程在演习中运行，**未消耗理智**；'
       '⑥已完成收尾：终止该进程，未留下后台任务。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第七十一轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
