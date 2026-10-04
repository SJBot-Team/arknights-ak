> WARN-INTERP: read_cpp.py 的 m / dis / who / xref 需要 pefile + capstone；ak\code\vision\.venv 未装 pefile（只有 find/cls 可用，它们只读 dump.cs）。必须用 D:\__soft\Anaconda\python.exe（已装 pefile+capstone）。read_cpp.py call 只输出 call/jmp 目标，是最省上下文的读法。（2026-09-28 T-077 实测）

# 29 cpp 层定位与读取流程（IL2CPP）
> 主题：**04B 读代码 / 反汇编**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）

> 层级：**T1（反汇编/元数据一手实证）**　建立日期：2026-09-13　任务：T-034 ①
> 样本：**日服 PC 客户端** Unity 2021.3.39f1，resVersion `26-08-16-14-00-43_415873`
> 证据形式：Il2CppDumper 产出的 dump.cs（类/字段偏移/方法 RVA）+ capstone 反汇编真实 x64 机器码

## 〇、结论速览

| 问题 | 结论 | 置信 |
|---|---|---|
| metadata 是否加密 | **否**，明文标准 IL2CPP，magic `af 1b b1 fa`，version 29 | T1 |
| 能否直接 dump | 能。Il2CppDumper 一次跑通，90 个 DummyDll + dump.cs 73MB | T1 |
| 局内数值用什么类型 | **`FP` 定点数 = Q32.32**（64 位，`FRACTIONAL_PLACES=32`，`ONE=2³²`） | T1 |
| 浮点→定点如何转换 | `(long)(value * 4294967296.0f)`：**单精度乘法后向零截断** | T1 |
| 局内逻辑步长 | **1/30 秒 = 0.03333330154418945**（Unity `Time.fixedDeltaTime`） | T1 |
| 战斗是否确定性 | **是**。快照 + 操作队列 + 随机种子 + 哈希校验 + 回放控制器 | T1 |
| 三角函数 | 查表（`SinLut`/`CosLut`/`TanLut`/`AcosLut`，`LUT_SIZE=205887`），非 libm | T1 |

这一层的意义：**它是「数值精度」问题的唯一权威来源**。gamedata 的 excel 与 Lua 伪代码只给公式形状，不给量化方式；同一公式在 float、double、Q32.32 下的第 8 位有效数字起就分道扬镳，而极限玩法恰恰在抠这些位。

---

## 一、目标产物与合规前置

### 1.1 两个输入文件

| 文件 | 路径 | 大小 | 作用 |
|---|---|---|---|
| `GameAssembly.dll` | `D:\YostarGames\Arknights_JP\GameAssembly.dll` | 127.9 MB | x64 PE，真正的 C# → C++ 机器码 |
| `global-metadata.dat` | `...\Arknights_Data\il2cpp_data\Metadata\global-metadata.dat` | 39.3 MB | 类型/方法/字段/字符串元数据 |

> **仅有日服客户端含这两个文件**：遍历本机所有 Arknights 安装目录后，只有 `Arknights_JP` 是 PC(IL2CPP) 端。国服/其他端在本机上没有同层级的二进制。

### 1.2 合规（依 `meta\合规声明_游戏客户端.md` 2026-09-02 版）

