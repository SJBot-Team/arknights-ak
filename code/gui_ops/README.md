# `gui_ops` — agent 驱动的《明日方舟》GUI 操作流程（原型）

> 目标形态：**agent 列操作清单 → MAA/prts+ 步进执行 → 结果与预期比对 → 符合就下一步 / 不符合就 agent 改清单**。
> 局外用 **MAA**（日常、进入关卡、编队），局内用 **prts+**（按轴表部署/放技能）。
> 这是**暂时**的 GUI 方案；实机账号使用**尚未开放**（用户要求等流程完善后再说）。

---

## 1. 结论速览

| 问题 | 结论 | 判据 |
|---|---|---|
| MAA 能被外部程序**步进驱动**吗？ | **能**，四条路径。★ 其中 **`SingleStep` 是 MAA 官方原生单步接口** | ✅ 实测：`AsstLoadResource`→`AsstCreateEx`→`AsstAppendTask`→`AsstStart`→回调 `TaskChainStart/Completed` |
| 结果怎么**读回**？ | 三种，可叠加：① 回调 JSON ② `asst.log`（与回调**逐字相同**）③ `AsstGetImage` 截图 | ✅ 实测三种全部可用 |
| 链**内部**能单步吗？ | 不能。但链内每步都会以 `SubTaskStart/Completed` 回调出来，可当过程遥测 | ✅ 实测（msg 20001/20002 携带 `task/algorithm/action/result.score/to_be_recognized`） |
| prts+ 能步进吗？ | **不能**。启动后一直跑到轴表结束 | ✅ 源码 |
| prts+ 的费用封顶卡死 | **根因已定位到源码 docstring 级**（见 §5），外围用"监控+杀+改轴续跑"，内部需换计时口径 | ✅ 根因 / 🟡 绕法待实机 |
| prts+ 能被外部干预吗 | **能**——xlsm 是**双向**状态面：它写回 K 列成败色 + 状态标签（`运行中/停止中/已停止`）；外部可通过 `set_paused`/控制格暂停它 | ✅ 机制 / 🔴 控制格格址未定 |
| agent 闭环 | 已跑通（离线 17/17 全绿 + 干跑 5 步 + MAA 绑定实测） | ✅ `selftest_loop.py` |

### ★★ MAA 的原生步进接口：`SingleStep`

```python
# subtype: stage（设关卡）/ start（开始作战）/ action（单步执行一个战斗操作）
AsstAppendTask(h, "SingleStep", json.dumps({
    "type": "copilot", "subtype": "action",
    "details": {"actions": [ {"type":"Deploy","name":"先锋","location":[5,3],"direction":"Right"} ]}
}))
```

⚠️ **官方文档的示例是错的**：源码 `SingleStepTask::append_copilot_action` 把 `details` 直接交给
`CopilotConfig::parse_actions`，后者第一行是 `json.at("actions")`
⇒ **`details` 必须是 `{"actions": [<单个 action>]}`**，传裸 action 对象会被静默拒绝（返回 **0**），
报错只在 `asst.log`：`[ERR] asst::SingleStepTask::append_copilot_action invalid map<K, T> key`。

本项目实测（`cli.py maa-singlestep`，MaaCore v6.17.5）：
```
裸 action（官方文档写法，错）  -> task_id = 0     # 0 = 被拒
包在 actions 数组里（正确）    -> task_id = 1     # >0 = 接受
subtype='stage' 设关卡 1-7    -> task_id = 2
subtype='start' 开始作战       -> task_id = 3
```

**四条步进路径**：A `SingleStep`（一个战斗操作）· B 一个任务链一步（`step()`）·
C 像素级 `AsstAsyncScreencap`→`AsstGetImage`→`AsstAsyncClick` · D `Custom` 单条内置识别任务。

---

## 2. 目录

