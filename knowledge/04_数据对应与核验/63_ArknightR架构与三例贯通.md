# 63 ArknightR 架构与三例贯通（含官方客户端对应定位）
> 主题：**04B 读代码 / 反汇编**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）

> 层级：**T1/T2**（T1 = 本地程序集 IL 反汇编实测；T2 = 与官方 dump 的对应判定）
> 日期：2026-09-23　目标：`D:\__soft\ak\ArknightR`（v0.1032，**完整副本**；E: 副本被裁剪，勿用）
> 方式：**读 `Assembly-CSharp.dll` 的 ECMA-335 元数据 + 自研 IL 解码器**（`ak\code\tools\mono_il.py`），全程**未用反编译器**（本机无 .NET SDK / ILSpy / dnSpy，也不需要）
> 官方侧：`E:\__file\ak_kb\client_res\il2cpp\dump\dump.cs` + `ak\code\tools\read_cpp.py`
> 配套：`63a_ArknightR调用链IL证据细目.md`（逐条 IL 证据 + 复现命令）、`63b_官方对应检索报告.md`（官方侧完整检索）
> 前序：`40_外部工具解析_ArknightR与AFA.md`（本文件**修正**其一处类名错误，见 §5）

---

## 〇、结论速览

1. **一句话**：ArknightR 是「**表驱动 + 反射分发 + 双段主循环 + 拉取式表现**」的自研 Unity 战斗模拟器；其**帧率是官方客户端的 2 倍**（60 Hz vs 官方 30 Hz，见 `04/29`），**类结构、tick 顺序、伤害入口、机制分发全部自行设计**，**不是官方代码的还原**。
2. **表里 `Type` 列 = C# 类名 → `Assembly.CreateInstance("Buffs." + Type)`** 这条范式，本次**在 IL 指令级拿到实证**（§1.6，`ldstr` + `CreateInstance` 原文，56 个反射点）。**⚠️ 但官方客户端没有这一套**（`Activator.CreateInstance` 战斗层 0 处；官方是 1310 个 `Nodes.* : ActionNode` + `Blackboard` + 枚举）⇒ 它是**ArknightR 的工程范式**，**不能**用来反推官方 gamedata 的字段语义。详见 §3.3。
3. 主循环是**两段式**：`BattleManager.Update`（真实时间累加 + `FloorToInt` 追赶）→ 每 tick `Battle::e3o()`；每帧另调 `Battle::e3w()`。官方对应 `BattleController` 的 `Update`（**不做 tick**）/ `FixedUpdate`（模块驱动）/ `OnTick`（定点推进）/ `ManualFrameTick`（注入输入＋一次 OnTick）。✅
4. 单 tick 分组顺序实测为 **Tile → Bullet → Unit**，单位内 **`st2`(推力) → `a3s`(buff tick + 属性重算) → `a3h`(回血/死亡) → `str`(格位)**。✅
5. **属性是每 tick 全量重算**（`Unit::a3a` 先把所有 `*Rate/*Add/*Fin/*Ex` 归零再算终值）——**无脏标记**；公式与舟游公开公式同构。✅
6. 伤害链：`Skill::aiw`（造 `DamageInfo`）→ `Unit::se2`（受击主流程，内含 `Unit::se3` 公式）→ `IShield::rht` → `Hp -= FinalDamage` → `UnitModeI::sww`（飘字）。✅
7. **表现层是"拉"不是"推"**：`NormalModel::LateUpdate` 每帧读 `Unit.Position/Direction/AnimationName` 写 transform；逻辑 `Unit` 全程不碰 transform。✅
8. **数据加载"散文件优先、Addressables 兜底"已实测**（`SaveHelper.hhe("/Data/X.txt")` 失败才 `Addressables.LoadAssetAsync<TextAsset>`），且**逐行 JSONL 解析 + 单行 try/catch**。✅
9. 官方对应：**强判据 5 处**（`DamageInfo`↔`Modifier` 7+ 字段、`AttackInfo` 4 字段、`CalculateDamage` 签名+分支、`MountPoint` 绑定点、`Attributes` 修饰器体系）；**中判据（职责/结构级）12 处**；**明确不对应 4 处**（**帧率 60 vs 30**、阻挡半径与搜索节拍、5% 保底项、伤害类型枚举值）；**官方 0 命中（需用替代物）5 处**。完整对照表见 §3，官方侧检索记录见 `63b`。
10. **四条对复刻最关键的"不能照抄 ArknightR"**：①**帧率**——ArknightR 60 Hz、官方 30 Hz（`04/29`），一切时间量（攻击间隔/技能持续/buff 周期/SP 回复/出怪时序/移动积分）都会被放大 2 倍；②`Unit::se3` **缺官方 `MIN_ATK_FACTOR = 0.05` 伤害保底**；③`DamageTypeEnum` 与官方 `DamageType` **数值整体错位**；④`Block` 官方拆成 `Enemy._blockVolume` + `Character._blockMode` 两层，ArknightR 只有单字段。
10. **数据→逻辑→表现**三例完整链路见 §2；每例都给了"哪一步在官方哪个类"。

---

## 一、架构

### 1.1 模块划分（判据：命名空间 + 类数与字段实测）

| 层 | 命名空间 / 类 | 规模 | 职责 | 关键类型 |
|---|---|---|---|---|
| **入口/驱动** | `BattleManager`、`MapManager`、`UIManager`、`AudioManager`、`EffectManager`、`TipManager`、`TrailManager` | 全局 | MonoBehaviour 单例 + 各 Update | `BattleManager`(6 方法/6 字段)、`MapManager`(11/11) |
| **战斗状态** | `Battle` | 全局 | 一局的全部状态 + tick 编排 | 36 方法 / **51 字段**：`Tick`、`Finish`、`Waves`、`CheckPoints`、`Map`、`Units`、`Bullets`、`MapData`、`OriginPathInfo`、`Random`、`TriggerDatas`、`Hp`、`CostCountSpeed` |
| **逻辑实体** | `Unit`（→ `Units.干员` / `Units.敌人` / `Units.普通单位` / `Units.中立单位` / `Units.战术点` / `Units.箱子类敌人` / `Units.沙漠晶块` …） | 全局 + `Units`(14) | 属性、状态机、buff 容器 | `Unit`: 68 方法 / **273 字段** |
| **机制处理器** | `Buffs`(614) / `Skills`(267) / `Modifys`(76) / `Bullets`(38) | 4 个命名空间 | 一个机制一个类，靠表 `Type` 列反射选中 | 基类 `Buff`/`Skill`/`Modify`/`Bullet` |
| **表现层** | `UnitModeI`(接口) + `NormalModel`/`PlayerUnitModel`/`SpineModel`/`BulletModel`/`MapTile`/`PitModel`/`PoolModel`/`PreDisplayModel`/`PullLineModel`/`SpecialPitModel`/`Effect`/`BattleCamera` | 全局 | MonoBehaviour 视图，**每帧拉取逻辑真值** | `UnitModeI`(19 方法) |
| **UI** | `BattleUI`(25) / `MainUI`(30) / `DungeonUI`(18) / `MapBuilderUI`(15) | 4 个命名空间 | FairyGUI（`ui://...`） | `UI_Battle`(35 方法/88 字段) |
| **数据** | `Database`、`GameData`、`*Data` 表类 | 全局 | 表容器 + JSONL 加载 + 反射工厂 | `Database`(15 方法) |
| **地图/路径** | `MapManager`、`Map`、`Tile`、`MapGrid`、`MapInfo`、`PathInfo`、`PathPoint`、`OnePath`、`PathHelper` | 全局 | 逻辑格阵 ↔ 视觉格阵、路点 → A* 折线 | `MapInfo`(16 字段) |
| **工具** | `*Tool`（`SpineDownLoadTool`、`EnemyInfoExcelTool` 等）、`ExcelHelper` | 全局 | 编辑器期导表 / 抓素材 | `ExcelHelper`(8 方法) |
| **第三方** | `AstarPath`（A* Pathfinding Project）、`FairyGUI`、`DOTween`、`Spine`、`Addressables` | 其它 dll | — | **寻路用 A\*，不用官方那套 SPFA** |