- 操作前已确认**游戏进程未运行**（`Get-Process Arknights*,UnityPlayer*` 无结果）。
- 未备份文件在游戏未运行时可**复制备份后读取**；原文件只读，不修改。
- 备份落点：`E:\__file\ak_kb\client_res\il2cpp\`（`GameAssembly.dll`、`global-metadata.dat`）。
- 备份是**只读副本**，后续所有分析只读副本。

### 1.3 校验 metadata 是否加密（每次换版本都要先做）

```powershell
$b=[System.IO.File]::ReadAllBytes("<...>\global-metadata.dat")[0..31]
($b|ForEach-Object{$_.ToString('x2')}) -join ' '
```

预期输出（本次实测）：

```
af 1b b1 fa 1d 00 00 00 00 01 00 00 f0 5c 04 00 ...
└─ sanity ─┘ └─ v29 ─┘ └─ stringLiteralOffset=0x100 ─┘
```

- 前 4 字节 `af 1b b1 fa` = `0xFAB11BAF`（IL2CPP sanity magic）→ **明文**。
- 第 5-8 字节 `1d 00 00 00` = 29 → metadata 版本。
- 若这里不是 `af 1b b1 fa`，说明被加固厂加密（`code\unpack\revenant\research\il2cpp-metadata-decryption.md` 记录了那种情况的处理路线：离线模拟解密器 / 活进程 hook dump）。

---

## 二、工具链（可复现）

### 2.1 Il2CppDumper

- 版本：`v6.7.46`，自包含 win 版（无需额外 .NET 运行时）：`Il2CppDumper-win-v6.7.46.zip`
- 下载（Steam++ 加速下 GitHub 需关吊销检查）：
  ```powershell
  curl.exe -L --ssl-no-revoke -o Il2CppDumper.zip `
    "https://github.com/Perfare/Il2CppDumper/releases/download/v6.7.46/Il2CppDumper-win-v6.7.46.zip"
  ```
- 本地位置：`E:\__file\ak_kb\tools\il2cpp\Il2CppDumper.exe`
- 运行（**注意它是交互式程序，跑完会等按键**，在非交互 shell 里末尾会抛 `Cannot read keys`，但那发生在全部产物写完之后，属正常）：
  ```powershell
  & 'E:\__file\ak_kb\tools\il2cpp\Il2CppDumper.exe' `
      'E:\__file\ak_kb\client_res\il2cpp\GameAssembly.dll' `
      'E:\__file\ak_kb\client_res\il2cpp\global-metadata.dat' `
      'E:\__file\ak_kb\client_res\il2cpp\dump'
  ```

本次输出关键行（可作对照）：`Metadata Version: 29` → `CodeRegistration : 185f80950` → `MetadataRegistration : 18696fef0` → `Done!`（Dumping / struct / dummy dll 全部 Done）。

### 2.2 产物

| 产物 | 大小 | 用途 |
|---|---|---|
| `dump.cs` | 73.6 MB / 203 万行 | **主索引**：类、字段偏移、方法 RVA |
| `il2cpp.h` | 113 MB | C 结构体布局（要按内存布局复刻时用） |
| `script.json` | 205 MB | 方法地址表（喂 IDA/Ghidra 脚本用） |
| `stringliteral.json` | 3.7 MB | 字符串字面量（按字面量找热更代码用得上） |
| `DummyDll\*.dll` | 90 个 | 伪程序集，可丢进 dnSpy/ILSpy 看继承关系 |

产物目录：`E:\__file\ak_kb\client_res\il2cpp\dump\`

### 2.3 自制读取器 `code\tools\read_cpp.py`

dump.cs 只有**声明**（函数体是 `{ }`），要拿实参/常量必须回读机器码。`read_cpp.py` 把两件事接起来（pefile 做 RVA→文件偏移，capstone 反汇编 x64）：

```powershell
$py='C:\Users\23922\Documents\ds_harness\课设\comp_physics\.venv\Scripts\python.exe'
$t='C:\Users\23922\Documents\ds_harness\ak\code\tools\read_cpp.py'

& $py $t find <正则>              # 在 dump.cs 里搜类/方法/字段
& $py $t cls  <类名>              # 打印某个类的完整定义（字段偏移 + 方法 RVA）
& $py $t m    <类名>.<方法名> [n]  # 定位方法并反汇编 n 条
& $py $t dis  <RVA十六进制> [n]    # 直接反汇编某地址
& $py $t who  <RVA十六进制>        # 按 RVA 反查"这是哪个方法"，并反汇编前几条
& $py $t call <类名>.<方法名>      # 只列方法体里的 call/jmp 目标，用来追调用链
```

依赖：`capstone`、`pefile`（已装在 `课设\comp_physics\.venv`）。

**rip 相对操作数会自动注解**，这是读 `.cctor` 里 `static readonly` 常量的关键：

```
0x054E4E20  f30f5905381e8800   mulss xmm0, dword ptr [rip + 0x881e38]
                               ; -> 0x5D66C60 u32=1056964608 f32=0.5
