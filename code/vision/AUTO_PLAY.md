# AUTO_PLAY — 纯 AI 打图工具流

> 复用 `code/vision` 既有无头框架（kernel + plugins），与模拟器 `ak/sim/draft/ak_sim`
> **共用同一份轴表**（cost + 费用内帧锚点）。

## 合规红线（强制，开工前必读）

**① 客户端数据**（用户 2026-08-31 / 2026-09-02）：仅「截图 + GUI/ADB 注入 + 本机回环 API」；
禁止读写游戏文件、禁止内存访问、禁止修改客户端；游戏运行时完全禁触。
详见 `ak/meta/合规声明_游戏客户端.md`。

**② 自动打图 / 账号与虚拟资产**（用户 2026-09-14，同等重要，权威文本 `ak/meta/合规声明_自动打图与账号.md`）：

| # | 红线 |
|---|---|
| 1 | 登录必须**逐次**获用户同意，且仅限用户指定账号；**禁止使用任何来源的「登录界面未保存的账号」** |
| 2 | 顶号/断线后重新登录**不属于**被允许的首次登录 → 需**再次同意**；同意换号时若已登录须**先退出再登录**确认 |
| 3 | **禁止动用除「理智」外的任何账号资源**；**禁止打开**仓库/基建/抽卡/商店/邮件/养成/模组界面，**误触立即退出** |
| 4 | 干员练度/技能/模组/潜能/信赖不匹配时，**禁止自行提升** → 请示用户（换号或提供助战） |
| 5 | 任何可能构成作弊或动用虚拟资产的操作，**AI 禁止自行尝试**；有需要请示用户 |
| 6 | **本次授权**：账号尾号 ******；**MuMu12 1 次 + PC 端 1 次**（共 2 次登录额度）；消耗仅「理智」 |

代码侧落地：配置 `compliance` 段 + `apps/run_axis.py` 实注入守卫
（`--live` 必须同时满足 `compliance.live_run_consent=true` 或 `--i-have-consent`；登录动作默认禁用）。

## 文件一览

| 文件 | 类型 | 作用 |
|---|---|---|
| `plugins/clock/cost_ruler.py` | 时钟 `clock` | **逻辑帧时钟**：费用尺（本机 API，HTTP/WS）+ 自研费用条兜底 + 虚拟/步进时钟；轴表→绝对帧调度；`anchor_ready`/`display_cost`/`ideal_anchor_frame` 供两端共用判据 |
| `plugins/recognize/cost_bar.py` | 识别器 `cost_bar` | 费用条填充像素 → 费用内帧；校准文件兼容 `ArknightsCostBarRuler` 的 `profile_*.json` |
| `plugins/action/adb_input.py` | 动作后端 `input:adb` | MuMu12 adb 注入（`input tap/swipe/keyevent`），**不移动宿主真实光标** |
| `plugins/task/axis_runner.py` | 任务 `axis_runner` | 轴执行器 v2：时钟驱动、同帧多操作、dry-run、逐条执行诊断日志 |
| `apps/run_axis.py` + `configs/axis_h12-4.json` | 入口 / 配置 | 一条命令跑轴（默认 dry-run，`--live` 才注入；`--clock`/`--timebase` 可覆盖） |
| `apps/video_cost_timeline.py` | 工具 | **录像费用轨迹读取**（离线）：自动定位费用数字 ROI → 自举数字模板 → 全片读帧 → 输出回费速率与消耗事件（用于判定倍速、定位落场时刻、给 `cost_bar.roi` 取实测值） |
| `ak_sim_axis_compat.py` | 工具 | 轴表坐标（如 `C12`）→ 格点，与 sim 侧同一实现 |
| `apps/test_costbar_axis.py` | 测试 | 费用条合成识别 + 轴表 dry-run |
| `apps/test_ruler_clock.py` | 测试 | 假费用尺（HTTP+WS）→ 时钟；轴表→帧计划；虚拟时钟全轴 dry-run |

## 时序模型（v2：帧时钟驱动）

```
                      ┌── ruler : 费用尺本机 API 127.0.0.1:2606（HTTP 快照 / WS 推送）
逻辑帧时钟 ClockState ─┼── cost_bar : 自研费用条识别器兜底（截图 + 周期回绕计数）
                      └── virtual : dry-run / 单测（按墙钟 × 加速倍率推进）

轴表 ops（cost 锚 + 费用内帧 foff）
   └─ build_frame_schedule ─► 静态帧计划（诊断/预演用；锚点行 = (显示费用 − 初始费用 + 净累计消耗) × 每费帧数 + foff）
        └─ 运行时调度（与模拟器 Battle.run_axis 同构）：
             费用锚点行 → 显示费用 == 锚点 且 费用内帧 ≥ foff（anchor_ready）
             无锚点行   → 上一操作**实际**触发帧 + foff
             部署费用不足 → cost_gate 顺延（等价于模拟器 retry_on_cost）
             ⇒ 同帧多操作自然成组，不重复读时钟、不做二次判定
```

**为什么不用绝对秒表**：费用条满/剿灭等场景下「绝对时间列不可靠」（赛博塑料使用须知第三条）。
费用条本身永远 0→1 循环、与消耗无关，因此 **费用尺的 `totalElapsedFrames`（战斗内累计逻辑帧）
是免疫该问题的绝对时钟**；而费用数字只用来做**锚点校验与消耗记账**。

