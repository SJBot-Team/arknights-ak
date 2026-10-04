# 共用轴表（Axis Table）—— 模拟器 / 打图端 / 校验器**共用同一份**

> 依据用户需求：「与模拟**共用易读易改的轴表**」「以事件发生的**精确帧**作为模拟准确性的判定口径」。
> 本目录是**唯一事实来源**：改一份 YAML，三方同时生效。

## 一、文件

| 文件 | 说明 |
|---|---|
| `1-1.yaml` | 1-1 标定对局（用户标定表 + 视频轴锚点） |
| `README.md` | 本文件（格式说明） |

## 二、格式（`1-1.yaml` 即范例）

```yaml
stage: "1-1"                     # 关卡代号（Scenario 会解析出 stage_code）
level:                           # 关卡参数（仅作记录，真实值仍由关卡数据读取）
  initial_cost / cost_interval / move_multiplier / max_life / char_limit / random_seed
squad:                           # 编队与练度（★"全量辨明关联机制"的落点）
  - {id: char_123_fang, name: 芬, elite: 2, level: 90, potential: 6, trust: 200,
     skill_index: 0, skill_level: 7, cost_override: 8}
deploys:                         # ★执行器（打图端 / 模拟器）共用的操作序列
  - {at: {frame: 10}, op: 芬, cell: D6, dir: 左, cost: 8}
expect:                          # ★校验器用的期望事件
  - {frame: 221, kind: dmg, victim: 猎狗pro, src: 芬, note: 芬 命中}
video_axis:                      # ★视频帧 ↔ 游戏帧（打图端对轴用）
  source: "...mp4"
  full_dump: "ak/.tmp/axis_full.jsonl"     # 逐帧表
  anchors: [{video: 621, game: 10, basis: "部署芬"}, ...]
```

### 字段约定
- **帧号一律是"游戏帧"**：进入游戏第一帧 = 0；1 秒 = 30 帧。
- `at:` 可写 `{frame: N}` 或 `{sec: X}`（frame 优先）。
- `cell:` 用标定表记法：**字母 = row+1、数字 = col+1**（`D6` ⇒ row 3, col 5）。
- ★★**两套费用语义，勿混**：

  | 字段 | 含义 | 谁用 |
  |---|---|---|
  | `cost` | **该干员的部署费用**（芬 8 = 天赋−1 + 潜能−2） | 模拟器扣费 / 费用记账 |
  | `cost_anchor` | **该时刻 HUD 的显示费用**（取自标定表/录像，如帧 10 → 10、帧 411 → 15） | **打图端费用锚点** |

  > 打图端 `run_axis.py` 的 `ops[].cost` 是**费用锚点**（显示费用），不是单位费用；
  > 单位费用由配置的 `unit_costs` 提供。桥接脚本 `axis_to_runner.py` 会自动把 `cost_anchor`
  > 写成打图端的 `cost`，并把 `frame % 30` 写成 `foff`（费用内帧相位）。
  > 实测反推：`帧 = (显示费用 − 初始费用 + 净累计消耗) × 30 + foff`
  > ⇒ 芬 `(10−10+0)×30+10 = 10`、月见夜 `(15−10+8)×30+21 = 411`，与轴表**逐帧一致**。

- `kind ∈ {spawn, dmg, kill, block}`；定位键 = `(kind, victim, src)`。
- `n:`（可选）显式指定"该键下第几次"；**不写则自动累计**。
  ★用于"该组更早还有未标注事件"的情形（如 1-1 的 461 猎狗命中芬，第 0 次在帧 418 未标注）。

## 三、三方如何使用（`sim/draft/axis_io.py`）

```python
from axis_io import load_axis, axis_to_deploy_plan, axis_expect_table, video_to_game

ax    = load_axis('1-1')
plan  = axis_to_deploy_plan(ax)     # {帧: [(干员id, (row,col), 方向, 费用)]}   ← 模拟器 / 打图端
table = axis_expect_table(ax)       # [{'frame','kind','victim','src','n'}]      ← 校验器
gf    = video_to_game(ax, 621)      # 视频帧 → 游戏帧（有 full_dump 时查表最准） ← 打图端
```

| 使用方 | 用哪些段 | 入口 |
|---|---|---|
| **模拟器** | `squad` + `deploys` | `sim/draft/replay_axis.py` |
| **打图端** | `squad` + `deploys` + `video_axis` | 先 `python sim/draft/axis_to_runner.py 1-1` 生成派生轴表 JSON ⇒ `code/vision/apps/run_axis.py`（`axis_runner.axis` 指向它） |
| **校验器** | `expect` | `sim/draft/replay_axis.py`（逐条偏差统计） |