| 文件 | 作用 |
|---|---|
| `contracts.py` | ★ **接口约定**：`Plan` / `OpStep` / `Observation` / `StepResult` + **失败分类表** |
| `maa_backend.py` | MAA 步进后端（ctypes 直调 `MaaCore.dll`） |
| `prts_backend.py` | prts+ 后端（子进程 + 日志解析 + 封顶卡死监控） |
| `noop_backend.py` | 干跑后端（`NoopBackend`）+ 离线回归后端（`ScriptedBackend`） |
| `agent_loop.py` | ★ **闭环执行器**（重试 / 升级 / 改清单 / 落盘） |
| `cli.py` | 入口：`preflight` / `maa-probe` / `maa-tasks` / `run` / `logs` |
| `plan.example.json` | 操作清单样例（局外 3 步 + 局内 1 步 + 结算 1 步） |
| `selftest_loop.py` | 离线回归（17 项） |
| `_runs/<plan>_<时间>/` | 每次运行的产物：`state.jsonl`、`plan.json`、`shots/*.png` |

**用哪个 Python**：`C:\Users\23922\Documents\ds_harness\ak\code\vision\.venv\Scripts\python.exe`
（已装 cv2 / numpy / pywin32；系统 python 也够跑 `selftest_loop.py` 与 `maa-probe`）

---

## 3. 快速开始

```powershell
$PY = "C:\Users\23922\Documents\ds_harness\ak\code\vision\.venv\Scripts\python.exe"
cd C:\Users\23922\Documents\ds_harness\ak\code\gui_ops

& $PY selftest_loop.py            # 17 项离线回归（不碰游戏）
& $PY cli.py preflight            # 检查 MAA DLL / prts+ exe / 模拟器窗口
& $PY cli.py maa-probe            # 只验证接口链路（不连接、不启动任务）
& $PY cli.py maa-probe --start    # 额外验证"错误回调"通道（不连设备⇒预期 ScreencapFailed）
& $PY cli.py maa-singlestep       # ★ 验证 SingleStep 原生单步（含 A/B 对照实验）
& $PY cli.py run --plan plan.example.json --dry-run    # 干跑整份清单
& $PY cli.py logs _runs\<dir>     # 读回 state.jsonl 出报告
```

实机（**模拟器需先启动、游戏已在主界面**）：
```powershell
# 方式 A：ADB（MAA 的常规通道，minitouch 点击 + adb screencap）
& $PY cli.py run --plan plan.example.json --connect-adb "D:\__soft\MuMu Player 12\shell\adb.exe,127.0.0.1:16384"
# 方式 B：Win32 直连窗口（无需 ADB）
& $PY cli.py run --plan plan.example.json --attach-hwnd 0x....
```

---

## 4. 接口约定

### 4.1 谁调谁

```
agent(人/LLM) ──写──> Plan(操作清单, JSON)
                        │
                   AgentLoop ──OpStep──> Backend(maa | prts | vision | noop)
                        │                      │
                        │<──StepResult─────────┘  (含 Observation: ui_state/cost/frame/截图)
                        │
              ┌─────────┴─────────┐
      verdict==ok              否则
        ⇒ 下一步          ┌──────┴──────┐
                    TRANSIENT      其它
                    ⇒ 自动重试   ⇒ Escalation → agent 改 Plan → rev+1 重跑
```

**两条铁律**
1. **判定用语义，不用像素差异**（界面状态 / 模板命中 / 费用数值）。地图动画会骗过像素差。
2. **只有 agent 能改清单**；`AgentLoop` 只做机械的比对与重试，不自己发明新操作。

### 4.2 Plan（操作清单）

```jsonc
{
  "plan_id": "demo-1-7", "rev": 1, "stage": "1-7",
  "steps": [
    {
      "id": "s1_home",                       // 键：state.jsonl / shots/ 都用它
      "backend": "maa",                      // maa | prts | vision | noop
      "phase": "outgame",                    // outgame(局外) | ingame(局内)
      "desc": "回到主界面",
      "payload": { "task": "StartUp", "client_type": "Official", "start_game_enabled": false },
      "expect": { "ui_state_in": ["home", "terminal"] },
      "retry": 2, "timeout": 90, "optional": false
    }
  ]
}
```

