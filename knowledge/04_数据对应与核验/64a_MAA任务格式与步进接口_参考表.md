# 64a · MAA 任务格式与步进接口（参考表）
> 主题：**04E 实机 / 打图操作**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）
> 层级：**T2（数据/流程整理类（未含强代码证据））**　建立日期：**—（待补）**　任务：—　｜　**头部为 2026-09-30 自动回填**，推断项已标注

> 子文件，配套 `64_MAA与prts+_GUI操作方案.md`。本文件只放**表与清单**，正文放精炼结论。
> 判据/置信度：✅ 本地实测或已读源码 · 🟡 推断 · 🔴 未查明。

---

## 一、`resource/tasks/tasks.json` 字段全表 ✅

**任务总数 869**（`tasks.json` 613KB 左右，另有 `tasks/` 下 100+ 个按模块拆分的 JSON）。
`_`/`//` 开头是注释；解析前需剥掉 `^\s*//.*$`。

| 字段 | 出现次数 | 含义 |
|---|---|---|
| `roi` | 487 | 识别区域 `[x,y,w,h]`，**基准 1280×720** |
| `next` | 415 | **候选链**（见 §三） |
| `action` | 348 | 识别成功后的动作，见下表 |
| `template` | 267 | 模板图路径（相对 `resource/template/`；`empty.png` = 占位） |
| `algorithm` | 238 | 识别算法：`JustReturn`112 / `OcrDetect`122 / `FeatureMatch`3 / `MatchTemplate`1 |
| `baseTask` | 193 | 继承模板任务（字段合并） |
| `postDelay` | 173 | 动作后延时 ms |
| `text` | 141 | OCR 目标文本数组；**`text: []` = 由调用方给出**（如关卡名/章节名） |
| `templThreshold` | 109 | 模板匹配阈值（默认见 §四） |
| `Doc`/`doc` | 148 | 人类可读说明（含大量实测踩坑记录，**极有价值**） |
| `specificRect` | 79 | `Swipe`/`ClickRect` 的起点矩形 |
| `maxTimes` | 65 | 该任务最多执行次数（超出走 `exceededNext`） |
| `rectMove` | 63 | 相对位移 `[dx,dy,w,h]`；`Swipe` 的终点、`BattleOperAvatar` 的 ROI 偏移 |
| `maskRange` | 56 | 模板匹配的掩码灰度区间 |
| `preDelay` | 44 | 动作前延时 ms |
| `exceededNext` | 43 | `maxTimes` 用尽后的去向 |
| `sub` | 39 | 子任务序列（如 `Fight` 的 `["Terminal-Entry"]`） |
| `specialParams` | 37 | 算法私有参数（数组） |
| `isAscii` | 26 | OCR 只认 ASCII（关卡代号） |
| `reduceOtherTimes` | 24 | 识别成功后**减少其他任务**的计数 |
| `ocrReplace` | 18 | OCR 纠错正则表 `[[pat, rep], ...]`（**值得照抄**，见 §五） |
| `colorScales` | 18 | 颜色匹配的缩放表 |
| `cache` | 16 | 缓存识别结果 |
| `fullMatch` | 14 | OCR 要求整串完全匹配 |
| `method` | 14 | 模板匹配方法 |
| `onErrorNext` | 11 | 出错时的去向 |
| `binThreshold` | 9 | 二值化阈值 |
| `useRaw` | 7 | 用原始图（不缩放到 1280×720） |
| `count` | 5 | 期望命中数量 |
| `detector` | 4 | 检测器（`MatchTemplateDetector` 等） |
| `withoutDet` | 3 | 不用检测器，直接匹配 |
| `highResolutionSwipeFix` | 2 | 高分辨率滑动修正 |
| `pureColor` / `colorWithClose` | 1/1 | 纯色判定相关 |

### `action` 取值 ✅
| 值 | 次数 | 行为 |
|---|---|---|
| `ClickSelf` | 239 | 点**识别到的位置**（模板中心 / OCR 文本框中心）；**若只有 `roi` 没有 `template`/`algorithm`，则点 roi 中心** |
| `ClickRect` | 48 | 点 `specificRect` 中心 |
| `DoNothing` | 40 | 只识别、不动（**"只观察不操作"就靠它**） |
| `Swipe` | 11 | `specificRect` 中心 → `rectMove` 中心，时长 `specialParams[0]` ms |
| `Stop` | 10 | 终止该任务链 |

