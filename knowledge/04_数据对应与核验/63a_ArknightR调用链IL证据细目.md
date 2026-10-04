# 63a ArknightR 调用链 IL 证据细目
> 主题：**04B 读代码 / 反汇编**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）
> 层级：**T1（含代码/RVA 证据（RVA 91，代码词 10））**　建立日期：**—（待补）**　任务：—　｜　**头部为 2026-09-30 自动回填**，推断项已标注

> 父文档：`63_ArknightR架构与三例贯通.md`
> 目标程序集：`D:\__soft\ak\ArknightR\ArknightR_Data\Managed\Assembly-CSharp.dll`
> 大小 1,060,352 B，Mono/ECMA-335，**md 版本 v4.0.30319**，TypeDef 1,623 / MethodDef 6,684 / Field 6,047 / TypeRef 269 / MemberRef 1,470 / `#US` 957 条
> 全部结论**由 IL 反汇编直接读出**（工具 `ak\code\tools\mono_il.py`，自研零依赖 ECMA-335 读取器 + IL 解码器 + 调用图）——**未使用任何反编译器**，本机无 .NET SDK / ILSpy / dnSpy 也能复现。
> 复现命令见文末。

---

## 〇、方法索引（本文反复引用的方法）

`MD` = MethodDef RID，`rva` = 元数据里的方法体 RVA。`rva=0x00208c` 表示**空方法体存根**（虚方法默认实现 / 抽象）。

| 方法 | MD | rva | 签名 |
|---|---|---|---|
| `BattleManager::Update` | 505 | 0x020df0 | `void ()` |
| `BattleManager::shs`（`StartBattle` 状态机） | 506 | 0x020e6c | — |
| `BattleManager::shh`（`resetBattle` 状态机） | 507 | 0x020ec0 | — |
| `Battle::e3o`（**单 tick**） | 80 | 0x011380 | `void ()` |
| `Battle::e3w`（**单帧**） | 79 | 0x011300 | `void ()` |
| `Battle::e3i`（战斗初始化） | 78 | 0x010b18 | `void (BattleInput)` |
| `Battle::e32`（建寻路） | 81 | 0x0118ac | `void ()` |
| `Battle::e33` | 82 | 0x011984 | `void ()` |
| `Battle::rre` | 106 | 0x013524 | `void ()` |
| `Battle::rrr` | 107 | 0x0137b4 | `void ()` |
| `Battle::rrt`（刷一波） | 105 | 0x013440 | — |
| `Battle::rts`（生成场景单位） | 87 | 0x011e74 | — |
| `Battle::rtr` / `Battle::rta` | 85 / 86 | 0x011b6c / 0x011d3c | `void (string)` |
| `Battle::rrs`（漏怪扣血） | 109 | 0x002376 | `void (int, Unit)` |
| `Battle::rrh`（广播 TriggerEnum） | 110 | 0x01381c | `void (TriggerEnum)` |
| `Battle::reh`（**子弹工厂**） | 99 | 0x012bac | — |
| `Tile::rwo` | 220 | 0x00287d | `void ()` |
| `Bullet::rhs` / `rhh` / `rhr` | 168 / 169 / 166 | 0x00208c / 0x002563 / 0x002511 | — |
| `Unit::st2`（推力/位移） | 420 | 0x01ecfc | `void ()` |
| `Unit::a3s`（buff tick + 属性重算） | 403 | 0x01d1f4 | `void ()` |
| `Unit::a3h`（回血/死亡） | 404 | 0x01d474 | `void ()` |
| `Unit::str`（格位/占位） | 412 | 0x01ddac | `void ()` |
| `Unit::a3o`（移除） | 407 | 0x01d7bc | `void (bool)` |
| `Unit::a3a`（**属性终值重算**） | 402 | 0x01c4e4 | `void ()` |
| `Unit::a3r`（**基础属性初始化**） | 401 | 0x01c34c | `void ()` |
| `Unit::a3e` | 400 | 0x01c288 | `void ()` |
| `Unit::sei`（**绑定表现层**） | 427 | 0x01f078 | `void ()` |
| `Unit::se2`（**受伤结算主流程**） | 430 | 0x01f348 | `void (DamageInfo)` |
| `Unit::seo`（治疗结算） | 429 | 0x01f1b0 | `void (DamageInfo, bool)` |
| `Unit::se3`（**伤害公式**） | 431 | 0x01fa5c | `float (float, DamageTypeEnum, float, float, float, Unit)` |
| `Unit::sth` / `sti` / `stw`（**加 buff**） | 415 / 416 / 417 | 0x01e5b4 / 0x01e7d8 / 0x01e9fc | `Buff (int, Skill[, int])` |
| `Unit::ssh` | 459 | 0x020458 | `void ()` |
| `Unit::sea` | 424 | 0x01eebc | `void (float)` |
| `Unit::seh`（置 StateEnum） | 426 | 0x01ef2c | `void (StateEnum)` |
| `Unit::sta`（发 TriggerEnum） | 413 | 0x01e3ac | `void (TriggerEnum)` |
| `Skill::asa`（**命中结算**） | 271 | 0x01887c | `void (Unit, Bullet, float)` |
| `Skill::ast` | 268 | 0x0185f4 | `void (Unit)` |
| `Skill::ass` | 272 | 0x018f20 | — |
| `Skill::aaw` | 264 | 0x017e08 | `void ()` |
| `Skill::aiw`（**DamageInfo 工厂**） | 297 | 0x01b1c4 | `DamageInfo (Unit, float, float)` |
| `Skill::asw` | 275 | 0x0194d0 | `void (Unit)` |
| `Buff::rro`（生效） | 128 | 0x0139e8 | `void ()` |
| `Buff::rah`（tick） | 136 | 0x013f7c | `void ()` |
| `Buff::rse`（移除） | 143 | 0x002467 | `void ()` |
| `Buff::rae`（刷新） | 132 | 0x013da8 | `void ()` |
| `Buff::ra2` | 140 | 0x014268 | `bool (int)` |
| `Modify::ror`（**伤害修正派发**） | 229 | 0x015298 | `DamageInfo (DamageInfo, Unit)` |
| `Modify::roe` | 228 | 0x00208c | `void ()` |
| `ModifyManager::ro3`（**Modify 工厂**） | 238 | 0x015344 | `Modify (int, Skill)` |
| `Units.敌人::a3h` | 2014 | 0x03d41c | `void ()` |
| `Units.敌人::a33`（**移动**） | 2020 | 0x03db7c | `void ()` |
| `Units.敌人::etwh`（**到达终点判定**） | 2021 | 0x03dfe8 | `void ()` |
| `Units.敌人::etwt`（**阻挡搜索**） | 2015 | 0x03d5ec | `void ()` |
| `Battle::re3`（**圆内索敌**） | 104 | 0x013138 | — |
| `Units.敌人::etwo`（**A\* 重算 TempPath**） | 2025 | 0x03e064 | — |
| `Units.敌人::eti2`（进图开始移动） | 2009 | 0x03ce38 | `void ()` |
| `NormalModel::LateUpdate`（**视图拉取**） | 524 | 0x021a04 | `void ()` |
| `NormalModel::sit` | 523 | 0x0032c8 | `void (Unit)` |
| `SpineModel::LateUpdate` / `sit` | 567 / 566 | 0x003349 / 0x0222ec | — |
| `Effect::Update` | 193 | 0x014468 | `void ()` |
| `EffectManager::irw`（Effect 工厂） | 1007 | 0x029778 | `Effect (int)` |
| `ResHelper::hse`（Addressables 装载） | 726 | 0x025070 | — |
| `Database::s2t<T>(int)` / `s2e<T>(string)` | 609 / 610 | 0x023090 / 0x023100 | `T (int)` / `T (string)` |
| `Database::s2o(string)` | 617 | 0x023314 | `MapInfo (string)` |
| `Database::s2w<T>()` | 616 | 0x0232c8 | — |
| `GameData::e2o`（读存档） | 26 | 0x0106f8 | `void ()` |
| `JsonHelper::hr3<T>(string)` | 708 | 0x0037b5 | `T (string)` |
| `SaveHelper::hhe(string)` | 753 | 0x026200 | `string (string)` |
| `PathHelper::.cctor` | 719 | 0x024f58 | — |

