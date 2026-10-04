# 66a 对照：调零修罗 PRTS 页面 ↔ 本地代码层
> 主题：**04B 读代码 / 反汇编**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）
> 层级：**T1（含代码/RVA 证据（RVA 5，代码词 9））**　建立日期：2026-09-28（文中标注（建立日期））　任务：T-075　｜　**头部为 2026-09-30 自动回填**，推断项已标注

> 子文件（**母文件：`66_伪代码读取与理解流程.md`**）　建立日期：2026-09-28　任务：T-075
> **口径**：PRTS 侧一律 **T2（玩家统一口径，可能出错）**；代码侧为 **T1**（日服 PC 客户端 IL2CPP，resVersion `26-08-16`，`dump.cs` 77,134,005 B / 09-13）。
> **规则**：冲突项**两侧说法与来源均保留**，标「待代码核验」，**不得删改任一方**（用户 2026-09-23 裁决）。

---

## 〇、方法与样本

- **PRTS 侧**：`ak\_raw\prts\调零修罗\` 21 页 / 143,373 B（清单见 `_抓取说明.md`）。
- **代码侧**：`E:\__file\ak_kb\client_res\il2cpp\dump\dump.cs`，用 `Select-String` 定位（**嵌套枚举须写全路径**，否则 0 命中）。
- **判据**：本次只用**低成本强判据**——枚举全量对拍（V1）与类存在性+基类对拍（V2）。**未做**反汇编级核验（除既有文档已记录者）。

---

## 一、新信息（我们没写的）

### 1.1 枚举补全（**T1，本次新取得**）

| 对象 | PRTS | 代码真值 | 差异 |
|---|---|---|---|
| `Torappu.CheckpointType` | 0–8 + `9=INVALID` | `MOVE=0, WAIT_FOR_SECONDS=1, WAIT_FOR_PLAY_TIME=2, WAIT_CURRENT_FRAGMENT_TIME=3, WAIT_CURRENT_WAVE_TIME=4, DISAPPEAR=5, APPEAR_AT_POS=6, ALERT=7, PATROL_MOVE=8, **WAIT_BOSSRUSH_WAVE=9, MAP_OFFSET_MOVE=10, INVALID=11**`（L158941 / 4318） | PRTS **缺 9/10**，并把 INVALID 误标为 9 → **冲突**，见 §三.1 |
| `Entity.MountPointType` | 0=FOOT,1=HIT,2=MUZZLE,3=HEAD,4=UI,7=GROUND（5/6/8+ 留空） | 同上 **0–4、7 全中**；另有 **`SPECIAL_0`~`SPECIAL_15` = 5,6,8,9,…,21**（L330648 / 8710） | 5/6/8–21 是我们原先**完全没有**的 |
| `Character.States.State` | 0=DEFAULT…9=FROZEN, −1=TERMINAL | 同上全中；**另有 `REBORN=10`、`DYING=11`、`DIALOG=12`、`DOZE=13`**（L376833 / 9636） | **+4 个状态**（`REBORN`/`DYING` 对死亡流程模拟有直接影响） |
| `Enemy.States.State` | 0=DEFAULT…14=LEVITATE, −1=TERMINAL | 同上全中；**另有 `DIALOG=15`、`PALSY=16`**（L379103 / 9665） | **+2 个状态**（`PALSY` 疑与「麻痹」相关） |
| `LifeType` | 3 型：IMMEDIATELY / LIMITED / INFINITY | 同上 + **`CUSTOM=3`**（L1230712 / 32103） | **+1** |
| `BuffData.OnEventPriority` | （未给值） | `HIGHER_PRIORITY=2000, HIGH_PRIORITY=1000, DEFAULT=0, LOW_PRIORITY=−1000, LOWER_PRIORITY=−2000, LOWEST_PRIORITY=−3000, **TITI_DOZE_PRIORITY=−4000**`（L149340 段 / 3801） | `04/39` 只记了"字段"，**值域是新增** |

> ★ `TITI_DOZE_PRIORITY` 是**具名彩蛋式常量**（"TITI"= 干员「提提」相关），说明 `OnEventPriority` 在代码里**确实被逐个具名使用**，不是抽象枚举。

### 1.2 `BuffData`（buff_template 模板）完整 schema——**`33` 缺这一类**

`33` §3.2 记的是 **`Buff` 运行时类**（`m_lifeTime`/`m_stackCnt`…）；**模板类 `Torappu.BuffData` 的 43 个字段此前没有系统记录**（`63b` 只摘了 3 个）。本次取全（L149358 / 3802）：

`attributes`0x10 · `buffKey`0x18 · **`loadFromDB`0x20** · `isDurableBuff`0x21 · `isDamageMissable`0x22 · **`isSilenceable`0x23** · **`isStunnable`0x24** · `isFreezable`0x25 · `isLevitatable`0x26 · **`statusResistable`0x27** · **`templateKey`0x28** · **`disableOverride`0x30** · **`overrideKey`0x38** · **`overrideType`0x40** · **`maxStackCnt`0x44** · `refreshRemainingTimeWhenStackMax`0x48 · `clearAllStackCntWhenTimeUp`0x49 · `maxValidStackCnt`0x4C · `independentCharacterSource`0x50 · `overrideEffectKey`0x58 · `overrideOnEventPriority`0x60 · **`onEventPriority`0x64** · `audioSignal`0x68 · **`lifeTimeType`0x70** · `takeSnapshotWhenExtend`0x71 · **`durationKey`0x78** · **`lifeTime`0x80** · **`triggerLifeType`0x84** · **`triggerCnt`0x88** · **`triggerInterval`0x8C** · `waitFirstTriggerInterval`0x90 · `firstTriggerInterval`0x94 · **`priority`0x98** · **`priorityBBKeys`0xA0** · `stripBlackboardParamsWithBuffKey`0xA8 · **`blackboard`0xB0** · `enableInitDirectionFromSource`0xB8；属性 `isAutoPriority`

方法：`get_isAutoPriority`(0x201B880) · `GetOverrideKey`(0x201B450) · `ToString`(0x201B4F0) · `EnsureBuffData`(0x201B3C0) · `DeepClone`

### 1.3 只从 PRTS 得到、代码侧尚未核（**T2，纯新增**）

| # | 内容 | 出处 |
|---|---|---|
| N1 | **`priority` 自动计算公式**：`priority`<0 时，若未设 `priorityBBKeys` → **= 修饰器中 ADDITION+MULTIPLIER+FINAL_ADDITION 之和 × 1000**；否则 → **= `blackboard` 中各 `priorityBBKeys` 取值绝对值之和 × 1000**。`priority`≥0 时即其本身 | `机制页_BUFF` |
| N2 | **抵抗影响计时**：Buff 受抵抗影响时，其**持续计时与触发计时**速度均变为 `1 / ONE_MINUS_STATUS_RESISTANCE` 倍 | `机制页_BUFF` |
| N3 | **`trig_cnt` 特例**：`triggerLifeType=INFINITY` 时，若 `blackboard` 中读到名为 **`trig_cnt`** 的值，**自动转为 LIMITED** | `机制页_BUFF` |
| N4 | **`ON_BUFF_*` 事件作用域**：以 `ON_BUFF_` 开头的事件**仅适用于单个 Buff**；除 `ON_BUFF_TRIGGER` 外**不受 Buff 失效影响** | `机制页_BUFF`（**已被代码特性证实**，见 §二.5） |
| N5 | **吸附点偏移量**：`HIT` = `[0, 0.23382]`；`FOOT` = `[0,0]`；`MUZZLE` 随 Spine；**敌人因 Spine 跟随足坐标，所有吸附点整体 `+[0,−0.2]`**；Spine 点位 → 地块相对坐标 = `[x,y] × [0.27, 0.23382]` | `Sandbox_吸附点` |
| N6 | **弹射两类算法**：①**瞬间弹射**（链术师/惊蛰）= 弹射**开始时**一次性定好全部目标（逐次最近，同权重取更早存在者*存疑*，不可重复目标）；倍率**累乘衰减**（X 模组"不再衰减"= 衰减乘数改 100%）；②**弹道弹射**（空弦2）= **击中/落地时**才定下一个目标，每次新弹道"攻击次数"−1（最低 1） | `Sandbox_弹射` |
| N7 | **特殊 Buff 实现范式 8 类**：数据库 / 附属 / 即效 / 模式切换 / 标记性 / 伪免疫 / 承载器 / 存在时间 / 伪登场触发 / 伪离场触发 | `Sandbox_特殊的Buff实现方式` |
| N8 | **中文描述词 ↔ 数值映射表**（14 档"间隔增大/缩短"，80+ 干员），且明示"**描述间无明确大小顺序**" | `攻击间隔数据统计`（自述基于**客户端 2.4.01**） |
| N9 | **特性解释**：要塞"不阻挡时优先远程群体物理攻击、溅射半径 1.0、无法对空"；普攻优先序 = 阻挡近战 > 范围内远程 > **自身地块内**近战。扩散术师溅射半径 1.1 | `特性解释` |
| N10 | **已知问题**：**法术伤害精度问题**——"法术伤害计算时的数值精度出现问题，导致**伤害永远会略低于理论数值**"，0 法抗 1000 攻打 1000 血会留 0 血不死；影响**所有法术伤害** | `Sandbox_已知问题汇总` |

> **N10 是本次最有价值的一条外部旁证**：它从**观测层**独立指出了"伤害系统性略低于理论值"，与 `29` §三 的 **Q32.32 定点截断**（乘法丢弃低位部分积、`FP.FromFloat` 向零截断）**方向完全一致**。
> 两者机制不同（一个是定点截断，一个是策划表/公式），但**现象吻合**，可作为"定点精度问题真实存在且玩家可观测"的互证。**待代码核验**：具体是 `FP.FastMul` 截断还是伤害链某一环的另一处截断。

---

## 二、互证清单（PRTS T2 ↔ 代码 T1，可升为"互证")

| # | 对象 | PRTS 说法 | 代码侧 | 强度 |
|---|---|---|---|---|
| 1 | `CheckpointType` | TypeID 0–8 全表 | 0–8 **逐值逐名全中** | ★★★ |
| 2 | `Entity.MountPointType` | 0–4、7 | 0–4、7 **逐值逐名全中** | ★★★ |
| 3 | `Character.States` | 0–9 + `TERMINAL=−1` | 全中 | ★★★ |
| 4 | `Enemy.States` | 0–14 + `TERMINAL=−1` | 全中 | ★★★ |
| 5 | `Sandbox/实体类型` 类层次 | 30 个类名 + 其归类 | **30/30 类存在，且基类与 PRTS 归类一致**（`PropLikeStaticBlockToken:Token`、`RallyPoint:Trap`、4 个 Trap 子类、3 个 `:LinkProjectile`、`Thorn2PolygonProjectile:SimpleProjectile`、`BounceProjectile:Projectile`、5 个 `:Tile`、12 个 `:Enemy`） | ★★★ |
| 6 | `loadFromDB` | "使用数据库"参数名 | `BuffData.loadFromDB`(0x20) **字段名逐字相同** | ★★★ |
| 7 | `overrideType` 5 策略 | DEFAULT/STACK/UNIQUE/EXTEND/EXTEND_TIME | `BuffData.OverrideType` 同名同序 `0..4` | ★★★（**顺序亦同**） |
| 8 | `statusResistable` | NO/YES/AUTOMATIC | `NO=0,YES=1,AUTOMATIC=2` | ★★★ |
| 9 | `Buff.Event` 30 事件 | 30 行 ID+内部ID+target 表 | 30 值逐一对应 | ★★★ |
| 10 | "除 `ON_BUFF_TRIGGER` 外不受失效影响" | 一句散文注释 | 每事件带 `[RunActionsWhenDisabled(bool)]`，**仅 `ON_BUFF_TRIGGER=2` 为 `False`** | ★★★（**散文↔特性命中**） |
| 11 | 伪免疫 Buff = "高叠加优先级的无效果同名 Buff" | 机制解释 | `OnEventPriority.HIGHER_PRIORITY=2000` + `04/39 §3.2`（容器按该值降序） | ★★（机制解释与已核验排序规则相符） |
| 12 | 沉默/晕眩响应 | `isSilenceable`/`isStunnable` 为 true 则该 Buff 在沉默/晕眩期间失效 | `BuffData.isSilenceable`(0x23) / `isStunnable`(0x24) **字段名逐字相同** | ★★★ |
| 13 | 承载器 Buff "重要的只有黑板" | 黑板=变量库 | `BuffData.blackboard`(0xB0) : `List<Blackboard.DataPair>` | ★★ |
| 14 | 红字阈值 1.5×期望伤害 | `新新红字概论` 全套（含"无敌×0"） | `Consts.MODIFIER_CRIT_THRESHOLD = 1.5` + `01a §3.1`/`02 §2.7` 逐条同 | ★★（PRTS 与**本地文档**互证；常量值 T1） |
| 15 | 攻击距离属性名 | `ABILITY_RANGE_FORWARD_EXTEND` | `AttributeType.ABILITY_RANGE_FORWARD_EXTEND = 15`，与 `01c` #15 一致 | ★★★（**枚举值对上**） |
| 16 | 附属 Buff `DerivedBuff` | 绑定主 Buff，主结束则子结束 | `_isDerivedBuff` 字段存在于多个 Buff/Node 类；`机制页_BUFF` §其它Buff工具 列出 `DerivedBuff` | ★★ |
| 17 | Buff 容器名 | `BuffContainer` | `Entity.buffContainer`(0x150)、`Buff.BuffContainer`（`33` §3） | ★★★ |

---

## 三、冲突清单（**两侧均保留**，标待代码核验）

### 3.1 🔴 `CheckpointType` 的 TypeID 9 —— PRTS 页面已过期

| | 说法 | 出处 |
|---|---|---|
| **PRTS** | `9 = INVALID`（表到 9 结束，只剩 10 行） | `Sandbox_路径点解析`（T2） |
| **代码** | `9 = WAIT_BOSSRUSH_WAVE`、`10 = MAP_OFFSET_MOVE`、**`11 = INVALID`** | `dump.cs` L158941 / TypeDefIndex 4318（T1） |

**保留双方**。**判定倾向**：PRTS 该页是**旧版本快照**——`WAIT_BOSSRUSH_WAVE`（"等待 BossRush 波次"）与 `MAP_OFFSET_MOVE` 显然是后加的新指令，它们插入后 `INVALID` 被挤到 11。
**为什么必须记下来**：`02_作战机制.md` §3.2 的路径点表也只到 8，`24`/`27` 的时间轴算法按 0–8 实现 —— **若某关用到 9/10 类检查点，现有实现会误判为 INVALID 而跳过该动作**。
**下一步核验**：查本地 `gamedata\levels\**\*.json` 的 `routes[].checkpoints[].type` 实际取值分布，看是否出现过 9/10（本关/活动关）。

### 3.2 🔴 「攻击距离」能否为负 + 延伸形状 —— 三份说法互不相同

| 来源 | 说法 |
|---|---|
| **PRTS** `攻击范围`（T2） | 攻击距离**可正可负**：为正时"**每一行**含单元格的攻击范围**向右**延伸 1 格"；为负时"从最右侧开始减去一格" |
| **本地** `01/01c` #15（T1，来自 gamedata/AB） | `ABILITY_RANGE_FORWARD_EXTEND` —— "对 ID 范围生效时令每个格子**往外延伸**若干格（**无法减少**）" |
| **本地** `02_作战机制/02a` §（T2/T1 混） | "多边形：每 1 点攻击距离令方块向**正前方**拉伸 1 格；**重叠部分无效** → 相当于向部署方向**前方多一列**。圆形：半径增加等同量" |

**保留三方**。三者**两两不同**：①"可负" vs "无法减少"；②"每行向右延一格" vs "向正前方拉伸一列"。
**判定倾向**：`01c` 的来源是**属性枚举表描述**，可信度最高但可能是**策划注释**而非实现；`02a` 描述的是**梭形/多边形**范围的表现；PRTS 描述的是**矩形/ID 范围**。**三者可能各自描述不同范围类型**，尚未排除。
**下一步核验**：反汇编 `Attributes`/范围扩展的实现方法（`AttributeType=15` 的消费者），确认 (a) 负值是否被 clamp；(b) 延伸是按行还是按列。
**影响**：直接影响模拟器"攻击距离 +1"干员的命中判定 → **在定谳前不得按任一方实现**（`04/60` 应登记）。

### 3.3 🔴 敌人「向下偏移」的量：`0.2` vs `0.1`

| | 说法 | 出处 |
|---|---|---|
| **PRTS** | 敌人因 Spine 跟随足坐标，"**所有吸附点**都跟随 Spine 一起偏移（即最终坐标 **`+[0,−0.2]`**）" | `Sandbox_吸附点`（T2） |
| **本地** | 敌人**物理碰撞箱**：「宽 0.2、高 0.4、**向下偏移 0.1** 的胶囊」，常量 `TILE_COLLIDE_DISTANCE=0.005`/`_WIDE=0.01` | `04/37`（T1，RVA 0x7527C0） |

**保留双方**。**判定倾向**：这**很可能是两个不同的量**（①吸附点/绘制坐标偏移 ②物理碰撞箱偏移），**并非真冲突**；但因数值接近（0.2 vs 0.1）极易混淆，且两者都会影响"敌人实际在哪"。
**下一步核验**：确认 `Enemy` 的 Spine 宿主偏移是否另有 `−0.2` 常量；若存在，则两者并存，本文按"同名不同量"处理（`66` §五.2）。
**本项列入冲突而非"新信息"，是因为**：在我们明确区分之前，**引用任一方描述"敌人坐标"都可能出错**。

---

## 四、⚠️ 口径风险（未构成冲突，但会直接影响模拟器）

| # | 风险 | 证据 | 后果 |
|---|---|---|---|
| R1 | **中文描述词 → 数值不可全局映射** | `攻击间隔数据统计`：**深靛**「小幅度缩短 = ×0.8」「略微缩短 = ×0.7」（**略微更短**）；**异客**「略微缩短 = −20%」「小幅度缩短 = −30%」（**小幅度更短**）——**同一对描述词在两干员上顺序相反**。PRTS 该页自述"部分间隔描述之间**没有明确的大小顺序关系**"；`已知问题汇总` 亦把"技能升级时间隔缩短描述文本递增"列为**描述问题** | 若模拟器按"描述词→单一数值"建全局表，**这两类干员必错**。必须**逐技能读表**（`skill_table` 的 `blackboard`），描述词只用于显示 |
| R2 | **`攻击间隔数据统计` 页面版本落后** | 页首自述基于**客户端 2.4.01**、截止六星 `荒芜拉普兰德` | 该页只可作**语义量级参考**；数值一律回本地 `character_table`/`skill_table`（现已 1373+ 干员） |
| R3 | **PRTS 页面版本 ≠ 本地客户端版本**（通用） | 本批 21 页中，`Sandbox/路径点解析`（§3.1）与 `攻击间隔数据统计`（R2）**两页已确认过期** | 引用任何 PRTS 页前先看其**自述基准版本**；无版本标注的按"可能过期"处理 |
| R4 | **`Sandbox/状态机` 页不存在** | 404（`_抓取说明.md` §1.1） | 状态机内容在 `用户:调零修罗/状态机`（子页面，无 Sandbox 前缀）与主命名空间 `状态机` 两处，**不可按 Sandbox 路径猜** |

---

## 五、本批未处理 / 待做

1. **`机制页_术语释义.txt`（38,665 B，本批最大）未展开** —— 它是 PRTS 术语总表，可用作 `07_名词对照` 的**外部校验源**（逐词比对官方术语 vs 我们收录的玩家俗称）。**建议单起一轮**。
2. **`机制页_地块筛选`(10,280) / `机制页_选择器`(12,254) / `机制页_元素`(6,921) / `机制页_可抵抗状态`(3,542) / `机制页_诱发移动`(5,548) 已存档未比对** —— 这 5 页分别对应
   `04/56`（范围/体积）、`04/38`（索敌过滤器）、`04/63`（元素 `EPController`）、`异常效果`、`04/37`+`57`（推拉/惯性）。**是高优先级下一批**。
3. **`CheckpointType` 9/10 的实际使用普查**（§3.1 下一步核验）未做。
4. **`AttributeType` 全表**（本次只看到 0–23）未取全 —— 它是"属性名 ↔ 中文"的权威表，对 `07_名词对照/02_代码层命名对照` 直接有用。
5. **反汇编级核验 0 项**：本批全部结论止于"枚举/类/字段/特性"层，**未验证任何算法实现**。

---

## 六、本批落盘动作（回填三件套）

| 动作 | 文件 |
|---|---|
| 新建流程主文 | `04_数据对应与核验/66_伪代码读取与理解流程.md` |
| 新建对照子文（本文） | `04_数据对应与核验/66a_对照_调零修罗PRTS页面与代码层.md` |
| 原始资料存档 | `ak\_raw\prts\调零修罗\`（21 页 + `_抓取说明.md` + `_抓取清单.csv`） |
| 母文件留指向 | `01_基础数据/10_调零指导_解包学习路径.md` §五 加指向 `66` 的一行 |
| 索引登记 | `00_Agent入口.md` §一 + §二（04 域） |
| 领域目录登记 | `04_数据对应与核验/00_目录.md` |
| 任务台账 | `management\tasks_registry.md`（**T-075**，派发号 T-068 已被占用） |
