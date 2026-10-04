# 40 外部工具解析：ArknightR 与 AFA.exe
> 主题：**04B 读代码 / 反汇编**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）

> 层级：**T2（静态分析取证：PE/元数据表/bundle 内容）**　日期：2026-09-14
> 方式：全部**静态分析**，未运行任何被分析程序；临时脚本在 `ak\.tmp\`
> 目的：从现成工具中提炼**工程经验**与**可复用资产**

---

## 〇、★ 最重要的一条

> **`ArknightR` 不是解包器，而是一个「《明日方舟》战斗模拟器 + 沙盒对战 + 地图编辑器 + 肉鸽模拟器」——用作者自研战斗引擎实现的 Unity 桌面程序（v0.1032）。**
>
> 这直接关系到本会话的终极目标（"基于知识库编程模拟还原特定游戏情景"）：**已经有人把一个可玩的舟游战斗模拟器做出来了**，它的架构值得当作参照。
>
> ⚠️ **但必须明确边界**：ArknightR 是**社区实现**，用的是**作者自己的战斗引擎**（`Buffs`/`Skills`/`Modifys` 全是自研类），**不是官方代码的还原**。因此它
> - ✅ 可以借鉴**架构与工程范式**
> - 🟡 可以用它的表结构/字段设计做**交叉参考**
> - ❌ **不能作为机制与数值的权威来源**（权威来源仍是 `29/33/34/37/38/39` 的客户端反汇编与 gamedata）

---

## 一、ArknightR（`E:\__file\ak\ArknightR`）

### 1.1 它是什么（判据全部来自二进制/数据）

| 判据 | 证据 |
|---|---|
| 名称/版本 | `PlayerSettings`：`productName='ArknightR'`、`companyName='Myacg'`、`bundleVersion='0.1032'`；Unity **2021.2.10f1** |
| 自研战斗引擎 | 命名空间类数：`Buffs` 614 / `Skills` 267 / `Modifys` 76 / `Bullets` 38 / `Units` 14 / `MainUI` 30 / `BattleUI` 25 / `DungeonUI` 18 / `MapBuilderUI` 15 |
| 直指舟游机制的类名（中文） | `Skills.乌尔比安位移`、`Skills.佩佩夏活领袖猫召唤`、`Buffs.凋亡减攻中毒`、`Modifys.对飞行额外伤害`、`Units.箱子类敌人`、`MapManager`、`BattleManager`、`PathManager`、`DamageInfo`、`ElementBar`（元素损伤） |
| 地图编辑器 | `MapBuilderUI.UI_MapBuilder` / `UI_PathPage` / `UI_WavePage` / `UI_GridInfo`、`MapGrid`、`OneWave`、`PathPoint` |
| 肉鸽模拟 | `DungeonManager`、`DungeonCard`、`DungeonRelic`、`DungeonReward`、`HopeHelper`、`ContractData` |
| 策划源表 | `battle.xlsx`（2.9MB）9 个 sheet：`CardData / UnitData / SkillData / BuffData / ModifyData / BulletData / EffectData / ContractData / RelicData` |
| 用户存档 | `data.sav`（26.7KB）**UTF-8 明文 JSON**：`{"Cards":[{"DefaultUsingSkill":1,"UnitId":"星熊","Upgrade":2,"Level":90},…]}` |

### 1.2 技术构成

- **Mono，不是 IL2CPP**：有 `ArknightR_Data\Managed\`（104 dll），**无** `il2cpp_data`
- 业务代码只有 **2 个自研程序集**：

| 程序集 | 大小 | TypeDef | MethodDef | 内容 |
|---|---|---|---|---|
| `Assembly-CSharp.dll` | 1,060,352 B | **1,623** | **6,684** | 全部业务逻辑（战斗/Buff/技能/UI/编辑器/爬虫） |
| `Assembly-CSharp-firstpass.dll` | 916,480 B | 581 | 5,413 | 纯第三方（FairyGUI / Spine / Newtonsoft 等） |

- **值得注意的第三方依赖**：`AstarPathfindingProject.dll`（A* 寻路，敌人走格子）、`ExcelDataReader.dll`（读 xlsx）、`Unity.Addressables 1.19.15`、`FairyGUI`（UI 框架）、**`OPS.Obfuscator.dll`（代码混淆器运行时）**、`DOTween`
- **混淆情况**：方法/内部类型名被混淆成 `e2t/rtt/ast`，**但业务类名（`Buffs.*`、`Skills.*`、中文名）完全保留**——原因见 §1.3 第 8 条
- **资源框架**：Unity Addressables（`aa/catalog.json` 5.87MB，`m_InternalIds` 共 6,520 条）；`aa/AddressablesLink/link.xml` 是**反射/序列化可寻址类型白名单**

### 1.3 ★ 可借鉴的工程经验（核心产出）

**① 数据驱动的行为分发：「表里 `Type` 列 = C# 类名」，反射实例化 —— 本次最硬的发现**

`battle.xlsx` 各 sheet 的 `Type` 列去重值，与 C# 命名空间下的类名**逐字完全匹配**：

| sheet | Type 去重值数 | 完全匹配 |
|---|---|---|
| `SkillData` | 234 | **234 / 234（100%）** |
| `ModifyData` | 63 | **63 / 63** |
| `UnitData` | 13 | **13 / 13** |
| `BulletData` | 36 | 35 / 36 |
| `BuffData` | 546 | 544 / 546 |

反射证据：MemberRef 含 `System.Type.GetType`、`Activator.CreateInstance`、`get_Assembly`、`GetField`、`Invoke`；TypeRef 含 `System.Reflection`。

> **经验**：把"行为"做成"一个行为一个类"，用数据行的 `Type` 直接选类 ⇒ **核心代码零修改即可扩机制**。614 个 Buff 类、267 个技能类都是这么长出来的，**没有巨型 `switch`**。
> **对我们的意义**：解析舟游 gamedata 的"效果/机制处理器"完全可以用同一范式（`buff_type`/`skill_type` → 处理器类注册表）。

**② 三行表头导表规范，类型列直接写 C# 类型名**
`Id / Type / …`（中文显示名）→ 英文字段名 → 类型（`string/bool/int/float/SkillReadyEnum/UnityEngine.Vector2Int[]/…`）。
`#` 前缀行表分类注释；单元格里甚至有 `'不要删！'`——**表格自带护栏**。