```

### 2.4 读 Unity 运行期设置 `code\tools\read_gvm.py`

逻辑步长这类值不在 C# 里，而在 Unity 打包时写死的序列化文件 `globalgamemanagers` 中：

```powershell
& $py 'C:\Users\23922\Documents\ds_harness\ak\code\tools\read_gvm.py' `
    'E:\__file\ak_kb\client_res\unity_player\globalgamemanagers' TimeManager
```

已备份的 Unity 播放器文件：`E:\__file\ak_kb\client_res\unity_player\`（`globalgamemanagers`、`boot.config`、`app.info`、`RuntimeInitializeOnLoads.json`、`ScriptingAssemblies.json`）。

---

## 三、关键发现 A：`FP` = Q32.32 定点数

`dump.cs` 1236143 行，`public struct FP`（TypeDefIndex: 32190）：

```
public long _serializedValue;        // 0x0
public const int  NUM_BITS = 64;
public const int  FRACTIONAL_PLACES = 32;
public const long ONE  = 4294967296;          // 2^32
public const long TEN  = 42949672960;         // 10 × 2^32
public const long HALF = 2147483648;          // 2^31
public const long PI         = 13493037704;
public const long PI_OVER_2  = 6746518852;
public const long PI_TIMES_2 = 26986075409;
public const int  LUT_SIZE   = 205887;
public static readonly long[] AcosLut, SinLut, TanLut;
public static readonly FP Precision, Epsilon, LutInterval, Deg2Rad, Rad2Deg, ...;
```

**判定**：这是 **SoftFloat / FixedMath.Net 风格的 Q32.32**（`ONE = 2³²` 是签名特征）。所有 `FP` 字段（如 `BattleController.s_fixedPlayTime`、`s_deltaPlayTimeFP`、`m_timeDeltaNoEnemy`）都是 8 字节定点。

### 3.1 浮点→定点的**确切**转换（RVA 0x54E4420）

```
0x054E4420  f30f590574b9af00   mulss  xmm0, dword ptr [rip + 0xafb974]   ; = 4.29497e+09 = 2^32 (float)
0x054E4428  f3480f2cc0         cvttss2si rax, xmm0                      ; 向零截断 → int64
0x054E442D  c3                 ret
```

即 `FP.FromFloat(f) = (long)(f * 4294967296.0f)`。

**三个必须复刻的细节**：
1. 乘法在 **float（单精度）** 下做，不是 double —— 大数值时 `f × 2³²` 本身就会丢精度。
2. `cvttss2si` 是**向零截断**，不是四舍五入。
3. 结果落进 int64。

> 推论：任何从配置文件读入的浮点数值（攻速、倍率、半径…）进入局内时都经过这条转换，**不是原样浮点参与运算**。

### 3.2 乘法实现（RVA 0x54E2200）

dump.cs 中 `op_Multiply` 与 `FastMul` 指向**同一 RVA**（0x54E2200），即 IL2CPP 合并了函数体；`OverflowMul` 是另一个（0x54E3030）。反汇编显示是 32×32 部分积展开：

```
sar rdx,0x20 / sar rcx,0x20 / shl rax,0x20 / imul rax,rcx / imul r8,r9 / imul rdx,r9
shr r8,0x20 / add rax,r8 ...
```

即把两个 64 位数拆成高 32 位（整数部）与低 32 位（小数部），做交叉乘后取高位——**低位部分积被丢弃，即截断而非舍入**。

> ⚠️ 待补（T1 未完成）：`FastMul` 的完整指令序列尚未逐条核对，尤其"被丢弃的低位是否参与舍入"这一点，需要读完整个函数体（约 20 条指令）才能定论。这是"模拟器与客户端逐位一致"的最后一个关卡。

### 3.3 常量真值（反汇编 `FP..cctor`，RVA 0x54E3980 起实测）

`static readonly FP` 的值不在 dump.cs，只在 `.cctor` 里：

| 常量 | 反汇编立即数 | 实际值 |
|---|---|---|
| `TEN` | `0xa00000000` | 10 × 2³² |
| `ONE` | `0x100000000` | 2³² |
| `HALF` | （`0x80000000` 段） | 2³¹ |
| `MAX_VALUE` | `0x7fffffffffffffff` | 2⁶³−1 |
| `MIN_VALUE` | `0x8000000000000000` | −2⁶³ |
| `PositiveInfinity` | `0x7ffffffffffffffe` | MAX−1 |
| `NegativeInfinity` | `0x8000000000000002` | MIN+2 |
| `EN1`…`EN8` | `0xa` / `0x64` / `0x3e8` / `0x2710` / `0x186a0` / `0xf4240` / `0x989680` / `0x5f5e100` | 10¹…10⁸ |
| `Pi` | `0x3243f6a88` | 13493037704 |
| `PiOver2` | `0x1921fb544` | 6746518852 |
| `PiTimes2` | `0x6487ed511` | 26986075409 |

`Sin`（RVA 0x54E3310）体内即出现 `movabs r8, 0x6487ed511`（= `PI_TIMES_2`），与 dump.cs 常量互相印证 —— **这是"dump.cs 正确 + 反汇编正确"的自检点**。

### 3.4 三角函数是查表

`LUT_SIZE = 205887` 与 `LutInterval` 同时存在，`AcosLut/SinLut/TanLut` 是 `long[]`。205887 ≈ (π/2) × 2¹⁷，即**查表格点间隔约 2⁻¹⁷**，配合插值。

> 影响：`FP.Sin/Cos/Tan/Asin/Acos/Atan2` 的结果与 `Math.Sin` 等 libm 实现**不相等**，误差量级在 2⁻¹⁷ 插值区间内。模拟器若用 libm，角度/朝向相关的位移会在长时间后漂移。

---

## 四、关键发现 B：逻辑步长 = 1/30 秒

### 4.1 推导链（三段证据）

1. `BattleController` 字段含 `static FP s_fixedPlayTime`、`s_deltaPlayTimeFP`、`s_fixedFrameCnt`（`uint`）、`isDeterministic`；`IBattleModule.OnFixedUpdate(FP fixedDeltaTime)` 是全模块的 tick 接口。
2. `GlobalConsts`（dump.cs 1230104）有 `static readonly FP FIXED_DELTA_TIME_FP`（0x38）与 `HALF_FIXED_DELTA_TIME_FP`（0x40），值只在 `.cctor` 里。
3. 反汇编 `GlobalConsts..cctor`（RVA 0x54E4D50）：

```
0x054E4E11  call 0x1859726c0                              ; Time.get_fixedDeltaTime()
0x054E4E20  mulss xmm0, [rip+0x881e38]  ; = 0.5f         ; HALF_FIXED_DELTA_TIME = dt * 0.5
0x054E4E37  movss [rcx+8], xmm0
```

`who 0x59726c0` → **`Time.public static float get_fixedDeltaTime()`**（Unity 引擎的固定时间步长）。于是 `FIXED_DELTA_TIME_FP = FP.FromFloat(Time.fixedDeltaTime)`。

### 4.2 步长真值（Unity TimeManager）

`read_gvm.py` 读 `globalgamemanagers` 的 TimeManager 对象：

```
Fixed_Timestep              = 0.03333330154418945
Maximum_Allowed_Timestep    = 0.3333333432674408
m_TimeScale                 = 1.0
Maximum_Particle_Timestep   = 0.03333330154418945
```

**`Fixed_Timestep = 0.03333330154418945` ≈ 1/30 秒 → 局内逻辑帧率 30 Hz。**

### 4.3 这一条改变了什么

- 社区说的"舟游 30 帧"**不只是渲染帧，就是逻辑帧**。
- 所有时间量（攻击间隔、技能持续、buff 周期、SP 回复、出怪时序、移动速度积分）都以 1/30 s 为**量化步长**。
- 注意 `0.03333330154418945` **不是**精确的 1/30：它先被 `FP.FromFloat` 单精度截断，之后每帧累加。要精确复刻 N 帧后的时刻，必须写成
  `t_N = N × FP.FromFloat(0.03333330154418945f)`（定点加法，不是浮点累加）。
- 已有观察（`23_B站专栏_解读比对与待核验清单.md` 的"仇恨精度 0.1 → 3 帧分组"）可由本条获得解释方向：0.1 s ≈ 3 帧。

---

## 五、关键发现 C：确定性战斗架构

`BattleController`（dump.cs 320906）字段直接暴露了架构：

| 字段 | 偏移 | 含义 |
|---|---|---|
| `static bool <isDeterministic>k__BackingField` | 0x10 | 确定性开关 |
| `static uint s_fixedFrameCnt` | 0x14 | **固定帧计数** |
| `static FP s_fixedPlayTime` / `s_fixedPlayTimeIgnored` / `s_fixedPlayTimeFloat` | 0x18/0x20/0x28 | 定点播放时间 |
| `static Random s_randomImp` / `s_randomTrivial` | 0x30/0x38 | 主随机流 / 杂项随机流 |
| `const RandomFactory.AlgorithmType RANDOM_ALGORITHM = 0` | — | 随机算法（DEFAULT=0） |
| `ObscuredInt m_randomSeed` | 0x198 | 随机种子（**混淆 int**，防内存改） |
| `HashCodeBuilder m_hashCodeBuilder` | 0x158 | 状态哈希 |
| `StringBuilder m_snapshotBuilder` | 0x160 | **快照** |
| `StringBuilder m_playerOperationBuilder` | 0x168 | **玩家操作记录** |
| `ReplayController m_replayController` | 0x108 | 回放控制器 |
| `PlayerOperationQueue m_playerOpQueue` | 0x130 | 操作队列 |
| `CoroutineSimulator m_coroutineSimulator` | 0x150 | 协程模拟器（把 Unity 协程搬进定点时间轴） |
| `FixedEventHandler<IPtrObject> m_fixedEventHandler` | 0x140 | 固定步长事件 |
| `PrecisePeriodicTimer`（`ListDict<PlayerSide, …> m_costTimerDict`） | 0xC8 | 精确周期计时器 |
| `ClientAntiCheatChecker m_antiCheatChecker` | 0x1B0 | 客户端反作弊校验 |
| `SpeedLevel m_speedLevel` / `float m_originTimeScale` | 0x234/0x290 | 倍速（2 倍速不应改变逻辑结果） |

配套：`LevelData.randomSeed`（每关自带种子）、`LevelTempData.AssignData`（关卡数据的一次性注入）。

**结论**：这套设计的目的就是"同一初始状态 + 同一操作序列 ⇒ 逐位相同的结果"，因此：
1. 客户端可以只上传**操作序列**，服务器/回放端能重算（对应 `battleReplay` 是一段可回放的输入记录）。
2. 模拟器只要复刻 (a) Q32.32 运算、(b) 1/30 步长、(c) 同一随机算法与种子、(d) 同一 tick 顺序，就能得到与游戏一致的局内过程。
3. `HashCodeBuilder` + `ClientAntiCheatChecker` 说明存在**逐步哈希**，任何一点不一致都会被发现——反过来说，**哈希一致可作为我们模拟正确性的判据**。

> 待办：`RandomFactory.Create` 的 `DEFAULT(=0)` 究竟实例化哪个算法（LCG/Mersenne/MOTHER_OF_ALL/RANROT_B/SFMT/WELL/XORSHIFT）需反汇编 0x5526C40 确认；`m_randomSeed` 如何由 `LevelData.randomSeed` 派生亦待查。

---

## 六、关键发现 D：关卡数据的权威 schema

`LevelData`（dump.cs 158830）就是关卡配置（level 表 / level_*.json）反序列化的目标类型：

```
levelId, mapId, bgmEvent, environmentSe,
mapData : MapData,
tilesDisallowToLocate : List<GridPosition>,
runes / optionalRunes, globalBuffs,
routes : RouteData[], extraRoutes : RouteData[],
enemies : LevelData.EnemyData[], enemyDbRefs, waves : LevelData.WaveData[],
branches : ListDict<string, LevelData.BranchData>,
predefines / hardPredefines : LevelData.PredefinedData,
excludeCharIdList, randomSeed : int, operaConfig, cameraPlugin,
runtimeData : LevelData.RuntimeData, options : LevelData.Options
```

`MapData`（159060）：

```
short[,] map;            // 二维格点矩阵，short 编码
TileData[] tiles;
MapData.Edge[] blockEdges;   // 地块间"阻挡边"
string[] tags; MapEffectData[] effects; string[] layerRects;
width / height / get_Item(r,c) / get_Item(GridPosition)
```

`RouteData.CheckpointData` / `RouteData`（158330/158351）是**出怪路径**；`CheckpointType` 枚举给出节点的全部行为：

```
MOVE, WAIT_FOR_SECONDS, WAIT_FOR_PLAY_TIME, WAIT_CURRENT_FRAGMENT_TIME,
WAIT_CURRENT_WAVE_TIME, DISAPPEAR, APPEAR_AT_POS, ALERT, PATROL_MOVE,
WAIT_BOSSRUSH_WAVE, MAP_OFFSET_MOVE, INVALID
```

这正是"出怪时序"（见 `27_露托数据源与出怪时序本地化.md`）的原始依据，也是把"波次表"翻译成"第 N 帧第 M 个敌人出现在格点 X"所需的全部算子。

### 6.1 类的分布规模（`// Namespace:` 统计，共 45192 条）

