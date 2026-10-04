# MAA（MaaAssistantArknights）任务描述格式 与 步进式驱动能力 逆向分析报告

> 分析对象：`D:\__soft\MAA`（Windows x64 本地安装）
> 分析时间：2026-09-23
> 报告文件：`C:\Users\23922\Documents\ds_harness\ak\.tmp\maa_report.md`
> 判据标记：✅ 实测 / 已读源码、🟡 推断、🔴 未查明

---

## 0. 环境基线（重要：实际版本与目录名不一致）

| 项目 | 实测值 | 判据 |
|---|---|---|
| 安装目录 | `D:\__soft\MAA` | ✅ |
| `MaaCore.dll` 自报版本 | **v6.17.5**（`AsstGetVersion()` 返回值） | ✅ 实测 |
| `MaaCore.dll` 文件时间 | 2026/9/9 21:49:10，5,761,024 字节 | ✅ |
| GUI（`MAA.dll`）自报版本 | **v6.17.5**（Built at 2026-09-10T05:50:42+08:00） | ✅ `debug\gui.log` |
| 目录内 `MAA-v6.14.1-win-x64.zip.temp` | 695,940 字节，2026/7/16，是一次**未完成/已过期**的更新包残留 | 🟡 推断 |
| `resource\version.json` | `last_updated: 2026-09-05 11:08:36.000`，活动「月行水上」 | ✅ |

> ⚠️ **副作用声明**：任务要求实测 `MAA.exe --help`。执行该命令时 MAA 的**自更新器被触发**，`MaaCore.dll` 由 v6.16.8（4,264,448 字节，Built Aug 11 2026）就地更新为 v6.17.5（5,761,024 字节）。本次分析未主动修改 `D:\__soft\MAA` 下任何文件，但 MAA 自身的更新器修改了它。下文导出表已按 **v6.17.5** 重新采集；需要区分时另行标注。
> ⚠️ 该更新同时把正在运行的 MAA GUI 进程一并拉起，分析结束后已终止（当前 `Get-Process MAA` 无残留）。

---

## 1. 任务描述格式（`resource/tasks/tasks.json` 的 schema）

### 1.1 文件布局（✅ 实测，`D:\__soft\MAA\resource\tasks\`）

```
resource\tasks\
├─ tasks.json                     5,876 行 / 177,862 B / 869 个任务定义   ← 主文件
├─ Stages\    base.json AD.json AS.json ... Supplies.json   (67 个文件)
├─ Roguelike\ base.json Phantom.json Mizuki.json Sami.json Sarkaz.json JieGarden.json routing.json
├─ RA\        Reclamation2.json Reclamation3.json plugin\base.json plugin\Tales.json
├─ MiniGame\  ALL.json AT.json OS.json PF.json SPA.json PixelPaint.json PV-Reproduction.json
│             InteractiveExhibition.json RebuildingMandate.json SecretFront.json
├─ UiTheme\   Depot.json Friends.json Gacha.json Infrast.json Mall.json OperBox.json
│             QuickSwitch.json Recruit.json SwitchTheme.json Task.json Terminal.json
└─ Copilot\   formation.json
```

**合计：79 个 `.json` 文件，3,295 条任务定义**（✅ 实测，脚本 `.tmp\analyze_tasks.py` / 统计脚本）。

> 注意：任务定义总数（3,295）> 实际可寻址任务数，因为存在 `baseTask` 派生任务与 `@` 型任务（隐式派生），它们会在加载期被展开。国服主文件 869 条是"直接定义"数。

### 1.2 全字段一览表