> 混淆情况：`OPS.Obfuscator` 把**方法名/内部类型名**改成 `e2o`/`a3h`/`rt`；**业务类名、字段名、接口名、枚举名全部保留** —— 这正是本次能不靠反编译器把链路读通的原因（判据：`Unit`/`DamageInfo`/`SkillData` 等 6,047 个字段名全可读）。

### 1.2 主循环（✅ IL 逐条实测）

```
Unity 引擎
 └─ BattleManager::Update()                    // MD505 @0x020df0
      if (Battle == null || Pause) return;
      Battle.e3w();                             // 每帧一次
      ExcuteTime += Time.deltaTime;
      int target = Mathf.FloorToInt(ExcuteTime / SystemConfig.DeltaTime);
      while (done < target - Battle.Tick) { Battle.e3o(); done++; }   // 追赶 tick
```
- `SystemConfig.DeltaTime` = **`0.016666668f`（= 1/60 s）**，由 `SystemConfig::get_DeltaTime`(MD391) 直接 `ldc.r4` 返回；另有 `TurningTime = 0.15f`。
- `BattleManager` 字段仅 6 个：`aeie`(单例)、`Battle`、`Pause`、`ExcuteTime`、`NowBattleInput`、`aeir`(TaskCompletionSource，供 `StartBattle` 等待)。
- **两个 MonoBehaviour 的 Update 互不排序**：`BattleManager.Update`（逻辑）与 `MapManager.Update`（地图表现）由 Unity 调度，**不能假定先后**。

单 tick `Battle::e3o()`(MD80) 顺序（IL 行号序，详见 `63a` §1.3）：

| 序 | 调用 | 作用 |
|---|---|---|
| 1 | `Battle::rrr` | tick 前归位（`CostCountSpeed` 等） |
| 2 | `Tick++` | 帧计数 |
| 3–4 | `Battle::e33`、`Battle::rre` | 关卡/经济/技力段、第二段 |
| 5–7 | `Battle::rtt(OneWave)` / `Battle::rts(...)` | **出怪**、检查点、场景单位 |
| 8 | `Tile::rwo()` × 格 | **地图格** |
| 9 | `Bullet::rhs()`、`Bullet::rhh()` × 子弹 | **子弹** |
| 10 | `Unit::st2` → `Unit::a3s` → `Unit::a3h` → `Unit::str` × 单位 | **单位** |
| 11 | `CountDown::rii` → `Unit::a3o` | 死亡清理 |

### 1.3 数据加载链（✅ IL 实测）

```
编辑器期：battle.xlsx ──ExcelHelper(ExcelDataReader)──▶ StreamingAssets/data/*.txt（JSONL，一行一对象）
运行期：  Database::Init()（异步 <Init>d__5）
            └─ 顺序：CardData → UnitData → SkillData → BuffData → BulletData → ModifyData
                     → EffectData → RelicData → ContractData → EventData → RewardData
                     → DungeonLevelData → SystemData
                       └─ Database::AddAsync<T>（<AddAsync>d__14`1::MoveNext, MD631）
                            ① SaveHelper.hhe("/Data/" + name + ".txt")        ← 散文件优先
                            ② 失败 → Addressables.LoadAssetAsync<TextAsset>(PathHelper.DataPath + name)
                            ③ text.Split('\n')  →  逐行 JsonHelper.hr3<T>(line)
                            ④ 单行异常只 LogError(name + "\n " + line)，不中断
                            ⑤ 落进 Dictionary<Type, IConfig[]>  Database::aewr
地图支线：Database::s2o(MapName) : MapInfo（MD617）
            ← StreamingAssets/map/<名>.map（Newtonsoft JSON，含 $type/$values 与 GridInfo[,]）
存档支线：GameData::e2o（MD26）← SaveHelper.hhe("/data.sav") + JsonHelper.hr3<GameData>
资源支线：PathHelper 常量（IL 原文）：
            DataPath="Assets/Bundles/Data/"、UnitPath="Assets/Bundles/Units/"、
            BulletPath、EffectPath、UIPath、SpritePath、AudioPath、DungeonGridPath、OtherPath
          ResHelper::hse(key) → Addressables 装载（Unit::sei 用它取模型）
```
> ⚠️ **42 个 `.map` 里没有任何一个带 `"Scene"` 字段**（实测 Select-String 全库 0 命中），而 `<StartBattle>` 的逻辑是「`sceneName = MapInfo.Scene`；为空则回落 `"Assets/Scenes/MapBuilder.unity"`」⇒ **运行期所有关卡都载入同一个 MapBuilder 场景，关卡几何完全由 `GridInfos` 数据 + `MapManager::hot(Tile[,])` 程序化搭建**。✅ 数据侧判据 + IL 侧判据双证。

### 1.4 战斗结算链（✅ IL 实测）

```
Skill::asa(target, bullet, rate)                      // 命中入口（65 处调用点）
 ├─ EffectManager::irw(SkillData.HitEffect) → Effect::rwr(...)      // 命中特效（表现）
 ├─ Skill::aie / Skill::asr                                        // 目标合法性
 ├─ 溅射分支：Battle::re3(...) 范围索敌 → 逐目标
 └─ Skill::aiw(target, damageBase, damageScale) : DamageInfo        // ★ 造伤害包（MD297）
       DamageInfo{ Target, AllCount, Source=Skill, DamageRate, DamageType, IsHeal, Attack }
       Attack 来源由 switch(SkillData.DamageBase) 12 分支决定
        └─ Unit::se2(DamageInfo)                                    // ★ 受击主流程（MD430, 642 行 IL）
             ① Battle.Random.NextDouble() ×4        // 闪避/暴击等概率
             ② UnitModeI::sot()                     // 受击表现
             ③ TriggerData push → Unit::sta(TriggerEnum) → pop      // 受击事件
             ④ Unit::se3(atk, type, defIgnoreFix, defIgnoreRate, scale, source) : float   // ★ 伤害公式（MD431）
                  物理: def = Max(0, Defence*(1-b-source.DefenceIgnoreRate) - a - source.DefenceIgnore)
                        dmg = Max(atk*scale, atk - def)
                  法术: mdef = Max(0, MagicDefence*(1-b-source.MagicDefenceIgnoreRate) - a - source.MagicDefenceIgnore)
                        dmg = Max(atk*scale, atk*(100-mdef)/100)
             ⑤ 护盾: IShield::rht(d)（List<IShield> 逐个）
             ⑥ UnitModeI::swo(RewriteDamage) / Hp -= RewriteDamage     // 截断伤害分支
             ⑦ UnitModeI::sww(d) / Hp -= d.FinalDamage                // ★ 飘字 + 扣血
             ⑧ ISelfAfterFinalAbsorb::rso(d)
             ⑨ IAfterDamageModify::roi(d) / ISelfAfterDamage::rsw(d) / ISelfAfterWithoutDamage::rs2(d)
             ⑩ TriggerData push → Battle::rrh(TriggerEnum) → pop → Hp 钳位 → Unit::a3w(...)   // 死亡
    治疗走另一条：Unit::seo(DamageInfo, bool) → IHeal::rsi / ISelfHeal::rs3 / UnitModeI::sw2