### 费用尺 API 关键字段（ArknightsCostBarRuler，apiVersion=2）

| 字段 | 用途 |
|---|---|
| `totalElapsedFrames` | 战斗内累计逻辑帧（绝对帧基准，由尺子维护） |
| `currentFrame` / `totalFramesInCycle` | 费用内帧 / 当前周期帧数（边界周期为 N+1，可识别「第 11 费 31 帧」） |
| `sampleIndex` / `droppedSincePrevious` | 截图管线是否丢帧（对轴可信度诊断） |
| `captureTimestampNs` | 截图时刻（本模块用收到时刻做帧内插值） |
| `rawPixelWidth` / `cursorBlocked` | 原始条宽 / PC 光标遮挡（遮挡帧不写历史） |
| `timingDebug.advancedFrames` | 本帧逻辑推进了几帧（跳帧诊断） |

帧内插值：`frame_now() = totalElapsedFrames + min(收到快照后的墙钟 × 30, 2帧)`，
把「某个逻辑帧的快照」推进到「现在」，从而做到亚帧到点判定与同帧多操作。

### 精度保障

- Windows 主循环内 `timeBeginPeriod(1)`：把 `time.sleep` 粒度从 15.6 ms 提到 1 ms；
- 分级休眠：剩余 >2 帧粗睡 20 ms，临近帧边界改 0.5 ms 短睡；
- 执行记录中 `late_real_frames` = 迟到帧数 ÷ 加速倍率，等价于 1× 实时下的迟到量
  （虚拟时钟 60× 自检下最大 0.385 帧，真实时钟下同量级）。

## 使用（dry-run 优先）

```powershell
cd C:\Users\23922\Documents\ds_harness\ak\code\vision
& '.\.venv\Scripts\python.exe' -X utf8 apps\test_costbar_axis.py    # 费用条合成 + 轴表概览
& '.\.venv\Scripts\python.exe' -X utf8 apps\test_ruler_clock.py     # 时钟/调度全线自检（无需游戏；含两端时序交叉验证）
& '.\.venv\Scripts\python.exe' -X utf8 apps\run_axis.py --config configs\axis_h12-4.json --speed 80
    # ↑ dry-run 全轴（虚拟时钟 80×，约 3.4s，50/50 条触发，最大迟到 0.031 帧）
& '...python.exe' -X utf8 apps\run_axis.py --config configs\axis_h12-4.json --clock ruler   # 接尺子干跑
& '...python.exe' -X utf8 apps\run_axis.py --config configs\axis_h12-4.json --clock ruler --live --i-have-consent
    # ↑ 实注入：需用户当场同意（缺 --i-have-consent 且配置未置 true 时直接拒绝，退出码 2）
```

> 安全护栏：非虚拟时钟连续 `clock_timeout`（默认 5s）无有效读数时**自动中止**，避免尺子掉线后盲打。
> 合规护栏：登录动作默认禁用；实注入需用户逐次同意（见文首「合规红线」）。

配置片段（`engine.config['axis_runner']`）：

```jsonc
{
  "axis": "C:/Users/23922/Documents/ds_harness/ak/data/derived/axis_h12-4_cyberplastic.json",
  "dry_run": true,
  "clock": { "source": "auto", "host": "127.0.0.1", "port": 2606, "transport": "ws" },
  "initial_cost": 10, "frames_per_cost": 30,
  "unit_costs": { "令": 10, "蕾缪安": 20, "弦惊": 23 },
  "grid": { "rows": 9, "cols": 13, "row_from": "bottom", "col_from": "left" },
  "battle_area": { "left": 0, "top": 0, "right": 0, "bottom": 0 },
  "coord_transform": "rc_rowflip",
  "log": "C:/Users/23922/Documents/ds_harness/ak/data/derived/logs_h12-4_run.json"
}
```

`clock.source`：`auto`（探到尺子用尺子，否则费用条兜底）/ `ruler` / `cost_bar` / `virtual`。

## 实机校准步骤（待用户在场时执行）

1. MuMu12 窗口 16:9，启动费用尺 `ArknightsCostBarRuler`（`http://127.0.0.1:2606/` 能取到快照）；
2. 进入关卡，确认尺子 `isRunning=true`、`battleState=battle`；核对 `totalElapsedFrames` 与游戏计时；
3. 截图 → 标定 `battle_area`（战场四角）、`grid`（行列数）；
4. 标定 `unit_slots`（待部署区卡槽）与 `ui.skill_button / retreat_button`；
5. 先 `dry_run: true` 跑一遍轴表，核对每条操作的 `frame_before` 与模拟器输出，再开启实注入。

## 待办

- 实机校准与同帧多操作实机验证（当前全部为离线/合成验证）；**实机操作前须取得用户对登录/注入的逐次同意**；
- 尺子不可用时的费用数字 OCR（做费用锚点交叉校验）；
- 自动启动 → 选关 → 选干员/技能/模组（需求 2.6）——**其中的登录步骤默认禁用**，需用户逐次同意且仅限授权账号（尾号 ****，MuMu12/PC 各 1 次）；
- PC 客户端输入后端（DirectInput）路径与模拟器差异处理。