---

## 一、主循环（✅ 实测，全部指令原文可复核）

### 1.1 `BattleManager::Update`（MD505，0x020df0）

```
if (Battle == null) return;
if (Pause) return;
if (Time.deltaTime <= 0) return;

Battle.e3w();                       // ① 每帧一次：表现/帧前准备
ExcuteTime += Time.deltaTime;       // ② 时间累加器
int target = Mathf.FloorToInt(ExcuteTime / SystemConfig.DeltaTime);   // ③ 目标 tick 数
int done = 0;
while (done < target - Battle.Tick) {   // ④ 追赶：一帧内补跑多个 tick
    Battle.e3o();                        //    单 tick
    done++;
}
```

**要点**：ArknightR 是「`Update` 里累加真实时间 + `FloorToInt` 追赶」的**变步长追帧**，tick 常量在 `SystemConfig.DeltaTime`。
`SystemConfig` 只有 1 个**实例字段** `float TurningTime`；`DeltaTime` 是**静态属性**（`SystemConfig::get_DeltaTime`，MD391，RVA 0x002dd4，`float ()`；`.cctor` MD393 在 0x002ddb，说明常量在静态构造里赋值）。

**常量的确切值（IL 原文）**：
```
SystemConfig::get_DeltaTime  (MD391, 0x002dd4):
  IL_0000: ldc.r4 0.01666666753590107     ← 即 float 0.016666668 = 1/60 秒
  IL_0005: ret
SystemConfig::.cctor         (MD393, 0x002ddb):
  IL_0000: ldc.r4 0.15000000596046448      ← TurningTime = 0.15 秒
  IL_0005: stsfld SystemConfig::TurningTime
```
> ★ **`0.016666668` 与官方 `Torappu.Battle.Consts.DELAY_SINGLE_FRAME`（dump.cs 行 294501）逐位相同** —— 这是本次唯一的"数值级"判据。

### 1.2 `Battle::e3w`（MD79）— 每帧

```
Battle.rrr();
CountDown.ris(Time.deltaTime);
foreach (Units.干员 u in Units.干员 list) u.ets3();   // 干员专属每帧
```

### 1.3 `Battle::e3o`（MD80）— 单 tick，**顺序由 IL 行号直接读出**

按 IL 出现顺序（`d_e3o.txt` 行 5→490）：