`expect` 支持的**可判定键**（`maa_backend.compare()` 逐键比对）：

| 键 | 含义 |
|---|---|
| `ui_state` / `ui_state_in` | 界面语义（单一 / 属于列表） |
| `cost` / `cost_min` / `cost_max` | 费用数字 |
| `cost_delta_ge` | 费用扣减量 ≥ N（部署成功的关键判据） |
| `frame_min` | 推算帧号 ≥ N |
| `max_score_min` | MAA 模板最高命中分 ≥ N |
| `task` / `subtask_seen` | MAA 任务名 / 必须观察到的子任务 |
| `exit_code` | prts+ 退出码 |

### 4.3 StepResult（一步结果）

```jsonc
{
  "step_id": "s1_home", "backend": "maa",
  "verdict": "ok|mismatch|error|timeout|skipped",
  "failure_class": "NONE|TRANSIENT|SEMANTIC|ENV|FATAL|DATA",
  "duration_s": 12.3,
  "expect": {...}, "observed": {...}, "diffs": ["cost 期望 >=18，实读 7"],
  "events": [ {"t":..., "msg":10002, "name":"TaskChainCompleted", "details":{...}} ],
  "evidence": {"before": {...}, "shot": "_runs/.../shots/s1_home_a0_before.png"},
  "message": "…"
}
```

### 4.4 状态文件格式

**`_runs/<plan>_<ts>/state.jsonl`** — 每步一行，append-only，可断点续跑：
```jsonc
{"step_id":"s1_home","backend":"maa","verdict":"ok","failure_class":"NONE",
 "duration_s":12.3,"expect":{...},"observed":{...},"events":[...],"diffs":[],
 "message":"","evidence":{...},"attempt":0,"plan_rev":1,"note":"","ok":true}
```
**`plan.json`** — 当前生效清单（agent 每次修订都覆盖并 `rev+1`）。
**`shots/*.png`** — 每步执行前的截图证据（命名 `<step_id>_a<尝试次数>_before.png`）。

---

## 5. 失败分类与处置（唯一分叉点）

`contracts.FAILURE_ACTIONS`：

| 分类 | 自动重试 | 交 agent | 例子 | 处置 |
|---|---|---|---|---|
| `TRANSIENT` | ✅ | ✗ | 截图超时、加载慢、动画未结束 | 退避重试，最多 `op.retry` 次 |
| `SEMANTIC` | ✗ | ✅ | 界面不对、点了没生效、费用没扣 | **必须** agent 改清单 |
| `ENV` | ✗ | ✅ | 模拟器没开、ADB 掉线、窗口找不到 | 上游先修环境 |
| `FATAL` | ✗ | ✅ | `TaskChainError` / 任务链内部错误 | 停止并交 agent |
| `DATA` | ✗ | ✅ | 轴表缺列、坐标无法映射 | 补数据 |

**已解决不算失败**：重试成功、或被 agent 改清单取代的旧尝试，仍留在 `state.jsonl`（审计），
但计入 `resolved_failures` 而非 `failed`。

---

## 6. MAA 后端要点（★ 实测过的坑）

### 调用顺序（顺序错会拿到空句柄）
```python
os.add_dll_directory(MAA_ROOT)
dll.AsstSetUserDir(USER_DIR)          # 日志/调试输出目录（指向工作区，别污染 MAA 安装目录）
dll.AsstLoadResource(MAA_ROOT)        # ★ 参数是 MAA **根目录**（其下有 resource/），不是 resource/ 本身
h = dll.AsstCreateEx(cb, None)        # ★ 必须保住 cb 实例引用，否则回调被 GC ⇒ OSError: single step
dll.AsstSetInstanceOption(h, 3, b"1") # 3 = DeploymentWithPause（= MAA 的 BattleDeployWhenPause）
tid = dll.AsstAppendTask(h, b"StartUp", b'{...}')
dll.AsstStart(h)
dll.AsstDestroy(h)
```
> 环境差异：本机 `MaaCore.dll` 是 **v6.16.8**，而 `resource/` 来自 GUI 的 **v6.14.1**（`version.json` last_updated 2026-08-08）。
> 现可正常加载；升级 resource 或换 DLL 时注意版本配对。