| 命名空间 | 类数 | 说明 |
|---|---|---|
| `Torappu` | 2736 | 主命名空间（含 LevelData/MapData/FP 等数据类） |
| `Torappu.UI` | 1042 | 关卡外 UI |
| **`Torappu.Battle`** | **755** | **局内战斗逻辑主战场** |
| `Torappu.UI.SandboxPerm.SandboxV2` | 726 | 生息演算 |
| `Torappu.UI.Roguelike` | 561 | 肉鸽 UI |
| `XLua` / `XLua.CSObjectWrap` | 387 / 290 | **Lua 绑定层与导出包装** |
| `Torappu.Battle.Abilities` | 265 | 技能/能力实现 |

> `XLua.CSObjectWrap` 的 290 个类 = Lua 能调到的 C# 接口清单，是"伪代码层 ↔ cpp 层"的**桥**。要回答"某条 Lua 逻辑最终落到哪个 C# 实现"，从这张表入手最省力。

---

## 七、实战案例（照着做一遍即可复现全部结论）

### 案例 1：一个 `static readonly` 常量的真值

```
① & $py $t find "FIXED_DELTA_TIME"
   → 命中 GlobalConsts 的字段声明，得到偏移 0x38
② 读该类的方法区 → 找到 .cctor 的 RVA 0x54E4D50
③ & $py $t m GlobalConsts..cctor 75
   → 看到 call 0x1859726c0 + mulss ...0.5 + 写回
④ & $py $t who 0x59726c0
   → Time.get_fixedDeltaTime
⑤ read_gvm.py 读 globalgamemanagers 的 TimeManager.Fixed_Timestep
   → 0.03333330154418945
```