| 序 | 调用 | 行号 | 作用 |
|---|---|---|---|
| 1 | `Battle::rrr` | 5 | tick 前重置（`CostCountSpeed` 等逐 tick 归位） |
| 2 | `Tick += 1` | — | 帧计数 |
| 3 | `Battle::e33` | 17 | 关卡/经济/技力段 |
| 4 | `Battle::rre` | 19 | 第二段更新 |
| 5 | 循环 `Waves[0]`：`Tick*DeltaTime > OneWave.Time` → `Battle::rtt(oneWave)` | 56 | **出怪** |
| 6 | 循环 `CheckPointWaves`：同判据 → `Battle::rtt(oneWave)` | 115 | 检查点出怪 |
| 7 | 循环 `CheckPointSceneUnits` → `Battle::rts(id,pos,dir,lifeTime,key)` | 172 | 场景单位生成 |
| 8 | 循环全部 `Tile[,]` → `Tile::rwo()` | 211 | **地图格** |
| 9 | `Bullets.ToArray()` 循环 → `Bullet::rhs()`、`Bullet::rhh()` | 237/238 | **子弹** |
| 10 | `Units.ToArray()` 循环：`Unit::st2` → `Unit::a3s` → `Unit::a3h` → `Unit::str` | 258/278/298/320 | **单位** |
| 11 | 单位死亡检查 `CountDown::rii()` → `List<Unit>::Remove` → `Unit::a3o(bool)` | 346/360 | 清理 |
| 12 | 其余 CountDown 批量推进 `CountDown::rir/ris` | 466/477/490 | 计时器 |

> **★ 与官方对比**：官方 `BattleController.OnTick`（RVA 0x354F880）的帧阶段骨架见 39 号文档 §6（此前标 🟡 强推断）。ArknightR 的 **Tile → Bullet → Unit** 分组是社区设计，**不得**当作官方顺序使用。

### 1.4 每单位 tick 内部

**`Unit::st2`（MD420）— 推力/位移**
```
CountDown::rih();
CountDown::rir(DeltaTime);
foreach (Buff b in Buffs.Reverse()) if (b is IPushBuff) b.rah();      // 反向遍历
if (!Unbalance) { ... }
Vector2 push = Vector2.zero;
foreach (IPushBuff p in ...ToList()) push += p.rhe();                 // 累加推力向量
Position += new Vector3(push.x, 0, push.y) * ...;                     // ← 位移落地
Unit::stt(); Unit::st3();
```

**`Unit::a3s`（MD403）— buff tick + 属性重算**
```
if (!ses()) ...
sss(); ssr(); ssa();
foreach (Buff b in Buffs.Reverse()) b.rah();     // ← 每 buff 的 tick 钩子
Unit::a3a();                                     // ← 属性终值整体重算
CountDown::rii(); Unit::seh(StateEnum); Buff::rao();
```
> **★ 关键设计**：ArknightR **每 tick 从零重算全部属性**（`a3a` 先把所有 `*Rate/*Add/*Fin/*Ex` 归零再重算）——**没有脏标记/增量更新**。官方则用 `Attributes` + `Modifier` 结构（33 号 §2.1 `Entity.m_attributes` 0x98）。

**`Unit::a3h`（MD404）— 回血与死亡**
```
if (ses() && !IfRevive) {
    Hp += HpRecover * DeltaTime;
    Hp += HpRecoverP * MaxHp * DeltaTime * MathF.Max(1 + HpRecoverRate, 0) * LastHpRecoverRate;
    if (Hp > MaxHp) Hp = MaxHp;
    if (IfUndead) Hp = MathF.Max(Hp, 1);
}
if (Hp <= 0) { TriggerData{Target=this}→push; sta(9); pop; if (Hp<=0) { Hp=0; a3w(null); return; } }
```

### 1.5 `Unit::a3r` / `Unit::a3a` — 属性系统（✅ 逐条指令可读）

**`Unit::a3r`（基础值来自表）**
```
SpeedBase   = UnitData.Speed;
HpBase      = (float)(UnitData.Hp + UnitData.HpEx);
AttackBase  = (float)(UnitData.Attack + UnitData.AttackEx);
DefenceBase = (float)(UnitData.Defence + UnitData.DefenceEx);
... MagicDefenceBase = UnitData.MagicDefence + MagicDefenceEx
```

**`Unit::a3a`（终值公式，a3a 共 1,278 行 IL）**
*先把以下全部字段归零*（逐条 `stfld 0.0`）：
`SpeedAdd/SpeedRate/SpeedRateFin/SpeedAddFin/PassiveSpeedRateEx/SkillSpeedRateEx`、
`HpAdd/HpRate/HpRateFin/HpAddFin/PassiveHpRateEx/SkillHpRateEx`、
`AttackAdd/AttackRate/AttackAddFin/AttackRateFin`、
`DefenceAdd/DefenceRate/DefenceAddFin/DefenceRateFin`、
`MagicDefenceAdd/...`、`AttackGapAdd/AttackGapRate`、`AttackRangeAdd/AttackRangeRate`、
`DamageReceiveAdd/Rate`、`Normal/Magic/RealDamageReceive*`、`HealReceiveRate*`、
`ElementDamageReceiveRate/ElementResistRate/PoisonDamageReceiveRate`、
`StopCountAdd/StopCountRate`、`DefenceIgnore(/-Rate)`、`MagicDefenceIgnore(/-Rate)`、`HeightAdd/HeightEx` 等

*然后算终值*（`d_a3a.txt` 行 737 起，原文）：