字段名 + 本地出现次数（79 文件合计，✅ 实测）+ 含义（来源：[MAA 官方《任务流程协议》](https://docs.maa.plus/zh-cn/protocol/task-schema.html)，已 web_fetch 全文）。

| 字段 | 出现次数 | 类型 | 含义 | 判据 |
|---|---:|---|---|---|
| `algorithm` | 942 | string | 识别算法：`JustReturn` / `MatchTemplate` / `OcrDetect` / `FeatureMatch`；**不填默认 `MatchTemplate`** | ✅ |
| `action` | 986 | string | `ClickSelf`(705) / `ClickRect`(147) / `DoNothing`(77) / `Swipe`(47) / `Stop`(10) / `Input`；**不填默认 `DoNothing`** | ✅ |
| `next` | 1,721 | array\<string\> | 当前任务+`sub` 执行完后要尝试的任务，**从前到后取第一个匹配上的**并执行 | ✅ |
| `sub` | 243 | array\<string\> | 子任务，当前任务完成后依次执行（推荐不使用） | ✅ |
| `subErrorIgnored` | 1 | bool | 是否忽略子任务错误，默认 `false` | ✅ |
| `exceededNext` | 65 | array\<string\> | 达到 `maxTimes` 上限后改走这里（否则停止） | ✅ |
| `onErrorNext` | 61 | array\<string\> | 出错后要执行的任务 | ✅ |
| `maxTimes` | 81 | int | 该任务最大执行次数，默认无穷大 | ✅ |
| `reduceOtherTimes` | 32 | array\<string\> | 执行后"扣减"其他任务的执行计数 | ✅ |
| `preDelay` | 108 | int(ms) | 识别到后延迟多久才执行 action，默认 0 | ✅ |
| `postDelay` | 467 | int(ms) | action 执行完后延迟多久才去识别 next，默认 0 | ✅ |
| `roi` | 1,288 | [x,y,w,h] | 识别范围，**以 1280×720 为基准自动缩放**；默认 `[0,0,1280,720]` | ✅ |
| `specificRect` | 263 | [x,y,w,h] | `ClickRect` 的点击区域 / `Swipe` 的起点；1280×720 基准 | ✅ |
| `rectMove` | 149 | [x,y,w,h] | 识别目标后的位移；`Swipe` 时必填=滑动终点；1280×720 基准 | ✅ |
| `specialParams` | 86 | array\<int\> | 特殊识别器参数。`Swipe` 时：`[0]`=duration，`[1]`=额外滑动方向(0 关/1上/2下/3左/4右)，`[2]`/`[3]`=缓入/缓出斜率(×10) | ✅ |
| `highResolutionSwipeFix` | 2 | bool | 高分辨率滑动修复，默认 false | ✅ |
| `cache` | 20 | bool | 是否缓存识别位置（第一次命中后固定），默认 false | ✅ |
| `baseTask` | 872 | string | 以该任务为模板派生（详见 1.4） | ✅ |
| `template` | 922 | string \| array | `MatchTemplate`/`FeatureMatch` 的模板图文件名，**默认 `"任务名.png"`**；在 `resource\template\` 下递归搜索 | ✅ |
| `templThreshold` | 267 | number \| array | 模板匹配阈值，**默认 0.8**（0~1） | ✅ |
| `maskRange` | 110 | array\<int,2\> | 灰度掩码范围，如 `[1,255]` 忽略涂黑部分 | ✅ |
| `method` | 60 | string \| array | 模板匹配算法：`Ccoeff`（默认，`cv::TM_CCOEFF_NORMED`）/ `RGBCount` / `HSVCount` | ✅ |
| `colorScales` | 65 | nested array | `method` 为 `HSVCount`/`RGBCount` 时必填的数色掩码范围 | ✅ |
| `colorWithClose` | 16 | bool | 数色时是否先用闭运算，默认 true | ✅ |
| `pureColor` | 2 | bool | 完全依赖颜色匹配、忽略模板得分，默认 false | ✅ |
| `text` | 639 | array\<string\> | `OcrDetect` **必填**，任一匹配即算识别到 | ✅ |
| `ocrReplace` | 86 | array\<[from,to]\> | OCR 常见错字替换（支持正则） | ✅ |
| `fullMatch` | 21 | bool | OCR 是否全字匹配，默认 false（子串即可） | ✅ |
| `replaceFull` | — | bool | ocrReplace 命中时是否替换整段文字，默认 false | ✅ 文档/二进制 |
| `isAscii` | 38 | bool | 待识别文字是否 ASCII，默认 false | ✅ |
| `withoutDet` | 23 | bool | 是否不使用检测模型，默认 false | ✅ |
| `useRaw` | 22 | bool | （`OcrDetect`+`withoutDet`）是否用原图匹配，默认 true | ✅ |
| `binThreshold` | 27 | [lower,upper] | 二值化灰度阈值，默认 `[140,255]` | ✅ |
| `inputText` | — | string | `algorithm=JustReturn` 且 `action=Input` 时必填 | ✅ 文档/二进制 |
| `count` | 5 | int | `FeatureMatch` 特征点数量阈值，默认 4 | ✅ |
| `ratio` | — | number | `FeatureMatch` KNN 距离比值，默认 0.6 | ✅ 文档/二进制 |
| `detector` | 4 | string | `FeatureMatch` 检测器：`SIFT`(默认)/`ORB`/`BRISK`/`KAZE`/`AKAZE`/`SURF` | ✅ |
| `Doc` / `doc` / `Doc2` / `maxTimesDoc` … | 502 + 352 + … | string | **纯注释字段**，不参与识别（命名不统一，仅为人读） | ✅ |

**任务列表字段支持表达式运算**（✅ 文档）：`@`（`@` 型任务）、`#`（虚任务）、`*`（重复）、`+`（合并）、`^`（差集）。
优先级：`#`(单目) > `@` = `#`(双目) > `*` > `+` = `^`。

### 1.3 ⚠️ 用户清单中"存在但实际不存在"的字段

对 `MaaCore.dll`（v6.16.8 与 v6.17.5）做全二进制字符串扫描（✅ 实测，`.tmp\` 内扫描脚本）：

| 用户提到的字段 | 本地实际 | 结论 |
|---|---|---|
| `roiOffset` | 0 次命中 | 🔴 **不存在**。请改用 `roi` + `rectMove` |
| `retryTimes` | 0 次命中 | 🔴 **不存在**。重试是**隐式**的：`next` 链中重复列自身即形成重试循环 |
| `onlyRecognition` | 0 次命中 | 🔴 **不存在**（详见 §4.5） |
| `replaceFullWidthChars` | 0 次命中 | 🔴 **不存在**。全角/半角处理由内部 OCR 常量 `FullWidthChars` 处理，非任务字段 |
| `ocr` | 0 次命中 | 🔴 不存在；字段名是 `text` |
| `threshold` | 仅在 `Infrast` **任务参数**（心情阈值 0.3）与 `binThreshold` 中出现 | 🟡 不是 tasks.json 字段 |
| `timeout` | 2 次命中，**上下文位于 copilot action 的键名列表中**（`...pre_delay..post_delay..rear_delay..timeout..doc_color..tool_men..distance..skip_if_not_ready..elapsed_time`） | 🟡 属**战斗流程（copilot）协议**，非 tasks.json 字段 |
| `MatchTemplateDetector` / `OcrDetector` / `ColorMatch` | 0 次命中 | 🔴 **不属 MAA Core**。这些是 **MaaFramework / MaaPipelineSupport** 的节点类型，与 MAA 任务系统是两套体系 |

补充：`MatchRect`（4 次命中）确实存在于二进制，但**未出现在官方 algorithm 文档列表中**，属内部类型名（`asst::MatchRect` / `asst::FeatureMatchRect` 结构体）。

### 1.4 特殊任务类型语义（✅ 文档）

- **派生任务**：带 `baseTask` 的任务。若是模板匹配任务，`template` 默认值仍为 `"任务名.png"`；若 `algorithm` 与基任务不同则**派生类参数不继承**；其余字段默认值 = 基任务字段值。
- **隐式 `@` 型任务**：形如 `B@A` 且未直接定义 → 继承 `A`，且列表型字段（`sub`/`next`/`onErrorNext`/`exceededNext`/`reduceOtherTimes`）自动加 `B@` 前缀。
- **虚任务**：`#none` / `#self` / `#back` / `#next` / `#sub` / `#on_error_next` / `#exceeded_next` / `#reduce_other_times`。
- **多文件**：后加载的同名任务若无 `baseTask` 则继承先加载者字段；若有 `baseTask` 则**直接覆盖**（可用 `"baseTask": "#none"` 阻断继承）。

### 1.5 代表性任务完整 JSON 片段（✅ 实测读取）

均取自 `D:\__soft\MAA\resource\tasks\tasks.json`，行号经 `Select-String` 定位。

**(a) `StartUp`（第 987 行）** — 典型的"反复确认主界面"循环任务：

```json
"StartUp": {
    "Doc": "有时候明明已经在主界面了，停了一小会又弹个窗。多检测几次，一直在主界面才算完成",
    "template": "SwitchTheme@ToggleSettingsMenu.png",
    "action": "DoNothing",
    "roi": [227, 327, 159, 152],
    "postDelay": 1000,
    "maxTimes": 3,
    "next": ["StartUp", "StartUp@LoadingText", "StartUp@CloseAnnos#next"]
}
```

**(b) `Fight`（第 1722 行）** — 只有 `sub` + `next`，识别部分交给子任务：

```json
"Fight": {
    "action": "DoNothing",
    "template": "SwitchTheme@ToggleSettingsMenu.png",
    "roi": [227, 327, 159, 152],
    "sub": ["Terminal-Entry"],
    "next": ["Fight@GoLastBattle", "Fight@CloseAnnos#next",
             "Fight@GoTerminalStopflag", "Fight@ReturnButtons#next"]
}
```

**(c) `BattleStart`（第 4226 行）** — `ClickSelf` 点击自身识别位置：

```json
"BattleStart": {
    "Doc": "base_task",
    "template": "empty.png",
    "action": "ClickSelf",
    "roi": [989, 318, 232, 374],
    "postDelay": 4000,
    "next": ["BattleOfficiallyBegin", "SkipThePreBattlePlot", "Stop"]
}
```

**(d) `BattleOperAvailable`（第 4516 行）** — 展示 `specialParams` + `rectMove`（无 action/next）：

```json
"BattleOperAvailable": {
    "template": "empty.png",
    "specialParams": [100],
    "specialParams_Doc": "用于做V通道平均值阈值",
    "rectMove": [0, 0, 10, 10]
}
```

**(e) copilot 相关：`Copilot@WaitUntilEndOfAction`（第 5205 行）** + **`Copilot@EndOfAction`（第 5233 行）**：

```json
"Copilot@WaitUntilEndOfAction": {
    "algorithm": "JustReturn",
    "maxTimes": 50,
    "exceededNext": ["Copilot@EndOfAction"],
    "next": ["Copilot@SkipThePreBattlePlot",
             "Copilot@EndOfAction",
             "Copilot@EndOfAction-Sandbox",
             "Copilot@FightMissionFailed",
             "Copilot@WaitUntilEndOfAction"]
},
"Copilot@EndOfAction": {
    "template": "EndOfAction.png",
    "reduceOtherTimes": [],
    "next": ["Copilot@StageDrops-Stars-3", "Copilot@StageDrops-Stars-Adverse"]
}
```

这是 `maxTimes` + `exceededNext` + 自递归 `next` 组成"轮询等待"的标准范式：最多等 50 次，每次 1 轮，超限转 `EndOfAction`。

`tasks.json` 中共有 **16 个 `Copilot@*` 任务**：`Copilot@FullStageNavigation`、`Copilot@StageNavigationSlowlySwipeLeft`、`Copilot@ChapterSwipeToTheRightAndPlot`、`Copilot@WaitUntilEndOfAction(-Bypass)`、`Copilot@SkipThePreBattlePlotConfirm`、`Copilot@EndOfAction(-Bypass)`、`Copilot@FightMissionFailed(-Bypass)`、`Copilot@StageDrops-Stars-3/Adverse`、`Copilot@EndOfAction-Sandbox`、`Copilot@ClickCornerUntilStartButton`、`Copilot@BattleStartPreFlag(-Return)`。
> 关键：**`Copilot` 本身不是 tasks.json 里的任务**，它是 C++ 层的 Task 类型（`asst::CopilotTask`），tasks.json 里只有它的 `@` 型派生辅助任务。

---

## 2. 任务流程控制机制

### 2.1 `algorithm` 取值集合（✅ 实测）

**本地 79 个任务文件的实测分布：**

| algorithm | 显式出现次数 |
|---|---:|
| `OcrDetect` | 376 |
| `JustReturn` | 543 |
| `MatchTemplate` | 20 |
| `FeatureMatch` | 3 |
| 未显式书写（继承 / 默认 `MatchTemplate`） | 2,353 |

**二进制内注册的算法名（`MaaCore.dll` 字符串扫描）：** `JustReturn`、`MatchTemplate`、`OcrDetect`、`FeatureMatch` —— 与官方文档完全一致，**没有** `MatchTemplateDetector` / `OcrDetector` / `ColorMatch` / `MatchRect`（作为算法名）。

**`action` 取值集合（实测）：** `ClickSelf`(705)、`ClickRect`(147)、`DoNothing`(77)、`Swipe`(47)、`Stop`(10)，另文档记载 `Input`（要求 `algorithm=JustReturn`）。

### 2.2 `next` 候选链的执行语义（✅ 文档 + ✅ 日志印证）

1. 任务 A 完成（含 `sub`）后，**按数组顺序**逐个尝试 `next` 中的任务；
2. 对每个候选执行其 `algorithm` 识别；**第一个识别成功的被选中并执行**，后面的不再尝试；
3. 都不成功 → 该候选链"空转"，通常回到上一层（日志里体现为 `to_be_recognized` 列表）。
4. **同名去重**：`["A","B","A","A"]` 归一化为 `["A","B"]`。
5. **`JustReturn` 型任务不允许出现在非最后一项**（因为它永远"匹配成功"）。
6. 不填 `next` → 当前任务执行完即停止该任务链。

日志实证（`D:\__soft\MAA\debug\asst.log`）：

```
[2025-12-29 15:52:39.446][INF][Px36668][Tx37153] {"class":"asst::ProcessTask","details":{"cur_retry":0,"retry_times":3,"to_be_recognized":["InfrastBottomLeftTab"]},"first":["InfrastBottomLeftTab"],"pre_task":"","subtask":"ProcessTask","taskchain":"Infrast","taskid":3}
```

`to_be_recognized` 就是当前正在轮询识别的候选集，`retry_times: 3` 是**内部固有重试**（3 次），并非任务字段。

### 2.3 失败重试 / 超时语义

| 机制 | 语义 | 判据 |
|---|---|---|
| `maxTimes` | 该任务累计执行次数上限；达到后走 `exceededNext`，否则停止 | ✅ |
| `exceededNext` | 超限后的去向 | ✅ |
| `onErrorNext` | 执行出错后的去向 | ✅ |
| `reduceOtherTimes` | **"扣减"其他任务的执行计数**。典型用途：用了理智药说明"点击开始行动"那次其实没生效，于是让 `StartButton2` 计数 −1 | ✅ 文档 |
| `retryTimes` | 🔴 **不存在**。重试靠 `next` 自递归 + `maxTimes` 实现（见 §1.5(e)） | 🔴 |
| `timeout` | 🔴 **tasks.json 无此字段**；仅 `copilot` action 有 `timeout`（毫秒，-1 不限） | 🟡 |
| 内部重试 | `ProcessTask` 内部对候选集做 `retry_times`（实测=3）次识别 | ✅ 日志 |

`maxTimes` 到限时会**先回传一条回调**（✅ 实测日志，`what = ExceededLimit`）：

```
[2026-02-17 03:45:57.883][INF][Px1420][Tx30420] Assistant::append_callback | SubTaskExtraInfo {"class":"asst::ProcessTask","details":{"exec_times":2,"max_times":2,"task":"CloseStonePage"},"first":["FightBegin"],"pre_task":"Fight@UseMedicine","subtask":"ProcessTask","taskchain":"Fight","taskid":4,"uuid":"a039090c57c2337d","what":"ExceededLimit"}
```

### 2.4 `roi` 坐标基准 = **1280×720**（✅ 三重证据）

**(1) 官方文档**：`"roi": [0, 0, 1280, 720], // 以 1280 * 720 为基准自动缩放`。

**(2) 运行日志中 roi 与截图的比值**（`asst.log`）：
```
[2025-12-29 15:52:37.344][TRC][Px36668][Tx37153] multi_match |  result: [{ rect: [ 119, 290, 71, 63 ], score: 0.982303 }, { rect: [ 43, 365, 71, 63 ], score: 0.950307 }] roi: [ 0, 240, 640, 400 ]
```
`roi` 的高度 400、宽度 640 —— 都在 1280×720 空间内，而设备实际是 1920×1080。

**(3) 坐标缩放日志（决定性）**：
```
[2025-12-29 15:52:35.977][TRC][Px36668][Tx37153] Swipe with scaled coordinates (132, 389) (1153, 376) 1.5
[2025-12-29 15:52:35.977][TRC][Px36668][Tx37153] minitouch swipe (198, 583) (1729, 564) 150 0 1 1
[2025-12-29 15:52:40.448][TRC][Px36668][Tx37153] Click with scaled coordinates (0, 719) 1.5
[2025-12-29 15:52:40.448][TRC][Px36668][Tx37153] minitouch click: (0, 1078)
```

算术核对：`132 × 1.5 = 198` ✅，`389 × 1.5 = 583.5 → 583` ✅，`1153 × 1.5 = 1729.5 → 1729` ✅，`376 × 1.5 = 564` ✅，`719 × 1.5 = 1078.5 → 1078` ✅。
**缩放系数 1.5 = 1920/1280 = 1080/720**，设备为 1920×1080，点击坐标上限 719/1078 对应 720 高的底边。

**结论（✅）**：MAA **先把截图归一化到 1280×720 再匹配，然后把结果坐标乘以 `实际宽度/1280` 再下发点击**。所以任务里写 `roi`/`specificRect`/`rectMove` 一律用 1280×720 坐标。

### 2.5 `template` 匹配默认阈值

**0.8**（✅ 官方文档：`"templThreshold": 0.8, // 可选项，图片模板匹配得分的阈值…默认 0.8`）。本地 267 处显式 `templThreshold`。日志里可直接看到得分：

```
result: [{ rect: [ 119, 290, 71, 63 ], score: 0.982303 }, { rect: [ 43, 365, 71, 63 ], score: 0.950307 }]
Assistant::append_callback | SubTaskStart {"class":"asst::ProcessTask","details":{"action":"DoNothing","algorithm":"MatchTemplate","exec_times":1,"max_times":2147483647,"result":{"rect":[290,391,29,24],"score":0.993911,"template":"SwitchTheme@ToggleSettingsMenu.png"},"task":"SpecialAccessActivitiesReturnHome"}, ...}
```

---

## 3. copilot（作业）JSON 格式

### 3.1 Schema（来源：[MAA《战斗流程协议》](https://docs.maa.plus/zh-cn/protocol/copilot-schema.html)，已 web_fetch 全文）

`resource/copilot/*.json`。**顶层字段：**

| 字段 | 必填 | 说明 |
|---|---|---|
| `stage_name` | ✅ | 关卡名（中文名 / code / stageId / levelId 任一唯一即可） |
| `opers` | — | 指定干员数组 |
| `groups` | — | 干员组（任选其一，优先练度高） |
| `actions` | ✅（常规作业） | 有序操作数组 |
| `minimum_required` | ✅ | 最低 MAA 版本，如 `"v6.7.0"` |
| `doc` | — | `{title, title_color, details, details_color}` |
| `difficulty` | — | 0 未设置 / 1 普通 / 2 突袭 / 3 两者 |
| `type` | 🟡（SSS 作业用） | `"SSS"`；本地 73/74 个文件有 |
| `buff` `equipment` `strategy` `tool_men` `drops` `blacklist` `stages` | 🟡 | **保全派驻（SSS）协议**专用，本地 73 个文件都有 |

**`opers[]` / `groups[].opers[]` 元素**（✅ 本地 293 次实测）：`name`(293)、`skill`(293)、`skill_usage`(293)、`skill_times`(20)，另文档有 `role`、`requirements{elite, level, skill_level, module, module_level, potential}`。

**`actions[]` 元素**（✅ 源码 `CopilotConfig.cpp::parse_actions` 全文已读）：

| 键 | 说明 |
|---|---|
| `type` | `Deploy`/`部署`、`Skill`/`技能`、`Retreat`/`撤退`、`SpeedUp`/`二倍速`、`BulletTime`/`子弹时间`、`SkillUsage`/`技能用法`、`Output`/`打印`、`SkillDaemon`/`摆完挂机`、`MoveCamera`/`移动镜头`、`DrawCard`/`抽卡`、`CheckIfStartOver`/`检查重开`、`ResetStopwatch`/`重置全局计时器`、`Click`/`点击`、`Swipe`/`滑动`（大小写不敏感，中英皆可） |
| `name` | 干员名 或 群组名 |
| `role` | 干员职业（英文，区分同名干员） |
| `location` | `[x, y]` 战场格坐标，`[0,0]` 为合法左上格 |
| `rect` | `[x,y,w,h]` **720p 基准像素矩形**（`Click` 用，与 `location` 至少填一，同填优先 `rect`） |
| `direction` | `Left`/`Right`/`Up`/`Down`/`None` 或 `左/右/上/下/无`（默认 Right） |
| `kills` / `costs` / `cost_changes` / `cooling` / `elapsed_time` | 执行条件（**且**关系）：击杀数 / 费用 / 费用变化量 / CD 中干员数 / 全局计时(ms) |
| `skill_usage` / `skill_times` | 修改技能用法 / 次数（`skill_usage`: 0 不自动、1 好了就用、2 用 X 次、3 自动判断） |
| `pre_delay` / `post_delay` / `rear_delay`(遗留) | 前置/后置延时(ms) |
| `timeout` | 超时(ms)，默认 -1 不限；`0` 表示只检查一次 |
| `distance` / `keep_kills` | `MoveCamera` 的镜头位移格数 / 是否不归零击杀 |
| `begin` / `end` / `duration` / `extra_swipe` / `slope_in` / `slope_out` / `with_pause` / `high_resolution_swipe_fix` | `Swipe` 专用，语义与 tasks.json 的 `special_params[0..3]` 一致 |
| `doc` / `doc_color` | 注释与显示颜色（无实际作用） |
| `skip_if_not_ready` | **已废弃**，用 `timeout: 0` 代替 |

### 3.2 本地真实作业样例（✅ 完整读取）

**文件：`D:\__soft\MAA\resource\copilot\OF-1_credit_fight.json`**（1,597 字节，唯一的非 SSS 常规作业）：

```json
{
    "minimum_required": "v4.0.0",
    "actions": [
        { "type": "SpeedUp" },
        { "type": "Deploy", "name": "先锋", "location": [5, 3], "direction": "Right" },
        { "type": "SkillDaemon" }
    ],
    "doc": { "title": "OF-1 Credit Fight", "details": "OF-1 Credit Fight" },
    "groups": [
        {
            "name": "先锋",
            "opers": [
                { "name": "推进之王", "skill": 2 },
                { "name": "风笛", "skill": 2 },
                { "name": "凛御银灰", "skill": 3, "skill_usage": 1 },
                { "name": "焰尾" },
                { "name": "德克萨斯", "skill": 2, "skill_usage": 1 },
                { "name": "凛冬" }, { "name": "贾维" }, { "name": "清道夫" },
                { "name": "讯使" }, { "name": "芬" }, { "name": "香草" }
            ]
        }
    ],
    "opers": [],
    "stage_name": "OF-1"
}
```

**本地 74 个作业文件的实测统计**（✅）：
- 顶层键：`minimum_required`(74), `doc`(74), `opers`(74), `stage_name`(74), `type`(73), `buff`(73), `equipment`(73), `strategy`(73), `tool_men`(73), `drops`(73), `blacklist`(73), `stages`(73), `actions`(29), `groups`(29)
- `type` 取值：`SSS` × 73，无 `type` × 1
- 目录结构示例：`resource\copilot\old\阿卡胡拉丛林_Acahuallan_Jungle\SSS_阿卡胡拉丛林.json`（24 KB 级保全作业）

> **`deploy` 字段说明**：作业协议里**没有** `deploy` 这个键；部署是 `actions[]` 中 `{"type": "Deploy", "name", "location", "direction"}` 这一条。`cost` 也**不是** `Deploy` 的字段，费用条件是 `costs` / `cost_changes`。用户清单中的 `deploy.location/name/direction/cost` 应理解为上述两处。

---

## 4. ★ 步进驱动能力（最关键）

### 4.1 `MAA.exe` 命令行参数 —— **无 CLI**（✅ 实测）

**实测命令与结果：**

```powershell
Start-Process -FilePath "D:\__soft\MAA\MAA.exe" -ArgumentList "--help" `
  -RedirectStandardOutput "$env:TEMP\maa_out.txt" -RedirectStandardError "$env:TEMP\maa_err.txt"
```

实测输出：
```
Process running: False  Id=80872
--- stdout size: 0 ---
--- stderr size: 0 ---
   Id ProcessName MainWindowTitle
79484 MAA         MAA - v6.17.5#0910 - 月行水上#0905 - MuMu 模拟器 (16384) - 官服
```

**结论（✅ 高置信）**：
1. `MAA.exe` **是纯 GUI 程序**（Avalonia/WPF 单实例），`--help` **不产生任何 stdout/stderr（均为 0 字节）**；
2. 它把 `--help` 当作**普通启动参数透传给 `MAA.dll`**，日志留痕：`Command Line: D:\__soft\MAA\MAA.dll --help`（`debug\gui.log`）；
3. 单实例机制：检测到已有实例就发激活信号并退出（`gui.log`: `Secondary launch detected, activation signal sent to existing instance` / `Shutdown called by OnStart`）。
4. **因此：不能用 `MAA.exe` 做步进驱动。必须直接用 `MaaCore.dll`。**

### 4.2 `MaaCore.dll` 导出函数完整清单（✅ 实测 PE 导出表解析）

用自写 PE 解析脚本（纯 `struct`，无第三方依赖，`.tmp\pe_exp2.py`）解析导出表：v6.16.8 与 v6.17.5 均为 **Base=1、NumberOfFunctions=NumberOfNames=33**，且**两版导出名完全一致**。

| Ord | v6.17.5 RVA | 函数名 |
|---:|---|---|
| 1 | 0x00112DE0 | `??0IScreenShotClass@@QEAA@AEBV0@@Z` (C++ 内部) |
| 2 | 0x00112DE0 | `??0IScreenShotClass@@QEAA@XZ` |
| 3 | 0x00113E20 | `??1IScreenShotClass@@UEAA@XZ` |
| 4 | 0x0001F7D0 | `??4IScreenShotClass@@QEAAAEAV0@AEBV0@@Z` |
| 5 | 0x0046D8B0 | `??_7IScreenShotClass@@6B@` |
| 6 | 0x0004B080 | **`AsstAppendTask`** |
| 7 | 0x0004B1E0 | **`AsstAsyncAttachWindow`** |
| 8 | 0x0004B260 | **`AsstAsyncClick`** |
| 9 | 0x0004B2B0 | **`AsstAsyncConnect`** |
| 10 | 0x0004B560 | **`AsstAsyncScreencap`** |
| 11 | 0x0004B5B0 | `AsstAttachWindow` (deprecated) |
| 12 | 0x0004B7D0 | **`AsstBackToHome`** |
| 13 | 0x0004B810 | `AsstConnect` (deprecated，已被异步连接取代) |
| 14 | 0x0004BC10 | **`AsstConnected`** |
| 15 | 0x0004BC50 | **`AsstCreate`** |
| 16 | 0x0004BCB0 | **`AsstCreateEx`** ← 注册回调的唯一入口 |
| 17 | 0x0004BD30 | `AsstDestroy` |
| 18 | 0x0004BD50 | **`AsstGetImage`** |
| 19 | 0x0004BE50 | **`AsstGetImageBgr`** |
| 20 | 0x0004BF50 | `AsstGetNullSize` |
| 21 | 0x0004BF60 | **`AsstGetTasksList`** |
| 22 | 0x0004C070 | **`AsstGetUUID`** |
| 23 | 0x0004C170 | `AsstGetVersion` |
| 24 | 0x0004C180 | `AsstLoadResource` |
| 25 | 0x0004C450 | `AsstLog` |
| 26 | 0x0004C5D0 | `AsstRunning` |
| 27 | 0x0004C610 | `AsstSetConnectionExtras` |
| 28 | 0x0004C9D0 | **`AsstSetInstanceOption`** |
| 29 | 0x0004CA90 | `AsstSetStaticOption` |
| 30 | 0x0004CB30 | **`AsstSetTaskParams`** |
| 31 | 0x0004CC20 | `AsstSetUserDir` |
| 32 | 0x0004CDC0 | **`AsstStart`** |
| 33 | 0x0004CE00 | `AsstStop` |

**注意**：**没有** `AsstSetCallback` —— 回调是在 `AsstCreateEx(callback, custom_arg)` 里一次性注册的。
**注意**：v6.17.0 release note 声称新增 `AsstCallerExtra` 扩展 C 接口，但在本机 v6.17.5 的 `MaaCore.dll` 导出表中**未出现**，全部 DLL 字符串扫描亦未命中 `AsstCallerExtra`（🔴 未查明其载体；可能是独立头文件/编译期别名，未单独导出）。

**对照 `include/AsstCaller.h`（✅ 已 web_fetch `dev-v2` 版本全文）**，签名如下：

```c
typedef void(ASST_CALL* AsstApiCallback)(AsstMsgId msg, const char* details_json, void* custom_arg);

AsstHandle ASSTAPI AsstCreate(void);
AsstHandle ASSTAPI AsstCreateEx(AsstApiCallback callback, void* custom_arg);
void       ASSTAPI AsstDestroy(AsstHandle handle);
AsstTaskId ASSTAPI AsstAppendTask(AsstHandle, const char* type, const char* params);
AsstBool   ASSTAPI AsstSetTaskParams(AsstHandle, AsstTaskId id, const char* params);
AsstBool   ASSTAPI AsstStart(AsstHandle);
AsstBool   ASSTAPI AsstStop(AsstHandle);
AsstBool   ASSTAPI AsstRunning(AsstHandle);
AsstBool   ASSTAPI AsstConnected(AsstHandle);
AsstBool   ASSTAPI AsstBackToHome(AsstHandle);
AsstAsyncCallId ASSTAPI AsstAsyncConnect(AsstHandle, const char* adb_path, const char* address, const char* config, AsstBool block);
AsstAsyncCallId ASSTAPI AsstAsyncAttachWindow(AsstHandle, void* hwnd, uint64_t screencap_method, uint64_t mouse_method, uint64_t keyboard_method, AsstBool block);
AsstAsyncCallId ASSTAPI AsstAsyncClick(AsstHandle, int32_t x, int32_t y, AsstBool block);
AsstAsyncCallId ASSTAPI AsstAsyncScreencap(AsstHandle, AsstBool block);
AsstSize ASSTAPI AsstGetImage(AsstHandle, void* buff, AsstSize buff_size);
AsstSize ASSTAPI AsstGetImageBgr(AsstHandle, void* buff, AsstSize buff_size);
AsstSize ASSTAPI AsstGetUUID(AsstHandle, char* buff, AsstSize buff_size);
AsstSize ASSTAPI AsstGetTasksList(AsstHandle, AsstTaskId* buff, AsstSize buff_size);
```

**`AsstAsyncClick` + `AsstAsyncScreencap` + `AsstGetImage` 就是"先看再点"的原语**（见 §4.6）。

### 4.3 回调 / 事件机制 —— "读回结果"的正规通道（✅ 实测 + ✅ 文档）

`AsstMsgId` 枚举（来源：[MAA《回调消息协议》](https://docs.maa.plus/zh-cn/protocol/callback-schema.html)）：

```cpp
enum class AsstMsg {
    /* Global Info */
    InternalError     = 0,      InitFailed        = 1,
    ConnectionInfo    = 2,      AllTasksCompleted = 3,
    AsyncCallInfo     = 4,      Destroyed         = 5,
    /* TaskChain Info */
    TaskChainError     = 10000, TaskChainStart     = 10001,
    TaskChainCompleted = 10002, TaskChainExtraInfo = 10003,
    TaskChainStopped   = 10004,
    /* SubTask Info */
    SubTaskError      = 20000,  SubTaskStart      = 20001,
    SubTaskCompleted  = 20002,  SubTaskExtraInfo  = 20003,
    SubTaskStopped    = 20004,
    /* Web Request */
    ReportRequest     = 30000,
};
```

本地 `Python\asst\utils.py` 第 20–60 行的 `Message` 枚举与之逐项对应（✅ 已读）。

**`details_json` 结构（实测日志直接给出）：**

```
TaskChainStart     {"taskchain":"StartUp","taskid":1,"uuid":""}
TaskChainCompleted {"taskchain":"Award","taskid":6,"uuid":"a039090c57c2337d"}
TaskChainError     {"taskchain":"Fight","taskid":4,"uuid":"a039090c57c2337d"}
AllTasksCompleted  {"finished_tasks":[1,2,3,4,5,6],"taskchain":"Award","taskid":6,"uuid":"a039090c57c2337d"}
SubTaskStart       {"class":"asst::ProcessTask","details":{"action":"DoNothing","algorithm":"MatchTemplate",
                    "exec_times":1,"max_times":2147483647,
                    "result":{"rect":[290,391,29,24],"score":0.993911,"template":"SwitchTheme@ToggleSettingsMenu.png"},
                    "task":"SpecialAccessActivitiesReturnHome"},
                    "first":["SpecialAccessActivitiesBegin"],"pre_task":"SpecialAccessActivitiesBegin",
                    "subtask":"ProcessTask","taskchain":"Award","taskid":6,"uuid":"a039090c57c2337d"}
SubTaskExtraInfo   {... "what":"SanityBeforeStage","details":{"current_sanity":16,"max_sanity":180,...}}
AsyncCallInfo      {"async_call_id":1,"details":{"cost":0,"ret":false},"uuid":"","what":"Screencap"}
Destroyed          {}
```

判定要点：
- **`TaskChainCompleted` / `TaskChainError` 就是"一个任务链跑完了"的同步点** —— 外部程序收到它就等于"这一步结束了"。
- **`SubTaskCompleted` 的 `details.result` 携带识别结果**（`rect` / `score` / `template` / OCR 文本），这就是"读回识别结果"。
- **`SubTaskExtraInfo` 的 `what` 字段**是业务语义通道（`StageDrops` 掉落、`RecruitResult` 公招结果、`DepotInfo` 仓库识别、`OperBoxInfo` 干员 box、`StageInfo` 关卡信息、`ExceededLimit` 次数超限…）。

**本报告独立实测（✅ 决定性）**：用 ctypes 直接加载 DLL，注册 `AsstCreateEx` 回调，**在不连接任何设备的情况下**调用 `AsstAsyncScreencap` / `AsstAsyncClick`，回调**确实被同步触发**：

```
== AsstGetVersion == v6.16.8
== AsstSetUserDir == 1
== AsstLoadResource == 1 cost 252 ms
== AsstCreateEx handle == 0x24b51af5c60
== AsstConnected (no device) == 0
== AsstAppendTask(StartUp) -> taskid 1
== AsstAppendTask(Fight) -> taskid 2
== AsstAppendTask(SingleStep) -> taskid 3
== AsstGetTasksList -> 3, ids=[1, 2, 3]
== AsstSetTaskParams(id=2, {'times':5}) == 1
== AsstAsyncScreencap -> 1
== AsstAsyncClick(640,360) -> 2
[CALLBACK] msg=4 details={"async_call_id":1,"details":{"cost":0,"ret":false},"uuid":"","what":"Screencap"}
== AsstStop == 1
[CALLBACK] msg=4 details={"async_call_id":2,"details":{"cost":0,"ret":false},"uuid":"","what":"Click"}
[CALLBACK] msg=5 details={}
== DONE, 3 callbacks ==
```

（`ret:false` 是因为没有连接设备；`cost:0` 是异步调用耗时。回调链路本身完全通。）

### 4.4 Python 绑定（✅ 本地文件已读全文）

**本地自带官方 Python 绑定：`D:\__soft\MAA\Python\`**

```
Python\sample.py            4,291 B / 122 行   ← 官方示例
Python\asst\asst.py        10,611 B / 340 行   ← ctypes 绑定主实现
Python\asst\utils.py        1,172 B /  73 行   ← JSON 类型别名、InstanceOptionType、Message 枚举
Python\asst\emulator.py     1,938 B            ← 蓝叠多开辅助
Python\asst\updater.py     10,362 B            ← 资源/程序更新
Python\asst\downloader.py   7,226 B
Python\asst\__init__.py        52 B
```

`asst.py` 关键接口（行号已核）：

| 方法 | 行号 | 说明 |
|---|---:|---|
| `Asst.load(path, incremental_path=None, user_dir=None)` | 26–82 | 静态方法。`ctypes.WinDLL(MaaCore.dll)` → 设 `PATH` → `AsstSetUserDir` → `AsstLoadResource` |
| `Asst.__init__(callback=None, arg=None)` | 84–94 | 有 callback 走 `AsstCreateEx`，否则 `AsstCreate` |
| `set_instance_option(option_type, option_value)` | 100–113 | `AsstSetInstanceOption` |
| `connect(adb_path, address, config="General")` | 130–146 | `AsstConnect` |
| `get_image(size) -> bytes \| None` | 148–162 | `AsstGetImage`，**需自己传字节数，如 `1280*720*3`** |
| `append_task(type_name, params={}) -> TaskId` | 178–192 | `AsstAppendTask` |
| `set_task_params(task_id, params) -> bool` | 194–206 | `AsstSetTaskParams` |
| `start()` / `stop()` / `running()` | 208–230 | `AsstStart` / `AsstStop` / `AsstRunning` |
| `get_version() -> str` | 244–250 | |

回调类型定义（第 13–15 行）：
```python
CallBackType = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_char_p, ctypes.c_void_p)
```

`utils.py` 的 `InstanceOptionType`：`touch_type=2`、`deployment_with_pause=3`、`adblite_enabled=4`、`kill_on_adb_exit=5`（⚠️ 本地这份是**旧版**，缺少新版的 `ClientType=6`）。

`sample.py` 第 114–118 行的注释给出了 `Copilot` / `Custom` 任务的用法样例：
```python
# asst.append_task('Copilot', {'filename': './GA-EX8-raid.json', 'formation': False})
# asst.append_task('Custom', {"task_names": ["AwardBegin"]})
```

> ⚠️ **该绑定未封装 `AsstAsyncClick` / `AsstAsyncScreencap` / `AsstGetUUID` / `AsstBackToHome` / `AsstGetTasksList` / `AsstAsyncAttachWindow`**，需要自己 ctypes 补。

### 4.5 是否支持"只识别不操作"（dry-run）

**结论：`tasks.json` 层没有 `onlyRecognition` / dry-run 字段**（🔴 0 次命中，见 §1.3）。

但**可以通过三种方式达成"先看再点"**：

1. **`Custom` 任务 + 只含识别任务的 `task_names`**（✅ 实测可 append 成功）：
   `{"task_names": ["AwardBegin"]}` —— 因为 `action` 可以是 `DoNothing`，识别成功也不点。MAA 内置大量 `action: DoNothing` 的纯识别任务（本地实测 **77 处**），例如 `StartUp`、`Fight`、`Copilot@WaitUntilEndOfAction`。
2. **`action: DoNothing` + 回调读 `result`**：识别结果通过 `SubTaskCompleted.details.result` 回传（`rect`/`score`/`template` 或 OCR 文本），外部程序据此决定下一步。
3. **`AsstAsyncScreencap` + `AsstGetImage` + `AsstAsyncClick` 完全绕开任务系统**：自己截图 → 自己识别 → 自己点击。这是最彻底的 dry-run（§4.6）。`AsstAsyncScreencap`/`AsstAsyncClick` 的 `block` 参数设为 1 即同步阻塞。

### 4.6 ★★ `SingleStep` 单步任务 —— MAA 官方的原生步进接口

**这是本次调查最重要的发现。** MAA 有一个**官方 Task 类型 `SingleStep`**（"单步任务（目前仅支持战斗）"），且在 `MaaCore.dll` 内**确实存在**（✅ 字符串扫描 12 次命中；✅ 源码已读）。

**官方文档 schema：**

| 字段 | 说明 |
|---|---|
| `type` | 目前仅支持 `"copilot"`（默认值也是 `copilot`） |
| `subtype` | `stage` — 设置关卡名，`details: {"stage_name": "xxxx"}`；<br>`start` — 开始作战，无 `details`；<br>`action` — 单步作战操作，`details` 为战斗协议中的单个 action |
| `details` | 子任务详细参数 |

**⚠️ 官方文档的 `action` 示例是错的。** 源码 `src/MaaCore/Task/Interface/SingleStepTask.cpp`（✅ 已 web_fetch 全文）：

```cpp
bool asst::SingleStepTask::set_params(const json::value& params)
{
    std::string type = params.get("type", "");
    std::string subtype = params.get("subtype", "");
    auto details_opt = params.find("details");
    if (type == "copilot") {
        if (subtype == "stage" && details_opt)      return set_copilot_stage(*details_opt);
        else if (subtype == "start")                return append_copllot_start();
        else if (subtype == "action" && details_opt) return append_copilot_action(*details_opt);
    }
    return false;
}

