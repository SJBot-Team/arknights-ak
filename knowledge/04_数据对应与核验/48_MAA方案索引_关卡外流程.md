# MAA 方案索引（关卡外：启动 / 登录 / 选关 / 进关）
> 主题：**04E 实机 / 打图操作**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）
> 层级：**T3（索引/导航类）**　建立日期：2026-09-23（头部 6 行内日期）　任务：—　｜　**头部为 2026-09-30 自动回填**，推断项已标注

> **续篇（2026-09-23）**：MAA 的**完整一轮任务流程**（资源装配顺序、回调读回、`SingleStep` 原生单步、
> 实测坑）见 **`64_MAA与prts+_GUI操作方案.md`** §一 与 **`64a_MAA任务格式与步进接口_参考表.md`**。
> 本文件只覆盖**关卡外**的识别清单；**登录相关动作**按用户 2026-09-23 裁决**暂缓实机使用**。

> **来源**：`D:\__soft\MAA\resource\tasks\tasks.json` —— MAA（MaaAssistantArknights）的**任务流水线定义**，
> 即"图像识别 → 操作步骤"的可执行索引（869 个任务）。本文件是**我照抄/对照 MAA 的清单**，
> 依用户 2026-09-15 要求："**关卡外严格对照 MAA 现有实现的识别方式，目前阶段不要自行发明方案**"。
>
> **坐标基准**：tasks.json 里的 `roi` / `specificRect` 一律是 **1280×720** 基准；
> 本机模拟器帧是 **1920×1080** ⇒ 换算 **×1.5**。
>
> **合规与安全**：MAA 的登录走"**账号管理**"——**OCR 识别账号名 + 点「登录」按钮**，
> **不保存、不输入账号密码**（密码由用户在游戏内/账号管理界面自行输入）。本索引同样照此执行，
> 我方**不读取、不存储任何账号凭据**；登录若需人工输入，则**交回用户**。

## 一、主界面判定（"是否已在主界面"）
| 任务 | 识别 | 参数（1280×720） | 说明 |
|---|---|---|---|
| `StartUp` | **template** `SwitchTheme@ToggleSettingsMenu.png` | `roi [227,327,159,152]` | 用**设置按钮**判定已在主界面；`maxTimes:3`、`postDelay:1000` |
| `StartUp` Doc | — | — | 原文："**有时候明明已经在主界面了，停了一小会又弹个窗。多检测几次，一直在主界面才算完成**" |
| `Fight` | **template** `SwitchTheme@ToggleSettingsMenu.png` | `roi [227,327,159,152]`，`sub: ["Terminal-Entry"]` | 主界面 → 终端入口判定 |

**⇒ 我采用的规则**：主界面判定 = 模板 `SwitchTheme@ToggleSettingsMenu.png` 在 roi 内命中，
且**连续多次命中**才算稳定（照抄 MAA 的"多检测几次"）。

## 二、启动后的界面分流（`StartUpThemes`，JustReturn + 多候选 next）
MAA 把"启动后会遇到的各种界面"列成一个**候选清单**，逐个尝试：
```
BiliBiliNoMorePromptsNextTime, LeidianGoogleFrameworkConfirm, GameStart, StartToWakeUp,
StartToWakeUpOCR, StartLoginBServer, StartUpConnectingFlag, MainThemes#next, CloseAnnos#next,
OfflineConfirm, GameStartCheckResourceOCR, GameStartUpdateOCR
```
辅助任务：
| 任务 | 识别 | 参数 | 说明 |
|---|---|---|---|
| `LoadingIcon` | template `LoadingIcon.png` | `roi [480,210,320,280]` | 原文："开始唤醒最后阶段的**黑色正三角加载画面**" |
| `OfflineConfirm` | template `OfflineConfirm.png` | `roi [310,409,648,165]` | 离线/重连确认弹窗 |
| `CloseHomeSanity` | template | `roi [750,610,140,70]`，`next:["Home"]` | 主界面理智提示弹窗 |

## 三、★账号 / 登录（安全关键：照 MAA，不自行发明）
| 任务 | 识别方式 | 参数（1280×720） | 对应 1920×1080 |
|---|---|---|---|
| `AccountManager` | `action: ClickSelf` | `roi [855,660,150,40]` | (1282,990) 附近 —— **点"账号管理"** |
| `AccountManagerLoginButton` | **OCR** `text:["登录"], fullMatch:true` | `roi [423,329,448,147]` | (634,493)–(1306,714) —— **点「登录」** |
| `AccountCurrentOCR` | **OCR** `isAscii:true, text:[]` | `roi [495,335,126,23]` | (742,502)–(931,537) —— **读当前账号名** |
| `AccountManagerOfficial` | template | `roi [570,165,140,80]` | 官服标识 |
| `AccountListSwipeToTop` | `action: Swipe` | `specificRect [700,330,20,20]` → `rectMove [700,380,20,20]`，`specialParams [150]` | 账号列表滑动 |