伤害修正钩子：Modify::ror(DamageInfo, target)（MD229）
     攻方 Buffs 中所有 ISelfDamageModify → roa(d)；受方 Buffs 中所有 IDamageModify → ros(d)
```

### 1.5 渲染/表现层接入 —— **拉取式（pull）**（✅ IL 实测）

```
Unit::sei()                                   // MD427：绑定时一次性
  if (UnitData.Model 为空) return;
  GameObject go = ResHelper.hse(PathHelper.UnitPath + UnitData.Model);   // "Assets/Bundles/Units/" + model
  UnitModel = go.GetComponent<UnitModeI>();     // Unit.UnitModel : UnitModeI
  UnitModel.sit(this);                          // 把逻辑 Unit 注入视图

NormalModel::LateUpdate()                      // MD524：每帧单向拉取
  if (Unit == null) return;
  transform.position        = Unit.Position + new Vector3(0, Unit.Height + Unit.HeightEx, 0);
  transform.localEulerAngles = new Vector3(0, 0, Vector2.SignedAngle(Vector2.right, Unit.Direction));
  animator.Play(Unit.AnimationName[0]);
```
`UnitModeI` 的 19 个方法构成**逻辑→表现的事件面**（实测调用点）：
`sit(Unit)` 绑定；`swo(float)` 血条（8 处）；`sww(DamageInfo)` 飘字（仅 `Unit::se2`）；`sw2(DamageInfo)` 治疗飘字；
`sws(Color)` 染色（4 处，`Units.敌人::a3h/a3e` 死亡变黑/受击变白）；`sot()` 受击；`soe/sor/soa/sos/soh(float)` 费用/技力/护盾等条。
`Effect`（`EffectManager::irw` 造，`EffectData.Prefab`）自己 `Update` 写 transform —— **特效是独立自驱的，不走 Unit 拉取**。

### 1.6 ★ 反射工厂：表 `Type` 列 = 类名（**IL 指令级实证**）

`ModifyManager::ro3(int id, Skill skill) : Modify`（MD238）IL 原文：
```
Database.Instance.s2t<ModifyData>(id)                    // 查表
typeof(Unit).Assembly.CreateInstance("Modifys." + m.Type) // ★ ldstr 'Modifys.' + CreateInstance
→ stfld Modify::Id, stfld Modify::Skill, → Modify::roe()
```
同类工厂**共 56 处 `Assembly::CreateInstance` 调用点**（`--who Assembly::CreateInstance`）：

| 代码前缀（`ldstr`） | 工厂方法 | 领域 |
|---|---|---|
| `"Units."` | `Battle::rts/rth/rti/rtw/rto/rt2/rt3/ret/ree/rer/rea/res` | 单位（12 处） |
| `"Bullets."` | `Battle::reh/rei/rew`、`Skills.秘术师攻击::erot` | 子弹 |
| `"Buffs."` | `Buff::ra2`、`Unit::sth/sti/stw/ssh`、`Skill::asi` | Buff（6 个 ldstr 点） |
| `"Modifys."` | `ModifyManager::ro3` | 属性修正 |
| `"Skills."` | `Unit::sts` + 33 处 buff/skill 内动态造技能 | 技能 |

`Unit::sth(int buffId, Skill src, int index) : Buff`（MD415）是本范式最完整的样本：
```
if (IgnoreBuffs.Contains(buffId)) return null;                            // 免疫
config = Database.s2t<BuffData>(buffId);
if (config.RelyBuff.HasValue && !Buffs.Any(b=>b.Id==config.RelyBuff)) return null;  // 前置依赖
exist = Buffs.FirstOrDefault(...); if (exist!=null) { exist.rae(); return exist; }  // 叠加/刷新
b = (Buff)typeof(Buff).Assembly.CreateInstance("Buffs." + config.Type);   // ★
b.Index/Id/Skill/Unit = ...;  Buffs.Add(b);
if (b is IShield) Shields.Add(...) sai();  if (b is IElementShield) ... sst();
if (b is IShieldCount) ...;                if (b is IHeal) Heals.Add(...);
b.rro();                                                                  // 生效钩子
```
> **另一条并存的分发**：`Skill::aiw` 用 `switch (SkillData.DamageBase)` 12 分支选伤害基数来源。⇒ ArknightR **同时存在"反射选类"与"枚举 switch"两种分发**，前者用于机制，后者用于小枚举。

---

## 二、三个例子：从底层代码到图形层的完整调用链

### 例 1 —— 一个单位（敌人）在空地图上移动

| 层 | 步骤 | 位置 |
|---|---|---|
| **数据** | `.map`（JSON）→ `MapInfo.PathInfos : List<PathInfo>`，`PathInfo{Name, Path:List<PathPoint>}`，`PathPoint{Pos:Vector2Int, Delay, DirectMove, HideMove}` | `StreamingAssets/map/*.map` |
| **数据** | 出怪表 `WaveInfo.sUnitId` → `Database::s2e<UnitData>(sUnitId)` | `Battle::rtr` IL_007F |
| **逻辑·建路** | `AstarPath.active.Scan()`；对每对相邻 `PathPoint.Pos` 调 `Map::rww(from,to,0) : List<Vector3>`，存 `Battle.OriginPathInfo[name][i]` | `Battle::e32`(MD81) ← `Battle::e3i` IL_01DC |
| **逻辑·出怪** | `Tick*DeltaTime > OneWave.Time` → `Battle::rtt(oneWave)` | `Battle::e3o` IL_0096 |
| **逻辑·入场** | `Units.敌人::eti2` → `State=3`（`Unit::seh`）+ `sta(5)` 触发 | MD2009 |
| **逻辑·移动** | `TempArriveDistance = Speed * DeltaTime`；`dir = (TempTarget - Position).normalized`；**`Position += dir * (Speed * DeltaTime)`**；`Direction = Vector2(delta.x, delta.z)`；`TargetScaleX = Sign(Round(delta.x))` | `Units.敌人::a3h` IL_0099 + `Units.敌人::a33` IL_0402（MD2020） |
| **逻辑·到达/漏怪** | `dist < TempArriveDistance` → `Position = TempTarget`；`TempIndex++`；越界则 `NowPathPoint++` + `PathWaiting.ris(PathPoint.Delay)`；走到末点 → `Battle::rrs(UnitData.Damage, this)` + `Unit::a3o(false)` | `Units.敌人::a33` IL_02A4；`Units.敌人::etwh` IL_0046；`Battle::rrs`(MD109) |
| **逻辑·阻挡** | `Battle::re3(Position2, UnitData.Radius + 0.3571f, 1, 1)` → 圆内单位 → `sr3(this)` + `sta(23)` | `Units.敌人::etwt`(MD2015) |
| **表现** | `NormalModel::LateUpdate` 读 `Unit.Position`（+Y=`Height+HeightEx`）与 `Unit.Direction` 写 `transform` | MD524 |

### 例 2 —— 一次普攻命中与伤害结算

| 层 | 步骤 | 位置 |
|---|---|---|
| **数据** | `SkillData{ DamageRate, DamageType, DamageBase, DamageWithFrameRate, Cooldown, IfHeal, AreaRange, AreaDamage, AreaMainDamage, AreaPoints, HitEffect, TargetTeam }`；`UnitData{ Attack, AttackEx, Defence, DefenceEx, MagicDefence, MagicDefenceEx, Radius }` | `StreamingAssets/data/SkillData.txt`(3.08MB) / `UnitData.txt`(1.89MB) |
| **逻辑·造包** | `Skill::aiw(target, damageBase, damageScale) : DamageInfo`：`DamageRate = damageBase*SkillData.DamageRate*damageScale*(DamageWithFrameRate?cd:1)`；`switch(DamageBase)` 12 分支定 `Attack` | `Skill::aiw`(MD297) |
| **逻辑·命中** | `Skill::asa(target,bullet,rate)`：命中特效 → `aie/asr` 合法性 → 溅射/逐格 → `target.se2(d)`（治疗走 `target.seo(d)`） | `Skill::asa`(MD271) ← 65 处调用点（Bullet 命中回调、近战命中、buff 反击…） |
| **逻辑·结算** | `Unit::se2(DamageInfo)`：随机 → `UnitModeI::sot()` → 事件 pop/push → **`Unit::se3` 公式** → `IShield::rht` → `Hp -= FinalDamage` | `Unit::se2`(MD430) |
| **逻辑·公式** | `Unit::se3`：物理 `Max(atk*scale, atk - Max(0, Def*(1-b-来源破防率) - a - 来源破防值))`；法术 `Max(atk*scale, atk*(100-mdef)/100)`；负值钳 0 | `Unit::se3`(MD431) |
| **逻辑·修正钩子** | `Modify::ror(d, target)`：攻方 `ISelfDamageModify::roa`、受方 `IDamageModify::ros` | `Modify::ror`(MD229) |
| **表现·特效** | `EffectManager::irw(SkillData.HitEffect)` → `Effect` → `Effect::Update` 写 transform | `EffectManager::irw`(MD1007)/`Effect::Update`(MD193) |
| **表现·数值** | `UnitModeI::sww(DamageInfo)` 飘字、`UnitModeI::swo(hpRate)` 血条（实现类对应 `BattleUI.UI_DamageInfo{ m_type, m_number, m_show }`） | `Unit::se2` IL_054A/058A |

### 例 3 —— 一个带 buff 的效果生效

| 层 | 步骤 | 位置 |
|---|---|---|
| **数据** | `BuffData`（29 字段，含 **`Type` = C# 类名**、`RelyBuff` 前置依赖）→ `StreamingAssets/data/BuffData.txt`（542KB JSONL） | — |
| **逻辑·加 buff** | `Unit::sth(buffId, src, index)`：免疫 → 查表 → 依赖检查 → 同名叠加走 `rae()` → **`CreateInstance("Buffs."+config.Type)`** → 按接口分流 `IShield/IElementShield/IShieldCount/IHeal` → `Buff::rro()` | `Unit::sth`(MD415) |
| **逻辑·tick** | `Buffs.Reverse()` 逐 buff `Buff::rah()`（`Unit::a3s`、`Unit::st2` 两处都做） | `Unit::a3s`(MD403)、`Unit::st2`(MD420) |
| **逻辑·属性生效** | **`Unit::a3a` 每 tick 全量重算**：先把 `*Add/*Rate/*Fin/*Ex` 全归零 → 再按 `终值 = (基础+加法)×(1+百分比)×(1+最终百分比)×(1+技能Ex)×(1+天赋Ex)×LastRate` 算 `Speed/MaxHp/Attack/Defence/MagicDefence` | `Unit::a3a`(MD402, 1278 行 IL)；基础值来自 `Unit::a3r`(MD401) |
| **逻辑·受击类 buff** | `IShield::rht(d)`（护盾）/ `IDamageModify::ros(d)` / `ISelfDamageModify::roa(d)`（增伤减伤）—— 由 `Unit::se2` 与 `Modify::ror` 反向调用 | 见例 2 |
| **逻辑·移除** | `Buff::rse()` ← `Buff::rae`、`Buff::rah`、`Skill::asw`、`Unit::a3o`（367 处） | — |
| **表现** | **没有独立 buff UI 类**（`BattleUI.*` 21 个类型里无 Buff）；buff 表现挂在 `BattleUI.UI_BattleUnit`(22 字段)/`UI_Head`/`UI_ShowAttribute`；元素损伤条 `UI_ElementBar`/`UI_EnemyElementBar`；buff 也可自带表现对象（`Unit::ssh` 里有 `ldstr "Buffs."` 反射点） | — |

---

## 三、与官方客户端的对应定位

**判据分级**（本文严格区分）：
`数值级`（常量逐位相同）> `字段/结构级`（字段名与语义逐个对上）> `签名级`（参数/返回类型对上）> `职责级`（做同一件事但结构不同）> `仅名字相似`（最弱，不作为依据）。

### 3.1 ★ 强判据 —— 已确认

| # | ArknightR | 官方（dump.cs 行 / RVA） | 判据 | 置信 |
|---|---|---|---|---|
| 1 | `DamageInfo`（22 字段） | **`Torappu.Battle.Modifier`（struct，行 352478，TypeDefIndex 9150）**：`m_source`0x0 / `m_target`0x10 / `m_value`0x20 / `ignoreMissFlag(DamageTypeMask)`0x30 / `realDelta`0x38 / `damageType`·`applyWay`·`attackType`·`elementType`0x58–0x68 / `originAtk`0x70 / `playerSide`0x80 + **22 个 flag 常量**（352481–352498） | **字段/结构级（最强）**：`Source↔m_source`、`Target↔m_target`、`FinalDamage↔m_value`、`Attack↔originAtk`、`ShowCrit↔get_isCritical`、`Avoid/ForbidAvoid↔ignoreMissFlag`、`NoFatal↔DAMAGE_IS_UNDEADABLE_THIS_TIME` | ✅ |
| 2 | `DamageInfo` 的 `Attack`/`AttackAdd`/`DamageRate`/`DamageType` | `BattleFormula.AttackInfo { damageType, originAtk, atk, atkScale, atkAddition }` **行 322624**（TypeDefIndex 8589）+ `GetFinalAtk()` RVA 0x3582350 | **字段/结构级**：四字段一一对应（`Attack↔atk`、`AttackAdd↔atkAddition`、`DamageRate↔atkScale`、`DamageType↔damageType`） | ✅ |
| 3 | `Unit::se3(float atk, DamageTypeEnum type, float a, float b, float scale, Unit source) : float` | `BattleFormula.CalculateDamage(FP atk, Entity target, DamageType damageType, FP atkScale, FP atkAddition)` **行 322686，RVA 0x3585AB0**；内部 `CalculateDamageInternal(AttackInfo, penetrateRatio, penetrateFixed, Entity)` 行 322683/RVA 0x3585060，实测先调 `AttackInfo.GetFinalAtk()`(0x3582350) | **签名级 + 指令级分支**：参数序一一对应（ArknightR 把 target 收成 `this`）；官方按 `DamageType` 分 4+1 路，**物理/法术结构与 ArknightR 同构** | ✅ |
| 4 | 逻辑↔视图绑定点（`Unit.UnitModel : UnitModeI` + `sit(this)`） | **`MountPoint`（行 352938）**：`m_transform : Transform`0x10 + `m_entity : ObjectPtr<Entity>`0x18，属性 `mapPosition/worldPosition/gridPosition/height/faceTo`；宿主 `Entity.m_footMountPoint/m_hitMountPoint/m_muzzleMountPoint/m_headMountPoint/m_uiMountPoint`0x108–0x128 | **字段/结构级**：一个对象同时持有**视图 Transform** 与**逻辑 Entity** | ✅ |
| 5 | `ModifyManager` + `Modify`（聚合与逐条应用） | **`Attributes`（行 319487）**：`m_attributeModifiers : HashSet<IAttributesModifier>[]`0x18、`m_rawData : ObscuredFP[]`0x40、**`m_dirtyMask : long`0x60**、`AddModifier/RemoveModifier/AddModifierToSingleAttribute` | **字段/结构级**：官方是"修饰器集合 + 脏掩码"；`Attributes.IAttributesModifier`（行 319406，6 个 long 掩码）↔ ArknightR 的 6 个 `I*Modify` 接口（**官方是 1 个接口 6 掩码，ArknightR 是 6 个接口**） | ✅ |
| 6 | 帧长：`SystemConfig.get_DeltaTime()` = `ldc.r4 0.016666668`（写死，**= 1/60 s**） | `Torappu.Battle.Consts.DELAY_SINGLE_FRAME = 0.016666668` **行 294501**；但 `GlobalConsts.FIXED_DELTA_TIME_FP`（行 1230134）**来自 `UnityEngine.Time.fixedDeltaTime`**（`GlobalConsts..cctor` @0x54E4D50：`call Time.get_fixedDeltaTime()` → `×0.5` / `×2^32`），而本库 `04/29` 已实读官方 `globalgamemanagers` 的 `Fixed_Timestep = 0.03333330154418945`（**= 1/30 s**） | **数值级仅限"某个官方常量"**：常量逐位相同 ✅，但**官方运行期步长是 `1/30 s`，ArknightR 是 `1/60 s` ⇒ 帧率差 2 倍**。`DELAY_SINGLE_FRAME` 是另一个用途的常量（`Consts` 里的单帧延迟），**不构成运行期对应** | ✅ 常量 / ❌ 运行期（**不对应**） |

### 3.2 中判据 —— 已确认（职责/结构对应，但不是逐字段对应）

| # | ArknightR | 官方 | 判据 | 置信 |
|---|---|---|---|---|
| 4 | `BattleManager`（MonoBehaviour 单例，字段 `Battle`/`Pause`/`ExcuteTime`；`Update` 内累加时间追赶 tick） | `BattleController : SingletonMonoBehaviour<BattleController>` **行 320906**；静态 `s_fixedFrameCnt`(0x14)/`s_fixedPlayTime`(0x18)/`s_deltaPlayTimeFP`(0x48)，方法 `Update` 0x3557AA0 / `FixedUpdate` 0x35487E0 / `OnTick` 0x354F880 / `ManualFrameTick` 0x354CB60 | **职责级 + 调用链**：官方 `Update` **不做 tick**（只做状态机/资源池/`Time.unscaledDeltaTime`）；**`FixedUpdate`** 才按 `Deck`×`PlayerSide` 驱动 `IBattleModule.OnFixedUpdate(FP)`；**`OnTick`** 是定点时间推进本体；**`ManualFrameTick` = `FrameData.DumpToPlayerOpQueue(...)` 后 `jmp OnTick`**（手动帧＝注入输入＋恰好一次 OnTick） | ✅（结构）/ 🟡（驱动等价） |
| 5 | `Battle`（一局状态容器：`Tick`/`Waves`/`CheckPoints`/`Map`/`Units`/`Bullets`/`Hp`/`CostCountSpeed`） | `BattleController` 实例区：`_map`(0x28)/`_scheduler`(0x30)/`m_levelData`(0x178)/`m_mapData`(0x180)/`m_lifePoint`(0x25C)/`m_costDict`(0xC0)/`unitManager`(0x2C0) | **职责级**：状态全在控制器里；官方把"出怪"拆到独立 `Scheduler`，ArknightR 塞在 `Battle` | 🟡 |
| 6 | `Unit`（`Hp`/`MaxHp`/`Attack`/`Defence`/`MagicDefence`/`Position`/`Direction`/`Block`/`State`/`UnitModel`） | `Entity` **行 330768**（`m_hp` 0x40 / `m_es` 0x48 / `m_attributes` 0x98 / `m_direction` 0xD4 / `m_abilities` 0xC8 / `buffContainer` 0x150）→ `Unit` 行 385204（`_modes` 0x188 / `m_currentMode` 0x1E8）→ `Character` 行 377663 / `Enemy` 行 380866；`Def` = `Entity.get_def()` **0x3608450** | **职责级**：属性+朝向+buff容器+表现模式都在同一实体上；**官方属性是 `Attributes` + `Modifier` 结构，ArknightR 是 40+ 个裸 float 字段**。**★ `Block` 官方拆两层**：`Enemy._blockVolume`0x2F8 + `Character._blockMode`0x29C ⇒ ArknightR 单字段是**语义压缩**，对照时必须标明哪一侧 | 🟡 |
| 7 | `UnitModeI`（接口）+ `NormalModel`/`SpineModel`（MonoBehaviour），`Unit.UnitModel` 单向引用 | `UnitMode : MonoBehaviour, ITalentOwner, IEffectSource` **行 386204**，字段 `host : Unit`(0xA8)、`_bodyTransform`(0x18)、`combat`/`attack`(Ability,0x38/0x40)、`_animatorHooker`(0x20)；`Unit._modes : UnitMode[]`(0x188) + `m_currentMode`(0x1E8)；动画侧 `UnitAnimator`(行 317861 抽象) → `SpineAnimator`(316817)/`CharacterAnimator`(314994)/`MeshAnimator`(315619)… | **字段级（绑定字段）**：`UnitModeI.Unit` ↔ `UnitMode.host` 同义；**但官方是"多 mode 数组 + 当前 mode"，且把 `combat`/`attack` 做成 `Ability` 挂在 mode 上**，ArknightR 是单一 model 引用 | 🟡 |
| 8 | `Units.敌人` 沿 `OriginPathInfo`（A* 折线）逐点平移，`PathPoint{Pos, Delay, DirectMove, HideMove}` | `Route` **行 349654**（`m_map`/`m_data:RouteData`/`m_targetNextMap:Node[,]`/`m_checkpointsNextMap`），`Route.Node`（行 349605：`pos`0x10/`tile`0x18/`nextTurn`0x20/`nextNode`0x28/`distance`0x30/`distToFinal`0x34）；`PathRequest`(struct,行 349475：`targetPos`/`motionMode`/`allowDiagonalMove`)；`SPFA : IPathFinding`(行 349505，`GenerateNextMap(PathRequest, Route.Node[,])` @0x5C9CE0 附近)；`LevelData.routes`0x60/`extraRoutes`0x68/`branches`0x88/`randomSeed`0xA8 | **字段/结构级（对 `Route.Node`/`PathRequest`）+ 职责级**：都是"路点表 → 局内预计算下一跳查找表 → 逐格平移"。**算法不同：官方 SPFA 逐格 `nextNode`/`nextTurn`；ArknightR 用 A\* Pathfinding Project 把路点插值成世界坐标折线**（见 §3.3） | 🟡 |
| 9 | `Unit::a3a` 终值公式 `(基础+加法)×(1+百分比)×(1+最终百分比)×(1+技能Ex)×(1+天赋Ex)×LastRate` | 官方公式本体未逐指令核验；官方属性载体是 `Entity.m_attributes`(0x98) / `Attributes`(行 319487，含 `m_rawData : ObscuredFP[]`0x40 与 `m_dirtyMask`0x60)；单条取值 `Buff.GetValue(AttributeType, out FP addition, out FP multiplier, out FP finalAddition, out FP finalScaler)` RVA **0x358CAA0 / 行 324888** | **结构级（公式形状同构）**：官方 `GetValue` 的 4 个输出（加法/乘法/最终加法/最终乘数）与 ArknightR 的 `Add/Rate/AddFin/RateFin` **四段一一对应** | ✅（四段结构）/ 🟡（公式本体） |
| 10 | `Unit.ElementBuffs` / `ElementShields` / `ElementShowBuff` + `IElementShield::rht/rso` / `IElementModify::ro2` + `Buffs.元素损伤`/`新版元素损伤`/`元素损伤易伤`/`元素损伤治愈` | **`Entity.EPController : Attributes.IAttributesModifier`（行 330394，TypeDefIndex 8702）**：`recoveryType:ElementType`0x10、`m_owner`0x18、`m_isInBreakRecovery`0x20、`m_tween`0x28；方法 `Reset`/`OnFinish`/**`OnTick`**/**`_CreateBrokenBuff(EPBreakBuffData, float)`**/`_StartEPRecovery`/**`OnElementBreak(ElementType)`**@0x35F39F0/`GetValue`；宿主 `Entity.m_epController`0xE8 与 **`Entity.m_epArray : FP[]`0x80**；`BattleFormula::CalculateElementDamage`（行 322689/322692/322695）；`EPBreakBuffData`（行 83685）；`ElementType{NONE,SANITY,WATER,FIRE,DARK}`（行 312016） | **字段/结构级 + 职责级**：都是"元素损伤累积 → 满则爆发并挂 break buff（`_CreateBrokenBuff` ↔ ArknightR 的 `元素损伤`buff）"；**但官方是 `Entity` 上的专用控制器类 + `FP[]`，ArknightR 是 buff 体系 + `List<>`**。`IElementShield` 官方**无 1:1**（仅 `IShieldSource` 行 333328 近似） | 🟡 |
| 11 | `Battle.Tick`（int 帧计数）驱动一切 | **`DiscreteTime`**（行 1981223，`internal struct`，`IComparable`）—— 官方把"离散帧时间"做成**独立值类型**；`BattleController.OnTick`(0x354F880) 实测调 `ControlTrack::op_Addition(DiscreteTime,DiscreteTime)` @0x3D2A010（机器码 `lea rax,[rcx+rdx]; ret`，即整数相加）与 `op_Subtraction` @0x54E23A0 | **职责级**：都是"整帧计数当时间"。官方有类型化的 `DiscreteTime` + 运算符重载，ArknightR 是裸 `int Tick` | 🟡 |
| 12 | 表现层偏移/朝向/血条等 UI | `UnitMode` 之外，相机侧官方**无 `BattleCamera`**，最近为 **`CameraController : SingletonMonoBehaviour<CameraController>`（行 325552）+ `CameraController.Plugin`（行 325359）**；`MapTile` ↔ `Tile : VisualObject`（行 351277）；`PoolModel`/`TrailManager` ↔ `ObjectPool.PoolManager`（行 183532）；伤害飘字 UI ↔ `Entity.ShieldUIController`(330495) 等 | **仅名字相似 / 职责级**（`BattleCamera` 类名在 203 万行 dump 里 **0 命中**） | 🟡 |

### 3.3 ★ 结构性差异（**ArknightR 不是官方还原**，三条最重要的）

| 维度 | ArknightR | 官方 | 影响 |
|---|---|---|---|
| **时钟驱动** | `MonoBehaviour.Update` 里 `ExcuteTime += Time.deltaTime` + `FloorToInt` 追赶（浮点累加），**步长写死 1/60 s（60 Hz）** | 静态 `s_fixedFrameCnt`/`s_fixedPlayTime`(FP 定点) + `FixedUpdate` + `ManualFrameTick(FrameData, additionalFrame)`，**步长 = `Time.fixedDeltaTime` = 1/30 s（30 Hz，见 `04/29`）** | ①ArknightR **帧率是官方的 2 倍**；②不具备官方的帧级确定性与回放能力（官方有 `ReplayController`、`PlayerOperationQueue`、`isDeterministic`、`randomSeed`）；③官方用 Q32.32 定点累加，ArknightR 用 float ⇒ **复刻确定性绝不能用 ArknightR 作依据** |
| **寻路** | A* Pathfinding Project（`AstarPath.active.Scan()`），路点间插值为世界坐标折线，移动 = 直线趋近 + 0.05/`Radius+0.3571` 硬编码阈值 | `Route` + `IPathFinding` + SPFA 预计算**逐格 `nextNode`/`nextTurn`**，`m_targetNextMap : Node[,]` | 阻挡/寻路细节（含 0.3571 常量）**不具官方效力** |
| **伤害/机制入口** | `Unit::se2(DamageInfo)` 一个巨型方法包办护盾→扣血→飘字→事件；机制靠 `Buff`/`Modify` 接口族钩入 | `BattleFormula.CalculateDamage` 纯函数 + `Entity` 上 `Ability`/`Buff` 事件；`Attributes`/`Modifier` 分离，且**有 `m_dirtyMask` 脏标记** | 借架构可以，**借数值/顺序不行** |
| **★ 机制分发** | **表 `Type` 列 = C# 类名 → `Assembly.CreateInstance("Buffs." + Type)`**（56 个反射点，`63a` §1.6 IL 实证） | **官方完全没有这一套**：`Activator.CreateInstance` 24 处**全在 UI/网络层，战斗层 0 处**；`Type.GetType(string)` 仅 3 处且只服务 JSON 反序列化；`buff_type` 0 命中。官方是 **1310 个 `Nodes.* : ActionNode` 子类 + `Blackboard` 数据对 + `ActionNode.Execute(Blackboard, SourceType, ref Snapshot)`（行 463568/463588）+ 枚举 switch** | **最重要的一条否定结论**：`Type` 列反射是 **ArknightR 的工程范式**，可作我们自建工具的设计参考，但**不是官方机制**——**不能**用它反推官方 gamedata（不能假设 `buff_type` 里存类名） |
| **★ 伤害保底** | `Unit::se3` = `Max(atk*scale, atk − def)`，负值钳 0，**无百分比保底项** | `BattleFormula..cctor`(@0x3586D00) 实测 `MIN_ATK_FACTOR = 0.05`（`movss [0x5D66D54]`）⇒ 物理 `max(FinalAtk − max(0,def−DefIgnoreFixed)×(1−DefIgnoreRate), **FinalAtk×0.05**)`；**PURE/HEAL 不减防**；元素走 `epDamageResistance` | **真实的数值差异**：ArknightR 缺 5% 保底 ⇒ 低攻高防场景伤害会算成 0 以下被钳 0，与官方不同。**复刻时不能照抄 ArknightR** |
| **★ 伤害类型枚举** | `DamageTypeEnum{Normal=0, Magic=1, Real=2, Element=3}`（Constant 表实测） | `DamageType{NONE=0, PHYSICAL=1, MAGICAL=2, PURE=3, HEAL=4, ELEMENT=5}`（行 311985） | **成员语义对应但数值整体错位**；且 ArknightR 把治疗走 `DamageInfo.IsHeal` 布尔，官方是独立枚举值 ⇒ **禁止按枚举整数直接对照** |

### 3.4 未找到 / 仅名字相似

| 目标 | 状况 | 卡点与下一步 |
|---|---|---|
| 官方 `OnTick` 单帧阶段 ↔ ArknightR tick 的 **Tile→Bullet→Unit** 分组 | **两套各自拿到，但互不印证** | 官方 20 阶段骨架（`63b` §A6，命令 `call 0x354F880 900`）**已实测**，可把 39 号文档 §6 的 🟡 升 ✅；但 ArknightR 的 **Tile→Bullet→Unit** 是**社区设计，不得当作官方顺序** |
| `Units.敌人::etwt` 的阻挡半径 **`0.3571f`** + **每帧**搜索 | **明确不对应** 🔴 | 官方：`Character.m_findBlockeeTicker`（**`FIND_BLOCKEE_TICK = 3`，每 3 帧**）+ `Enemy._blockVolume`0x2F8 / `Character._blockMode`0x29C + `stableBlockPosition` |
| `BattleCamera` / `BuffManager` / `IElementShield` / 6 个 `IModify` 接口 | **官方 0 命中（无同名类/接口）** 🔴 | 替代物已定位：`CameraController`(行 325552)+`CameraController.Plugin`(325359)；`Entity.buffContainer`(0x150)+`Buff.BuffContainer`(323489)+`BattleController.m_globalBuffs`(0x68)；`IShieldSource`(333328)+`Entity.m_es`(0x48)；`Attributes.IAttributesModifier`(319406)+`Entity`/`Buff.OnCalculateDamage` 虚方法族(332281/325031)。**⇒ 不必再找同名类** |
| ArknightR 的 `MapManager`/`PathManager`/`MapGrid`/`OnePath`/`PathPoint`/`BuildPathPoint` **类名** | **官方 0 命中** 🔴 | 结构等价物已定位（`Map`/`SPFA`/`Route`/`PathRequest`/`Route.Node`/`GridPosition`）⇒ 这套命名是 ArknightR **自研重构** |
| 官方属性**终值合成本体**（`Attributes` 把 `m_rawData` 合成终值） | 🟡 半查 | 四段结构已核实（`Buff.GetValue` 的 `addition/multiplier/finalAddition/finalScaler` ↔ ArknightR 的 `Add/Rate/AddFin/RateFin`，RVA 0x358CAA0 / 行 324888）；但 `Attributes` 的合成点未逐指令核验 → 下一步 `cls Attributes` + 反汇编其 `Get/Set` 与 `m_dirtyMask` 使用点 |
| 官方 `OnTick`/`FixedUpdate` 的**调用方** | 🔴 扫描不到 | `xref 0x354F880` / `xref 0x35487E0` 均 **0 个 E8 直接调用者** ⇒ 走 Unity 消息 / `__Hotfix0_*` DelegateBridge。唯一确定入口 `ManualFrameTick → jmp OnTick`。下一步：从 DelegateBridge 注册点反查或动态 hook |
| 官方元素分支是否也吃 **5% 保底** | 🟡 未判定 | 元素块与法术块共享尾段，静态未切分 → 下一步 `dis 0x3585137 120` 跟寄存器 |
| ArknightR `.map` 里 `WaveInfo`/`MapUnitInfo` 的完整字段语义 | 🟡 | 本次只取了移动/伤害/buff 所需字段 | 
| ArknightR 的 `MapBuilder` 运行期可行性 | 🟡 | 42 张图都回落加载 `MapBuilder.unity`（数据 + IL 双证），但**未运行程序验证** → 用 D: 完整副本启动，进 `SampleScene` → 选图 → 观察 `MapManager::hot` 是否真的程序化搭图 |
| `OPS.Obfuscator` 混淆名映射 | **不可还原** 🔴 | dll 内无映射文件；只能靠"字段名保留 + 调用图"反推（本次即用 `--refs`/`--who`/`andrefs.py`） |

---

## 四、解包/解析流程（可复现，已实测）

### 4.1 判目标是不是 Mono（决定用哪条工具链）

```powershell
Get-ChildItem 'D:\__soft\ak\ArknightR\ArknightR_Data\Managed' | Measure-Object   # 有 Managed\ → Mono
Test-Path 'D:\__soft\ak\ArknightR\ArknightR_Data\il2cpp_data'                    # False → 不是 IL2CPP
python ak\code\tools\read_mono.py '...\Assembly-CSharp.dll'                       # CLI 目录 rva≠0 → 是 .NET 程序集
```
**判据**：`Managed\` 有 104 个 dll + 无 `il2cpp_data/` ⇒ Mono ⇒ 用 ECMA-335 路线；反之用 `read_cpp.py` + dump.cs。

### 4.2 元数据 + IL 全链路（本次新工具，零依赖）

> 工具已从 `.tmp` 提升到 **`ak\code\tools\`**（与 `read_mono.py`、`read_cpp.py` 并列，长期可复用）：
> `mono_il.py`（ECMA-335 元数据 + IL 反汇编 + 调用图/引用索引，36KB）、`calls.py`、`andrefs.py`、`enumvals.py`（读 Constant 表取枚举值）、`il2cpp_rva_map.py`（官方侧 RVA→方法名）。

```powershell
$env:PYTHONIOENCODING='utf-8'; cd C:\Users\23922\Documents\ds_harness\ak\code\tools
$dll='D:\__soft\ak\ArknightR\ArknightR_Data\Managed\Assembly-CSharp.dll'
python mono_il.py $dll --stats                       # 表规模 + 命名空间分布（判"自研引擎"）
python mono_il.py $dll --types --grep Element        # 类型检索
python mono_il.py $dll --methods "Unit::"            # 方法 + 可读签名（含泛型实参）
python mono_il.py $dll --fields "DamageInfo"         # 字段 + 类型（字段签名要按 0x06 FIELD 前缀解析）
python mono_il.py $dll --dis "Unit::se3"             # ★ 反汇编（IL 偏移 + 操作码 + 解析后的 token）
python mono_il.py $dll --who "Unit::se2"             # ★ 谁调用它（全库调用图，95 个调用点）
python mono_il.py $dll --refs "DamageInfo::"         # ★ 谁碰过某 token（字段/方法/类型/字符串通用）
python calls.py   "Battle::e3o"                      # 列出被调方法 + 未在库内的外部调用
python andrefs.py "NowPathPoint" "Unit::Position"    # ★ 交集检索（混淆代码下的主武器）
python enumvals.py DamageTypeEnum StateEnum          # ★ 读枚举的字段默认值（Constant 表）
```
**"判据优先"用法**：方法名被混淆 ⇒ 先用 `--refs` 找"碰过官方语义字段（`DamageInfo::*`、`Unit::Hp`、`UnitData::*`）的方法"，再用 `andrefs.py` 交集收窄到唯一候选，最后 `--dis` 读指令确认。本次 3 个例子的核心方法都是这样定位的。

### 4.3 运行期数据（散文件优先，可直接读）

```powershell
Get-ChildItem 'D:\__soft\ak\ArknightR\ArknightR_Data\StreamingAssets\data' -Filter *.txt   # 9 个 JSONL 表
Get-ChildItem 'D:\__soft\ak\ArknightR\ArknightR_Data\StreamingAssets\map' -Filter *.map    # 42 个 JSON 地图
Get-Content '...\StreamingAssets\battle.xlsx' -TotalCount 1        # 编辑器源表（2.9MB）
Get-Content '...\StreamingAssets\data.sav' -Raw                    # 明文 JSON 存档
```
**判据**：`*.txt` 为**行式 JSON（一行一对象）**，可 `Get-Content | % { $_ | ConvertFrom-Json }` 逐行解析；`.map` 为 **Newtonsoft `$type`/`$values` 格式**（含 `GridInfo[,]` 二维数组），需带 `TypeNameHandling` 的反序列化器或手工递归 `$values`。
**双轨验证法**：同一张表在 `StreamingAssets/data/X.txt`（散文件）与 Addressables 包内 `TextAsset 'X'` 都存在 ⇒ 改数值不必重打包（`63a` §5 已给 IL 判据）。

### 4.4 本次踩坑（**复现必须知道**）

1. **pip 在本机必须先 `$env:PYTHONUTF8='1'`**，否则因某个 legacy editable 安装文件报 `UnicodeDecodeError: 'gbk' codec`（不是网络问题）。
2. `read_cpp.py dis/call/who/xref` 依赖 `pefile`+`capstone`，本机原先**没装**（`find/cls/m` 只用 dump.cs 所以能跑）——已装（见环境变更记录）。
3. 自研 IL 读取器的 **4 个 ECMA-335 必坑**（漏一个就整表错位）详见 `63a` §7；其中 `CustomAttribute` 行宽漏项 `read_mono.py` 也有一份，只因它只读 `CustomAttribute` 之前的表才没暴露 ⇒ **若要扩展 `read_mono.py` 必须先修这条**。
4. `#US` 堆解析**不能跳过短字符串**（长度 <4 的项也要记录），否则 `ldstr` token 查不到（本次从 957 条修到 999 条，3,182 个 `ldstr` 全部可解析）。

---

## 五、待查与卡点

| 项 | 状态 | 卡点 | 下一步 |
|---|---|---|---|
| 官方单帧阶段 ↔ ArknightR tick 分组 | ✅ 官方侧已拿到 / ❌ 无对应 | 官方 20 阶段骨架（`63b` §A6）已实测 ⇒ **可把 39 号 §6 由 🟡 升 ✅**；但 **ArknightR 的 Tile→Bullet→Unit 是社区顺序，不得混用** | 若要引 ArknightR 的顺序，必须显式标注"社区实现，无官方效力" |
| ArknightR `SystemConfig.DeltaTime` ↔ 官方**运行期**步长 | ❌ **已查明为不对应** | ArknightR 写死 `1/60 s`；官方运行期步长 = `UnityEngine.Time.fixedDeltaTime`（`GlobalConsts..cctor` @0x54E4D50）+ `globalgamemanagers` 的 `Fixed_Timestep = 0.03333330154418945`（**1/30 s**，见 `04/29` §四）⇒ **两者相差 2 倍**。`Consts.DELAY_SINGLE_FRAME = 0.016666668` 只是另一个常量，不构成运行期对应 | **已闭环，无需再查**；引用 ArknightR 的任何时间量都必须先 ×2 折算，或干脆不用 ArknightR 的时间数据 |
| 官方 `m_dirtyMask` 如何驱动属性重算 | 🔴 未查明 | 已知 `Attributes.m_dirtyMask : long //0x60` 与 `m_rawData : ObscuredFP[] //0x40`，但合成路径未反汇编 | `cls Attributes` + 反汇编其 `Get/Set` 与 `m_dirtyMask` 消费点 → 用于判断"官方是否只重算脏属性" |
| 官方元素分支是否也吃 5% 保底 | 🟡 未判定 | 元素块与法术块共享尾段，静态未切分 | `dis 0x3585137 120` 跟寄存器 |
| 官方 `OnTick`/`FixedUpdate` 的调用方 | 🔴 扫描不到 | `xref` 均 0 处（走 Unity 消息 / `__Hotfix0_*` DelegateBridge） | 从 DelegateBridge 注册点反查，或动态 hook |
| ArknightR `.map` 里 `WaveInfo`/`MapUnitInfo` 的完整字段语义 | 🟡 | 本次只取了移动/伤害/buff 需要的字段 | 单独写一份表结构对照（可放进 `05_舟数据` 层） |
| ArknightR 的 `MapBuilder` 运行期可行性 | 🟡 | `<StartBattle>` 逻辑上 42 张图都回落加载 `MapBuilder.unity`，但**本次未运行程序验证** | 用 D: 完整副本启动一次，进 `SampleScene` → 选图 → 观察 `MapManager::hot` 是否真的程序化搭图 |

> **本文件的自我限制**：全部结论来自静态 IL 反汇编 + 数据文件读取，**未运行 ArknightR**（因此"运行期行为"类结论一律标 🟡）。官方侧结论只用了 `dump.cs` 的**类/字段/签名/RVA**，除 `CalculateDamage` 外**未做机器码级验证**（🔴 的部分已列在 §3.4）。

## 相关文件
- `63a_ArknightR调用链IL证据细目.md` —— 逐条 IL 证据、方法索引（MD/rva/签名）、复现命令、ECMA-335 坑位
- `63b_官方对应检索报告.md` —— 官方 IL2CPP 侧完整检索记录（关键词 + 命中行号 + 判据）
- `40_外部工具解析_ArknightR与AFA.md` —— 前序静态分析（本文件修正其 `ElementBar` 说法）
- `33_cpp层战斗类结构与字段速查.md`、`37/38/39` —— 官方侧类结构与同帧顺序基线
- `ak\code\tools\mono_il.py`、`calls.py`、`andrefs.py`、`enumvals.py`、`il2cpp_rva_map.py` —— 本次自研工具（Mono 侧 IL 反汇编 + 官方侧 RVA 解析；`.tmp` 下有同源工作副本）
