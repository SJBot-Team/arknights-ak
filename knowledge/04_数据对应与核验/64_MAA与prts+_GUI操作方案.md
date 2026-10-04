# 64 · MAA 与 prts+ 的 GUI 操作方案（含 agent 驱动闭环）
> 主题：**04E 实机 / 打图操作**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）
> 层级：**T2（数据/流程整理类（未含强代码证据））**　建立日期：**—（待补）**　任务：—　｜　**头部为 2026-09-30 自动回填**，推断项已标注

> **本轮任务**：解析 MAA 与 prts+ 两个工具的完整任务流程，并初步搭建"agent 驱动"的操作流程。
> 定位：**暂时**的 GUI 操作方案 —— **局外用 MAA**（日常、进关、编队），**局内用 prts+**（按轴表部署/放技能）。
> **合规**：MAA 与 prts+ 均**非**本地官方游戏客户端（`D:\YostarGames\` 未触碰）。
> 登录相关动作**未纳入**本方案；用户要求"等进一步解析 MAA 工作流程完善实机方案后再开放使用账号"。
> **实机状态**：本轮分析期间**模拟器未启动**（`MuMu模拟器12` 窗口不存在、`adb devices` 为空），
> 故所有实机连线测试均**未执行**；结论以**读源码 / 读二进制 / 读真实日志**为据。
>
> **判据标注**：✅ 实测或已读源码 · 🟡 推断（高置信但未直证）· 🔴 未查明（见 §五）
>
> **配套子文件**（本文件只留精炼结论，长表另存）：
> - `64a_MAA任务格式与步进接口_参考表.md` —— tasks.json 字段全表、导出函数全表、回调目录、日志格式、SingleStep、copilot schema
> - `64b_prts+轴表与控制面_参考表.md` —— xlsm 列定义、设置区、宏/控制台、源码字符串、封顶根因
> - 原型代码：`ak\code\gui_ops\`（含 `README.md`）
>
> 既有相关记录：`45_资产索引…§七`、`48_MAA方案索引_关卡外流程.md`、`49_战斗内操作协议_部署.md`、`53_PRTS+部署实现_源码剖析.md`
>
> ⚠️ **环境变更（必读）**：为查明"MAA 有无 CLI"，执行了一次 `MAA.exe --help`，
> **该命令触发了 MAA 自带更新器**，`MaaCore.dll` 由 **v6.16.8 就地升级为 v6.17.5**（`MAA.dll` 同步）。
> 我方未主动修改 `D:\__soft\MAA` 任何文件。两个版本导出表**完全一致（33 项）**，升级后本项目回归仍 17/17 PASS。
> **教训：不要再用命令行参数探测 `MAA.exe`**（要版本就读 `AsstGetVersion()`）。已登记 `management\environment_change_log.md`。

---

## 〇、一页结论

| 问题 | 结论 | 判据 |
|---|---|---|
| **MAA 能否被外部程序步进驱动？** | **能**，且有**四条**路径；其中 **`SingleStep` 是官方原生单步接口** | ✅ |
| MAA 的"一步"粒度 | 任务链（`AsstAppendTask` 一个任务）/ **单步战斗操作**（`SingleStep`）/ 一次点击（`AsstAsyncClick`） | ✅ |
| MAA 结果怎么读回 | ①`AsstCreateEx` 回调 JSON ②`debug/asst.log`（与回调**逐字相同**）③`AsstGetImage` 截图 | ✅ |
| MAA 有 CLI 吗 | **没有**。`MAA.exe --help` stdout/stderr 均为 0 字节（GUI 单实例）⇒ 必须直接调 `MaaCore.dll` | ✅ |
| MAA 输入通道 | 本机实际走 **ADB + minitouch**；另支持 **Win32 直连窗口**（`AsstAsyncAttachWindow`） | ✅ |
| MAA 坐标基准 | **1280×720**，再乘回原分辨率（本机 ×1.5） | ✅ |
| **prts+ 能步进吗** | **不能**。启动后一直跑到轴表结束 | ✅ 源码 |
| prts+ 的"状态文件" | **就是那份 xlsm**。★**双向**：它写回 `作战记录!K`（成败底色）+ `中转站!B1/B2/B3`；外部写 `中转站!B1='停止中'` 即可**暂停它** | ✅ 源码级 |
| **prts+ 费用封顶卡死的根因** | 根因**已定位到源码 docstring 级**；**作者自己在《使用须知》里承认"无法在费用抵达上限…情况下使用"** | ✅ |
| **agent 闭环** | 已跑通：离线回归 **17/17 PASS** + 干跑 5 步 + MAA 绑定实测（含错误回调） | ✅ |

---

## 一、MAA 一轮完整任务流程

### 1.1 任务如何被描述 ✅
- **`resource/tasks/tasks.json`**（869 个任务）+ `resource/tasks/` 下 79 个按模块拆分的 JSON（**合计 3295 条定义**）。
  字段全表见 `64a §一`。核心是一个 `{算法, roi, 动作, next}` 四元组：
  - 识别：`template`（模板图，267 处）/ `algorithm:"OcrDetect" + text`（122 处）/ `template+roi+templThreshold`；
  - 动作：`action` ∈ `ClickSelf`(239) / `ClickRect`(48) / `DoNothing`(40) / `Swipe`(11) / `Stop`(10)；
  - 控制：`next`（**候选链**）、`maxTimes`+`exceededNext`（重试）、`preDelay`/`postDelay`、`sub`、`reduceOtherTimes`。
- **`resource/copilot/*.json`**（74 份作业）：`stage_name` + `opers/groups` + `actions[]`；
  `actions[].type` ∈ `Deploy`/`Skill`/`Retreat`/`SpeedUp`/`BulletTime`/`SkillDaemon`/`DrawCard`/`Click`/`Swipe`…（见 `64a §九`）。
- ⚠️ **`onlyRecognition`/`roiOffset`/`retryTimes`/`replaceFullWidthChars`/`MatchTemplateDetector`/`OcrDetector`/`ColorMatch` 在 MaaCore 中不存在**（二进制 0 命中）——详见 `64a §一-bis`。

### 1.2 一轮任务从启动到结束（骨架）✅
```
① 连接设备        AsstAsyncConnect(adb_path, address, config)        # 或 AsstAsyncAttachWindow(hwnd,…)
② 装配资源        AsstSetUserDir(dir) → AsstLoadResource(MAA根目录) → AsstCreateEx(cb)
③ 排队任务链      AsstAppendTask(h, "StartUp"/"Fight"/"Copilot"/…, params) → task_id
④ 启动            AsstStart(h)                                       # 同一时刻只跑队列
⑤ 循环：识别→动作  MaaCore 内部 ProcessTask 循环：
                    截图(adb screencap / PrintWindow) → 缩到 1280×720
                    → 按 to_be_recognized 候选清单逐个识别（模板/OCR/FeatureMatch）
                    → 命中则执行 action（坐标 ×缩放比 送回设备）
                    → 按 next 候选链选下一个任务；未命中则 cur_retry+1，达 retry_times 则该轮失败
⑥ 结果回传        每次识别/动作都发 SubTaskStart(20001)/SubTaskCompleted(20002)；
                  业务数据发 SubTaskExtraInfo(20003).what（StageDrops/DepotInfo/…）
⑦ 结束            TaskChainCompleted(10002) / TaskChainError(10000)；全部完成 AllTasksCompleted(3)
⑧ 收尾            AsstStop / AsstDestroy
```
**实测样本**（`debug/asst.log`，Fight 链）：`StageBegin`(JustReturn) → `Fight@ReturnButton`(MatchTemplate 0.991)
→ `Fight@ReturnConfirm`(0.976) → `LoadingIcon`(0.998) → **连续 7 次 `LoadingIcon` 重试** → `Fight`(0.991)
→ `Terminal-Entry`。⇒ 这就是"识别→动作→判定→下一步"的真实形状。

### 1.3 界面识别判据 ✅
| 项 | 值/做法 |
|---|---|
| 坐标基准 | **1280×720**（日志 `Click with scaled coordinates (0,719) 1.5` → `minitouch click: (0,1078)`） |
| 模板匹配阈值 | **默认 0.8**，可用 `templThreshold` 覆盖；实测命中分 0.976~0.999 |
| 模板匹配 | `cv::matchTemplate`；`multi_match` 返回多候选 + 分数 + `roi` |
| OCR | 自带 **PaddleOCR**（`PaddleOCR/`、`PaddleCharOCR/`）+ ONNX；`fullMatch`/`isAscii`/`ocrReplace` 纠错正则 |
| 专用判定 | `specialParams` 存算法私有参数（如 `BattleHasStarted` = `[亮度阈值 235, 点数 200]`；`BattleOperAvailable` = V 通道均值 100） |
| 语义落地（我方） | `plugins/recognize/ui_state.py`：`battle`/`squad`/`viewport`/`unknown`，阈值 0.80 |

**流程控制**：`maxTimes`+`exceededNext`（次数上限与去向）、`cur_retry`/`retry_times`（链内重试，实测 5 次）、
`preDelay`/`postDelay`、`reduceOtherTimes`、`cache`、`onErrorNext`。**没有通用 `timeout` 字段**。

### 1.4 它如何驱动输入 ✅
| 项 | 结论 |
|---|---|
| 本机实际 | **ADB + minitouch**（日志 `minitouch click: (258, 447)`、`adb.exe … exec-out "screencap \| gzip -1"`） |
| 另一条通道 | **Win32 直连窗口**：`AsstAsyncAttachWindow(hwnd, screencap, mouse, keyboard, block)`，截图法 `GDI/FramePool/DXGI_DesktopDup/PrintWindow/ScreenDC`，输入法 `Seize/SendMessage/PostMessage/SendMessageWithWindowPos/…` |
| 坐标自适应 | **在 1280×720 空间识别与计算，再按缩放比送到设备**（本机 1920/1280 = 1.5） |

### 1.5 ★ 可被外部程序"步进式"驱动吗 —— **能** ✅

| # | 路径 | 接口 | 粒度 | 状态 |
|---|---|---|---|---|
| **A** | **`SingleStep`（官方原生单步）** | `AsstAppendTask(h,"SingleStep",{"type":"copilot","subtype":"action","details":{"actions":[<一个action>]}})` | **一个战斗操作** | ✅ 本机实测（task_id 1~6） |
| B | 一个任务链一步 | `AsstAppendTask(h, "<TaskType>", params)` → `AsstStart` → 等 `TaskChainCompleted` | 一个任务链 | ✅ 本项目实现并实测链路 |
| C | 像素级"先看再点" | `AsstAsyncScreencap` → `AsstGetImage` → `AsstAsyncClick` | 一次点击 | ✅ 实测（`AsyncCallInfo` 回调） |
| D | 单条内置识别任务 | `AsstAppendTask(h,"Custom",{"task_names":["AwardBegin"]})` | 一个内置识别 | ✅ append 成功 |

**★★ `SingleStep` 的两个要点**（✅ 两处独立实测复现）：
1. **`subtype`**：`stage`（设关卡，`details:{"stage_name":"1-7"}`）/ `start`（开始作战）/ `action`（单步操作）。
2. **官方文档的 `action` 示例是错的**：源码 `SingleStepTask::append_copilot_action` 把 `details`
   直接交给 `CopilotConfig::parse_actions`，后者第一行是 `json.at("actions")`
   ⇒ **`details` 必须是 `{"actions": [<单个 action>]}`**，传裸对象会被拒（返回 0）。
   实测：裸 action → `task_id=0`；包数组 → `task_id=1`。报错只在 `asst.log`：
   `[ERR] asst::SingleStepTask::append_copilot_action invalid map<K, T> key`。

**结果读回三条正规通道** ✅：① `AsstCreateEx` 回调（`TaskChainCompleted`/`SubTaskCompleted.result{rect,score,template}`/
`SubTaskExtraInfo.what`）；② **`debug/asst.log`**（每行 `Assistant::append_callback | <Msg> <json>`，
**与回调逐字相同** ⇒ 不写 C 绑定也能事后重建整条决策链）；③ `AsstGetImage`（BGR，buffer 自算）。

**链内部能否单步**：不能。但链内每步都以 `SubTaskStart/Completed` 回调出来（携带
`task/algorithm/action/result.score/to_be_recognized/cur_retry`）⇒ 可作**过程遥测**。

---

## 二、prts+ 完整流程

### 2.1 输入：xlsm 轴表格式与字段 ✅（详见 `64b §二、§三`）

工作簿 4 页：**`作战记录`**（轴表主体）/ `Sheet1`（作者换算辅助表）/ `使用须知` /
**`中转站`（隐藏，= 源码里的 `control_sheet`，控制面）**。

**「作战记录」列定义**（✅ 来自 `dataValidation` 全文，含官方 prompt）：

| 列 | 表头 | 说明 |
|---|---|---|
| A | 当前执行 | 脚本写 `→` 标当前行 |
| B | 费用 | 整数 0–999（用于脚本的费用校验） |
| C | 帧数 | `0至(每费帧数-1)` ⇒ **秒内帧** |
| D | 绝对时间 | `表示费用条一共满过几次的非负整数` ⇒ **秒** |
| E | 操作 | `部署, 技能, 撤退` |
| F | 干员 | 全名或简称 |
| G | 坐标 | `map上的坐标 例如B3` |
| H | 朝向 | `上, 下, 左, 右, 无` |
| I | 简称 | 命名当前单位供后续引用 |
| J | 备注 | 不影响执行 |
| **K** | **运行结果** | `绿=成功 / 黄=延迟 / 红=失败` |
| M/N | 设置区 | 见下 |

**目标帧 = D（绝对时间）× N4（每费帧数，默认 30）+ C（帧数）。**

**「设置」区（N 列）★ 全部阈值都从这里进**（无需改代码/参数）：

| 格 | 名称 | H12-4 | 映射源码常量 |
|---|---|---|---|
| N2 / N3 | 关卡代号 / 关卡全名 | `H12-4` / 空 | `Settings.map_code/map_name` |
| **N4** | **每费帧数**（30/40/60/120） | `30` | `GameTime.TICK_MAX` |
| N5 | 脚本路径 | `D:\__soft\ak\prts+\prts+.exe` | 启动按钮用 |
| N6 | 初始时间（运行前费用条曾满过几次） | 空 | `reset_time_counter(initial_time)` |
| N9/N10/N11 | 等待时间 1/2/3 | `0.02`/`0.1`/`0.3` | `MINIMUM_WAITTIME`/`FRAME_WAITTIME`/`GENERAL_WAITTIME` |
| N12/N13 | 阈值-子弹时间 / 阈值-逐帧定位 | `15`/`2` | `BULLET_THRESHOLD`/`FRAME_THRESHOLD` |

### 2.2 启动参数与运行前提 ✅
- **只有三个参数**（`main.py` 的 argparse 原文）：`--xlsm <路径>`（`The path to the Excel file.`）、
  `--debug`（`Run in debug mode.`）、`--autoenter`（`Run in auto enter mode.`）。
- **路径必须纯 ASCII**（实测中文会被 PowerShell 传参打坏）⇒ 原型里 `to_ascii_path()` 自动转存。
- **运行前提（官方 VBA 原文）**：
  > `' 脚本正在运行。此时无法响应。请确保excel没有单元格处于编辑状态，并确保已经进入关卡并暂停游戏。`
  ⇒ **必须已进关并在第一秒内暂停**（它按费用条相对长度定位秒内帧；越早暂停越准）。
  **不能有单元格处于编辑态**（COM 会读不到值）。
- `--autoenter` 走局外自动进关：`wait_for_game_start()` 监视**费用区右下角像素亮度**（先变暗=加载、再变亮=开战）
  → 点 `START_BUTTON_RATIO` → 发暂停 → `Successfully paused at time{}` → 点 `SPEED_BUTTON_RATIO` 切 **2 倍速**。
- xlsm 里的"开始"按钮走 VBA：`WScript.Shell.Run "<N5路径>\prts+.exe --debug? --autoenter? --xlsm ""<本工作簿>""", 1, False`。

### 2.3 它如何识别局内状态、如何执行、如何判定"该下一步了" ✅
| 环节 | 做法 |
|---|---|
| 截图 | **Windows GDI `BitBlt`** 抓游戏窗口（不是 ADB/WGC）：`GetWindowDC`→`CreateCompatibleDC`→`BitBlt(SRCCOPY)`→`cv2.cvtColor(BGRA2GRAY)`→**`resize(1280,720)`** |
| 秒内帧 | `tick = round(费用条白色像素占比 × TICK_MAX)`（`COST_AREA_RATIO=(0.906,0.685,1,0.755)`） |
| 绝对秒 | `_update_time_counter`：**仅当 `current_tick < last_tick`（费用条回绕）才 `time+=1`** |
| 费用数字 | `tesserocr` + `lang='arknights_digit'` + `PSM.SINGLE_WORD`，置信度阈值过滤；失败返回 −1 |
| 干员定位 | 在 `OPERATOR_AREA_RATIO=(0,0.8,1,1)` 里对 `resource/avatars/` 模板做 `matchTemplate(TM_CCOEFF_NORMED)`，阈值 `TEMPLATE_MATCH_THRESHOLD` |
| 格子→屏幕 | `calc_view` 3D 透视投影（正视/侧视两套，视角参数来自关卡数据）；**部署用 side、技能/撤退用 front** |
| 执行 | `SendMessage` 鼠标消息到渲染子窗口；暂停/esc 用**鼠标侧键**；部署 = 选中→上拖一次→`esc`暂停→移到目标格→`mouseup`→定朝向 |
| **"该下一步了"的判定** | `wait_until_threshold(target, threshold, need_cost, user_paused)` 三段式逼近：<br>① `time + BULLET_THRESHOLD(15帧) < target` ⇒ 恢复→等到子弹阈值内→**进子弹时间**→暂停<br>② 已在子弹阈值内 ⇒ 直接进子弹时间<br>③ 已在 `FRAME_THRESHOLD(2帧)` 内 ⇒ 只进子弹时间、**不恢复**<br>再用 `while get_game_time() < target: 恢复→sleep(FRAME_WAITTIME=0.1)→暂停` **逐帧推进** |
| 判定结果 | 写回 **K 列颜色**（绿/黄/红）；异常文案即失败分类：<br>`当前操作晚了超过一费`(PerformLateError) / `用户停止`(UserPausedError) / `疑似发生错误` / **`请求人工接管`** / `未定义错误` |

### 2.4 ★ 费用封顶卡死：根因与绕法

**根因（✅ 源码 docstring 级证据，见 `64b §六`）**：
```
tick 的唯一来源 = 费用条白色像素占比 × TICK_MAX
_update_time_counter 的原文 docstring:
   "If the current tick is less than the last tick,
    it means the cost bar has been filled once."
⇒ 只有 tick 回绕 才 time += 1
```
费用**封顶**（H12-4 上限 20）后费用条**不再填充** ⇒ tick **冻结在定值** ⇒
`current_tick < last_tick` **永远为假** ⇒ `_time_counter` **停止递增** ⇒ `game_time` **完全静止**。
而"该下一步了"的循环是 `while get_game_time() < target_time: 恢复→sleep(0.1)→暂停`
⇒ **退出条件永不满足 ⇒ 卡死**（不推进、不报错，表现为"停在那里"）。
**附带损伤**：封顶持续 N 秒，`_time_counter` 就**少计 N** ⇒ 即使离开封顶，绝对时间轴**整体偏移 N 秒**。
**触发条件**：费用触顶**且仍有后续操作等待**。H12-4 上限 20、轴表密集 ⇒ 必然发生。
**★ 作者自己承认**（《使用须知》第三条 1 原文）：**"无法在费用抵达上限……情况下使用"**。

**绕法**（详见 `64b §六.2`）：
| # | 绕法 | 要点 | 判据 |
|---|---|---|---|
| **A₀** | ★**官方推荐：让费用永不到顶** | 多带一个高费干员，**在封顶前部署再撤退**故意泄费，维持费用条继续填充 | ✅ 官方文档；零改码最稳，但轴里要预留这次"泄费" |
| **A** | **外部计时，不用 prts+ 的 tick** | 用 `plugins/clock/frame_clock.py`（官方 `pixel_map` 查表）+ `cost_timeline.py`（**上限锚点，已实现"跨越封顶"**）+ `plugins/action/deploy.py` 自己驱动 | ✅ 既有实现正是为此；视频基准已验证（99.6% ≤2 帧、无漂移） |
| **B** | **切段 + 官方断点** | 在首个封顶点**插一个空行**（官方"使用技巧 5"：运行到第一个非法处即停）⇒ prts+ 自然停下；封顶段由 agent 用 `paused_protocol` 驱动；之后改 `中转站!B2`（起始行）续跑 | ✅ 断点机制是官方功能；🟡 切点对齐待实机 |
| **B₂** | **改绝对时间轴 + `初始时间(N6)`** | 轴写成 `绝对时间`(D)+`帧数`(C)；中途开始就在 N6 填"运行前已回满次数" | ✅ 能解决**"部署扣费破坏时间轴"**；❌ **不能解决封顶** |
| **C** | **监控→杀→改表续跑** | 检测"进程活着但 `Performing action` 停 > N 秒 且费用已达上限" ⇒ 杀掉续跑 | ✅ 已实现（`gui_ops/prts_backend.py::watch()`） |
| **E** | **打补丁改计时** | 连续 N 次读到相同 `(tick,cost)` 且 `white_ratio≈1.0` 时切换为本地自增计数；退出条件由"读数<目标"改为"步进 K 次" | 🟡 唯一能全自动跑通封顶段的改法（用户已授权改 prts+） |

> **不建议**只改 `初始时间(N6)`：封顶期间 tick 是**冻结**而非**变慢**，单改原点无法让 `while` 退出。

**★ 版本差异（重要修正）**：本机 `prts+.exe` **比公开仓库 `main`/`develop`/`release-0.2.0` 都新**
（多了 `GameTime.time`/绝对时间、`_time_counter`/`reset_time_counter`、`get_game_time(need_cost)`、
`wait_for_game_start()`、`初始时间` 设置、`绝对时间` 列；`MINIMUM_WAITTIME` 0.02→0.03）
⇒ **既有 `53_PRTS+部署实现_源码剖析.md`（基于公开 main）对"输入格式 / 时间语义"只对了一半**；
且用户手上的模板与**本机 exe** 配套。**判据优先级：本机 exe > 公开仓库。** 详见 `64b §六-bis`。

**★ 它其实是"可被外部干预"的**（这对 agent 闭环很关键）✅：
- 它读的 sheet 固定为 `作战记录`（动作表）与 `中转站`（隐藏控制/状态面板，走 **Excel COM**，需装 Excel）；
- **`中转站!B1` = 状态**（`运行中`/`停止中`/`已停止`），`is_paused()` 就是判 `B1=='停止中'` ⇒ **外部写这一格即可暂停它**；
- **`中转站!B2` = 当前操作行号**（可改 = 官方"手动改起始行"）；**`中转站!B3` = 错误日志**；
- `作战记录!K<行>` = 成败**底色**，`A<行>` = `→` 指针 ⇒ **逐行成败读回**；
- 官方还给了**断点机制**："通过插入空行达到打断点的效果"。
- ⚠️ `--xlsm` 必须传**规范化后的绝对路径**，否则它会再开一份副本，"停止"按钮失效。

---

## 三、★ agent 驱动的操作流程（本轮核心产出）

### 3.1 接口约定（谁调谁 / 数据怎么传 / 结果怎么读回）

```
agent(人/LLM) ──写──> Plan 操作清单(JSON)
                        │
                   AgentLoop ──OpStep──> Backend (maa | prts | vision | noop)
                        │                      │
                        │<──StepResult──────────┘  含 Observation(ui_state/cost/frame/截图)
                        │
              ┌─────────┴──────────┐
        verdict == ok           否则
          ⇒ 执行下一步      ┌─────┴─────┐
                      TRANSIENT      其它(SEMANTIC/ENV/FATAL/DATA)
                      ⇒ 自动重试      ⇒ Escalation → agent 改 Plan(rev+1) → 重跑
```

**两条铁律**
1. **判定用语义，不用像素差异**（界面语义 / 模板命中 / 费用数值）。地图动画会骗过像素差。
2. **只有 agent 改清单**；`AgentLoop` 只做机械的比对、重试与落盘，不自己发明新操作。

**"谁执行" 的路由**：`OpStep.phase` 决定 ——
`outgame` → MAA（或既有 `vision` 侧 `AutoEnter`）；`ingame` → prts+（或既有 `axis_runner`）。

### 3.2 关键数据结构（`ak\code\gui_ops\contracts.py`）

```jsonc
// Plan 操作清单 —— agent 读写，落盘为 _runs/<id>/plan.json
{ "plan_id":"demo-1-7", "rev":1, "stage":"1-7",
  "steps":[ { "id":"s1_home", "backend":"maa", "phase":"outgame",
              "desc":"回到主界面",
              "payload":{"task":"StartUp","client_type":"Official","start_game_enabled":false},
              "expect":{"ui_state_in":["home","terminal"]},
              "retry":2, "timeout":90, "optional":false } ] }

// StepResult 一步结果 —— 每步一行 append 到 _runs/<id>/state.jsonl
{ "step_id":"s1_home", "backend":"maa",
  "verdict":"ok|mismatch|error|timeout|skipped",
  "failure_class":"NONE|TRANSIENT|SEMANTIC|ENV|FATAL|DATA",
  "duration_s":12.3,
  "expect":{...}, "observed":{...}, "diffs":["cost 期望 >=18，实读 7"],
  "events":[{"t":...,"msg":10002,"name":"TaskChainCompleted","details":{...}}],
  "evidence":{"shot":"_runs/.../shots/s1_home_a0_before.png"},
  "message":"…", "attempt":0, "plan_rev":1, "ok":true }
```

**`expect` 支持的可判定键**：`ui_state` / `ui_state_in` / `cost` / `cost_min` / `cost_max` /
`cost_delta_ge`（部署成功的关键判据）/ `frame_min` / `max_score_min` / `task` / `subtask_seen` / `exit_code`。

**状态文件（3 个）**：`state.jsonl`（每步一行，append-only，可断点续跑）·
`plan.json`（当前生效清单，agent 每次修订覆盖并 `rev+1`）· `shots/*.png`（每步执行前截图证据）。

### 3.3 失败分类与处置（唯一分叉点）

| 分类 | 自动重试 | 交 agent | 典型 | 处置 |
|---|---|---|---|---|
| `TRANSIENT` | ✅ | ✗ | 截图超时、加载慢、动画未结束 | 退避重试，最多 `op.retry` 次 |
| `SEMANTIC` | ✗ | ✅ | 界面不对、点了没生效、费用没扣 | **必须** agent 改清单 |
| `ENV` | ✗ | ✅ | 模拟器没开、ADB 掉线、窗口找不到 | 上游先修环境 |
| `FATAL` | ✗ | ✅ | `TaskChainError` / 任务链内部错误 | 停止并交 agent |
| `DATA` | ✗ | ✅ | 轴表缺列、坐标无法映射、params 非法 | 补数据 |

**已解决不算失败**：重试成功、或被 agent 改清单取代的旧尝试仍留在 `state.jsonl`（审计），
但计入 `resolved_failures` 而非 `failed`。

### 3.4 原型代码：`ak\code\gui_ops\`（含 README）

| 文件 | 作用 |
|---|---|
| `contracts.py` | ★ 接口约定：`Plan`/`OpStep`/`Observation`/`StepResult` + 失败分类表 |
| `maa_backend.py` | MAA 步进后端（ctypes 直调 `MaaCore.dll`），含 `SingleStep` 原生单步 + `AsstAsyncClick` 窄接口 |
| `prts_backend.py` | prts+ 后端（子进程 + 日志解析 + **封顶卡死监控** `watch()`） |
| `noop_backend.py` | 干跑后端 `NoopBackend` + 离线回归后端 `ScriptedBackend` |
| `agent_loop.py` | ★ 闭环执行器（自动重试 / 升级 / 改清单 / 落盘 / 报告） |
| `cli.py` | `preflight` / `maa-probe` / **`maa-singlestep`** / `maa-tasks` / `run` / `logs` |
| `plan.example.json` / `selftest_loop.py` | 操作清单样例（局外 3 + 局内 1 + 结算 1）/ 离线回归 17 项 |

**用法**（用 `ak\code\vision\.venv\Scripts\python.exe`）：
```powershell
python selftest_loop.py                                   # 17/17 离线回归（不碰游戏）
python cli.py preflight                                   # 检查 MAA DLL / prts+ exe / 模拟器窗口
python cli.py maa-probe --start                           # 验证"下达+读回"闭环（不连设备）
python cli.py maa-singlestep                              # ★ 验证 SingleStep 原生单步（含 A/B 对照）
python cli.py run --plan plan.example.json --dry-run      # 干跑整份清单
```

**MAA 绑定的三个实测坑（已写进代码注释）**
1. **顺序**：`AsstSetUserDir → AsstLoadResource(MAA*根目录*) → AsstCreateEx`。顺序错返回空句柄；
   `AsstLoadResource` 的参数是**根目录**（其下有 `resource/`），**不是** `resource/` 本身。
2. **回调必须保活实例**：只存 `CFUNCTYPE` 类型不够，实例被 GC 后会调到已释放的 trampoline ⇒
   `OSError: exception: single step`（本项目踩过并修复）。
3. **缓冲尺寸协议**：`AsstGetImage`/`AsstGetUUID`/`AsstGetTasksList` 是 `(h, buff, n) -> size`，
   先传 `NULL,0` 取所需字节数；**未连接时返回哨兵 `AsstGetNullSize() = 2^64-1`**。

---

## 四、分工与现状

### 4.1 建议的分工（本轮结论）
| 阶段 | 用谁 | 理由 |
|---|---|---|
| 局外：唤醒/回主界面/进终端/选关/编队 | **MAA**（任务链步进 + 读回调） | MAA 已覆盖 869 个任务、3295 条定义，且能单步 + 读回判据 |
| 局外：进关后**立刻暂停** | **我方 `vision`**（既有 `AutoEnter` + `paused_protocol`） | 🔴 **MAA 无对应任务**（MAA 的 copilot 自己管部署，不暴露"进关即暂停"）；prts+ 则是 `--autoenter` |
| 局内：按轴表部署/技能 | **无封顶关** → prts+；**有封顶关（如 H12-4）** → 我方 `axis_runner` + `frame_clock`（绕法 A/B） | §二.4 根因 |
| 局内：结果判定 | MAA 战斗结算识别 / 我方 `ui_state` | — |

### 4.2 跑通程度 ✅
- 离线回归 **17/17 PASS**（全绿 / 自动重试 / 升级改清单 / 终止 / 干跑 / 状态文件字段）
- `cli.py maa-probe --start`：完整走通 `LoadResource → CreateEx → AppendTask → Start → 回调`，
  收到 `TaskChainStart(10001)` + `ConnectionInfo(2){what:ScreencapFailed}`（结构化错误读回）+
  `SubTaskStart/Completed(20001/20002)`（含候选清单与 `result`）
- `cli.py maa-singlestep`：**A/B 对照复现**——裸 action `task_id=0`、包数组 `task_id=1`
- `cli.py run --dry-run`：5 步清单干跑，`state.jsonl` 5 行、字段齐全
- 升级到 `MaaCore v6.17.5` 后回归仍 **17/17 PASS**、probe 正常

### 4.3 未验证（需实机；本轮模拟器未启动、账号未开放）🔴
- 真连接下 `step()` 的端到端（ADB 与 Win32 两条通道**都没在真机试过**）
- `SingleStep` "每次 append 只走一步"（🟡 文档语义，未连设备验证）
- prts+ 会话的实际日志行是否与 `prts_backend.LINE_PATTERNS` 完全吻合（模式来自既有实测记录）
- 封顶绕法 A/B 的实机效果
- `vision` 后端的 `step()`（进关+暂停）尚未接上既有 `AutoEnter`/`paused_protocol`

### 4.4 建议的下一步顺序
1. 补 `vision` 后端（零件齐全：`plugins/nav/auto_enter.py` + `clock/paused_protocol.py`）；
2. 起模拟器 → `cli.py preflight` 确认三条前提；
3. `--dry-run` 确认清单 → 分步放开（先 s1/s2，再 s3，再 s4）；
4. 再做 `SingleStep` 的实机逐步部署，与 prts+ 的"子弹时间"口径互证。

---

## 五、未查明项与卡点

| # | 项 | 卡点 | 下一步 |
|---|---|---|---|
| 1 | 封顶时费用条的**具体画面形态**（满格 1.0 还是停在中途） | 🔴 需实机截帧 | 实机在刚封顶时量 `COST_AREA_RATIO` 最后一行的白像素比例；若恒为 1.0 ⇒ 印证 `tick≡29` |
| 2 | 封顶绕法 A₀/A/B/E 的实机效果 | 🔴 模拟器未启动、账号未开放 | 等用户放开实机 |
| 3 | 真连接下的 `step()` 端到端 | 🔴 ADB 与 Win32 两条通道都没在真机试过 | 起模拟器后分步放开 |
| 4 | `SingleStep` "每次 append 只走一步" | 🟡 文档语义，未连设备验证 | 实机验证 |
| 5 | `convert_pos` 的行/列方向 | ✅ 已由两样例定出 `(行号-1, (列数-1)-(字母序))`（`'C12'→(11,6)`、`'G9'→(8,2)`，9×13）；仓库 docstring 与文件内注释互相矛盾 | 实机再用 1~2 个坐标验证 |
| 6 | `DARK_THRESHOLD=30` / `BRIGHT_THRESHOLD=67` 的**顺序**（哪个是哪个） | 🟡 marshal 常量串扰 | 反解 `config.py` 常量顺序 |
| 7 | MAA 是否有"进关即暂停"的任务 | 🔴 未找到；只有 `BattleDeployWhenPause`（在暂停时部署） | 若确认没有，则局外→局内的交接必须由我方完成 |
| 8 | copilot 新格式的完整 `Skill`/`Retreat` 字段 | 本机 74 份作业多为旧 SSS 格式 | 从 MAA《战斗流程协议》文档补齐 |
| 9 | MAA 的 `AsstCallerExtra`（6.17.0 声称新增） | 🔴 导出表未出现 | 查 changelog 或等后续版本 |
| 10 | prts+ VBA「控制台」UserForm 的完整源码 | 🟡 MS-OVBA 自实现解压仍有重复片段 | **非必需**——控制逻辑已在 Python 侧查明（`中转站!B1/B2/B3`） |

### ⚠️ 环境变更（需登记）
本轮调查中实测 `MAA.exe --help` **触发了 MAA 自带更新器**，
`MaaCore.dll` 由 **v6.16.8 就地升级为 v6.17.5**（`MAA.dll` 同步）。
未主动修改 `D:\__soft\MAA` 下任何文件，但 MAA 自身改了；两个版本的导出表**完全一致（33 项）**。
分析结束后无残留进程。⇒ 应登记到 `management/environment_change_log.md`。

---

## 六、临时产物
- `ak\.tmp\maa_report.md`（MAA 逆向详报，65KB）· `ak\.tmp\prtsplus_report.md`（prts+ 详报）
- `ak\.tmp\maa_formats.txt` / `maa_formats.py`（tasks/copilot 格式提取）
- `ak\.tmp\maa_bind3.py` / `maa_step.py`（MaaCore 绑定与步进验证）
- `ak\.tmp\h124_dump.txt`（H12-4 轴表解压全文）· `ak\.tmp\validations.txt`（列定义）
- `ak\.tmp\vba_source.txt` / `vba4.py`（VBA 提取，部分成功）
- `ak\.tmp\str_src_*.txt`（prts+ PyInstaller pyc 源码字符串）
