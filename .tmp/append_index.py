# -*- coding: utf-8 -*-
"""append_index.py — 建立结论索引（任务一：汇总归档两条任务线的已成功成果）。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\00_结论索引.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

MD = '''# 结论索引（可查阅归档）

> **用法**：按主题线检索既有结论，避免重复劳动（对应机制 2）。
> **维护规则**：每产生一条**已验证**的结论，必须在本表登记一行；
> 字段 = `结论 | 关键参数/修正 | 验证方式 | 验证结果 | 证据文件`。
> **约束**：本表只登记**已成功/已验证**的结论；未验证的假设写在专题文档的"待办"里。

---

## A. 模拟环境（任务一）

| # | 结论 | 关键参数 / 修正 | 验证方式 | 验证结果 | 证据文件 |
|---|---|---|---|---|---|
| A1 | **关卡可动态加载**（任意关卡同一套流程） | `Scenario(stage).stage_code`；`row=字母序号−1`、`col=数字−1` | 1-1/12-4/H12-4 加载 + 与 h12-4 的"令 C12→(r2,c11)"互证 | ✅ 一致 | `sim/draft/ak_sim/scenario.py` |
| A2 | **费用经济**：初始费用、上限、每秒 +1、部署按 `attrs.cost` 扣减 | `options.initialCost/maxCost`；`need=int(spec['attrs']['cost'])`；支持 `cost=` 覆盖 | 1-1 标定表逐秒费用对照 | ✅ **0s~13s Δ 全部归零** | `probe_cost_diff.py`、`probe_cost_detail.py` |
| A3 | **★费用 +1 的相位**：应落在"每秒第 0 帧" | 引擎在 `f % 30 == 29` 时增长（`f` 为进入 tick 的帧号） | 逐帧打印费用变化帧 | ✅ 落在 **帧 30/60/90** | `engine.py::tick()` |
| A4 | **单位关联机制必须全量提取**（★教训） | 干员数值 = 基值(阶段插值) → 信赖 → 潜能 → **模组** → 技能黑板 → **天赋**；芬的天赋"部署费用 −1"使其为 **8** 而非 9 | 1-1 标定（标定表自洽：10−8+3=5） | ✅ **确认芬 = 8 费** | `probe_cost_detail.py`、本目录 `55_工作前提与五项机制.md` |
| A5 | **地图格子属性可提取** | `mapData.tiles[tileKey/heightType/buildableType/passableMask]`；`map` 存的是 tiles 索引 | 1-1 渲染 + D6/D4/D1/G5 交叉验证 | ✅ 吻合 | `sim/draft/ak_sim/mapview.py` |
| A6 | **出怪时序可提取** | `waves[].fragments[].actions[]`（SPAWN），`enemyDbRefs[].id` | 1-1 出怪表 vs 事件帧 | ✅ 帧90 spawn 与标定"出现影子@94"差 4 帧 | `ak_sim/scenario.py` |
| A7 | **逐帧切片完整可用** | 顶层 `f/cost/life/ops/units/rng_state/rng_draws`；单位 31 字段（含 `atk/df/res/attack_speed/atk_interval_frames/move_speed/block_cnt/weight/route_index/buffs/talents`） | 字段枚举 + 1-1 实跑 | ✅ | `engine.py::_record_frame` |
| A8 | **事件帧提取与比对框架** | `extract_events/compare_events/to_reference_format` | 1-1 输出 43 条事件、与标定表逐条对照 | ✅ 伤害/出生事件差 **0~5 帧** | `ak_sim/events.py` |
| A9 | **伤害事件帧与实机吻合** | — | 标定表 vs 模拟器事件 | ✅ **帧298 命中 ⇒ damage@298（差 0）**；帧285 ⇒ @286（差1）；帧236 ⇒ @234（差2） | `replay_11calib.py` 输出 |
| A10 | **随机数可控** | 同 seed 多次运行结果完全一致 | 1-1 跑 3 次、1-7 跑 2 次比对 | ✅ 逐位一致 | `ak_sim/run_stage.py` |
| A11 | **关卡自带 randomSeed 可提取** | `level.randomSeed`（1-1=978975386 等） | 批量探明台账 | ✅ | `.tmp/stage_survey.json` |
| A12 | **高速且可并行** | 149× 实时、单帧 0.22ms；4 进程并行 | 1-1 复刻计时 | ✅ **601 帧/0.134s** | `replay_11calib.py` |
| A13 | **1-1 标定对局前半部分已成功复刻** | 帧10 部署芬@(3,5)朝左、帧411 部署月见夜@(3,3)朝上 | 与标定表逐秒/逐事件对照 | ✅ 部署成功、费用归零、事件帧吻合 | `sim/draft/replay_11calib.py` |
| A14 | **多关卡数据可抓取补全** | `code/unpack/fetch_level.py <levelId>` | 抓取第 1 章 12 关 | ✅ 全部成功 | `.tmp/stage_survey.md` |
| A15 | **关卡机制（runes）可提取** | 12-4：`cbuff_max_cost(max_cost=20)`、`enemy_attribute_mul(atk/def×1.2)`、`env_system_new(sightSystem)` | 与既有手工分析比对 | ✅ 吻合 | `ak_sim/scenario.py` |

---

## B. 纯 AI 打图（任务二）

| # | 结论 | 关键参数 / 修正 | 验证方式 | 验证结果 | 证据文件 |
|---|---|---|---|---|---|
| B1 | **费用尺相位识别达帧级** | 官方 `pixel_map` 查表；180px = 30 帧 ⇒ **6px = 1 帧**；采样间隔 **0.5~0.9s** 最佳 | 实机两次测量 + 录像 18 秒跨度 + 离线 300 帧 | ✅ 实机中位 **0.59/0.80 帧**；录像 99.6% ≤2 帧、**无漂移** | `plugins/clock/frame_clock.py` |
| B2 | **实机读数 → 游戏内帧** | `frame_of(cost, tick, initial_cost)` = `(cost−init)×30 + tick` | 与模拟器同帧对照 | ✅ **差异 0 帧** | `plugins/action/deploy.py` |
| B3 | **流速识别可用** | 右上角 ROI (1560,30)-(1720,115)，OCR `eng/psm7` | 战斗中切换倍速 | ✅ 稳定返回 **1X/2X** | `apps/speed_probe.py` |
| B4 | **过帧宏效果 = 真实时间 × 流速** | 云迹 R/T/Y = 12/33/166ms | 三种流速下反复过帧测帧数 | ✅ **1X: T=1.03 帧**；**2X: T=2.08 帧**；子弹时间 ≈0.2 帧 | `apps/speed_probe.py` |
| B5 | **F 键语义 = 按下暂停、松开恢复** | 需 `key_down`/`key_up` 分开控制 | 实测画面停在 PAUSE | ✅ | `plugins/action/win_input.py` |
| B6 | **关卡外流程严格照 MAA 可走通** | `GameStart`→`StartToWakeUp`→`NextAfterLoadingIcon`→`StartUp`；终端/曲谱/乐章收录/章节卡片/关卡节点/演习/编队/开始行动 | 逐界面模板判定 | ✅ **全流程到 1-1 演习战斗** | `apps/maa_wakeup.py`、`knowledge/04/48…` |
| B7 | **章节切换靠"底部相邻章节卡片"**（非滑动） | 乐章总览点章节标签；详情页点左侧卡片逐级后退 | 实测 | ✅ EP15→EP01 成功 | `knowledge/04/48…` §十 |
| B8 | **目标窗口 = 渲染子窗口** | 按标题找 `MuMuPlayer`（`FindWindowEx(PARENT,0,None,"MuMuPlayer")`）；或类名 `nemuwin` | 实测注入生效 | ✅ | `plugins/action/win_input.py` |
| B9 | **注入通道**：本机实测 | `SendMessage`（同步）/`PostMessage`（异步）/真实鼠标（`SetCursorPos`+`SendInput`）三种皆已实现；A/B 对照证明"点选可生效" | 对照实验 | ✅/⚠️ 见专题文档 | `knowledge/04/53…` §十二 |
| B10 | **待部署卡片可动态检测** | 列梯度能量 + 列亮度双通道分段；实测 12 张 ⇒ 10 段，中心 `[100,275,458,627,801,980,1136,1352,1644,1858]` | 可视化红框比对 | ✅ 与画面吻合 | `apps/card_probe.py` |
| B11 | **绿色可部署格可检测** | HSV (33,55,55)-(95,255,255)；★**只在暂停态出现**；可按 `cell_px≈130` 切分为格子单元 | 暂停态点卡片后检测 | ✅ 稳定返回 2~3 格 | `plugins/action/deploy.py` |
| B12 | **暂停可可靠确认** | `ensure_paused()`：先判界面为 battle，再用"两次读数（费用+相位）不变"确认 | 实机多次 | ✅ | `plugins/action/deploy.py` |
| B13 | **实机 ↔ 模拟器帧级对照首次成功** | 实机 `cost=15,tick=21` ⇒ 帧 **171**；模拟器同帧 | 同一判据下部署 | ✅ **差异 0 帧、费用 Δ 一致** | `sim/draft/ak_sim/compare_deploy.py` |
| B14 | **轴表自带 PRTS+ 计时列** | 「作战记录」的 `费用/帧数/绝对时间`；精确时刻 = `time + tick/30` | 与模拟器逐条比对 | ✅ 令 1.50s、蕾缪安 20.00s | `sim/draft/dump_cyberplastic_timing.py` |
| B15 | **PRTS+ 已开源** | `github.com/jue-ce-zhe/prts-plus`（`src/mumu` 输入、`src/logic` 部署、`src/config.py` 常量）；常量 `BULLET_THRESHOLD=15`、`FRAME_THRESHOLD=2`、`FRAME_WAITTIME=0.1`、`TICK_MAX=30` | 源码阅读 + 与其运行日志互证 | ✅ | `knowledge/04/53…` |
| B16 | **云迹键鼠宏参数可提取** | F=时停（按下暂停/松开恢复）、W=划火柴、S=0帧选取、E=卡帧对轴；暂停按钮 rel(0.94,0.07) | 解析 `keymapConfig/*.json` | ✅ | `apps/speed_probe.py`、`knowledge/04/51…` |

---

## C. 二者互验（任务线三）

| # | 结论 | 验证方式 | 验证结果 | 证据文件 |
|---|---|---|---|---|
| C1 | **实机"费用+相位"与模拟器"逐帧切片"是同一条时间轴** | 同一操作在两端的时刻换算 | ✅ 差异 0 帧 | `compare_deploy.py` |
| C2 | **标定表可直接作为模拟器的对照基准** | 1-1 标定表的"该秒初始费用"与账本自洽 | ✅ 逐秒吻合（修正相位与芬费用后 Δ=0） | `knowledge/04/54…` |
| C3 | **模拟器的伤害/出生事件帧与实机吻合 0~5 帧** | 1-1 标定表 vs `extract_events` | ✅ 其中一条差 **0 帧** | `replay_11calib.py` |

---

## D. 待办（尚未验证，勿当作结论）

| # | 待办 | 现状 |
|---|---|---|
| D1 | **部署动作在实机上的稳定复现** | 点选可稳定触发（绿格出现），但"落格提交"未成功；已排除输入通道问题 |
| D2 | **1-1 标定视频后半部分的图像识别比对**（用户工作流第 3 步） | 未开始 |
| D3 | **0 帧选中 / 开局 0 帧暂停的宏应用**（用户指出这两项仍需宏且重要） | 未开始 |
| D4 | **`Y`(166ms) 在非子弹时间下无变化的原因** | 待查 |
| D5 | **h12-4 / 弧光7 / 净尘7 的帧级对齐** | 等用户提供精确素材 |

---

## 检索词速查

- 坐标映射 / 行序 / D6 / (row, col) → A1、A5
- 费用 / 相位 / 30n / 扣费 / 潜能 → A2、A3、A4
- 天赋 / 模组 / 单位机制 → A4、机制 5
- 切片 / 字段 / move_speed → A7
- 事件帧 / spawn / damage → A8、A9、C3
- 随机数 / seed → A10、A11
- 效率 / 并行 → A12
- 费用尺 / 相位 / pixel_map → B1、B2
- 倍速 / 过帧 / 宏 → B3、B4、B6
- 窗口 / 注入 / SendMessage → B8、B9
- 卡片 / 绿格 / 暂停确认 → B10、B11、B12
- PRTS+ / 云迹 / MAA → B15、B16、B6
'''

io.open(DOC, 'w', encoding='utf-8').write(MD)
print('已写出结论索引:', DOC)

ADD = (' **★任务一：建立结论索引（汇总归档两条任务线的已成功成果）2026-09-15**：'
       '①**新建 `knowledge/04/00_结论索引.md`**，按四条线归档：'
       '**A 模拟环境 15 条**（关卡动态加载、费用经济与相位修正、**单位关联机制必须全量提取（芬=8费的教训）**、'
       '地图属性、出怪时序、逐帧切片 31 字段、事件帧框架、伤害事件帧吻合、随机数可控、关卡 randomSeed、'
       '149× 实时、1-1 标定复刻成功、多关卡抓取、关卡机制 runes）；'
       '**B 打图 16 条**（费用尺帧级精度三重验证、实机读数→游戏内帧、流速识别、'
       '**过帧宏效果=真实时间×流速**（1X:T=1.03、2X:T=2.08 帧）、F 键按下/松开语义、'
       '**关卡外严格照 MAA 走通到 1-1 演习**、章节切换靠卡片、目标窗口=渲染子窗口、三种注入通道、'
       '卡片动态检测、绿格检测（仅暂停态出现）、暂停可靠确认、**实机↔模拟器帧级对照差异 0 帧**、'
       '轴表自带 PRTS+ 计时列、**PRTS+ 已开源**及其常量、云迹宏参数）；'
       '**C 二者互验 3 条**（同一时间轴、标定表可作对照基准、伤害事件帧吻合 0~5 帧）；'
       '**D 待办 5 条**（部署落格复现、视频后半图像识别、0帧选中/开局0帧暂停宏、Y 宏待查、'
       'h12-4/弧光/净尘帧级对齐）；'
       '②每条含**结论 / 关键参数·修正 / 验证方式 / 验证结果 / 证据文件**五要素，并附**检索词速查**；'
       '③**维护规则**：每产生一条已验证结论必须登记；未验证的假设只写在专题文档待办中；'
       '④**合规**：仅文档整理；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
os.makedirs(os.path.join(DST, 'knowledge', '04_数据对应与核验'), exist_ok=True)
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