要点：**dump.cs 只给"在哪"，反汇编给"是什么"，Unity 序列化文件给"配置真值"**，三步缺一不可。

### 案例 2：反查一个神秘调用目标

反汇编里出现 `call 0x1803f8a50` 这类**绝对地址**时，`RVA = 地址 − 0x180000000`（**ImageBase = 0x180000000**，可由 dump.cs 自证：`VA 0x1854E32F0 − RVA 0x54E32F0 = 0x180000000`）。然后 `who <RVA>`。`read_cpp.py` 会先在 dump.cs 的 RVA 索引里查，并给出"最近前驱 + 偏移"（用于命中函数内部的情况）。

### 案例 3：确认 dump 与反汇编彼此自洽

`FP.Sin` 体内出现 `movabs r8, 0x6487ed511`，而 dump.cs 声明 `PI_TIMES_2 = 26986075409 = 0x6487ED511`。**两者对上 = 工具链可信**。换客户端版本后应先跑这个自检再开始挖。

---

## 八、局限与后续路线

### 8.1 当前局限

1. **没有交叉引用(xref)工具**。dump.cs 只有"定义"，没有"谁调用了它"。追调用链目前靠 `call` 命令人工跟，效率有限。
   → 解决路线：把 `script.json` 导入 IDA/Ghidra（仓库里已有 `ida_with_struct_py3.py`、`ghidra_with_struct.py`），或本地建一个 x64 全量扫描索引。