bool asst::SingleStepTask::append_copilot_action(const json::value& details)
{
    auto task = std::make_shared<SingleStepBattleProcessTask>(m_callback, m_inst, TaskType);
    // 请参考自动战斗协议
    auto actions_opt = CopilotConfig::parse_actions(details);   // ← 注意这里
    ...
}
```

而 `CopilotConfig::parse_actions`（✅ 已读全文）第一行是：

```cpp
for (const auto& action_info : json.at("actions").as_array()) {
```

⇒ **`details` 必须是 `{"actions": [ <单个 action> ]}`，而不是文档示例里的裸 action 对象。**

**本报告实测验证（✅ 决定性）** —— 对照实验：

```
# 文档示例形式（裸 action）—— 全部失败，返回 taskid=0
no-type            -> 0
with-Deploy        -> 0
Deploy-EN          -> 0
obj-SpeedUp        -> 0
obj-二倍速          -> 0
obj-SkillDaemon    -> 0
array-1-Deploy     -> 0

# 正确形式（actions 数组包裹）—— 全部成功
W1 wrap-SpeedUp    -> taskid=1
W2 wrap-Deploy     -> taskid=2
W3 wrap-Retreat    -> taskid=3
W4 wrap-2steps     -> taskid=4
W5 wrap-Click      -> taskid=5
W6 wrap-Skill      -> taskid=6
```

对应源码级报错（`asst.log`）：
```
[ERR] asst::SingleStepTask::append_copilot_action invalid map<K, T> key
[ERR] asst::Assistant::append_task | invalid params: {"type": "copilot", "subtype": "action", "details": {"type": "Deploy", ...}}
```

**提交单步后，MAA 会以 `taskchain: "SingleStep"` 发起任务链，并通过标准回调回传每次 `SubTaskStart/Completed` 与 `SubTaskExtraInfo`** ⇒ 外部程序可以"发一步 → 等回调 → 再发下一步"。这就是原生的逐步驱动通道（✅ 文档列出 `SingleStep` 任务链名；🟡 "每次 append 只走一步"这点未在真机连设备验证，因为本机未连接模拟器）。

**另一条更底层的路（✅ 实测回调可用）**：`AsstAsyncScreencap` → `AsstGetImage` → `AsstAsyncClick`，完全绕过任务系统，**每一步都由外部程序控制**。

### 4.7 日志格式（✅ 实测）

存在两个日志文件（`D:\__soft\MAA\debug\`）：

| 文件 | 大小 | 最后写入 | 来源 |
|---|---:|---|---|
| `asst.log` | 56,377,911 B | 2026/9/23 21:22:09 | **MaaCore**（C++） |
| `asst.bak.log` | 67,108,881 B | 2025/12/29 | 轮转备份 |
| `gui.log` | 3,133,059 B | 2026/9/23 21:21:06 | **GUI**（C#） |
| `gui.bak.log` | 4,200,554 B | 2025/12/26 | 轮转备份 |
| `drops/` `interface/` `map/` `other/` `recruit/` `roguelike/` | — | — | 调试图片，命名 `2026.02.14-11.04.42.536_raw.png` |

**行格式（✅ 实测，两种略有差异）：**

```
# MaaCore（asst.log）—— 4 段
[<yyyy-MM-dd HH:mm:ss.fff>][<lvl>][Px<pid>][Tx<tid>] <message>

# GUI（gui.log）—— 3 段 + 模块名
[<yyyy-MM-dd HH:mm:ss.fff>][<lvl>][<Module>] <线程id> <message>
```

级别：`TRC` / `INF` / `WRN` / `ERR`（`utils.py` 里也有 `Message`/等级概念；`AsstLog(level, message)` 可写自定义日志）。

**实测头部（该文件由本报告在 `.tmp\maauser\debug\asst.log` 生成，行号精确）：**

```
   1: [2026-09-23 21:25:17.319][TRC][Px97028][Tx6089] -----------------------------
   2: [2026-09-23 21:25:17.319][TRC][Px97028][Tx6089] MaaCore Process Start
   3: [2026-09-23 21:25:17.319][TRC][Px97028][Tx6089] Version v6.16.8
   4: [2026-09-23 21:25:17.319][TRC][Px97028][Tx6089] Built at Aug 11 2026 12:08:01
   5: [2026-09-23 21:25:17.319][TRC][Px97028][Tx6089] User Dir C:\Users\23922\Documents\ds_harness\ak\.tmp\maauser
   6: [2026-09-23 21:25:17.319][TRC][Px97028][Tx6089] -----------------------------
   7: [2026-09-23 21:25:17.319][TRC][Px97028][Tx6089] asst::ResourceLoader::load | enter
   8: [2026-09-23 21:25:17.335][TRC][Px97028][Tx6089] asst::OnnxSessions::load | enter
   ...
 205: [2026-09-23 21:25:17.569][ERR][Px97028][Tx6089] asst::Controller::inited | m_controller is not inited
 206: [2026-09-23 21:25:17.569][INF][Px97028][Tx6089] asst::Assistant::append_task StartUp {"client_type": "Official"}
 211: [2026-09-23 21:25:17.569][INF][Px97028][Tx6089] asst::Assistant::append_task | task_id: 1
 223: [2026-09-23 21:25:17.569][INF][Px97028][Tx6089] asst::Assistant::append_task Copilot {"filename": "copilot/OF-1_credit_fight.json", "formation": false}
 227: [2026-09-23 21:25:17.569][ERR][Px97028][Tx6089] asst::CopilotConfig asst::AbstractConfig::load file does not exist copilot/OF-1_credit_fight.json
 230: [2026-09-23 21:25:17.569][ERR][Px97028][Tx6089] asst::Assistant::append_task | invalid params: {"filename": "copilot/OF-1_credit_fight.json", "formation": false}
 238: [2026-09-23 21:25:17.569][INF][Px97028][Tx6089] asst::Assistant::append_task | task_id: 3
```

**生产日志（`D:\__soft\MAA\debug\asst.log`）真实关键行：**

```
[2026-09-23 21:23:29.815][INF][Px82192][Tx4605] Assistant::append_callback | TaskChainStart {"taskchain":"StartUp","taskid":1,"uuid":""}
[2026-02-17 03:45:59.797][INF][Px1420][Tx30420] Assistant::append_callback | TaskChainCompleted {"taskchain":"Fight","taskid":4,"uuid":"a039090c57c2337d"}
[2026-02-14 11:04:42.560][INF][Px16312][Tx12992] Assistant::append_callback | TaskChainError {"taskchain":"Fight","taskid":4,"uuid":"a039090c57c2337d"}
[2026-02-17 03:48:25.931][INF][Px1420][Tx30420] Assistant::append_callback | AllTasksCompleted {"finished_tasks":[1,2,3,4,5,6],"taskchain":"Award","taskid":6,"uuid":"a039090c57c2337d"}
[2025-12-29 15:52:37.344][TRC][Px36668][Tx37153] multi_match |  result: [{ rect: [ 119, 290, 71, 63 ], score: 0.982303 }, { rect: [ 43, 365, 71, 63 ], score: 0.950307 }] roi: [ 0, 240, 640, 400 ]
[2025-12-29 15:52:35.977][TRC][Px36668][Tx37153] Swipe with scaled coordinates (132, 389) (1153, 376) 1.5
[2025-12-29 15:52:36.328][TRC][Px36668][Tx37153] asst::ProcessTask::run | leave, 352 ms
[2025-12-29 15:52:37.062][INF][Px36668][Tx37153] Call ` D:\__soft\MuMu Player 12\shell\adb.exe -s 127.0.0.1:16384 exec-out "screencap | gzip -1" ` ret 0 , cost 232 ms , stdout size: 1338984 , socket size: 0
[2026-09-23 21:23:34.885][TRC][Px82192][Tx4605] asst::WordOcr [{ text: ., rect: [ 0 (324), 0 (579), 219, 141 ], score: 0.940320 }] by OCR Pipeline , cost 8 ms
```

日志行类型速查：
- **任务链层**：`Assistant::append_callback | TaskChainStart/Completed/Error ...` ← 每行都是**回调的原始 JSON**，等价于"日志即事件流"
- **任务层**：`asst::Assistant::append_task <Type> <params-json>` + `asst::Assistant::append_task | task_id: N`
- **识别层**：`multi_match |  result: [{ rect, score }] roi: [...]`、`asst::WordOcr [{ text, rect, score }] by OCR Pipeline , cost N ms`
- **输入层**：`Click with scaled coordinates (x, y) <scale>`、`minitouch click: (x, y)`、`Swipe with scaled coordinates ...`
- **性能层**：`Call \` <cmd> \` ret 0 , cost N ms , stdout size: N`
- **进出栈 + 耗时**：`asst::<Class>::<method> | enter` / `| leave, N ms`

> 📌 **实用结论**：`asst.log` 是**唯一完整可回放的事件流**——每一条 `Assistant::append_callback | <MsgName> <json>` 与 `AsstCreateEx` 回调收到的内容完全一致。所以**即使不写 ctypes 回调，也可以 tail `asst.log` 来读回结果**（🟡 这是本报告的推断，但日志行与回调 JSON 逐字相同，证据很强）。

### 4.8 `maa-cli` 与 HTTP / 集成接口

**(a) `maa-cli`（Rust 命令行版）—— 本机不存在，但项目真实存在** ✅/🔴

```
Get-Command maa, maa-cli, maa_cli   → 无
D:\__soft\MAA 全目录搜索 *cli*      → 只命中 UIAutomation*.resources.dll（无关）
```
⇒ **本机没有 `maa-cli`**（🔴 本地不可用）。
但它确实是官方项目：[`MaaAssistantArknights/maa-cli`](https://github.com/MaaAssistantArknights/maa-cli)（"MAA命令行工具 | A simple CLI for MAA"），文档在 [docs.maa.plus/zh-cn/manual/cli/install.html](https://docs.maa.plus/zh-cn/manual/cli/install.html)（🟡 搜索命中，未逐行读源码）。它同样是**调 MaaCore 的封装**，不提供新的步进语义。

**(b) MAA 的 HTTP 接口 —— MAA 是 HTTP *客户端*，不是服务端** ✅

[MAA《远程控制协议》](https://docs.maa.plus/zh-cn/protocol/remote-control-schema.html)（已 web_fetch 全文）：**MAA 不暴露 REST API**，而是**主动轮询**你提供的两个 http(s) 端点（默认 1 秒间隔）：

- `getTask` 端点：MAA POST `{"user":..., "device":...}`，你返回 `{"tasks":[...]}`。支持的任务 type：
  - 顺序执行：`CaptureImage`（截图并以 **Base64** 放在汇报 payload）、`LinkStart`、`LinkStart-<子功能>`（`Base`/`WakeUp`/`Combat`/`Recruiting`/`Mall`/`Mission`/`AutoRoguelike`/`Reclamation`）、`Toolbox-GachaOnce`/`Toolbox-GachaTenTimes`、`Settings-ConnectAddress`/`Settings-Stage1`
  - 立即执行：`CaptureImageNow`、`StopTask`、`HeartBeat`
- `reportStatus` 端点：MAA POST `{"user","device","task","status":"SUCCESS"|"FAILED","payload"}`

⇒ **这是"外部程序驱动 MAA"的官方 HTTP 通道**，粒度是"下发一个内置任务 + 拿回截图/状态"，**不是任意任务的步进**。要在 MAA 侧配置"获取任务端点 / 汇报任务端点"。

**(c) 第三方接口方案** 🟡

- **MaaFramework**（`MaaXYZ/MaaFramework`）：一套独立的、面向"Pipeline JSON + 自定义任务"的通用框架，提供 `MaaController`/`MaaTasker`/`MaaResource` 等 C API 与 Python/Node 绑定，内置 `DirectHit`/`TemplateMatch`/`OCR`/`ColorMatch`/`FeatureMatch` 等**节点类型**——用户清单里的 `MatchTemplateDetector` / `OcrDetector` / `ColorMatch` 属于**这一体系**，不是 MAA Core。MAA v6.17.0 起 `interface.json` 也新增了 Win32 连接方式（release note 提及）。
- **MaaPipelineSupport**：VS Code 扩展（`nekosu.maa-support`），用于编辑 MAA 的 `resource/tasks`——官方文档本体就在推荐它（✅ 见《任务流程协议》页首提示），**是编辑器工具，不是运行时接口**。

---

## 5. 输入通道：ADB vs Win32 与分辨率自适应

### 5.1 `resource/config.json` 的连接配置结构（✅ 已读全文）

`D:\__soft\MAA\resource\config.json` 顶层：`version` / `options` / `packageName` / **`connection`**。

- **`packageName`**：`Official` / `Bilibili` / `YoStarEN` / `YoStarJP` / `YoStarKR` / `txwy` → 安卓包名。
- **`connection[]`**：每个元素含 `configName`（+ 可选 `baseConfig` 做继承），把连接动作抽象成**命令模板字符串**，占位符有 `[Adb]`、`[AdbSerial]`、`[PackageName]`、`[x]/[y]/[x1]/[y1]/[x2]/[y2]`、`[duration]`、`[NcAddress]/[NcPort]`、`[DisplayId]`、`[minitouchLocalPath]` 等。核心键：

```json
{
  "configName": "General",
  "devices":   "[Adb] devices",
  "connect":   "[Adb] connect [AdbSerial]",
  "uuid":      "[Adb] -s [AdbSerial] shell settings get secure android_id",
  "display":   "[Adb] -s [AdbSerial] shell \"wm size | tail -n 1 | grep -o -E [0-9]+\"",
  "click":     "[Adb] -s [AdbSerial] shell input tap [x] [y]",
  "swipe":     "[Adb] -s [AdbSerial] shell input swipe [x1] [y1] [x2] [y2] [duration]",
  "screencapRawWithGzip": "[Adb] -s [AdbSerial] exec-out \"screencap | gzip -1\"",
  "callMinitouch": "[Adb] -s [AdbSerial] shell \"/data/local/tmp/[minitouchWorkingFile]\" -i",
  "back_to_home":  "[Adb] -s [AdbSerial] shell input keyevent HOME",
  ...
}
```

**内置 configName 全集（18 个）**：`General`、`CapWithShell`、`BlueStacks`、`MuMuEmulator12`、`LDPlayer`、`Androws`、`Nox`、`XYAZ`、`WSA`、`Compatible`、`SecondResolution`、`CompatMac`、`CompatPOSIXShell`、`Waydroid`、`AVD`（+ `baseConfig` 引用的中间层）。
`Androws` / `WSA` 用 `displayId` 支持"第二显示器"；这两个 config 的 `displayId` 查询依赖 `[PackageName]`，因此**连接前必须先 `AsstSetInstanceOption(ClientType)`**（✅ AsstCaller.h 注释）。

**连接方式选择（✅ 实测 + 文档）：**

| 方式 | 入口 | 参数 |
|---|---|---|
| **ADB**（模拟器/真机） | `AsstConnect(handle, adb_path, address, config)`（deprecated）或 `AsstAsyncConnect(handle, adb_path, address, config, block)` | `config` 即上表的 `configName`；`address` 如 `127.0.0.1:16384` |
| **Win32**（PC 端 / 窗口） | `AsstAsyncAttachWindow(handle, hwnd, screencap_method, mouse_method, keyboard_method, block)`（`AsstAttachWindow` 已 deprecated） | 仅 `_WIN32` 编译；`hwnd` 为目标窗口句柄 |
| 触控模式（ADB 侧细分） | `AsstSetInstanceOption(handle, 2, value)` | `minitouch`(默认) / `maatouch` / `adb` / `MacPlayTools` / `MaaFwAdb` / `MumuExtras` |

**Win32 枚举（✅ `include/AsstCaller.h` 已读全文）：**

```c
typedef enum AsstWin32ScreencapMethodEnum {
    AsstWin32ScreencapMethod_None = 0,
    AsstWin32ScreencapMethod_GDI = 1,
    AsstWin32ScreencapMethod_FramePool = 1 << 1,
    AsstWin32ScreencapMethod_DXGI_DesktopDup = 1 << 2,
    AsstWin32ScreencapMethod_DXGI_DesktopDup_Window = 1 << 3,
    AsstWin32ScreencapMethod_PrintWindow = 1 << 4,
    AsstWin32ScreencapMethod_ScreenDC = 1 << 5,
} AsstWin32ScreencapMethodEnum;

typedef enum AsstWin32InputMethodEnum {
    AsstWin32InputMethod_None = 0,
    AsstWin32InputMethod_Seize = 1,
    AsstWin32InputMethod_SendMessage = 1 << 1,
    AsstWin32InputMethod_PostMessage = 1 << 2,
    AsstWin32InputMethod_LegacyEvent = 1 << 3,
    AsstWin32InputMethod_PostThreadMessage = 1 << 4,
    AsstWin32InputMethod_SendMessageWithCursorPos = 1 << 5,
    AsstWin32InputMethod_PostMessageWithCursorPos = 1 << 6,
    AsstWin32InputMethod_SendMessageWithWindowPos = 1 << 7,
    AsstWin32InputMethod_PostMessageWithWindowPos = 1 << 8,
} AsstWin32InputMethodEnum;
```

**`MaaWin32ControlUnit.dll`（✅ 实测 PE 导出，仅 3 个具名导出）：**
```
1  0x00013F20  MaaWin32ControlUnitCreate
2  0x00014350  MaaWin32ControlUnitDestroy
3  0x000145C0  MaaWin32ControlUnitGetVersion
```
**`MaaAdbControlUnit.dll`（✅ 实测，8 个具名导出，其中 3 个为 C 接口）：**
```
6  0x000190C0  MaaAdbControlUnitCreate
7  0x00019C10  MaaAdbControlUnitDestroy
8  0x00019E80  MaaAdbControlUnitGetVersion
```
⇒ 二者都是 `MaaCore` 的**内部插件式控制单元**（「PC 端（Win32）连接配置独立拆分」是 v6.17.0 的重构点），**不通过 tasks.json 配置**，而是由 `AsstAsyncConnect`/`AsstAsyncAttachWindow` 在 C API 层选择。
`AsstSetConnectionExtras(name, extras)` 用于补充连接配置（GUI 里封装成 `AsstSetConnectionExtrasMuMu` / `AsstSetConnectionExtrasLdPlayer` 等，✅ 见 `MAA.dll` 字符串）。

### 5.2 坐标如何自适应分辨率（✅ 已实证）

**流程：**
1. 连接后读设备分辨率（`display` 命令 / Win32 窗口客户区），得到 `W×H`；
2. 截图统一缩放到 **1280×720** 后做模板匹配 / OCR；
3. 识别结果（`roi` 空间，即 1280×720 空间）→ 计算点击点 → **乘以 `W/1280`（= `H/720`）** → 转成设备像素 → 下发到底层控制单元。

**证据链**（三条独立证据，见 §2.4）：
- 官方文档：`roi` / `specificRect` / `rectMove` / copilot 的 `rect`/`begin`/`end` 全部"以 1280×720 为基准自动缩放"；
- 日志：`Click with scaled coordinates (0, 719) 1.5` → `minitouch click: (0, 1078)`（0×1.5=0，719×1.5=1078.5→1078，设备高 1080）；
- 日志：`Swipe with scaled coordinates (132, 389) (1153, 376) 1.5` → `minitouch swipe (198, 583) (1729, 564) ...`（132×1.5=198, 389×1.5=583.5→583, 1153×1.5=1729.5→1729, 376×1.5=564）。

`resource\config.json` 里 `SSSFightScreencapInterval: 16`、`CopilotFightScreencapInterval: 16`、`RoguelikeFightScreencapInterval: 100`（ms）控制战斗期截图频率；`taskDelay: 500` 是全局识别间隔。

---

## 6. 结论汇总

### 6.1 能否"步进驱动"？—— **能，且有多条路径** ✅

| 路径 | 粒度 | 如何读回结果 | 置信度 |
|---|---|---|---|
| **A. `SingleStep` 任务** | **单个战斗操作**（1 步 = 1 个 copilot action） | 标准回调 `TaskChain*`/`SubTask*`（`taskchain = "SingleStep"`） | ✅ 可 append 成功已实测；真机逐步行为 🟡 |
| **B. `Custom` 任务 + `task_names` 单选** | 单条 `ProcessTask` 及其 `next` 子图 | 回调 `SubTaskCompleted.details.result`（`rect`/`score`/`template`/OCR 文本） | ✅ append 实测成功 |
| **C. `AsstAsyncScreencap` → `AsstGetImage` → `AsstAsyncClick`** | **像素级**，完全绕过任务系统 | `AsyncCallInfo` 回调（`what: Screencap/Click`，含 `ret`/`cost`）+ `AsstGetImage` 取原始像素 | ✅ **回调链路已实测跑通** |
| **D. tail `debug\asst.log`** | 观察级，最省事 | 每行 `Assistant::append_callback \| <Msg> <json>` 与回调内容逐字一致 | ✅ 日志格式实测；🟡 作为"读回通道"的等价性推断 |
| **E. HTTP 远程控制端点** | 内置任务级（`LinkStart-*` / `CaptureImage`） | `reportStatus` POST 回传 `status` + `payload`（截图 Base64） | ✅ 文档 |
| ~~F. `MAA.exe` CLI~~ | — | **不可用**：`--help` 输出 0 字节，纯 GUI 单实例 | ✅ 实测 |

### 6.2 "怎么读回结果"—— 三条正规通道 ✅

1. **`AsstCreateEx(callback, custom_arg)` 注册的 `AsstApiCallback`** — 事件流。
   - 同步点：`TaskChainStart(10001)` / `TaskChainCompleted(10002)` / `TaskChainError(10000)`
   - 识别结果：`SubTaskCompleted(20002)` 的 `details.result` = `{rect, score, template}` 或 OCR 结果
   - 业务数据：`SubTaskExtraInfo(20003)` 的 `what`（`StageDrops`/`DepotInfo`/`OperBoxInfo`/`RecruitResult`/`StageInfo`/`ExceededLimit`…）
   - 全局：`AllTasksCompleted(3)` 带 `finished_tasks: [taskid...]`
   - 异步调用：`AsyncCallInfo(4)` 带 `async_call_id` / `what` / `details.ret` / `details.cost`
2. **`AsstGetImage(handle, buf, buff_size)`** — 直接拿上次截图的 BGR 像素（`size` 必须自算，如 `1280*720*3`；另有 `AsstGetImageBgr`）。`AsstGetUUID` / `AsstGetTasksList` / `AsstRunning` / `AsstConnected` 提供状态查询。
3. **`debug\asst.log` 文本 tail** — 全量事件流落盘，格式稳定（`[ts][lvl][Px..][Tx..] msg`）。

### 6.3 最小可运行 Python 骨架

**本报告实际执行通过的精简版**（去掉注释与错误处理），文件：`.tmp\probe_api.py` / `.tmp\probe_tasks.py`：

```python
import ctypes, json, os, pathlib, threading, time

MAA     = r"D:\__soft\MAA"                        # MaaCore.dll 与 resource 所在目录
USERDIR = r"C:\...\maauser"                       # 日志/调试图写入目录（勿指向 MAA 安装目录）
os.environ["PATH"] = MAA + os.pathsep + os.environ["PATH"]
os.add_dll_directory(MAA)                         # 让 MaaCore 找到同目录的依赖 DLL
lib = ctypes.WinDLL(os.path.join(MAA, "MaaCore.dll"))

def bind(name, res, args):
    f = getattr(lib, name); f.restype = res; f.argtypes = args; return f

AsstSetUserDir   = bind("AsstSetUserDir",   ctypes.c_ubyte,  (ctypes.c_char_p,))
AsstLoadResource = bind("AsstLoadResource", ctypes.c_ubyte,  (ctypes.c_char_p,))
AsstCreateEx     = bind("AsstCreateEx",     ctypes.c_void_p, (ctypes.c_void_p, ctypes.c_void_p))
AsstDestroy      = bind("AsstDestroy",      None,            (ctypes.c_void_p,))
AsstAppendTask   = bind("AsstAppendTask",   ctypes.c_int32,  (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p))
AsstSetTaskParams= bind("AsstSetTaskParams",ctypes.c_ubyte,  (ctypes.c_void_p, ctypes.c_int32, ctypes.c_char_p))
AsstAsyncConnect = bind("AsstAsyncConnect", ctypes.c_int32,  (ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ubyte))
AsstAsyncScreencap=bind("AsstAsyncScreencap",ctypes.c_int32, (ctypes.c_void_p, ctypes.c_ubyte))
AsstAsyncClick   = bind("AsstAsyncClick",   ctypes.c_int32,  (ctypes.c_void_p, ctypes.c_int32, ctypes.c_int32, ctypes.c_ubyte))
AsstGetImage     = bind("AsstGetImage",     ctypes.c_uint64, (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint64))
AsstStart        = bind("AsstStart",        ctypes.c_ubyte,  (ctypes.c_void_p,))
AsstStop         = bind("AsstStop",         ctypes.c_ubyte,  (ctypes.c_void_p,))

# ---------- 结果回传通道 ----------
events, lock, cv = [], threading.Condition()
CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_int32, ctypes.c_char_p, ctypes.c_void_p)

@CALLBACK
def cb(msg, details, arg):
    d = details.decode("utf-8", "replace") if details else ""
    with cv:
        events.append((msg, d)); cv.notify_all()

def wait_for(msg_id, timeout=60):
    """阻塞直到收到指定 AsstMsgId，返回其 details JSON"""
    end = time.time() + timeout
    i = 0
    with cv:
        while True:
            while i < len(events):
                m, d = events[i]; i += 1
                if m == msg_id:
                    return json.loads(d) if d else {}
            if not cv.wait(end - time.time()):
                raise TimeoutError(f"msg {msg_id} not received")

# ---------- 初始化 ----------
AsstSetUserDir(USERDIR.encode())
assert AsstLoadResource(MAA.encode()) == 1, "资源加载失败"
handle = AsstCreateEx(ctypes.cast(cb, ctypes.c_void_p), None)

# ---------- 连接（ADB；PC 端改用 AsstAsyncAttachWindow）----------
AsstAsyncConnect(handle, b"adb.exe", b"127.0.0.1:16384", b"MuMuEmulator12", 1)

# ---------- 路径 A：SingleStep 逐步驱动（注意 details 必须包在 actions 数组里！）----------
AsstAppendTask(handle, b"SingleStep",
               json.dumps({"type": "copilot", "subtype": "stage",
                           "details": {"stage_name": "1-7"}}).encode())
AsstAppendTask(handle, b"SingleStep", json.dumps({"type": "copilot", "subtype": "start"}).encode())
AsstStart(handle)
wait_for(10002)                                             # TaskChainCompleted：关卡已设置并开战
AsstAppendTask(handle, b"SingleStep", json.dumps({           # ← 单步：打一发二倍速
    "type": "copilot", "subtype": "action",
    "details": {"actions": [{"type": "SpeedUp"}]}}).encode())
AsstStart(handle)
wait_for(10002)                                             # 等这一步跑完
AsstAppendTask(handle, b"SingleStep", json.dumps({           # ← 单步：部署史尔特尔
    "type": "copilot", "subtype": "action",
    "details": {"actions": [{"type": "Deploy", "name": "史尔特尔",
                             "location": [4, 5], "direction": "Left"}]}}).encode())
AsstStart(handle); wait_for(10002)

# ---------- 路径 C：纯截屏 + 纯点击（"先看再点"，绕过任务系统）----------
AsstAsyncScreencap(handle, 1)                               # block=1，同步
info = wait_for(4)                                          # AsyncCallInfo{"what":"Screencap","details":{"ret":true,...}}
buf = ctypes.create_string_buffer(1280 * 720 * 3)
n = AsstGetImage(handle, buf, 1280 * 720 * 3)               # 返回字节数；像素为 BGR 顺序
frame = bytes(buf) if n > 0 else None                       # ← 交给自己的识别器

AsstAsyncClick(handle, 640, 360, 1)                         # block=1，同步点击 (1280x720 空间坐标)
wait_for(4)                                                 # AsyncCallInfo{"what":"Click"}

# ---------- 路径 B：单条内置识别任务 + 读 result ----------
AsstAppendTask(handle, b"Custom", json.dumps({"task_names": ["AwardBegin"]}).encode())
AsstStart(handle)
done = wait_for(3)                                          # AllTasksCompleted{"finished_tasks":[...]}
AsstStop(handle); AsstDestroy(handle)
```

> **实测注意事项（✅ 血泪）**
> 1. `Copilot` 任务的 `filename` **相对路径会相对进程 CWD 解析**，不是相对 `resource\`。实测 `{"filename": "copilot/OF-1_credit_fight.json"}` → `taskid=0`（`ERR ... file does not exist`）；传**绝对路径** → `taskid=1` 成功。
> 2. `AsstAppendTask` **返回 0 即失败**，原因只在日志里（`invalid params` / `invalid type`）。务必校验返回值。
> 3. `SingleStep` 的 `subtype: "action"` 的 `details` **必须**是 `{"actions":[...]}`（官方文档示例是错的）。
> 4. `AsstGetImage` 的 buffer 大小必须**自己算**（`1280*720*3`），且要在成功截图之后调用。
> 5. 先用 `AsstSetUserDir` 把日志目录指到别处，否则 `debug\asst.log` 会写进 MAA 安装目录。
> 6. `AsstStart` 必须在 `AsstAppendTask` 之后；`AsstStart` 在已有任务运行时返回成功但不会重入（🟡）。

### 6.4 判据与置信度总表

| # | 结论 | 置信度 |
|---|---|---|
| 1 | tasks.json 共 869 任务；tasks/ 共 79 文件 3,295 任务定义 | ✅ 实测 |
| 2 | 任务字段全集与默认值（`templThreshold`=0.8、`roi` 默认 `[0,0,1280,720]` 等） | ✅ 文档 + 二进制字符串 |
| 3 | `roiOffset`/`retryTimes`/`onlyRecognition`/`replaceFullWidthChars`/`MatchTemplateDetector`/`OcrDetector`/`ColorMatch` **不存在** | ✅ 二进制 0 命中 |
| 4 | algorithm 实际只有 4 个 + 内部 `MatchRect` | ✅ 二进制 + 资源统计 |
| 5 | 坐标基准 1280×720 + 乘回原分辨率（×1.5 实证） | ✅ 日志算术核对 |
| 6 | `MAA.exe` 无 CLI（`--help` 输出 0 字节） | ✅ 实测 |
| 7 | `MaaCore.dll` 33 个具名导出（全清单） | ✅ PE 解析 |
| 8 | 回调枚举与 `details` JSON 结构 | ✅ 文档 + 本机日志 + 自建回调复现 |
| 9 | Python 绑定直接 ctypes 调 DLL | ✅ 本地源码全文 |
| 10 | `SingleStep` 存在，`details` 须为 `{"actions":[...]}` | ✅ 源码 + 对照实验（裸对象全 0，包裹全成功） |
| 11 | 远程控制是 MAA 主动轮询 http 端点，MAA 不提供 REST 服务端 | ✅ 文档 |
| 12 | 本机无 `maa-cli`；官方 maa-cli 项目存在 | ✅ 本地 / 🟡 上游 |
| 13 | Win32 输入 = `AsstAsyncAttachWindow` + 枚举（非 tasks.json 配置） | ✅ AsstCaller.h + DLL 导出 |
| 14 | `AsstCallerExtra`（v6.17.0 声称新增）未在本机导出表/字符串中出现 | 🔴 未查明 |
| 15 | `SingleStep` 真机逐步行为（每次 append 只走一步） | 🟡 未连设备验证 |
| 16 | tail `asst.log` 可等价替代回调 | 🟡 日志与回调逐字相同，强证据但未做程序化对比 |

---

## 附录 A：本次分析使用的临时脚本（均在 `.tmp\`）

| 脚本 | 用途 |
|---|---|
| `.tmp\analyze_tasks.py` | tasks.json 任务数、字段频次、algorithm/action 分布、子文件枚举 |
| `.tmp\dump_tasks.py` | 导出代表性任务完整 JSON |
| `.tmp\analyze_copilot.py` | copilot 作业 schema 统计 |
| `.tmp\pe_exports.py` / `.tmp\pe_exp2.py` / `.tmp\pe_debug.py` | PE 导出表解析（无第三方依赖） |
| `.tmp\log_probe.py` | asst.log 格式与关键词行提取 |
| `.tmp\probe_api.py` | **ctypes 加载 MaaCore + 注册回调 + 异步截图/点击实测** |
| `.tmp\probe_tasks.py` | Copilot/SingleStep/Custom 任务参数对照实验 |

## 附录 B：外部参考链接

- [任务流程协议（tasks.json schema）](https://docs.maa.plus/zh-cn/protocol/task-schema.html)
- [集成文档（AsstAppendTask 全任务参数、SingleStep）](https://docs.maa.plus/zh-cn/protocol/integration.html)
- [回调消息协议（AsstMsg 枚举与 details 结构）](https://docs.maa.plus/zh-cn/protocol/callback-schema.html)
- [战斗流程协议（copilot JSON schema）](https://docs.maa.plus/zh-cn/protocol/copilot-schema.html)
- [远程控制协议（HTTP 端点）](https://docs.maa.plus/zh-cn/protocol/remote-control-schema.html)
- [`include/AsstCaller.h`（dev-v2）](https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/dev-v2/include/AsstCaller.h)
- [`src/MaaCore/Task/Interface/SingleStepTask.cpp`](https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/dev-v2/src/MaaCore/Task/Interface/SingleStepTask.cpp)
- [`src/MaaCore/Config/Miscellaneous/CopilotConfig.cpp`](https://github.com/MaaAssistantArknights/MaaAssistantArknights/blob/dev-v2/src/MaaCore/Config/Miscellaneous/CopilotConfig.cpp)
- [`MaaAssistantArknights/maa-cli`（Rust CLI）](https://github.com/MaaAssistantArknights/maa-cli)

> 注：`raw.githubusercontent.com` 与 `github.com` 直连在本机网络下失败，本报告所有 GitHub 源码均通过 `cdn.jsdelivr.net/gh/<owner>/<repo>@<ref>/<path>` 读取；任务/回调/copilot/远程控制四份协议文档通过 `docs.maa.plus` 读取。