```
Speed  = max(0, SpeedBase * CCSpeedRate + SpeedAdd)
       * (1+SpeedRate) * (1+SpeedRateFin) * (1+SkillSpeedRateEx) * (1+PassiveSpeedRateEx)
       * LastSpeedRate;
clamp 到 [SpeedBase/…, …]（后续两条 clamp 分支）

MaxHp  = max(1, HpBase + ModuleHp)
       * CCHpRate + HpAdd
       * (1+HpRate) * (1+HpRateFin) * (1+SkillHpRateEx) * (1+PassiveHpRateEx) * LastHpRate;
```
Attack / Defence / MagicDefence 同构。
> **判据**：这与舟游公开的属性公式 `最终 = (基础 + 加法) × (1 + 百分比) × (1 + 最终百分比)` **逐项对应**；`*Ex`（`Skill*RateEx`/`Passive*RateEx`）与 `CC*Rate`（控制/减益乘区）是 ArknightR 自己拆的乘区。✅

---

## 二、例 1 —— 一个单位在空地图上移动（数据 → 逻辑 → 表现）

### 2.1 数据层
- `StreamingAssets/map/<关卡名>.map`（42 个）→ `Database::s2o(string)`（MD617）读出 → `Battle.MapData : MapInfo`
- `MapInfo.PathInfos : List<PathInfo>`；`PathInfo { Name, Path : List<PathPoint> }`；`PathPoint { Pos : Vector2Int, Delay : float, DirectMove : bool, HideMove : bool }`（字段实测）
- `WaveInfo` 引用 `sUnitId`（`Database::s2e<UnitData>(sUnitId)`，见 `Battle::rtr` IL_007F）

### 2.2 逻辑层 —— 建路（`Battle::e32`，MD81，0x0118ac）

```
AstarPath.active.Scan();                                  // ★ A* Pathfinding Project 重建格图
foreach (PathInfo pi in MapData.PathInfos) {
    OriginPathInfo[pi.Name] = new Dictionary<int, List<Vector3>>();
    for (int i = 0; i < pi.Path.Count - 1; i++) {
        List<Vector3> seg = Map.rww(pi.Path[i].Pos, pi.Path[i+1].Pos, 0);  // 两点间世界坐标折线
        OriginPathInfo[pi.Name].Add(i, seg);
    }
}
```
> 即：**策划表里的格子路点 → 用 A* 插值成世界坐标折线**。`Battle::e32` 由 `Battle::e3i`（IL_01DC）在战斗初始化时调用一次。

### 2.3 逻辑层 —— 每 tick 移动（`Units.敌人::a33`，MD2020，0x03db7c）

关键片段（`d_a33.txt` IL_02A4 起 + IL_0402 起，原文）：

```
// (1) 到达判定
if (Units.敌人::etww(get_TempTarget(), Unit.Position) < TempArriveDistance) {
    Unit.Position = get_TempTarget();          // 吸附到路点
    TempIndex++;
    if (TempIndex >= TempPath.Count - 1) {
        NowPathPoint++;
        if (NowPathPoint >= PathPoints.Count - 1) {
            // 走到终点 = 漏怪
            if (!DealBattleDamage) Battle.rrs(UnitData.Damage, this);
            Unit.a3o(false);                   // 移除
            return;
        }
        PathWaiting.ris(PathPoints[NowPathPoint].Delay);   // 路点停顿
        StopAttack = false;
        if (PathPoints[NowPathPoint].HideMove) { ... Visiable=0; TempPath=null; etwo(); return; }
        Units.敌人::etwo();                    // 重新算 TempPath（A*）
    }
} else {
    // (2) 移动：朝目标点直线推进
    Vector3 dir = (get_TempTarget() - Unit.Position).normalized;
    Unit.Position += dir * (Unit.Speed * SystemConfig.DeltaTime);   // ★ IL_0423/IL_0433 原文
}
```
方向与朝向（IL_01E3 起）：
```
Vector3 delta = get_TempTarget() - Unit.Position;
TargetScaleZ = MathF.Round(delta.z);
Unit.Direction = new Vector2(delta.x, delta.z);
TargetScaleX = MathF.Sign(MathF.Round(delta.x));   // ±1 决定左右翻转
```

每 tick 的入场距离（`Units.敌人::a3h` IL_0099）：
```
TempArriveDistance = Unit.Speed * SystemConfig.DeltaTime;
```

阻挡搜索（`Units.敌人::etwt`，MD2015）：
```
Battle.re3(Position2, UnitData.Radius + 0.3571f, 1, 1)   // 找圆内单位
  .Where(etoa).OrderBy(Index).ThenBy(etos).ToList();
if (list.Count > 0) { list[0].sr3(this); TriggerData{User=list[0],Target=this}→push; sta(23); pop; }
```
> `0.3571f` 是硬编码常量（≈ 官方阻挡偏移 0.7071 的一半附近，**不等于**官方 `Consts.BLOCK_RADIUS`）。**🔴 待查**：该常量与官方 `stableBlockPosition` 的对应关系。

### 2.4 表现层（拉取式，✅ 实测）