**③ 运行期数据用 JSONL（行式 JSON，省略默认值），不用大 JSON 数组**
bundle 内 `TextAsset 'BuffData'`（505,002 B）实测：
```
{"Id":"测试Buff","Type":"测试Buff"}
{"Id":"攻速提升","Type":"数值变化","Data":{"t":["AgiAdd"]}}
{"Id":"生命提升叠加","Type":"数值变化叠加","Data":{"t":["HpRate"],"MaxLevel":99}}
```
**共 4,365 行，每行独立可 `json.loads`，一行最多 8 个字段**。
> **经验**：体积小（4365 条仅 505KB）、**逐行 diff 友好、可追加/流式、单行坏掉不毁全表**。

**④ 数据双轨制：散装 txt + 打包副本，散文件优先**
D: 副本的 `StreamingAssets\data\`（9 个 `.txt`，与 bundle 内 TextAsset 同名同源）与 `StreamingAssets\map\`（**42 个 `.map`**，文件名就是关卡代号：`TN-1 冰与火.map`、`H13-4.map`、`圣光启迪.map`…）。
> **经验**：发布走 Addressables，调试/热改走散文件覆盖目录 ⇒ 改数值不用重新打包。**很便宜的可维护性投资。**

**⑤ 拿舟游素材的路线：绕开加密，走公开静态源**
内建工具族：`SpineDownLoadTool`、`EnemySpineDownloadTool`、`StandPicDownLoadTool`、`SpineBoneFindTool`、`EnemyInfoExcelTool`、`MapInfoExChangeTool`；URL 字面量：`http://static.prts.wiki/spine38/char/`、`.../enemy/`、`http://prts.wiki/w/`、`http://prts.wiki/images`。
> **经验（重要）**：**它完全没有实现舟游的 AES/XXTEA 解密**，而是抓 PRTS 静态 CDN 的 Spine（`.skel/.atlas/.png`）+ 立绘，再在自己工程里重制。
> ⇒ **别把预算花在复刻加密上，优先找已公开的等价源。**