---

## 一-bis、⚠️ 更正：以下字段**在 MaaCore 中不存在** ✅（二进制 0 命中）

任务清单里点名的这些字段**实际不存在**，不要照抄：

| 不存在的字段 | 替代做法 |
|---|---|
| `onlyRecognition` | 用 `action: "DoNothing"` 的任务"只识别"，再读回调里的 `result` |
| `roiOffset` | 用 `rectMove` 或直接写绝对 `roi` |
| `retryTimes` | **不存在**；重试靠 `next` 自递归 + `maxTimes` + `exceededNext`（示例 `Copilot@WaitUntilEndOfAction`） |
| `replaceFullWidthChars` | 用 `ocrReplace` |
| `ocr`（作为字段） | OCR 靠 `algorithm: "OcrDetect"` + `text` |
| `MatchTemplateDetector` / `OcrDetector` / `ColorMatch` | 这些属于 **MaaFramework**（另一个项目体系）；MaaCore 只有 4 个 `algorithm` |
| `timeout`（作为通用字段） | 只属 copilot 的 action；任务链层没有 |

`algorithm` 实际只有 4 个：`JustReturn` / `MatchTemplate`（**默认**）/ `OcrDetect` / `FeatureMatch`。
`resource/tasks/` 合计 **79 个 JSON、3295 条任务定义**（`tasks.json` 里有 869 条）。

---

## 二、代表性任务原文 ✅（`resource/tasks/tasks.json`）

```jsonc
// 主界面判定：用「设置按钮」模板；连续命中 maxTimes 次才算稳定
"StartUp": { "Doc":"有时候明明已经在主界面了，停了一小会又弹个窗。多检测几次，一直在主界面才算完成",
  "template":"SwitchTheme@ToggleSettingsMenu.png", "action":"DoNothing",
  "roi":[227,327,159,152], "postDelay":1000, "maxTimes":3,
  "next":["StartUp","StartUp@LoadingText","StartUp@CloseAnnos#next"] }

// 进战斗开始：OCR「开始行动」等 6 种文案
"BattleStartPre": { "algorithm":"OcrDetect",
  "text":["开始行动","开始作战","开始推演","开始突袭","开始试炼","开始测试"],
  "roi":[1000,600,280,120], "action":"ClickSelf", "preDelay":500, "postDelay":1000 }

// 战斗是否已开始（含 YJWL 更新踩坑记录）
"BattleHasStarted": { "Doc":"20260109 YJWL更新后暂停按钮向右移动约8像素, 且暂停后亮度上限245",
  "template":"empty.png", "roi":[1178,33,53,39], "specialParams":[235,200] }   // [亮度阈值, 点数]

// ★ 战斗内：在暂停时部署（与 prts+ 的"子弹时间"同源）
"BattleDeployWhenPause": { "algorithm":"JustReturn", "specialParams":[1] }
// 部署后拖方向
"BattleDeployDirectionRectMove": { "template":"empty.png", "rectMove":[-48,-48,96,96] }
// 卡片中心 → 头像区 / 费用数字区
"BattleOperAvatar": { "template":"empty.png", "rectMove":[7,32,60,60] }
"BattleOperCost":   { "template":"empty.png", "rectMove":[-10,12,30,17] }
// 卡片是否可用（费用够/未冷却）：V 通道均值阈值
"BattleOperAvailable": { "template":"empty.png", "specialParams":[100], "rectMove":[0,0,10,10] }

// 关卡名 OCR（全屏）+ 纠错表
"ClickStageName": { "algorithm":"OcrDetect", "action":"ClickSelf", "roi":[0,0,1280,720],
  "fullMatch":true, "isAscii":true, "text":[], "next":["ClickedCorrectStageOrSwipe","#self"],
  "ocrReplace":[["-\\]","-1"],[" ",""],["s","S"],["c","C"],["o","O"],["g","8"],["t","T"],
    [":",""],["'",""],["(H\\d+)O(?=-)","${1}0"],["(-\\d+)O","${1}0"],["([A-Z])0(?=-)","${1}O"],
    [".*?([A-Z]{2}-EX-\\d+)","$1"],["-I$","-1"]], "specialParams":[0,0,160,180,30,255] }
```