`Unit::sei`（MD427）——**绑定**：
```
if (string.IsNullOrEmpty(UnitData.Model)) return;
GameObject go = ResHelper.hse(PathHelper.UnitPath + UnitData.Model);  // "Assets/Bundles/Units/" + model
UnitModel = go.GetComponent<UnitModeI>();                             // ★ 取组件
UnitModel.sit(this);                                                  // ★ 把逻辑 Unit 注入视图
```
`PathHelper::.cctor` 常量（IL 原文）：`DataPath="Assets/Bundles/Data/"`、`UIPath`、`SpritePath`、`OtherPath`、**`UnitPath="Assets/Bundles/Units/"`**、`BulletPath`、`EffectPath`、`AudioPath`、`DungeonGridPath`。

`NormalModel::LateUpdate`（MD524）——**每帧拉取**：
```
if (Unit == null) return;
transform.position = Unit.Position + new Vector3(0, Unit.Height + Unit.HeightEx, 0);
transform.localEulerAngles = new Vector3(0, 0,
        Vector2.SignedAngle(Vector2.right, Unit.Direction));   // Direction(Vector2) → 绕 Z 旋转角
animator.Play(Unit.AnimationName[0]);
```
> ⇒ **逻辑 Unit 是唯一真值源；视图只在 `LateUpdate` 单向读取**。`Unit` 全程不写 transform。

---

## 三、例 2 —— 一次普攻命中与伤害结算（数据 → 逻辑 → 表现）

### 3.1 数据层
`SkillData`（155 字段）关键参与项：`DamageRate`、`DamageType`、`DamageBase`、`DamageWithFrameRate`、`Cooldown`、`IfHeal`、`AreaRange`、`AreaDamage`、`AreaMainDamage`、`AreaPoints`、`HitEffect`、`TargetTeam`。
`UnitData` 侧：`Attack/AttackEx`、`Defence/DefenceEx`、`MagicDefence/MagicDefenceEx`、`Radius`、`Damage`（漏怪扣血）。

### 3.2 逻辑层 —— 构造伤害包（`Skill::aiw`，MD297，0x01b1c4）

```
FP/float cd = SkillData.Cooldown; if (cd < DeltaTime) cd = DeltaTime;
DamageInfo d = new DamageInfo {
    Target      = target,
    AllCount    = aesr.Count,
    Source      = this,                                     // ★ Source 是 object，实际放 Skill
    DamageRate  = damageBase * SkillData.DamageRate * damageScale
                  * (SkillData.DamageWithFrameRate ? cd : 1f),
    DamageType  = SkillData.DamageType,
    IsHeal      = SkillData.IfHeal,
};
switch (SkillData.DamageBase) {          // 12 个分支，IL_0098: switch [211,233,...,529]
  case 0: d.Attack = Skill.Unit.Attack;  break;   // 攻击力
  case 1: d.Attack = target.MaxHp;       break;   // 目标最大生命
  case 2: d.Attack = d.DamageRate; d.DamageRate = 1f; break;  // 纯倍率
  case 3: d.Attack = target.Attack;      break;   // 目标攻击力
  case 4: d.Attack = Skill.Unit.MaxHp;   break;
  ...（共 12 个 case，落在 IL_00D3..IL_0240）
}
```
> **★ 设计要点**：伤害基数来源用 `SkillData.DamageBase` 的 **switch 枚举**（而非类），与 `Type` 列反射那套是**并存的两种分发**。

### 3.3 逻辑层 —— 命中分发（`Skill::asa`，MD271，0x01887c）

```
if (SkillData.HitEffect.HasValue) {
    Effect hitFx = EffectManager.Instance.irw(SkillData.HitEffect.Value);   // ① 命中特效（表现）
    hitFx.rwr(Skill.Unit, target?.sr2() ?? bullet.TargetPos, bullet.Direction, 1f);
}
Skill::asw(target);
if (SkillData.DamageRate <= 0) return;
Skill::aie(target); if (!Skill::asr(target)) return;       // 目标合法性
if (SkillData.AreaRange != 0) {                            // ② 溅射分支
    hugeEnemys.Clear();
    ... Battle.re3 / 范围索敌（AreaRange + Unit.AreaRangeExRate）
    DamageInfo d2 = aiw(AreaMainDamage|AreaDamage, rate);  // 主目标用 AreaMainDamage，其余用 AreaDamage
    if (isHeal) target.seo(d2, ...);  else { target.se2(d2); if (d2.Avoid) { aia(target); aih(d2); air(target); } }
}
... SkillData.AreaPoints != null → 逐格（AreaPoints.Select(...)）再走一遍
```
（`d_asa.txt` 里 `Unit::seo` 出现于 IL_0285/0473/05AC，`Unit::se2` 出现于 IL_02BB/04A9/05CD，`DamageInfo::Avoid` 紧随其后。）

### 3.4 逻辑层 —— 受伤主流程（`Unit::se2`，MD430，0x01f348；642 行 IL）

按 IL 行号（`d_se2.txt`）：