**⑥ 自产资源包不做任何加密**：833/833 明文 `UnityFS`；`catalog.json`、`link.xml`、连 `data.sav` 都是明文 JSON。

**⑦ 按用途选两套序列化**：编辑器存档用 Json.NET `TypeNameHandling` 直存对象图（地图里可见 `$type` + `$values` + `GridInfo[,]` 二维数组）；运行期数据表用 JSONL + `Type` 列。**分工很清楚。**

**⑧ 混淆只打内部实现，保留"数据契约名"**：因为表里按名字引用类，混淆就崩 ⇒ 必须维护不可混淆白名单（Unity 侧对应 `link.xml` 的 `preserve="all"`）。

**⑨ 分领域命名空间 + 中文类名**：`Buffs`(614)/`Skills`(267)/`Modifys`(76)/`Bullets`(38)/`Units`(14)，类名与策划表 `Type` 列 1:1 ⇒ **表↔代码↔讨论三处零翻译成本**。

**⑩ Mono + 裸 `.dll` 交付对同好分析极友好**：本次**未用反编译器**，仅靠自写 ECMA-335 元数据解析就拿到 1,623 类 / 6,684 方法 / 957 条字符串字面量。

**⑪ 关键战斗分支都有可读日志**：中文用户字符串全是调试/错误文案（`表: {0} 的 {1} id重复`、`此次推力大小为{0}`、`{0}的{1}全部目标不合法,强制打断抬手动作{2}`）——把**校验断言直接写进流程**，与"逆向知识库要可追溯"的目标同构。

### 1.4 ⚠️ 重要：E: 副本被裁剪过，完整副本在 D:

| | `E:\__file\ak\ArknightR` | `D:\__soft\ak\ArknightR` |
|---|---|---|
| 文件数 / 总量 | 969 / **180.3 MB** | 3,543 / **735.5 MB** |
| `.bundle` 数 | 833 | **3,336** |
| 关键目录 | 仅 effect/data/maps/dungeontile | **`bundles\units` 1918 个 / 407.7 MB**、`ui` 53 / 75.3 MB、`effect` 1297 / 134.2 MB |
| `MonoBleedingEdge\` | **缺失**（⇒ **E: 副本大概率无法启动**） | 有 |
| `StreamingAssets\data\*.txt` | 缺失 | **有 9 个** |
| `StreamingAssets\map\*.map` | 缺失 | **有 42 个**（含关卡代号命名） |

两份 exe SHA256 相同（`72A6386B…D9FBEE`，同为 v0.1032）。
> **⇒ 要取"工具携带的舟游衍生数据/素材"，应看 D: 副本**（角色/敌人 Spine 模型在那 407MB 里，散装表与地图也在 D:）。

**833 个 bundle 的性质**：标准明文 `UnityFS`（833/833，无自定义头/无加密）；目录分布 = 作者工程结构；包内**确实带舟游内部资源名**（`Texture2D 'enemy_mandra_15'`、`Material 'Boss_Rathalos_01_dikuai'`）⇒ **是 ArknightR 自己导出的 Addressables 包，但素材源自舟游本体（提取后重制）**。

---

## 二、AFA.exe（`D:\__soft\ak\AFA.exe`）

### 2.1 它是什么

> **`Arknights Frame Assistant` —— 用 AutoHotkey v2.0 写的《明日方舟》PC 端辅助宏工具**（快捷键技能/撤退、跳帧、自动接管战斗、自动更新），开源在 GitHub `CloudTracey/arknights-frame-assistant`。

判据：内嵌源码首行 `; <COMPILER: v1.1.37.02>` / `#Requires AutoHotkey v2.0`；RT_MANIFEST 为 AHK 清单；业务串 `HotIfWinActive("ahk_exe Arknights.exe")`、`ApiUrl := "https://api.github.com/repos/CloudTracey/arknights-frame-assistant/releases"`、`configDir := A_AppData "\ArknightsFrameAssistant\PC"`。

### 2.2 技术构成