### `next` 的特殊记号 ✅
| 记号 | 含义 |
|---|---|
| `#self` | 回到本任务（循环重试） |
| `#next` | 透传到上一层的 next |
| `#back` | 回退到前一个任务 |
| `Task@Sub` | 子任务（`@` 分隔，如 `StartUp@LoadingText`） |
| `Task#next` | 用该任务的 next 列表**展开**（`StartUp@CloseAnnos#next`） |
| 纯字符串 | 普通任务名 |

**候选链语义**：`next` 是**候选列表**，引擎按顺序尝试"其识别在当前画面命中"的第一个；
全不命中则取第一个兜底。⚠️ 与"按顺序执行"不同。

---

## 三、流程控制机制 ✅

| 机制 | 字段 | 语义 |
|---|---|---|
| 重试 | `maxTimes` + `exceededNext` | 该任务最多执行 `maxTimes` 次；超出走 `exceededNext` |
| 链内重试 | 日志 `cur_retry` / `retry_times` | 每轮识别失败 +1，达上限则该轮判失败 |
| 延时 | `preDelay` / `postDelay` | 动作前后 ms |
| 超时 | 无显式 `timeout` 字段 | 由上层任务链的循环次数与延时共同约束 |
| 计数干预 | `reduceOtherTimes` | 命中后扣减其他任务的计数（避免重复执行） |
| 缓存 | `cache` | 复用上一次识别结果 |
| 出错 | `onErrorNext` | 出错分支 |

---

## 四、界面识别的判据 ✅/🟡

| 项 | 值 | 判据 |
|---|---|---|
| 坐标基准 | **1280×720** | ✅ 三重证据：日志 `Click with scaled coordinates (0,719) 1.5` → `minitouch click: (0,1078)`；`132×1.5=198`；缩放系数 = 1920/1280 = **1.5** |
| 模板匹配阈值 | **默认 0.8**；单任务可用 `templThreshold` 覆盖 | ✅ 本机实测命中分 0.976~0.999 |
| 模板匹配方法 | `cv::matchTemplate`，`multi_match` 会返回多个候选 + 分数 | ✅ 日志 `multi_match \| result: [{rect:[...], score:0.982303}, ...] roi:[...]` |
| OCR 引擎 | 自带 PaddleOCR（`PaddleOCR/`、`PaddleCharOCR/`）+ ONNX；**没有** Tesseract | ✅ 资源目录 |
| OCR 匹配 | `fullMatch` 要求整串相等；`ocrReplace` 先做正则纠错；`isAscii` 限定字符集 | ✅ 字段定义 |
| 二值化 | `binThreshold` / `maskRange` / `specialParams` | 各任务自定义 |
| 界面语义（我方） | `plugins/recognize/ui_state.py`：`battle`/`squad`/`viewport`/`unknown`，阈值 0.80，锚点 `Battle/BattleFlag/BattleOfficiallyBegin.png` | ✅ 既有实现，8/8 自检通过 |

---

## 五、`MaaCore.dll` 导出函数全表 ✅（本机解析 PE 导出表，33 项）

```
AsstSetUserDir          AsstLoadResource        AsstSetStaticOption
AsstCreate              AsstCreateEx            AsstDestroy
AsstSetInstanceOption   AsstConnect(弃用)        AsstAppendTask
AsstSetTaskParams       AsstStart               AsstStop
AsstRunning             AsstConnected           AsstBackToHome
AsstAsyncConnect        AsstSetConnectionExtras
AsstAttachWindow(弃用)   AsstAsyncAttachWindow
AsstAsyncClick          AsstAsyncScreencap
AsstGetImage            AsstGetImageBgr         AsstGetNullSize
AsstGetUUID             AsstGetTasksList        AsstGetVersion
AsstLog
（+ 4 个 C++ 内部符号 IScreenShotClass 构造/析构）
```
**注意**：v6 **没有** `AsstSetCallback` —— 回调通过 `AsstCreateEx(callback, custom_arg)` 注册。
本机 DLL 版本 **v6.16.8**（GUI 为 6.14.1，`resource/version.json` last_updated `2026-08-08`）。