| IL | 动作 |
|---|---|
| 0x002D / 0x006C / 0x00AC / 0x00EC | `Battle.Random.NextDouble()` ×4 —— 闪避 / 暴击等概率判定 |
| 0x0126 | `UnitModeI::sot()` —— **受击表现**（闪白） |
| 0x0136–0x018A | `TriggerData{User,Target,Skill}` push → `Unit::sta(TriggerEnum)` → pop（**受击事件**） |
| 0x029E / 0x038D | **`Unit::se3(...)` —— 伤害公式**（两条支路） |
| 0x03D9 | `List<IShield>::ToArray()` → **`IShield::rht(d)`** —— 护盾吸收 |
| 0x054A | `UnitModeI::swo(RewriteDamage)` —— 截断伤害时的血条 |
| 0x055D | `Hp -= RewriteDamage`（`Unit.RewriteDamage>0 && d.FinalDamage>RewriteDamage` 分支） |
| 0x058A | `UnitModeI::sww(d)` —— **伤害数字飘字** |
| 0x059D | `Hp -= d.FinalDamage`（常规分支；条件含 `d.ShowCrit`） |
| 0x05A8 | `List<ISelfAfterFinalAbsorb>` → **`rso(d)`** |
| 0x0641 / 0x0683 | `TriggerData` push → `Battle::rrh(TriggerEnum)` → pop（**死亡/后置事件**） |
| 0x06DC / 0x06E3 | `Hp` 钳位、`Unit::a3w(...)` |

补充：`List<Modify>` → `IAfterDamageModify::roi(d)`；`List<ISelfAfterDamage>` → `rsw(d)`；`List<ISelfAfterWithoutDamage>` → `rs2(d)`（均由 `calls.py Unit::se2` 直接列出）。

**伤害公式 `Unit::se3`（MD431，0x01fa5c，签名 `float this(float atk, DamageTypeEnum type, float a, float b, float scale, Unit source)`）**，IL 原文：
```
// type==0 物理
def = Max(0, this.Defence * (1 - b - source.DefenceIgnoreRate) - a - source.DefenceIgnore);
atk = Max(atk * scale, atk - def);
if (atk < 0) atk = 0;
// type==1 法术
mdef = Max(0, this.MagicDefence * (1 - b - source.MagicDefenceIgnoreRate) - a - source.MagicDefenceIgnore);
atk  = Max(atk * scale, atk * (100 - mdef) / 100);
if (atk < 0) atk = 0;
// type==2 真实伤害：def = Max(0, Defence*(1-b) - a); 不参与百分比减伤
```
（`d_se3.txt` IL_0013–IL_00BC 为物理/法术两支原文。）

### 3.5 伤害修正钩子（`Modify::ror`，MD229，0x015298）

```
foreach (Buff b in this.Unit.Buffs)   if (b is ISelfDamageModify) b.roa(d);   // 攻方自身
foreach (Buff b in target.Buffs)      if (b is IDamageModify)     b.ros(d);   // 受方
return d;
```
`Modify` 的 6 个接口（全部 `abstract`，RVA 0）：
`ISelfDamageModify::roa(DamageInfo)`、`IDamageModify::ros(DamageInfo)`、`ITargetModify::roh(int):int`、
`IAfterDamageModify::roi(DamageInfo)`、`IAfterAttackModify::roo()`、`IElementModify::ro2()`。

### 3.6 表现层
- 命中特效：`EffectManager::irw(effectId)` → `EffectData.Prefab` → `Effect`（`Effect::Update` 里 `transform.set_position/set_localScale`）
- 伤害数字：`UnitModeI::sww(DamageInfo)` → 实现类里对应 `BattleUI.UI_DamageInfo`（字段 `m_type/m_number/m_show`）
- 血条：`UnitModeI::swo(float hpRate)` / `UnitModeI::sw2(DamageInfo)`

---

## 四、例 3 —— 一个带 buff 的效果生效（数据 → 逻辑 → 表现）

### 4.1 数据层
`battle.xlsx` 的 `BuffData` sheet → `StreamingAssets/data/BuffData.txt`（542,043 B，JSONL）→ 运行期 `Database` 字典。
`BuffData` 实测 29 字段，关键：**`Type`（= C# 类名）**、`RelyBuff`（前置依赖）、以及数值/标签/时长类字段。

### 4.2 逻辑层 —— 加 buff（`Unit::sth`，MD415，0x01e5b4）

```
if (IgnoreBuffs.Contains(buffId)) return null;                       // 免疫
BuffData config = Database.Instance.s2t<BuffData>(buffId);           // ① 表查行
if (config.RelyBuff.HasValue && !Buffs.Any(b => b.Id == config.RelyBuff)) return null;  // ② 前置依赖
Buff exist = Buffs.FirstOrDefault(b => ...);
if (exist != null) { exist.Skill = source; exist.Index = index; exist.rae(); return exist; }  // ③ 叠加/刷新
Buff b = (Buff) typeof(Buff).Assembly.CreateInstance("Buffs." + config.Type);   // ★④ 反射实例化
b.Index = index; b.Id = buffId; b.Skill = source; b.Unit = this;
Buffs.Add(b);
if (b is IShield)      { Shields.Add((IShield)b);         sai(); }   // ⑤ 按接口分流到各子表
if (b is IElementShield){ ElementShields.Add(...);        sst(); }
if (b is IShieldCount) { ShieldCounts.Add(...); }
if (b is IHeal)        { Heals.Add(...); }
Buff.rro();                                                          // ⑥ 生效钩子
```
> 同一范式在**每个**领域重复出现，实测调用点（`--who Assembly::CreateInstance`，共 56 处）：
> `Battle::rts/rth/rti/rtw/rto/rt2/rt3/ret/ree/rer/rea/res` + `ldstr "Units."` → 单位；
> `Battle::reh/rei/rew` + `ldstr "Bullets."` → 子弹；
> `Buff::ra2`、`Unit::sth/sti/stw/ssh`、`Skill::asi` + `ldstr "Buffs."` → Buff；
> `ModifyManager::ro3` + `ldstr "Modifys."` → 属性修正；
> `Unit::sts` 及 33 处 `ldstr "Skills."` → 技能。