2. **Cpp2IL 未使用**。它能产出 `diffable-cs`（近似 C# 源码）与伪代码，比反汇编可读得多。仓库 `code\unpack\revenant\research\cpp2il-macho-verdict.md` 记录了它的内存代价：isil pass 峰值 15.7 GB（本机 31.7 GB 物理内存，可用 16 GB，**偏紧**）。若要用，先只跑 `--output-as isil`，并避免 `nativemethoddetector` processing layer。
3. **`FastMul` 完整语义未核对**（见 §3.2 待补）。
4. **随机算法未确认**（见 §5 待办）。
5. 样本是**日服**客户端；国服资源版本不同（国服 2.7.71 / resVersion 见 OpenBachelorS `conf/version.json`）。中日服共用同一 Unity 工程，机制层预期一致，但**新增机制/改动的时序差异需要在比对时留意**。

### 8.2 优先级建议（按"对局内模拟的价值"排序）

| 优先 | 目标 | 手段 |
|---|---|---|
| 高 | 随机算法与种子派生 | 反汇编 `RandomFactory.Create`(0x5526C40)、`BattleController` 初始化流程 |
| 高 | 定长 tick 内各模块的**执行顺序** | `BattleController` 的 tick/Update 方法与 `m_modules` 遍历顺序 |
| 高 | 攻击间隔 / 攻速 / 伤害公式的定点实现 | 由 `23` 号文档的公式反查对应方法（如 `_UpdateMoveSpeed`、`Attack`） |
| 中 | 阻挡与 body radius（K 清单 🔴 项） | `Tile`/`Unit` 的 block 相关方法 + `blockEdges` |
| 中 | 出怪调度（波次 → 具体帧） | `LevelData.WaveData`/`RouteData.CheckpointData` 字段 + `Scheduler` |
| 低 | Cpp2IL 交叉验证 | 见 8.1 第 2 条 |