### 关键签名 ✅（`include/AsstCaller.h`）
```c
AsstBool  AsstSetUserDir(const char* path);
AsstBool  AsstLoadResource(const char* path);      // ★ = MAA **根目录**（其下有 resource/）
AsstHandle AsstCreateEx(AsstApiCallback cb, void* custom_arg);
AsstBool  AsstSetInstanceOption(AsstHandle, AsstInstanceOptionKey, const char* value);
AsstTaskId AsstAppendTask(AsstHandle, const char* type, const char* params);   // 返回 task_id，<0 失败
AsstBool  AsstStart(AsstHandle);  AsstBool AsstStop(AsstHandle);
AsstBool  AsstRunning(AsstHandle); AsstBool AsstConnected(AsstHandle);
AsstAsyncCallId AsstAsyncConnect(h, adb_path, address, config, AsstBool block);
AsstAsyncCallId AsstAsyncAttachWindow(h, void* hwnd, uint64 screencap, uint64 mouse, uint64 keyboard, AsstBool block);
AsstAsyncCallId AsstAsyncClick(h, int32 x, int32 y, AsstBool block);
AsstAsyncCallId AsstAsyncScreencap(h, AsstBool block);
AsstSize  AsstGetImage(h, void* buff, AsstSize buff_size);      // NULL,0 → 所需字节数
AsstSize  AsstGetUUID(h, char* buff, AsstSize n);
AsstSize  AsstGetTasksList(h, AsstTaskId* buff, AsstSize n);
AsstSize  AsstGetNullSize(void);                                // = 2^64-1（哨兵）
const char* AsstGetVersion(void);   void AsstLog(const char* level, const char* message);
typedef void(ASST_CALL* AsstApiCallback)(AsstMsgId msg, const char* details_json, void* custom_arg);
```

### Win32 通道枚举 ✅
```
截图 AsstWin32ScreencapMethod: None=0 GDI=1 FramePool=2 DXGI_DesktopDup=4
                             DXGI_DesktopDup_Window=8 PrintWindow=16 ScreenDC=32
输入 AsstWin32InputMethod:    None=0 Seize=1 SendMessage=2 PostMessage=4 LegacyEvent=8
                             PostThreadMessage=16 SendMessageWithCursorPos=32
                             PostMessageWithCursorPos=64 SendMessageWithWindowPos=128
                             PostMessageWithWindowPos=256
```

---

## 六、`AsstMsg` 回调消息目录 ✅（`src/MaaCore/Common/AsstMsg.h`）

| msg | 名称 | 时机 | 对 agent 的用途 |
|---|---|---|---|
| 0 | `InternalError` | 内部错误 | 停止 |
| 1 | `InitFailed` | 初始化失败 | 停止 |
| 2 | `ConnectionInfo` | 连接相关 | **错误读回**（实测 `{"what":"ScreencapFailed","why":"ScreencapFailed"}`） |
| 3 | `AllTasksCompleted` | 全部任务完成 | 队列跑完 |
| 4 | `AsyncCallInfo` | 异步调用信息 | 异步接口回执 |
| 5 | `Destroyed` | 实例销毁 | 收尾 |
| **10001** | `TaskChainStart` | 任务链开始 | **步进起点** |
| **10002** | `TaskChainCompleted` | 任务链完成 | **★ 步进终点（成功）** |
| 10000 | `TaskChainError` | 任务链错误 | **★ 步进终点（失败）** |
| 10003 / 10004 | `TaskChainExtraInfo` / `Stopped` | 额外信息 / 手动停止 | 遥测 |
| **20001 / 20002** | `SubTaskStart` / `SubTaskCompleted` | 原子任务级 | **★ 链内过程遥测** |
| 20000 / 20003 / 20004 | `SubTaskError` / `ExtraInfo` / `Stopped` | 原子级错误/额外/停止 | 诊断 |