### 缓冲尺寸协议
`AsstGetImage` / `AsstGetUUID` / `AsstGetTasksList` 都是
`(handle, buff, buff_size) -> AsstSize`：先传 `NULL, 0` 取所需字节数；
**未连接时返回哨兵值 `AsstGetNullSize() == 2^64-1`**（不是 0）。

### 连接通道二选一
- **ADB**：`AsstAsyncConnect(h, adb_path, address, config, block=True)` — MAA 常规通道（minitouch/adb screencap）
- **Win32**：`AsstAsyncAttachWindow(h, hwnd, screencap, mouse, keyboard, block=True)` — **无需 ADB**，
  截图方式 `PrintWindow/DXGI_DesktopDup/...`，输入方式 `SendMessage/PostMessage/Seize/...`
  ⇒ 目标 hwnd 实测应为**渲染子窗口**（MuMu 的 `nemuwin` / 标题 `MuMuPlayer`），不是主窗口。

### 窄接口（agent 可直接操纵）
`AsstAsyncClick(h, x, y, block)` 单点、`AsstAsyncScreencap(h, block)` 单截图。
⇒ 即使不用任务链，agent 也能用"观察→点击→再观察"的裸循环。

### 安全边界
本模块**不会** append 登录相关任务，`--dry-run` 下不注入任何输入。

---

## 7. prts+ 后端要点

### 运行前提（✅ 源码 + 实测）
1. `prts+.exe --xlsm <ASCII路径> [--debug] [--autoenter]`；**路径必须纯 ASCII**（`to_ascii_path()` 会自动转存）
2. **局内起**（默认）：游戏**已在战斗中**，且**在第一秒内暂停**——它按费用条相对长度定位秒内帧
3. `--autoenter` 走局外自动进关（它只识别**关卡内待部署区**的干员）
4. 时间口径 **1 秒 = 30 tick**；`BULLET_THRESHOLD=15`、`FRAME_THRESHOLD=2`、`FRAME_WAITTIME=0.1`

### ★ 费用封顶卡死：根因与绕法
**根因**：prts+ 用**费用条的填充长度**算"秒内相位 tick"，`game_time = 已完成秒数×30 + tick`。
费用**封顶**（H12-4 上限 20）后费用条**不再填充** ⇒ tick 读数**停滞** ⇒
它的"逐帧推进"循环 `while get_game_time() < target_time: 恢复 → sleep(0.1) → 暂停`
**退出条件永不满足** ⇒ 停在那里。
✅ 源码 docstring 级证据：`_update_time_counter` 原文 *"If the current tick is less than the last tick,
it means the cost bar has been filled once."* —— 只有 tick **回绕**才 `time += 1`。
**★ 作者自己在《使用须知》里承认**："无法在费用抵达上限……情况下使用"。

**绕法**（本模块已实现 C 项的外围）：
- **A₀（官方推荐）**：多带一个高费干员，**封顶前部署再撤退**故意泄费，维持费用条继续填充。
- **A 换计时源**：不依赖 prts+ 的 tick——用工作区 `plugins/clock/frame_clock.py`（官方 `pixel_map` 查表）
  + `cost_timeline.py`（**上限锚点，已实现"跨越封顶"**）+ `plugins/action/deploy.py` 自己驱动。
- **B 切段 + 官方断点**：在首个封顶点**插一个空行**（官方"使用技巧 5"：运行到第一个非法处即停）
  ⇒ prts+ 自然停下；封顶段由 agent 用 `paused_protocol` 驱动；之后改 `中转站!B2`（起始行）续跑。
- **C 监控+杀+续跑**（`PrtsBackend.watch()`）：进程活着但 `Performing action` 停了
  > `stall_seconds`，且费用已达轴表上限 ⇒ 判"封顶卡死"。
- **E 打补丁改计时**：连续 N 次读到相同 `(tick,cost)` 且 `white_ratio≈1.0` 时切换为本地自增计数。