### 4.3 逻辑层 —— 属性生效（`Unit::a3a` 每 tick 全量重算）
见 §1.5。**buff 只要写 `Unit.*Rate/*Add/*Fin/*Ex`，下一个 tick 的 `a3a` 就会把它算进终值**——不需要 buff 自己触发任何"重算"。

### 4.4 逻辑层 —— buff 生命周期钩子

| 钩子 | 触发点（实测） |
|---|---|
| `Buff::rro()` 生效 | `Unit::sth/sti/stw`、473 处调用点（含 buff 触发 buff） |
| `Buff::rah()` tick | `Unit::a3s`、`Unit::st2`（均为 `Buffs.Reverse()` 反向遍历） |
| `Buff::rae()` 刷新 | `Unit::sth/sti/stw` 命中已有同 Id buff 时 |
| `Buff::rse()` 移除 | `Buff::rae`、`Buff::rah`、`Skill::asw`、`Unit::a3o`（367 处） |
| `Buff::rao()` | `Unit::a3s` 尾部 |
| 受击类 | `IShield/IAfterDamageModify → rht/roi(DamageInfo)`，由 `Unit::se2` 调 |

### 4.5 表现层
- **buff 图标/层数没有独立的 `UI_Buff` 类**（实测 `BattleUI.*` 共 21 个类型，无 Buff）：buff 相关表现挂在 `BattleUI.UI_BattleUnit`（22 字段）、`UI_Head`、`UI_BattleLeft`、`UI_ShowAttribute` 上。
- 元素损伤条：`BattleUI.UI_ElementBar` / `UI_EnemyElementBar`（TD383/385）。
- 3D/2D 表现：`Unit::ssh` 里另有 `ldstr "Buffs."` 的反射点，说明**buff 也能自带表现对象**（与 `Buffs.*` 614 个类同族）。
- ⚠️ **修正 40 号文档 §1.1 的一处说法**：此前把 `ElementBar` 列为 ArknightR 的类名，实测**不存在** `ElementBar` 类；元素损伤的实现是 `IElementShield` / `IElementModify` 接口 + `Unit.ElementBuffs/ElementShields/ElementShowBuff` 字段 + `Buffs.元素损伤` / `Buffs.新版元素损伤` / `Buffs.元素损伤易伤` / `Buffs.元素损伤治愈` 四个 buff 类，`BattleUI.UI_ElementBar` 只是 UI 条。

---

## 五、数据加载链（✅ 实测，`Database::Init` 状态机 `<Init>d__5::MoveNext`）

**加载顺序（IL 原文 `ldstr` + `call Database::s2w<T>`）**：
```
CardData → UnitData → SkillData → BuffData → BulletData → ModifyData → EffectData
→ RelicData → ContractData → EventData → RewardData → DungeonLevelData → SystemData
```
（另有 `ldstr '导表结束'` —— 导表工具的输出文案。）

**单表加载 `Database::AddAsync<T>`（编译进 `<AddAsync>d__14\`1::MoveNext`，MD631）**：
```
string text = SaveHelper.hhe("/Data/" + name + ".txt");            // ① 先读散装文件
if (string.IsNullOrEmpty(text)) {
    Debug.Log(name + "load from address");
    var op = Addressables.LoadAssetAsync<TextAsset>(PathHelper.DataPath + name);  // ② Addressables 兜底
    text = op.Result.text;
    Addressables.ReleaseInstance(op);
}
if (string.IsNullOrEmpty(text)) return;
string[] lines = text.Split('\n');                                 // ③ 逐行 JSONL
IConfig[] arr = new IConfig[lines.Length];
for (int i = 0; i < lines.Length; i++) {
    try   { arr[i] = JsonHelper.hr3<T>(lines[i]); }                // ④ 一行一个对象
    catch (Exception e) { Debug.LogError(name + "\n " + lines[i]); }  // ⑤ 单行坏掉不毁全表
}
this.aewr.Add(typeof(T), arr);                                     // ⑥ Dictionary<Type, IConfig[]>
```
> `Database::aewr` 就是运行期唯一的表容器；`s2t<T>(int id)`/`s2e<T>(string id)` 从它查行。
> `battle.xlsx` **只在编辑器期**由 `ExcelHelper` 读（`ExcelHelper::he3/hrt/hre/hra`，`ExcelDataReader`），运行期不碰 xlsx。

**地图/存档（另一条支线）**：
- `Database::s2o(string) : MapInfo`（MD617）—— 地图；`Battle::e3i` IL_0063 与 `<StartBattle>d__9::MoveNext` IL_00A0 各调一次
- `GameData::e2o`（MD26）—— `SaveHelper.hhe("/data.sav")` + `JsonHelper.hr3<GameData>`（`data.sav` 是明文 JSON）
- `.map` 走 `SaveHelper.hhe("/Map/" + name + ".map")`（IL 原文 `ldstr '/Map/'` + `ldstr '.map'`）

---

## 六、战斗启动链（`BattleManager::shs` → `<StartBattle>d__9::MoveNext`，IL 顺序）