| 项 | 结论 | 证据 |
|---|---|---|
| 语言 | **AutoHotkey v2.0**（非 .NET / 非 PyInstaller / 非 Go/Rust/C++） | AHK 专有语法 `Buffer`/`Map`/`A_TickCount`/`IniWrite`/`FileInstall`/`ImageSearch` |
| 不是 .NET | CLR Runtime Header = **rva 0 / size 0** | 数据目录第 15 项；无 `BSJB`/`#~` |
| PE | PE32+ / x64，6 段，ImageBase `0x140000000`，Subsystem GUI | 自写 PE 解析 |
| 版本 | `RT_VERSION` 里 `FileVersion = ProductVersion = 2.0.26`（**无 FileDescription/CompanyName** ⇒ 资源管理器显示为空） | — |
| 无 overlay | 末段结束 `0x1cbe00` == 文件长度 ⇒ **trailing bytes = 0** | 不是自解压多合一 |

**RT_RCDATA ×4（关键）**：

| 资源名 | 大小 | 说明 |
|---|---|---|
| `..\LOGO.PNG` | 341,766 B | 脚本用 `FileGetSize(...) != 341766` 做**内容指纹校验** |
| `RESOURCES\IMAGES\TAKEOVERBUTTON_1.PNG` / `_2.PNG` | 751 / 2,111 B | `ImageSearch` 用的"接管按钮"模板 |
| **`1`** | **151,066 B** | **完整 AHK v2 明文源码**（偏移 `0x1a6738`） |

功能：动作族 `Skill/OneClickSkill/PauseSkill/Retreat/…`；跳帧表 `Map("30","1","60","2",…,"240+","7")`；`ImageSearch(..., "*60 …")` 找接管按钮；**用 `InjectTouchInput` 触摸注入（而非键鼠模拟）以打进模拟器**；配置 INI 落 `%AppData%\ArknightsFrameAssistant\PC\`。

### 2.3 ★ 可借鉴的工程经验

**① 脚本语言 + 编译发布，但不加密** ⇒ 源码明文躺在 `.rsrc` 里，几行代码就能取出。
> 对我们的决策：小工具别指望加密，把力气花在可维护性。

**② `FileInstall` + 精确字节数当版本指纹（自愈式资源释放）**
```ahk
if (!FileExist(LogoPath) || FileGetSize(LogoPath) != 341766)
    FileInstall "..\logo.png", LogoPath, 1