### 打图端桥接（同一份 YAML → 执行器格式）

```powershell
cd ak\sim\draft
python axis_to_runner.py 1-1         # → ak/data/derived/axis_1-1.json（{level,timebase,seed,meta,ops}）
```
生成的 `ops` 与打图端既有派生轴表（`data/derived/axis_h12-4_cyberplastic.json`）**同构**：
```json
{"op":"deploy","unit":"芬","coord":"D6","dir":"左","cost":8,"frame":10,"abs_seconds":0.333}
```
⇒ 打图端只需把 `configs/axis_*.json` 的 `axis_runner.axis` 指向新文件，即可执行**与模拟器同一份轴**。

## 四、跑一遍

```powershell
# ① 模拟器/校验器：按轴表复刻 1-1 并逐条校验
cd ak\sim\draft
python replay_axis.py

# ② 打图端：共用轴表 → 执行器派生轴表，并用执行器**干跑**（不注入任何输入）
python axis_to_runner.py 1-1
cd ..\code\vision
& '.\.venv\Scripts\python.exe' -X utf8 apps\test_axis_runner.py
```

**当前结果**（2026-09-15）：

| 侧 | 结果 |
|---|---|
| **模拟器/校验器**（`replay_axis.py`） | 18/18 可对齐；16 条伤害/出生/击杀 **平均 2.19 帧、最大 7 帧**；2 条 `block` 偏差 −31/−32（★恒定偏移，登记 D14） |
| **打图端**（`test_axis_runner.py`，dry-run + 虚拟时钟） | **2/2 执行**、目标帧 **[10, 411]** 与轴表一致、费用锚 **10/15** 正确、**迟到 >0.5 帧 0 条**（最大 0.018 帧） |

⇒ **同一份 YAML，模拟端与打图端给出同一组帧号**。

## 五、★同帧多操作（"操作前先步进/暂停定位帧再执行"）

一帧 = 1/30 s；若两条操作按"顺序等时钟"下发，注入耗时会把第二条挤到下一帧。
若轴表里确有**同一帧的多条操作**，用执行配置开启**冻结模式**：

```jsonc
"same_frame_mode": "freeze",           // 默认 "sequential"（既有顺序语义）
"freeze": {
  "mode": "sim",                       // sim（离线/回归，不注入）| win（Windows 注入）| adb
  "pause_key": "f",                    // ★F 键语义 = 按下暂停 / 松开恢复（key_down/key_up）
  "step_key": "t",                     // 过帧键（可选；用于步进对齐到目标相位）
  "step_max": 5, "step_wait_s": 0.04,
  "pause_button": [x, y]               // adb 模式：暂停按钮相对坐标
}
```

行为：同一目标帧的连续操作会被归为一组 ⇒ **冻结**（暂停）→ 必要时**步进**对齐相位 →
**连续下发该组全部操作** → **恢复**。
每条记录新增可审计字段：`group_id` / `group_size` / `frozen` / `frozen_frame` /
`frozen_mode` / `frozen_steps`；返回体带 `frozen_groups` / `frozen_ops` / `frozen_mismatch`。

**已验证（`code/vision/apps/test_same_frame.py`，dry-run + 虚拟时钟 + `mode='sim'`）**：
- 合成轴表（两条部署同帧 411）⇒ `frozen_groups=1`、`frozen_ops=2`、两条 **同 `group_id`**、
  `frozen_frame` 一致且 = 411、`frozen_mismatch=0`；
- 顺序模式无回归（`frozen` 全 False）。

> ★**实机前置条件**（既有结论，勿重复试错）：`F` 键 = 按下暂停/松开恢复（需 `key_down`/`key_up`）；
> ADB 的 `input keyevent` **无法触发 MuMu 宏**，Windows 层需 `PostMessage`；
> 「0 帧选中」「开局 0 帧暂停」仍需宏。`win`/`adb` 模式**需实机标定**后才可用。

---

## 六、新增一份轴表

1. 复制 `1-1.yaml` 改名（如 `h12-4.yaml`）；
2. 填 `stage / squad / deploys / expect`；
3. 若有录像：用 `code/vision/apps/video_axis.py` 产出逐帧表，把**硬锚点**写进 `video_axis.anchors`；
4. `python replay_axis.py h12-4` 校验。