**安全要点（我方的执行约束）**：
1. **只做**"点账号管理 → OCR 识别账号名 → 点登录"这类**界面级**动作；
2. **绝不**读取/记录/推断账号密码，**绝不**在日志或文档里留存账号凭据；
3. 若登录需要**人工输入密码/验证码** ⇒ **暂停并交回用户**；
4. 换号前先确认当前账号名（`AccountCurrentOCR`），**避免误登/误切**。

## 四、选关（关卡地图 → 关卡详情）
| 任务 | 识别方式 | 参数 | 说明 |
|---|---|---|---|
| `ClickStageName` | **OCR**（全屏）`roi [0,0,1280,720]`，`fullMatch`，`isAscii` | — | 找关卡名并**点击**；带 `ocrReplace` 纠错表 |
| `ClickedCorrectStage` | **OCR** `roi [845,72,220,50]` | 换算 (1268,108)–(1598,183) | 判定"已进入目标关卡详情" |
| `ClickedCorrectStageOrSwipe` | 组合：找到就点、没找到就滑 | — | 关卡地图上滑动寻找 |
| `EnterEpisodeNew` → `-Click` | template → **OCR** `text:["前往章节"]` `roi [1078,595,112,42]` | (1617,893)–(1785,956) | 章节入口 |
| `EnterChooseLevelOfDifficulty` | `ClickSelf` | `roi [0,598,131,122]` | (197,897) 附近 —— 选择难度 |

**OCR 纠错表（MAA 原文，值得照抄）**：`OPERATION` 去掉、`-]`→`-1`、空格去掉、`o`→`O`、`g`→`8`、
`t`→`T`、`:`/`'` 去掉、`(H\d+)O(?=-)`→`${1}0`、`.*?([A-Z]{2}-EX-\d+)`→`$1` 等。

## 五、进关（关卡详情/编队 → 战斗）
| 任务 | 识别方式 | 参数（1280×720） | 1920×1080 |
|---|---|---|---|
| `BattleStartPre` | **OCR** `text:["开始行动","开始作战","开始推演","开始突袭","开始试炼","开始测试"]` | `roi [1000,600,280,120]` | 中心 ≈ **(1710, 990)** |
| `BattleStart`（旧） | template `empty.png` + `ClickSelf` | `roi [989,318,232,374]` | 中心 ≈ (1657,757) |

## 六、我方的落地方式（不自行发明）
1. **关卡外**：把上表直接翻成 `plugins/task/pipeline.py` 的流水线配置
   （`recognize.template` / `recognize.ocr` + `action.click_self` + `next` 候选列表），**参数照抄 MAA**；
2. **关卡内**（战斗）：MAA 的战斗识别不适用于我们的"费用尺 + 暂停驱动"目标，
   这部分**沿用我方既有实现**（`clock/frame_clock.py` 的费用条相位 + `clock/paused_protocol.py` 的暂停协议），
   并**新增** `ocr` 识别类型到 `pipeline`（MAA 用 OCR 的场景我已照抄目标文本）；
3. **登录**：只做界面级动作 + OCR 读账号名；**凭据一律不碰**；需人工时交回用户。

## 七、待补
- 上表个别任务（如 `StartToWakeUpOCR`、`GameStartCheckResourceOCR`）的具体参数尚未逐条抄录，
  下一步按需补齐；使用时以 `D:\__soft\MAA\resource\tasks\tasks.json` 原文为准。


---

## 八、实战补充（2026-09-15，照 MAA 实跑中发现）

| 发现 | 内容 |
|---|---|
| `Terminal-Entry` 的位置 | **不在主 `tasks.json`**，在 **`tasks/UiTheme/Terminal.json`**；形式为 `JustReturn` + `next:[TerminalDefault, TerminalDark, TerminalSami, TerminalMistCity, TerminalSiege, TerminalSarkaz, TerminalDelicious, …]`，`crop_doc.roi=[903,120,97,58]` ⇒ **终端按钮按 UI 主题有多套外观，需逐个候选尝试** |
| 章节切换 | `ClickChapter`：**OCR**（`text:[]` 由调用方传入目标章节名），`roi [142,43,250,150]`；**`ClickChapter1` 的 text = ["觉醒"]** ⇒ **第一章名为「觉醒」**；`ToChapter1` 为候选链（`ClickChapterNew` 优先） |
| 启动候选链实测 | `GameStart`(0.997) → `StartToWakeUp`(0.926) → `NextAfterLoadingIcon`(0.998) → `StartUp`(0.994) 全部命中 ⇒ 照 MAA 可行 |
| OCR 引擎 | PRTS+ 自带 Tesseract v5.3.0（`chi_sim`/`eng`/`arknights_digit`/`ark_digit`）；**调用必须显式 `encoding="utf-8"`**，否则中文乱码 |
| `text:[]` 的语义 | MAA 里表示"**目标文本由调用方给出**"（如关卡名、章节名），**不是**"任意文本即命中" |


---

## 九、章节导航的 MAA 约定与实测（2026-09-15 补充）