```
⇒ 一次解决"文件不存在/被改坏/版本旧"三种情况，**比 mtime 或版本号更鲁棒**。

**③ 脏检查（dirty check）驱动的设置界面**：建立初始值快照 → 逐控件比较 → 有改动才亮"保存"。适合含"需重启才生效"项的面板。

**④ 更新器写成「状态机 + 结构化返回」，不抛异常**
```
{status:"up_to_date", localVersion, remoteVersion, downloadUrl}
{status:"update_available", …, changelogBody}
{status:"rate_limited" / "token_invalid" / "check_failed", message(给人), errorDetail(给日志)}
```
⇒ UI 只按 `status` 分发，日志只吃 `detail`。

**⑤ 自更新必处理的四件事（可直接照抄清单）**：代理与鉴权 → 传输鲁棒性（分块 + 停顿检测）→ **原子替换**（备份 + 生成 `.bat` 等本进程退出后替换/重启/清理）→ 全链路日志。

**⑥ 自动化四件套**：`WinGetClientPos` 客户区 → `ClientToScreen` 换算 → `ImageSearch` 图像锚点（容差 60）→ 原生输入注入；**所有等待时间都做成配置**（不同机器/模拟器性能差异极大）。

**⑦ 版本号写进 `RT_VERSION`**：可以"隐身"（不写公司与描述），但**版本字段必须有**——自动更新的前提是程序能自报版本。

---

## 三、`D:\__soft\ak` 其它工具一览

| 目录 | 类型 | 用途 |
|---|---|---|
| `ArknightsCostBarRuler-v2.3.2\`（+ `cost_ruler` 等 4 份副本） | **Rust 编译的桌面程序**（Tauri 形态） | 量舟游费用条像素位置的覆层标尺；含 `calibration/profile_*.json` 校准档 |
| `ArkUnpacker\` | **PyInstaller（Python 3.12）+ 内嵌 AssetStudio .NET 工具链** | 舟游资源解包：Python 外壳调度 AssetStudio |
| `prts+\` | **PyInstaller（Python 3.9）** | 生成/管理舟游 PC 端键鼠方案（示例 json 2.7KB） |
| **`技能搜索与合并优化\`** | **Vue 3 SPA + PWA（已构建）** + **`ArkDPS代码逻辑解析.md`(17KB)** | "ArkDPS" 纯前端 DPS 计算/技能搜索。⚠️ **那份 17KB 的中文源码级解析与我们的知识库目标高度相关，建议后续单独精读** |
| `费用条尺子\` | 第三方现成工具集合（OnTopReplica + Snipaste）+ 手工尺子 PNG | 人工量费用条 |

---

## 四、对我们自建工具的建议

1. **数据层采用「三行表头 + JSONL 行式表」范式**（源自 ArknightR 的 `battle.xlsx → *.txt/TextAsset` 流水线）：一行一个 JSON、省略默认值、逐行可 diff/追加/断点续处理。对"几千行且常需人工校正"的知识库表尤其重要。
2. **机制分发用「`Type` 字段 = 处理器类名」的注册表，而不是巨型 switch**。我们解析舟游 gamedata 时可照用（`buff_type`/`skill_type` → 解析器类），并把"名字不许改名"写进约定。
3. **资源获取优先走公开静态源 + 已解包缓存，别复刻游戏加密**：把"解密"做成可选插件、把"公开源/缓存"做成主路径，并内置下载器的**进度与失败重试日志**。
4. **自产产物不加密，并保留"散文件优先"的覆盖目录**：`build/` 是产物、`overrides/` 是人工修正层，同源可 diff。
5. **所有工具输出「结构化状态 + 双通道日志」**：`{status, version, message(给人), errorDetail(给日志)}`，日志落固定路径；批处理可对 `status` 做断言。另抄 AFA 的**自愈式资源释放**（精确字节数当指纹）。
6. **沉淀两条腿的分析能力**：
   - **Mono 目标 → ECMA-335 元数据解析**（子代理在 `.tmp\dotnet_md.py` 实现了一个**不依赖 .NET SDK** 的读取器：TypeDef/MethodDef/TypeRef/MemberRef/`#US`）
   - **IL2CPP 目标 → `read_cpp.py` + dump.cs**（已有）
   建议把前者整理进 `ak\code\tools\`。

---

## 五、待查与卡点

| 项 | 状态 | 卡点 | 下一步 |
|---|---|---|---|
| `Assembly-CSharp.dll` 方法体级反编译 | 🔴 未查明 | 本机**无 .NET SDK**（`dotnet tool install ilspycmd` 失败）；也无 ILSpy/dnSpy | 装 .NET SDK 后用 `ilspycmd`，或直接装 dnSpyEx（Mono 目标可直接反编译） |
| ArknightR 运行行为 | 🔴 未验证 | 静态分析；**E: 副本缺 `MonoBleedingEdge\` 大概率无法启动** | 用 **D: 完整副本**启动；配合 ProcMon 观察读写路径 |
| E: 副本被裁掉了什么 | 🟡 | 无来源元数据 | 对比两份 `catalog.json` 的 `m_InternalIds` 差异集 |
| `OPS.Obfuscator` 混淆名映射 | 🔴 | exe/dll 内无映射文件 | 一般无法还原，只能靠行为/调用图反推 |
| AFA 动态行为（注入是否被拦） | 🔴 未运行 | 需游戏运行，超出静态分析范围 | **抽源码通读**（`.rsrc` RT_RCDATA `1`，偏移 `0x1a6738`）比动态测试更安全 |
| `ArkDPS代码逻辑解析.md` | 🟡 未读 | 超出本次范围 | **建议后续单独精读** |

## 相关文件

- `knowledge\04\00_目录.md`（知识导航）
- `knowledge\04\30_信息获取渠道索引_按数据层级.md`
- `code\unpack\`（既有解包流程脚本）
- `ak\.tmp\`（本次静态分析脚本，可复现）