```
UIManager.ira<MainUI.UI_Loading>()                     // 加载界面
SaveHelper.hht()
Database.Instance.s2o(...)                             // 读地图 MapInfo
Addressables.LoadSceneAsync(...)  → await             // 载入战斗场景
MapManager::hot(Tile[,])                               // ★ 把格阵交给地图表现层
TimeHelper.Instance.hii() → await
Camera.main.transform.position = ...
Camera.main.GetComponent<BattleCamera>()
SceneManager.LoadSceneAsync(...) → SetActiveScene(...)
AudioManager.e2r(...)
Battle::e3i(BattleInput)                               // 逻辑初始化
```

`Battle::e3i`（MD78）内部（IL 顺序）：`Database.s2o(map)` → 每单位 `Unit::a3e()` + `Unit::sts(skill)`（建技能）→ 遍历 `ContractData`（合约）→ `Map::rwh()` → **`Battle::e32()`**（建寻路）→ 遍历 `MapInfo.Units` 用 `Tile[,].Get(...)` 取实体坐标 → 塞 `MapUnitInfo`。

**场景加载（`<StartBattle>d__9::MoveNext` IL 原文）**：
```
MapInfo mi   = Database.Instance.s2o(battleConfig.MapName);   // IL_00A0
sceneName    = mi.Scene;                                      // IL_00B6  ← MapInfo.Scene（16 字段之一）
if (string.IsNullOrEmpty(sceneName)) {
    sceneName = "Assets/Scenes/MapBuilder.unity";              // IL_00CB 空值兜底
    Addressables.LoadSceneAsync(sceneName, SceneManager.LoadSceneMode.Additive /*=1*/);
} else {
    Addressables.LoadSceneAsync(sceneName, Scenes.LoadSceneMode.Additive);
}
SceneManager.GetSceneByName(sceneName); SceneManager.SetActiveScene(...);   // IL_0264/IL_0269
AudioManager.Instance.e2r("battle");                                        // IL_0279（音频 bank 名，不是场景名）
```
**★ 实测数据判据**：对 `StreamingAssets/map/*.map` 全 42 个文件按 `"Scene"\s*:\s*"([^"]*)"` 检索，**0 命中** ⇒ 运行期 `MapInfo.Scene` 恒为空 ⇒ **所有关卡都回落加载同一个 `Assets/Scenes/MapBuilder.unity`**，关卡几何完全由 `.map` 里的 `GridInfos : GridInfo[,]` 数据 + `MapManager::hot(Tile[,])` 程序化搭建。
（`globalgamemanagers` 里全工程只有 5 个场景：`SampleScene`、`Default`、`Maps/TestMap`、`Maps/H6-4`、`Maps/Rune_01-03`，**均无 `.map` 引用它们**。）

`MapManager`（MonoBehaviour）字段：`Instance`、**`Grids : MapGrid[,]`**（视觉格阵）、`ae3s/ae3h/...`；暴露 `Awake/Start/Update`，`hot(Tile[,])` 接逻辑格阵并按 `,` 分割的 tile 名列表做 parent 绑定。

---

## 七、复现命令

```powershell
$env:PYTHONIOENCODING='utf-8'
cd C:\Users\23922\Documents\ds_harness\ak\code\tools
$dll = 'D:\__soft\ak\ArknightR\ArknightR_Data\Managed\Assembly-CSharp.dll'

python mono_il.py $dll --stats                      # 元数据表规模 + 命名空间分布
python mono_il.py $dll --types --grep Element        # 找类型
python mono_il.py $dll --methods "Unit::"           # 列某类方法（含签名/RVA）
python mono_il.py $dll --fields "DamageInfo"        # 列字段类型
python mono_il.py $dll --dis "Unit::se3"            # 反汇编单个方法（含 IL 偏移）
python mono_il.py $dll --who "Unit::se2"            # 谁调用了它（全库调用图）
python mono_il.py $dll --refs "DamageInfo::" --limit 300   # 谁碰过某 token（字段/方法/类型通用）
python calls.py   "Battle::e3o"                      # 列出某方法调用了什么（含未展开的外部调用）
python andrefs.py "NowPathPoint" "Unit::Position"    # 交集检索：同时引用两个 token 的方法
```
写出 `mono_il.py` 时踩到并已修正的 4 个 ECMA-335 坑（**复现时必须注意**）：
1. `MethodDef` 签名里 `ParamCount` 是**压缩整数**，不是 4 字节；
2. 签名内 `TypeDefOrRef` 编码是**压缩整数**（`0b10xxxxxx` 双字节形式），不是定长 coded index；
3. `ShortInlineVar`（`ldarg.s`/`ldloc.s`/`stloc.s` 等 0x0E–0x13）操作数是 **1 字节**，`InlineVar`（0xFE09–0xFE0E）才是 2 字节；
4. **`CustomAttribute` 表行宽 = Parent(coded) + Type(coded CustomAttributeType) + Value(blob)**，漏掉中间的 Type 会让该表之后**所有**表的偏移错位（`TypeSpec` 会解析出垃圾）——`read_mono.py` 里有一模一样的漏项，但它只读 `TypeDef/MethodDef`（都在 `CustomAttribute` 之前）所以没暴露。

## 相关文件
- `63_ArknightR架构与三例贯通.md`（主文档）
- `63b_官方对应检索报告.md`（官方 IL2CPP 侧对应）
- `40_外部工具解析_ArknightR与AFA.md`（前序记录，本文件修正其 §1.1 的 `ElementBar` 说法）
- `ak\\code\\tools\\mono_il.py`、`ak\\code\\tools\\calls.py`、`ak\\code\\tools\\andrefs.py`（本次自研工具）