| 项 | MAA 定义（来源 `tasks.json`） | 实测 |
|---|---|---|
| 章节总览入口 | `ClickChapterNewOverview`：OCR「乐章」，`roi [1175,20,65,40]` | ✅ 实测「乐章收录」位于 @1920 (1763,30)-(1860,90)，**与换算完全吻合** |
| 进度档位 | `ClickChapterNewDefaultProgress`：OCR「默认进度」 | ✅ 乐章总览顶部存在「默认进度/奖励进度/完成进度」 |
| **章节滑动** | `ChapterSlowlySwipeToTheLeft`：`[300,100,20,20]→[900,100,20,20]`，Doc「在上面一点滑避免点到关卡划不动」 | ❌ 在章节详情页 / EP15 地图 / 乐章总览 均**无变化** |
| 关卡滑动 | `SlowlySwipeToTheLeft/Right`：`[300,310,100,100]↔[880,310,100,100]`，`specialParams [200,1,2,0]` | ❌ 同上 |
| 寻关流程 | `FullStageNavigation`：「右滑 10 次，然后检测关卡并左滑」 | 待验证 |
| 关卡点击 | `ClickStageName`（全屏 OCR）、`Stage1-7`（OCR「1-7」，`roi [0,190,1080,60]`） | 待验证 |

**坐标基准**：MAA 的 roi 为 1280×720 ⇒ 本机 1920×1080 需 **×1.5**。
**推断**：乐章总览第一排卡片上方有「EP 08 / EP 07」字样，疑为**上一排章节**或**可点击标签** ⇒ 下一步优先验证。


---

## 十、★章节导航的真实方式（2026-09-15 实测，与 MAA 滑动方案的差异）

| 环节 | 实测有效的做法 | 坐标（帧 @1920） |
|---|---|---|
| 进章节总览 | 主界面 → 终端 → 底部导航「**曲谱**」 | 终端入口 ≈(1315,258) |
| 乐章总览 | 右上角「**乐章收录**」（= MAA `ClickChapterNewOverview` 的「乐章」） | ≈(1810,60) |
| **切章** | **乐章总览里点章节标签（EP08 等）** 可直达该章详情；**章节详情底部三张相邻章节卡片**，**点左侧卡片逐级后退** | 标签 ≈(774,34)；左侧卡片 ≈(250,943) |
| 进关卡地图 | 章节详情右下「**前往章节**」 | ≈(1693,924) |
| 选关 | 关卡地图点关卡名节点（1-1 等）；MAA `Stage1-7` roi 换算后 y≈285~375，**实测吻合** | 1-1 ≈(937,519) |
| 关卡详情 | 底部三按钮：突袭模式 / **演习** / 开始行动 | ≈(681,973) / **(1441,973)** / (1103,973) |
| 出战 | 编队界面右侧「**开始行动**」 | ≈(1583,681) |

**MAA 滑动方案在本机的实测结果**：`ChapterSlowlySwipeToTheLeft`（y=100@1280 上方滑动）、
`SlowlySwipeToTheLeft/Right`（y=310@1280）在**章节详情页 / EP15 关卡地图 / 乐章总览**均**无变化**
⇒ **本关卡的章节切换以"卡片点击"为准**，滑动仅作为 MAA 通用实现的参考。
**坐标系提醒**：截图预览 1066×600 ⇒ 帧坐标 = 预览坐标 × **1.801**。


---

## 十一、战斗内（关卡内）操作：MAA 定义（战斗不适用"关卡外严格照 MAA"的同一套，但定义可照抄）

| 任务 | 定义（来源 `tasks.json`） | 含义 |
|---|---|---|
| **`BattleDeployWhenPause`** | `{"algorithm":"JustReturn","specialParams":[1]}` | **在暂停时部署**（MAA 交其 C++ 核心执行）⇒ 与 prts+ 的"子弹时间"同源 |
| `BattleDeployDirectionRectMove` | `rectMove [-48,-48,96,96]` | 部署后**拖动调朝向** |
| `BattleOperAvatar` | `rectMove [7,32,60,60]` | 卡片中心 → 头像区域 |
| `BattleOperCost` | `rectMove [-10,12,30,17]` | 卡片中心 → 费用数字 |
| `BattleOperAvailable` | `specialParams [100]`（V 通道均值阈值），`rectMove [0,0,10,10]` | 判定卡片是否可用（费用够/未冷却） |
| `BattleCancelSelection` | `{"action":"ClickRect","specificRect":[630,0,20,20]}` | 取消当前选择 |
| `BattleHasStarted` | `roi [1178,33,53,39]`；Doc：「**20260109 YJWL更新后暂停按钮向右移动约8像素, 且暂停后亮度上限245**」 | 判定已进入战斗 + 暂停按钮位置 |
| `BattleOperRetreat` / `BattleOperRetreatJustClick` | — | 撤退 |
| `BattleOfficiallyBegin` / `BattleHpFlag` / `BattleCostFlag` / `BattleKillsFlag` | 已用于我方 `ui_state`（battle 判定） | 战斗界面判定 |

**本轮实测结论**：`cost` 读取✅、暂停✅、待部署区卡片识别✅，但**"部署"动作尚未打通**（点选式与拖拽式各试 2 次均未生效）⇒ 下一轮优先解决。