---

## 附：本次新增的文件

| 路径 | 说明 |
|---|---|
| `E:\__file\ak_kb\client_res\il2cpp\GameAssembly.dll` | IL2CPP 二进制只读备份（127.9 MB） |
| `E:\__file\ak_kb\client_res\il2cpp\global-metadata.dat` | 元数据只读备份（39.3 MB） |
| `E:\__file\ak_kb\client_res\il2cpp\dump\` | Il2CppDumper 全部产物 |
| `E:\__file\ak_kb\client_res\unity_player\` | Unity 播放器序列化文件（含 TimeManager 步长真值） |
| `E:\__file\ak_kb\tools\il2cpp\Il2CppDumper.exe` | 工具 |
| `ak\code\tools\read_cpp.py` | dump.cs 检索 + x64 反汇编 |
| `ak\code\tools\read_gvm.py` | 读 Unity 全局管理器设置 |

## 相关文件

- `knowledge\04_数据对应与核验\23_B站专栏_解读比对与待核验清单.md`（K-001~024 待核验项，本层可批量解决）
- `knowledge\04_数据对应与核验\26_地图干员敌人数据解包标准流程与数据源边界.md`
- `knowledge\04_数据对应与核验\27_露托数据源与出怪时序本地化.md`
- `code\unpack\revenant\research\cpp2il-macho-verdict.md`、`il2cpp-metadata-decryption.md`
- `meta\解包经验.md`（工具获取与网络环境）