### 回调 JSON 结构 ✅（本地 `debug/asst.log` 真实样本，缩略）
```jsonc
// TaskChain 级
{"taskchain":"Fight","taskid":4,"uuid":"a039090c57c2337d"}
// SubTask 级：带 action/algorithm/result.score/exec_times
{"class":"asst::ProcessTask","details":{"action":"ClickSelf","algorithm":"MatchTemplate",
  "exec_times":1,"max_times":2147483647,"result":{"score":0.990966},"task":"ReturnButton"},
 "first":["StageBegin"],"pre_task":"StageBegin","subtask":"ProcessTask",
 "taskchain":"Fight","taskid":4,"uuid":"..."}
// 识别轮：候选清单 + 重试计数（★ 这就是"界面识别 + 流程控制"的可观测形态）
{"class":"asst::ProcessTask","details":{"cur_retry":0,"retry_times":5,
  "to_be_recognized":["Fight@ReturnButton","Fight@FromStageSN","Fight","Fight@CloseAnno", ...]},
 "first":["StageBegin"],"pre_task":"StageBegin","subtask":"ProcessTask","taskchain":"Fight","taskid":4}
// 额外信息（带业务语义）
{"class":"asst::InfrastTradeTask","details":{"facility":"Trade","index":0},
 "subtask":"InfrastTradeTask","taskchain":"Infrast","taskid":3,"what":"EnterFacility"}
```

---

## 七、`debug/asst.log` 行格式 ✅（本机真实日志，56MB）

```
[2025-12-29 15:52:37.344][TRC][Px36668][Tx37153] multi_match |  result: [{ rect: [ 119, 290, 71, 63 ], score: 0.982303 }] roi: [ 0, 240, 640, 400 ]
[2025-12-29 15:53:54.533][INF][Px36668][Tx37153] Assistant::append_callback | SubTaskStart {...JSON...}
[2025-12-29 15:52:35.977][TRC][Px36668][Tx37153] Swipe with scaled coordinates (132, 389) (1153, 376) 1.5
[2025-12-29 15:52:35.977][TRC][Px36668][Tx37153] minitouch swipe (198, 583) (1729, 564) 150 0 1 1
[2025-12-29 15:52:37.345][TRC][Px36668][Tx37153] Click with scaled coordinates (172, 298) 1.5
[2025-12-29 15:52:37.345][TRC][Px36668][Tx37153] minitouch click: (258, 447)
[2025-12-29 15:52:37.062][INF][Px36668][Tx37153] Call ` ...adb.exe -s 127.0.0.1:16384 exec-out "screencap | gzip -1" ` ret 0 , cost 232 ms , stdout size: 1338984
```

**格式**：`[YYYY-MM-DD HH:MM:SS.mmm][级别][PxPID][TxTID] 模块/消息`
**★ 可解析结构**：`Assistant::append_callback | <MsgName> <JSON>` —— 上面 §六 的全部回调
都以这一行形式落在日志里 ⇒ **不用写 C 绑定也能事后重建整条决策链**。
`TRC` 级含识别分数、候选 `roi`、缩放前/后坐标；`INF` 级含回调与 ADB 调用。
日志目录：`<UserDir>/debug/`（本机 `D:\__soft\MAA\debug\`，含 `asst.log` / `gui.log` / 子目录 `drops`/`map`/`recruit`/`roguelike`/`interface`）。

---

## 八、输入通道与坐标自适应 ✅

| 项 | 结论 | 判据 |
|---|---|---|
| 本机 MAA 实际用的通道 | **ADB + minitouch** | ✅ 日志 `minitouch click: (258, 447)`、`adb.exe ... exec-out "screencap | gzip -1"` |
| 可用通道 | ADB（`AsstAsyncConnect`）/ **Win32 窗口**（`AsstAsyncAttachWindow`） | ✅ 导出函数 + `MaaWin32ControlUnit.dll` / `MaaAdbControlUnit.dll` |
| 坐标自适应 | **在 1280×720 空间里识别与计算，再按缩放比送到设备** | ✅ `Click with scaled coordinates (172, 298) 1.5` → `minitouch click: (258, 447)`（×1.5） |
| 截图 | ADB：`exec-out "screencap | gzip -1"`；Win32：`PrintWindow`/`DXGI`/GDI/ScreenDC | ✅ 日志 + 枚举 |

---

## 九、copilot（作业）JSON 格式 ✅

本地 `resource/copilot/`：**74 个作业文件**（大部分是 `old/` 下的旧格式）。字段频次：
`minimum_required`74 / `doc`74 / `opers`74 / `stage_name`74 / `type`73 / `buff`73 /
`equipment`73 / `strategy`73 / `tool_men`73 / `drops`73 / `blacklist`73 / `stages`73 /
`actions`29 / `groups`29

```jsonc
// 新格式（OF-1 信用作战，v4.0.0+）
{ "minimum_required": "v4.0.0", "stage_name": "OF-1",
  "doc": { "title": "OF-1 Credit Fight", "details": "OF-1 Credit Fight" },
  "opers": [],
  "groups": [ { "name": "先锋", "opers": [
      {"name":"推进之王","skill":2},
      {"name":"凛御银灰","skill":3,"skill_usage":1},
      {"name":"焰尾"} ] } ],
  "actions": [ {"type":"SpeedUp"},
               {"type":"Deploy","name":"先锋","location":[5,3],"direction":"Right"},
               {"type":"SkillDaemon"} ] }