### ★ xlsm 是**双向**的：它天生可被外部干预
prts+ 用 **Excel COM**（`win32com`）读写工作簿，读的 sheet 固定为 `作战记录`（动作表）
与 `中转站`（隐藏的控制/状态面板）。**需本机装有 Excel**。

| 格 | 含义 | 方向 |
|---|---|---|
| `中转站!B1` | 状态：`运行中`/`停止中`/`已停止`。`is_paused()` 就是判 `B1 == '停止中'` | 双向 ⇒ **写这一格即可暂停它** |
| `中转站!B2` | 当前操作行号 | 可改 = 官方"手动改起始行" |
| `中转站!B3` | 错误日志（如 `错误：无法识别当前费用。`） | 读 |
| `作战记录!K<行>` | 成败**底色**：绿=成功/黄=延迟/红=失败 | 读 ⇒ **逐行成败读回** |

⇒ 本模块的 `PrtsBackend` 提供 `read_status()` / `request_pause()` / `read_progress()` 三个方法
（Excel 未开时优雅降级，不抛异常）。

⚠️ **`--xlsm` 必须传规范化后的绝对路径**：`_connect()` 用 `normpath(abspath(wb.FullName)) == file_path`
做等值比较，而 `main.py` 原样传参 ⇒ 路径不一致会**再开一份副本**，"停止"按钮失效。
`to_ascii_path()` 已一律 `normpath(abspath(...))`。

### ⚠️ 版本差异：本机 exe 比公开仓库新
本机 `prts+.exe` 比 GitHub `main`/`develop`/`release-0.2.0` 都新（多了 `GameTime.time`/绝对时间、
`_time_counter`/`reset_time_counter`、`get_game_time(need_cost)`、`wait_for_game_start()`、
`初始时间` 设置、`绝对时间` 列；`MINIMUM_WAITTIME` 0.02→0.03）
⇒ 既有 `53_PRTS+部署实现_源码剖析.md`（基于公开 main）对"输入格式/时间语义"只对了一半。
**判据优先级：本机 exe > 公开仓库。**

### prts+ 的"一步"是什么
它不是步进式的，所以本后端把"一步"定义为 **起一个受监督会话，跑到进程结束 / 封顶卡死 / 超时**。
日志逐行解析成结构化记录（`initial_tick` / `action` / `performing` / `bullet` / `mismatch` / `error`），
落到 `_runs/<...>/prts_<ts>.jsonl`。

---

## 8. 现状与下一步

**已跑通（离线，OK）**
- `selftest_loop.py` **17/17 PASS**：全绿 / 自动重试 / 升级改清单 / 终止 / 干跑 / 状态文件字段
- `cli.py maa-probe --start`：完整走通 `LoadResource → Create → AppendTask → Start → 回调`
  ⇒ 证明"下达一步 + 读回结构化结果（含错误）"闭环成立
- `cli.py run --dry-run`：5 步清单干跑，`state.jsonl` 5 行、字段齐全

**未验证（需实机，模拟器当前未启动）**
- 🔴 真连接下的 `step()` 端到端（ADB 与 Win32 两条通道都没在真机上试过）
- 🔴 prts+ 会话的实际日志行是否与 `LINE_PATTERNS` 完全吻合（模式来自既有实测记录）
- 🔴 封顶绕法 A/B 的实机效果
- 🔴 `vision` 后端的 `step()`（进关+暂停）尚未接上既有 `AutoEnter`/`paused_protocol`

**建议顺序**：先把 `vision` 后端补上（已有全部零件）→ 起模拟器跑 `preflight` → 用 `--dry-run` 确认清单 →
分步放开（先只跑 s1/s2，再 s3，再 s4）。

---

## 9. 合规

MAA 与 prts+ 均**非**官方游戏客户端；本方案只做**图形界面级**操控。
登录相关动作（账号管理/点登录）**未纳入**本清单；用户明确要求
"等进一步解析 MAA 工作流程完善实机方案后再开放使用账号"。