// 旧格式（SSS 等，用 stages/strategies）
{ "type":"SSS", "stage_name":"...", "strategy":"Main Strategy",
  "buff":"丛林用示踪信标", "equipment":["A","A","A","A","A","A","A","A"],
  "tool_men":{"Guard":5,"Supporter":4,"Vanguard":3,"Defender":3,"Medic":2},
  "stages":[ {"stage_name":"丛林式寒暄",
     "strategies":[ {"core":"水月","tool_men":{"近卫":3,"先锋":1},"location":[4,2],"direction":"Down"} ],
     "draw_as_possible": true,
     "actions":[ {"type":"二倍速"},
                 {"type":"Deploy","name":"丛林用示踪信标","location":[3,2],"direction":"None"} ],
     "retry_times": 3 } ] }
```

**`actions[].type` 取值**：`Deploy`（`name`+`location[r,c]`+`direction`）、`Skill`、`Retreat`、
`SkillDaemon`、`SpeedUp`、`BulletTime`、`Output`、`MoveCamera` 等。
`opers[].skill_usage`：`0` 好了就放 / `1` 费用够就放 / `2` 按轴（见 MAA 文档）。
🔴 **完整 `Skill`/`Retreat`/`BulletTime` 的字段清单**未在本机文件中出现（本地多为旧格式），
下一步从 MAA 文档或 `resource/copilot/` 的 `SSS` 新格式作业补；使用时以
<https://maa.plus/docs/> 的「战斗流程协议」为准。

---

## 九-bis、★★ MAA 的**原生步进接口**：`SingleStep` 任务 ✅

这是"能否步进驱动"问题的**决定性答案**：MAA 有一个官方任务类型 **`SingleStep`**（"单步任务，目前仅支持战斗"）。

| 字段 | 值 | 说明 |
|---|---|---|
| `type` | `"copilot"`（默认） | 目前只支持 copilot |
| `subtype` | `"stage"` | 设置关卡，`details: {"stage_name": "1-7"}` |
| | `"start"` | 开始作战，无 `details` |
| | `"action"` | **单步执行一个战斗操作**，`details` 为战斗协议里的 action |

```jsonc
// subtype = "action"
{"type":"copilot", "subtype":"action", "details": {"actions": [ {"type":"Deploy","name":"先锋","location":[5,3],"direction":"Right"} ]}}
```

### ⚠️ 官方文档的示例是**错的** ✅（两处独立实测均复现）
源码 `src/MaaCore/Task/Interface/SingleStepTask.cpp` → `append_copilot_action()` 把 `details`
**直接**交给 `CopilotConfig::parse_actions()`，而后者第一行就是

```cpp
for (const auto& action_info : json.at("actions").as_array()) {
```

⇒ **`details` 必须是 `{"actions": [<单个 action>]}`**，不能是裸 action 对象。
本机实测对照（`cli.py maa-singlestep`，MaaCore **v6.17.5**）：

```
裸 action（官方文档写法，错）  -> task_id = 0      # 0 = 被拒
包在 actions 数组里（正确）    -> task_id = 1      # >0 = 接受
subtype='stage' 设关卡 1-7    -> task_id = 2
subtype='start' 开始作战       -> task_id = 3
```
失败时源码级报错只在 `asst.log` 里：
```
[ERR] asst::SingleStepTask::append_copilot_action invalid map<K, T> key
[ERR] asst::Assistant::append_task | invalid params: {...}
```

### 提交后如何读回
MAA 以 **`taskchain: "SingleStep"`** 发起任务链，用标准回调回传
`SubTaskStart/Completed` 与 `SubTaskExtraInfo` ⇒ 外部程序可以
**"发一步 → 等回调 → 再发下一步"**，这就是原生逐步驱动（🟡 "每次 append 只走一步"未在真机连设备验证）。

### 另外两条步进路径
| 路径 | 做法 | 粒度 |
|---|---|---|
| **B. `Custom` 单条内置任务** | `AsstAppendTask(h,"Custom",{"task_names":["AwardBegin"]})` | 一个内置识别任务（"只识别"的好办法） |
| **C. 像素级"先看再点"** | `AsstAsyncScreencap` → `AsstGetImage` → `AsstAsyncClick`，**完全绕过任务系统** | 一次点击 |
| D.（本项目实现）**一个任务链一步** | 每次只 append 一个任务、`AsstStart`、等 `TaskChainCompleted` | 一个任务链 |

路径 C 已 ctypes 实测跑通回调：`AsstAsyncScreencap→1`、`AsstAsyncClick→2`，
回调实收 `msg=4 {"async_call_id":1,"details":{"cost":0,"ret":false},"what":"Screencap"}`。

### copilot action 类型全集 ✅（抄自 `CopilotConfig.cpp`）
`Deploy` / `Skill` / `Retreat` / `SpeedUp`（=`二倍速`）/ `BulletTime` / `SkillDaemon` /
`DrawCard` / `CheckIfStartOver` / `MoveCamera` / `Click` / `Swipe` / `Output` 等。
**注意：没有 `deploy` 顶层键** —— 是 `actions[].type == "Deploy"` 配 `location`/`direction`/`name`；
费用条件用 `costs` / `cost_changes`。

---

## 十、MAA CLI / 其他接口面 ✅/🟡

| 项 | 结论 | 判据 |
|---|---|---|
| `MAA.exe --help` | **stdout/stderr 均为 0 字节**，退出码 0 ⇒ GUI 单实例（`gui.log`: `Command Line: MAA.dll --help` / `Secondary launch detected`），**没有 CLI** | ✅ 两次独立实测 |
| `maa-cli`（Rust 版命令行） | 本机未安装；官方仓库 <https://github.com/MaaAssistantArknights/maa-cli> 存在 🟡 | ✅ 未在 `D:\__soft\MAA` 出现 |
| MaaCore 的 Python 绑定 | 官方 `asst` 包（ctypes 直调 `MaaCore.dll`）；本项目也用 ctypes 自行绑定 | ✅ 官方仓库 `src/Python/asst/asst.py` |
| 是否支持"只识别不操作" | **没有 dry-run 字段**；用 `action:"DoNothing"` 的任务或 `Custom` + 单条识别任务，再读回调 `result` | ✅ |
| HTTP / REST 接口 | MAA 本体**不暴露** REST 服务端；它是**客户端主动轮询**用户提供的端点（`getTask`/`reportStatus`） | ✅ 报告 §4.8 |
| 进程外可观测面 | **`debug/asst.log` 是完整的决策链日志**（每行 `append_callback \| <Msg> <json>`，与回调**逐字相同**） | ✅ 见 §七 |
| 配套 / 易混项目 | **MaaFramework**（另一套架构，`MatchTemplateDetector`/`OcrDetector`/`ColorMatch` 属它，**不要与 MaaCore 字段混用**）；**MaaPipelineSupport**（VS Code 编辑器扩展，非运行时） | ✅ |

### ⚠️ 环境副作用记录
本次调查中实测 `MAA.exe --help` **触发了 MAA 自带更新器**，
`MaaCore.dll` 由 **v6.16.8 就地升级为 v6.17.5**（`MAA.dll` 同步）。两次版本导出表**完全一致**（33 项）。
`AsstCallerExtra`（6.17.0 发布说明声称新增）**未出现** 🔴。

