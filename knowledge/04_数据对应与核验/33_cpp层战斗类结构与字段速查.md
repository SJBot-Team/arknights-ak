# 33 cpp 层战斗类结构与字段速查
> 主题：**04B 读代码 / 反汇编**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）

> 层级：**T1（IL2CPP dump 一手）**　建立日期：2026-09-13　任务：T-034 ①/④
> 来源：`E:\__file\ak_kb\client_res\il2cpp\dump\dump.cs`（日服，203 万行）
> 用法：本文是**索引**。要某个类的完整定义（含全部方法与 RVA）：
> `read_cpp.py cls <类名>`；要反汇编某方法：`read_cpp.py m <类名>.<方法名>`。

---

## 〇、两条必须先记住的坐标系规则

1. **`// 0x…` 偏移有两种坐标系**
   - 带 `static` 的字段：属于**静态字段区**，从 0x0 独立编号，**与实例偏移不是同一坐标系**（数值会撞车）。
   - 不带 `static` 的：才是真正的**实例偏移**。
   例：`BattleController.s_randomImp // 0x30` 是静态区偏移；`<playerSide> // 0x18` 是实例偏移。

2. **实例布局链**（可直接用于内存扫描/结构对齐）：

```
BObject  ──►  Entity（实例段至 0x180）  ──►  Unit（0x180–0x288）
                                              ├─► Character（0x290 起）
                                              └─► Enemy    （0x290 起）
```

   宿主类起点不同：`MonoBehaviour` 派生的实例字段**从 0x18 起**（如 `Scheduler.m_blockCounter // 0x18`）；`SingletonMonoBehaviour` 派生的从 **0x20** 起（`BattleController`）。

3. **两个反内存修改包装**（按尺寸算对齐时必用）：
   - `ObscuredInt` 占 **0x14** 字节
   - `ObscuredFP` 占 **0x28** 字节
   玩家的 `cost` / `lifePoint` / `characterLimit`、`Scheduler` 的各类计数器、`BattleController.m_randomSeed` 全是这类包装。

> 命名空间规律：`Torappu.Battle` = 战斗运行期（BattleController/Entity/Unit/Character/Enemy/Ability/Buff/Scheduler/Route/Map/BObject）；`Torappu` = 配置数据与坐标基元（LevelData/RouteData/TileData/MapData/GridPosition）。`LevelData.*` / `RouteData.*` 在 dump 中 `// Namespace:` 为空，因为它们是嵌套类。

---

## 一、`BattleController`（TypeDefIndex 8588，行 320906 起）

**定位**：单局战斗的唯一总控与状态机宿主，持有确定性时钟、全局随机源、关卡与地图数据、玩家经济、单位管理器与对象池。

### 1.1 静态区（★ 时间/帧/随机全在这里）

| 字段 | 类型 | 静态偏移 |
|---|---|---|
| `<isDeterministic>` | static bool | 0x10 |
| **`s_fixedFrameCnt`** | static uint | 0x14 |
| **`s_fixedPlayTime`** / `s_fixedPlayTimeIgnored` | static FP | 0x18 / 0x20 |
| `s_fixedPlayTimeFloat` | static float | 0x28 |
| **`s_randomImp`** / `s_randomTrivial` | static Random | 0x30 / 0x38 |
| `s_battleUidCounter` | static uint | 0x40 |
| **`s_deltaPlayTimeFP`** | static FP | 0x48 |
| `s_buildCountInOneFrame` | static int | 0x50 |
| `RANDOM_ALGORITHM` | const AlgorithmType | = 0（DEFAULT） |
| `INITIAL_OBJECT_CAPACITY` / `INITIAL_BUFF_PRELOAD_CNT` | const int | 1024 / 100 |

### 1.2 实例区（逻辑相关节选）

| 字段 | 类型 | 偏移 |
|---|---|---|
| `_map` / `_scheduler` / `_factory` | Map / Scheduler / BattleFactory | 0x28 / 0x30 / 0x38 |
| `m_modules` | `List<IBattleModule>` | 0x58 |
| `m_globalBuffs` / `m_buffPool` | `List<GlobalBuff>` / `ObjectPool<Buff>` | 0x68 / 0x90 |
| `m_originCostIncreaseTime` | float | 0xB8 |
| `m_costDict` / `m_lifePointDict` / `m_characterLimitDict` | `ListDict<PlayerSide, ObscuredInt>` | 0xC0 / 0xD0 / 0xD8 |
| `m_costTimerDict` | `ListDict<PlayerSide, PrecisePeriodicTimer>` | 0xC8 |
| `m_replayController` | BattleController.ReplayController | 0x108 |
| `m_playerOpQueue` | BattleController.PlayerOperationQueue | 0x130 |
| `m_fixedEventHandler` | `FixedEventHandler<IPtrObject>` | 0x140 |
| `m_coroutineSimulator` | CoroutineSimulator | 0x150 |
| `m_hashCodeBuilder` / `m_snapshotBuilder` / `m_playerOperationBuilder` | HashCodeBuilder / StringBuilder×2 | 0x158 / 0x160 / 0x168 |
| **`m_levelData`** / **`m_mapData`** | LevelData / MapData | 0x178 / 0x180 |
| **`m_randomSeed`** | ObscuredInt | 0x198 |
| `m_antiCheatChecker` | ClientAntiCheatChecker | 0x1B0 |
| `m_physicManager` / `m_levelScriptManager` | TPhysicManager / LevelScriptManager | 0x1E8 / 0x1F0 |
| `m_state` / `m_result` | State / GameResult | 0x22C / 0x230 |
| `m_speedLevel` | SpeedLevel | 0x234 |
| `m_lifePoint` / `m_maxLeftPoint` / `m_tempLifePoint` | ObscuredInt | 0x25C / 0x248 / 0x270 |
| `m_originTimeScale` | float | 0x290 |
| `m_realPlayTime` | float | 0x294 |
| **`m_timeDeltaNoEnemy`** | FP | 0x298 |
| `unitManager` | UnitManager | 0x2C0 |

### 1.3 关键方法（RVA）

| 方法 | RVA |
|---|---|
| `static get_fixedFrameCnt()` | 0x3563340 |
| `static get_fixedPlayTime()` | 0x35633D0 |
| `static get_deltaPlayTimeFP()` | 0x3562BA0 |
| `static get_randomImp()` / `get_randomTrivial()` | 0x35650E0 / 0x3565210 |
| `get_randomSeed()` | 0x3565170 |
| **`ResetSeed()` / `ResetSeed(int)`** | 0x3553700 / 0x3553550 |
| **`LoadGame(List<BattlePlayerData>, LevelData, MapData, Difficulty)`** | 0x354C580 |
| `StartGame()` / `ResetAll()` | 0x3556330 / 0x3552B10 |
| `FinishGame(GameResult, bool, Action)` | 0x35483C0 |
| **`ManualFrameTick(FrameData, bool additionalFrame)`** | 0x354CB60 |
| `Update()` / `FixedUpdate()` / `OnTick()` | 0x3557AA0 / 0x35487E0 / 0x354F880 |
| `GetLifePoint` / `SetLifePoint` / **`ModifyLifePoint`** | 0x3549950 / 0x3554360 / 0x354D550 |
| `GetCost` / `SetCost` / **`ModifyCost`** | 0x35491E0 / 0x3554040 / 0x354D0C0 |
| `ModifyCostIncreaseTime` / `SetCostIncreaseTime` | 0x354CEB0 / 0x3553E50 |
| `ModifyCharacterLimit` | 0x354CCF0 |
| `_UpdateCost(FP fixedDeltaTime, PlayerSide)` | 0x3560310 |
| `RecycleBuffNextFrame(ObjectPtr<Buff>)` | 0x3551B50 |

---

## 二、`Entity` → `Unit` → `Character` / `Enemy`

### 2.1 `Entity`（8716，行 330768）

| 字段 | 类型 | 偏移 |
|---|---|---|
| `FACE_TO_TARGET_MIN_DISTANCE_SQR` | const float | = 0.040000003 |
| **`m_hp`** / `m_es`（护盾） | FP | 0x40 / 0x48 |
| **`m_sp`** | ObscuredFP（占 0x28） | 0x50 |
| `m_epArray` | FP[] | 0x80 |
| **`m_attributes`** | Attributes | 0x98 |
| `m_faceTo` | Vector2 | 0x8C |
| `m_changeableMotionMode` | MotionMode | 0x94 |
| **`m_hpRecoverTimer`** / `m_epRecoverTimer` | PrecisePeriodicTimer | 0xA8 / 0xC0 |
| **`m_abilities`** | `ListSet<Ability>` | 0xC8 |
| `m_direction` | `SharedConsts.Direction` | 0xD4 |
| **`m_buffEffects`** | `Dictionary<string, BuffEffectHolder>` | 0xF8 |
| 挂点 `m_footMountPoint` / `m_hitMountPoint` / **`m_muzzleMountPoint`** / `m_headMountPoint` / `m_uiMountPoint` | MountPoint ×5 | 0x108–0x128 |
| `id` / `tmplId` | string | 0x130 / 0x138 |
| **`pathMotionMode`** | MotionMode | 0x144 |
| **`originTile`** | Tile | 0x148 |
| **`buffContainer`** | Buff.BuffContainer | 0x150 |
| `maxSp` | int | 0x160 |
| `minusHp` / `maxMinusHpRatio` | FP | 0x168 / 0x170 |

> ★ **`Entity.attackTime` 是 `FP` 属性**（dump.cs 331266 / get 0x331685）——攻击时点是逻辑量，不是动画事件。

**继承备注**：`Entity : BObject`，`BObject.m_prdCounter`(0x28) / `m_prdSubEntities`(0x30) 是 **PRD（伪随机分布）** 载体，服务于暴击/闪避类概率的确定性。

### 2.2 `Unit`（9758，行 385204）— 实例段 0x180–0x288

| 字段 | 类型 | 偏移 |
|---|---|---|
| `_animator` | UnitAnimator | 0x180 |
| **`_modes`** | UnitMode[] | 0x188 |
| **`_commonAbilities`** | Ability[] | 0x190 |
| `m_currentMode` | UnitMode | 0x1E8 |
| **`m_overrideAttack`** / `m_overrideTrigger` / **`m_overrideCombat`** | Ability / TargetTrigger / Ability | 0x1F0 / 0x1F8 / 0x200 |
| `talents` | `BasicTalent[]` | 0x248 |
| `m_rootDynamicAbilities` | `List<KeyValuePair<Ability, Blackboard>>` | 0x250 |
| **`m_attackRangeTiles`** / `m_originAttackRangeTiles` | `List<Tile>` | 0x278 / 0x288 |

关键方法：`get_attack` 0x7707F0、`get_combat` 0x7709F0、`get_attackTrigger` 0x770730、`get_attackRangeTiles` 0x770520、`OverrideAttack` 0x76CB50、`OverrideCombat` 0x76CC70、`GetAttackBlackboard` 0x769600。

### 2.3 `Character`（9661，行 377663）— 我方可部署单位

| 字段 | 类型 | 偏移 |
|---|---|---|
| `_motionMode` / **`_blockMode`** | MotionMode | 0x298 / 0x29C |
| `_ignoreBlockMode` | bool | 0x2A0 |
| **`_buildCondition`**（建造/部署条件） | BuildCondition | 0x2A8 |
| **`_traitAbility`**（特性） | Ability | 0x2F8 |
| `_withdrawCostRecoverRatio` / `_maxWithdrawCostRatioOfRawCost` | float | 0x300 / 0x304 |
| `m_defaultRangeId` / `m_defaultModeIndex` | string / int | 0x340 / 0x348 |
| **`m_hatred`**（仇恨） | FP | 0x350 |
| **`m_createdTime` / `m_deadTime`** | FP | 0x358 / 0x360 |
| **`m_rootTile`** | Tile | 0x370 |
| **`m_blockedEnemyMgr`** | Character.BlockedEnemyManager | 0x378 |
| **`m_findBlockeeTicker`** | PeriodicTicker | 0x380 |
| **`m_skill` / `m_skillData`** | BasicSkill / SkillData | 0x398 / 0x3A0 |
| `m_deckBuffDatas` / `m_deckBuffBlackboard` | `IList<DeckBuff>` / `IList<Blackboard>` | 0x420 / 0x428 |
| `m_buildCondition` / `m_additionalBuildCondition` | BuildCondition | 0x440 / 0x490 |
| `m_traitAbility` | Ability | 0x4A8 |
| **`m_advancedBuildState` / `m_deployCostThisTime`** | AdvancedCardBuildState / int | 0x4B8 / 0x4BC |
| `m_overrideBornTime` | float | 0x4D4 |
| **`m_changableBlockMode` / `m_oldBlockMode`** | MotionMode | 0x4DC / 0x4E0 |
| `data` | BattleCharacterData | 0x4E8 |
| `m_mainTriggerColliderRadius` | FP | 0x4F8 |

**静态常量（★ 阻挡机制的关键数字）**：
`FIND_BLOCKEE_TICK = 3`（阻挡搜索**每 3 帧**一次）、`HATRED_VALUE_GAP`(FP)、`HATRED_VALUE_PER_FRAME_GAP`(FP)、`DEFAULT_REMAINING_CHARACTER_CNT_VOLUME = 1`。

关键方法：`get_blockedEnemies()` 0x705700、`get_blockedTotalVolumn()` 0x705790、`get_canBlockEnemyOnRootTile()` 0x705B00、`get_rootTile()` 0x708030、`get_oldTile()` 0x707970、`get_skill()` 0x7084E0、`get_buildCondition()` 0x705820、`get_additionalBuildCondition()` 0x704DB0、`get_advancedBuildState()` 0x704F50、`get_isInCombat()` 0x706F10。

### 2.4 `Enemy`（9708，行 380866）— 敌方单位

| 字段 | 类型 | 偏移 |
|---|---|---|
| **`m_lastMoveDirVec`** | Vector2 | 0x290 |
| `_sideTypeIndex` / `_locateRange` | SideTypeIndex / Range | 0x298 / 0x2A0 |
| `_bodyDirectionPolicy` / `_scaleMoveBySpeed` | — / bool | 0x2AC / 0x2B0 |
| **`_delayToBorn`** | float | 0x2DC |
| **`_blockVolume`**（阻挡体积） | int | 0x2F8 |
| **`_specialBlockCondition`** | Enemy.SpecialBlockCondition | 0x300 |
| `_canNotExit` | bool | 0x30B |
| **`m_totalMoveDist`** | float | 0x314 |
| **`m_currentTile` / `m_oldTile`** | Tile | 0x320 / 0x328 |
| **`m_cachedRoute`**（运行期路径缓存） | Route | 0x338 |
| **`m_moveController`** | MoveController | 0x358 |
| **`m_blocker`**（被哪个干员阻挡） | `ObjectPtr<Character>` | 0x360 |
| `m_updatePosTicker` | PeriodicTicker | 0x370 |
| `m_spineAnimator` | SpineAnimator | 0x380 |
| **`m_blockTween`** | ITweenHandler | 0x3B0 |
| **`m_blockPosition`**（阻挡后的吸附位置） | Vector2 | 0x3C0 |
| `m_contDirAfterEnd` / `m_posInLastFrame` | Vector2 | 0x3C8 / 0x3D0 |
| `m_mainTriggerColliderRadius` | FP | 0x3F0 |
| **`m_allSkills` / `m_skills`** | EnemySkill[] / `List<EnemySkill>` | 0x410 / 0x498 |
| **`m_blockVolumeAddition`** | int | 0x468 |
| **`m_createdTime`** | FP | 0x470 |
| **`m_routeSpawnPosition`** | GridPosition | 0x478 |
| **`m_attackAbilityCasted` / `m_combatAbilityCasted`** | Ability | 0x4A8 / 0x4B0 |
| **`m_combatNextEscapeTime`** | FP | 0x4B8 |
| **`lifePointReduce`**（进蓝门扣多少生命） | int | 0x4C4 |
| `data` | `LevelData.EnemyData` | 0x4D0 |
| `attackWrapper` / `combatWrapper` | Enemy.AttackWrapper / CombatWrapper | 0x510 / 0x518 |
| `m_frictionFactor` / `m_frictionFactorAdditional` | float | 0x520 / 0x524 |

**静态常量**：`UPDATE_POS_TICK = 5`（位置**每 5 帧**更新一次）、`BLOCKING_TWEEN_DURATION = 0.2`、`HATRED_VALUE_GAP = 1000`、`MIN_BLINK_DISTANCE = 0.01`。

关键方法：`get_lifePointReduce()` 0x732810、`get_blockVolume()` 0x72FE30、`set_blockVolumeAddition(int)` 0x7348A0、`get_blocker()` 0x72FEB0、`get_stableBlockPosition()` 0x733D40、`SetSpecialBlockCondition(...)` 0x729C00、`get_moveController()` 0x732D00、`get_totalMoveDist()` 0x734050、`get_routeSpawnPosition()` 0x7339A0、`get_lastMoveDirVec()` 0x7325F0、`get_isInMoveState()` 0x7321A0、`get_isInBornState()` 0x731E00、`get_isInDyingState()` 0x732070、`get_isInCombatState()` 0x731560。

---

## 三、`Ability`（8423，行 312655）与 `Buff`（8609，行 324345）

### 3.1 Ability

| 字段 | 类型 | 偏移 |
|---|---|---|
| **`_selector`**（目标选择器） | TargetSelector | 0x28 |
| `m_owner` | `ObjectPtr<Entity>` | 0x48 |
| **`m_isCasting`** | bool | 0x58 |
| **`m_castStartFrameCnt`**（帧计数） | uint | 0x5C |
| **`m_cooldownTimer`** | PeriodicTimer | 0x68 |
| `abilityUniqueId` / `blackboard` | uint / Blackboard | 0x78 / 0x80 |
| **`damageMissFlag`** | bool | 0xB0 |
| `m_prdEntityHash`（PRD 随机） | PRDEntityHash | 0xBC |

方法：`get_remainingTime()` 0x34F8A30、`get_cooldownProgress()` 0x34F7DF0、`get_periodTime()` 0x34F87F0、`get_isCastable()` 0x34F8220、`Attach(Entity)` 0x34F5420、`Detach()` 0x34F5750、`DoFinish(...)` 0x34F5C30、`UpdateSelector()` 0x34F7970。

### 3.2 Buff

| 字段 | 类型 | 偏移 |
|---|---|---|
| `m_source` / `m_ability` / `m_sourceProjectile` | ObjectPtr ×3 | 0x18 / 0x28 / 0x38 |
| **`m_attributeAdditions` / `m_attributeMultipliers` / `m_attributeFinalAdditions` / `m_attributeFinalScalers`** | FP[] ×4 | 0x50 / 0x48 / 0x58 / 0x60 |
| `m_data` | BuffData | 0x68 |
| **`m_lifeTime` / `m_remainingTime` / `m_existingTime`** | FP | 0x70 / 0x78 / 0x80 |
| **`m_triggerCnt`** / **`m_stackCnt`** / `m_maxValidStackCnt` | int | 0x88 / 0x8C / 0x90 |
| **`m_triggerTimer`** | PrecisePeriodicTimer | 0x98 |
| `m_actions` | ActionNode[][] | 0xA0 |
| 布尔组 `m_isDurableBuff` / `m_isDamageMissable` / `m_isSilenceable` / `m_isStunnable` / `m_isFreezable` / `m_isStatusResistable` / `m_isLevitatable` | bool ×7 | 0x1E0–0x1E6 |
| 状态组 `m_started` / `m_isFinished` / `m_needRemove` / `m_isValid` … | bool ×9 | 0x1E7–0x1EF |
| `key` / `overrideKey` | string | 0x1F0 / 0x1F8 |
| **掩码组** `attributeMask` / `abnormalFlagMask` / `abnormalImmuneMask` / `abnormalAntiMask` / `abnormalComboMask` / `abnormalComboImmuneMask` | long ×6 | 0x208–0x230 |
| `m_derivedBuffs` | `List<ObjectPtr<Buff>>` | 0x258 |

静态常量：`INFINITY_TIME`(FP)、`EVENT_NUM = 101`、`ABFLAGS_IS_AUTO_STATUS_RESISTABLE`、`ABFLAGS_ABLE_TO_BE_RESISTED`。

**★ 属性结算核心：`Buff.GetValue(AttributeType, out FP addition, out FP multiplier, out FP finalAddition, out FP finalScaler)` RVA 0x358CAA0** —— 所有攻击/防御/速度的最终数值都从这里按 `attributeMask` 聚合。要复刻数值链，这是第一优先反汇编目标。

---

## 四、关卡数据层（`Torappu` 命名空间）

### 4.1 `LevelData.Options`（4291，行 158398）— 局内规则参数

| 字段 | 类型 | 偏移 |
|---|---|---|
| `characterLimit` / **`maxLifePoint`** | int | 0x10 / 0x14 |
| `initialCost` / `maxCost` | int | 0x18 / 0x1C |
| **`costIncreaseTime`** | float | 0x20 |
| **`moveMultiplier`** | float | 0x24 |
| **`steeringEnabled`** | bool | 0x28 |
| **`maxPlayTime`** | float | 0x30 |
| `functionDisableMask` | BattleFunctionDisableMask | 0x34 |
| `configBlackBoard` | Blackboard | 0x38 |
| `enemyTauntLevelPow` | int | 0x40 |

### 4.2 `RouteData`（4288，行 158351）与 `RouteData.CheckpointData`（4287，行 158330）

| CheckpointData 字段 | 类型 | 偏移 |
|---|---|---|
| **`type`** | CheckpointType | 0x10 |
| **`time`** | float | 0x14 |
| **`position`** | GridPosition | 0x18 |
| **`reachOffset`** / `randomizeReachOffset` / `reachDistance` | Vector2 / bool / float | 0x20 / 0x28 / 0x2C |

| RouteData 字段 | 类型 | 偏移 |
|---|---|---|
| **`motionMode`** | MotionMode | 0x10 |
| **`startPosition` / `endPosition`** | GridPosition | 0x14 / 0x1C |
| **`spawnRandomRange` / `spawnOffset`** | Vector2 | 0x24 / 0x2C |
| **`checkpoints`** | `CheckpointData[]` | 0x38 |
| `allowDiagonalMove` / `visitEveryTileCenter` / `visitEveryNodeCenter` / `visitEveryCheckPoint` | bool ×4 | 0x40–0x43 |

### 4.3 `LevelData.EnemyData` 系列

`EnemyData`（4295，行 158473）：`attributes`(AttributesData,0x28)、`applyWay`(0x30)、`motion`(0x34)、`enemyTags`(0x38)、**`lifePointReduce`**(int,0x50)、**`rangeRadius`**(float,0x54)、`viewRadius`(0x5C)、`levelType`(0x60)、`talentBlackboard`(0x68)、**`skills`**(`ESkillData[]`,0x70)、**`spData`**(0x78)、`m_runtimeData`(0x80)。
属性：`keyInLevel`、`isBoss`、`runtimeData`。

- `ESkillData`（4292）：`prefabKey`(0x10)、`priority`(0x18)、**`cooldown`**(0x1C)、**`initCooldown`**(0x20)、`spCost`(0x24)、`blackboard`(0x28)
- `ESpData`（4293）：`spType`(0x10)、**`maxSp`**(0x14)、**`initSp`**(0x18)、**`increment`**(0x1C)
- **`EnemyDataDbReference`**（4296，行 158520）：`useDb`(0x10)、`id`(0x18)、`level`(0x20)、**`overwrittenData`**(`EnemyDatabase.EnemyData`,0x28) ← **关卡实例化敌人的入口**

### 4.4 `LevelData.WaveData` 系列 — 出怪时序

`WaveData`（4302，行 158645）：**`preDelay`/`postDelay`**(float,0x10/0x14)、**`maxTimeWaitingForNextWave`**(0x18)、**`fragments`**(`FragmentData[]`,0x20)、`advancedWaveTag`(0x28)。
`FragmentData`（4301）：**`preDelay`**(float,0x10)、**`actions`**(`ActionData[]`,0x18)。

`FragmentData.ActionData`（4300，行 158582）：

| 字段 | 类型 | 偏移 |
|---|---|---|
| **`actionType`** | ActionType | 0x10 |
| **`managedByScheduler`** | bool | 0x14 |
| **`key`** | string | 0x18 |
| **`count`** | int | 0x20 |
| **`preDelay` / `interval`** | float | 0x24 / 0x28 |
| `useExtraRoute` / **`routeIndex`** | bool / int | 0x2C / 0x30 |
| **`blockFragment`** | bool | 0x34 |
| **`randomSpawnGroupKey` / `randomSpawnGroupPackKey`** | string | 0x40 / 0x48 |
| **`randomType` / `refreshType`** | RandomType / RefreshType | 0x50 / 0x54 |
| **`weight`** | int | 0x58 |

方法：`get_weightValue` 0x210D850（实现 `IItemWithWeight`，加权随机抽取）。

**ActionType 枚举**（4297）：`SPAWN=0, PREVIEW_CURSOR=1, STORY=2, TUTORIAL=3, PLAY_BGM=4, DISPLAY_ENEMY_INFO=5, ACTIVATE_PREDEFINED=6, PLAY_OPERA=7, TRIGGER_PREDEFINED=8, BATTLE_EVENTS=9, WITHDRAW_PREDEFINED=10, DIALOG=11, SHOW_ALL_HIDDEN_CARDS=12, EMPTY=13`。

`LevelData.BranchData`（4304）：`phases`(`PhaseData[]`,0x10)。
`PhaseData`（4303）：**`preDelay`**(0x10)、**`actions`**(0x18)；方法 `FetchActionsWithRandomSpawn(bool refreshResult)` 0x21186B0、`GetEnemiesCnt()` 0x2118A00。
`LevelData.ActionID`（struct）：`waveI`(0x0)、`fragI`(0x4)、`actionI`(0x8)。

### 4.5 `MapData` / `TileData` / `GridPosition`

`MapData`（4325，行 159060）：**`map`**(`short[,]`,0x10)、**`tiles`**(`TileData[]`,0x18)、**`blockEdges`**(`MapData.Edge[]`,0x20)、`tags`(0x28)、`effects`(0x30)、`layerRects`(0x38)。
`MapData.Edge`（4324）：**`pos`**(GridPosition,0x10)、**`direction`**(0x18)、**`blockMask`**(MotionMask,0x1C) ← **格子边界上的阻挡**（高台/墙壁边缘），寻路关键输入（推断）。

`TileData`（4323，行 159021）：`tileKey`(0x10)、**`heightType`**(0x18)、**`buildableType`**(0x1C)、**`passableMask`**(MotionMask,0x20)、**`playerSideMask`**(0x24)、`advancedBuildableMask`(0x28)、`blackboard`(0x30)、`effects`(0x38)。
`HeightType` 枚举：`LOWLAND=0, HIGHLAND=1`。

`GridPosition`（1538，struct，行 114774）：**`row`**(0x0)、**`col`**(0x4)；静态常量 `GRID_ZERO/LEFT/RIGHT/UP/DOWN/UP_LEFT/...`、`GRID_FOUR_WAYS/GRID_EIGHT_WAYS`。
方法：`Encode(GridPosition)` 0x1DF8C60 / `Decode(int)` 0x1DF8C20（**行列打包成 int 作字典键**）、`FromVectorPosition(Vector2)` 0x1DF8D80、`IsAdjacent` 0x1DF8E60、`RotateVector` 0x1DF8F10、`manhattan`/`magnitude`/`sqrMagnitude`。

### 4.6 `Route`（运行期寻路，9088，行 349654）与 `Route.Node`（9087，行 349605）

`Route`：`m_map`(0x10)、**`m_data`**(RouteData,0x18)、`m_pathFinder`(0x20)、**`m_targetNextMap`**(`Node[,]`,0x28)、**`m_checkpointsNextMap`**(`Node[,][]`,0x30)。
方法：`ReconstructRoute(RouteData)` 0x5C7710、`ReconstructNextMap()` 0x5C7400、**`GetDistToFinal()`** 0x5C6DF0、`GetPredictFuturePositionWithoutCheckpoints(Vector2, float)` 0x5C6FC0、`GetSpawnPosition()` 0x5C73A0、`GetSpawnOffset()` 0x5C72D0、**`CheckReached(Vector2)`** 0x5C69D0、`CheckReachable(bool,bool)` 0x5C6700。

`Route.Node`：**`pos`**(GridPosition,0x10)、**`tile`**(Tile,0x18)、**`nextTurn`**(Vector2,0x20)、**`nextNode`**(`Route.Node`,0x28)、`distance`(0x30)、**`distToFinal`**(0x34)、`isInOpenList`(0x38)。
方法：`GetSafeNextPosition()` 0x5C5830、**`IsPassableGoTo(MotionMode, GridPosition)`** 0x5C58C0、`CheckObstacleLikeOrInvalid(MotionMode)` 0x5C56B0。

> **判定**：`RouteData` 是策划配的路点表；`Route` 是局内用 `IPathFinding` **预计算出的逐格下一跳查找表**；`Route.Node` 是 A* 结果节点。敌人沿 `m_cachedRoute` 按 `nextTurn`/`nextNode` 平移到下一格中心。

---

## 五、`Scheduler`（9266，行 359000）— 出怪导演

实例段自 **0x18** 起（MonoBehaviour 派生）。

| 字段 | 类型 | 偏移 |
|---|---|---|
| `m_blockCounter` | int | 0x18 |
| **`m_spawnedEnemiesCnt` / `m_spawnedWavesCnt`** | uint / int | 0x1C / 0x20 |
| `m_finishedEnemiesCnt` / `m_killedEnemiesCnt` / `m_validFinishedEnemiesCnt` / `m_validKilledEnemiesCnt` / `m_validMissedEnemiesCnt` | ObscuredInt ×5 | 0x24 / 0x38 / 0x4C / 0x60 / 0x74 |
| **`m_waveStartTime` / `m_fragmentStartTime`** | FP | 0x88 / 0x90 |
| **`m_waves`** | `LevelData.WaveData[]` | 0x98 |
| `m_enemyMap` | `Dictionary<string, EnemyItem>` | 0xA0 |
| **`m_actionQueue`** | `List<Scheduler.ActionItem>` | 0xB0 |
| `m_managedWaveEnemies` / `m_managedFinalEnemies` | `List<Enemy>` | 0xB8 / 0xC0 |
| **`m_brancheMap`** | `ListDict<string, BranchRuntime>` | 0xC8 |
| `m_enabledHiddenGroups` | `ListSet<string>` | 0xD0 |
| `m_cachedEnemies` / `m_waveCachedEnemies` | `ListSet<Enemy>` / `Dictionary<int, ListSet<Enemy>>` | 0xD8 / 0xE8 |
| `m_inWavePostDelay` | bool | 0xF0 |
| `m_mainCoroutine` | CoroutineId | 0xF8 |
| `m_wavePlugin` | `List<IWavePlugin>` | 0x118 |
| `totalEnemiesCnt` | int | 0x120 |

关键方法：`Init(LevelData, IList<string>, IList<string>)` 0x623FE0、`Reset()` 0x625BD0、**`OnGameInit(LevelData.Options)`** 0x625140、`UpdateWaves(LevelData.WaveData[])` 0x629550、`FinishCurrentWave(bool)` 0x623D50、`ReleaseEnemyFromCurrentWave(Enemy,bool)` 0x6257F0、`TrackEnemyAtNextWave(Enemy,int)` 0x6282A0、`TryMoveNextBranch(string,bool)` 0x628DD0、**`TryPickRandomBranchNotRepeat(string,bool)`** 0x629010、**`TryGetEnemyRouteFromBranch(string,int,out Route,out string)`** 0x628A50、`AddBlockGameKey(string)` 0x623390。

---

## 六、★ 横向索引（按"要模拟什么"查）

| 关注点 | 落点 |
|---|---|
| **时间 / 帧 / delta** | `BattleController.s_fixedFrameCnt`(0x14静态)、`s_fixedPlayTime`、`s_deltaPlayTimeFP`、`m_realPlayTime`(0x294)、`m_timeDeltaNoEnemy`(0x298)、`m_originTimeScale`(0x290)、`m_speedLevel`(0x234)、`_UpdateCost(FP,PlayerSide)` 0x3560310、`ManualFrameTick` 0x354CB60；`Ability.m_castStartFrameCnt`(0x5C)；`Character.m_createdTime/m_deadTime`(0x358/0x360)；`Enemy.m_createdTime`(0x470)、`m_combatNextEscapeTime`(0x4B8)、`_delayToBorn`(0x2DC)；`Buff.m_lifeTime/m_remainingTime/m_existingTime`(0x70/0x78/0x80)；`Scheduler.m_waveStartTime/m_fragmentStartTime`(0x88/0x90)；`LevelData.Options.costIncreaseTime/maxPlayTime`(0x20/0x30)；`RouteData.CheckpointData.time`(0x14) |
| **随机 / seed** | `BattleController.s_randomImp`(0x30静态)、`s_randomTrivial`(0x38静态)、`m_randomSeed`(ObscuredInt 0x198)、`ResetSeed()` 0x3553700、`RANDOM_ALGORITHM`；`LevelData.randomSeed`(0xA8)；`RouteData.spawnRandomRange`(0x24)、`CheckpointData.randomizeReachOffset`(0x28)；`ActionData.weight/randomType/randomSpawnGroupKey`(0x58/0x50/0x40)；`PhaseData.FetchActionsWithRandomSpawn` 0x21186B0；`Scheduler.TryPickRandomBranchNotRepeat` 0x629010；**PRD**：`BObject.m_prdCounter`(0x28)、`Ability.m_prdEntityHash`(0xBC) |
| **坐标 / 格子** | `GridPosition.row/col`(0x0/0x4) + 11 个静态方向常量；`RouteData.startPosition/endPosition/spawnOffset`(0x14/0x1C/0x2C)；`Enemy.m_routeSpawnPosition`(0x478)、`m_currentTile/m_oldTile`(0x320/0x328)、`m_blockPosition`(0x3C0)；`Character.m_rootTile`(0x370)；`Entity.originTile`(0x148)；`Unit.m_attackRangeTiles`(0x278)；`MapData.map/tiles/blockEdges`(0x10/0x18/0x20)；`TileData.passableMask/buildableType/heightType`(0x20/0x1C/0x18) |
| **移动 / 速度** | `MotionMode{WALK=0,FLY=1}`；`LevelData.Options.moveMultiplier`(0x24)、`steeringEnabled`(0x28)；`RouteData.motionMode/allowDiagonalMove/visitEveryTileCenter/visitEveryNodeCenter`(0x10/0x40–0x42)；`Route.Node.nextNode/nextTurn/distance/distToFinal`(0x28/0x20/0x30/0x34)；`Enemy.m_moveController`(0x358)、`m_totalMoveDist`(0x314)、`m_lastMoveDirVec`(0x290)、`m_updatePosTicker`(0x370)；`Character._motionMode/_blockMode`(0x298/0x29C)；`GridPosition.FromVectorPosition` 0x1DF8D80 |
| **攻击 / 伤害** | `Unit.m_overrideAttack/m_overrideCombat/m_overrideTrigger`(0x1F0/0x200/0x1F8)、`_commonAbilities`(0x190)、`get_attack` 0x7707F0；`Character.m_skill/m_skillData`(0x398/0x3A0)、`_traitAbility`(0x2F8)、`m_hatred`(0x350)；`Enemy.m_attackAbilityCasted/m_combatAbilityCasted`(0x4A8/0x4B0)、`m_allSkills`(0x410)、`lifePointReduce`(0x4C4)、`ESkillData.cooldown/initCooldown`(0x1C/0x20)；`Ability._selector/m_cooldownTimer/damageMissFlag`(0x28/0x68/0xB0)；**`Buff.GetValue(...)` 0x358CAA0**；`Entity.m_hp/m_es/m_sp`(0x40/0x48/0x50)；`BattleController.ModifyLifePoint` 0x354D550 |
| **阻挡** | `Character._blockMode`(0x29C)、`_ignoreBlockMode`(0x2A0)、`m_changableBlockMode/m_oldBlockMode`(0x4DC/0x4E0)、`m_blockedEnemyMgr`(0x378)、**`m_findBlockeeTicker`(0x380, `FIND_BLOCKEE_TICK=3`)**、`get_blockedEnemies()` 0x705700、`get_blockedTotalVolumn()` 0x705790；`Enemy._blockVolume`(0x2F8)、`m_blockVolumeAddition`(0x468)、`m_blocker`(0x360)、`m_blockTween`(0x3B0)、`m_blockPosition`(0x3C0)、`get_stableBlockPosition()` 0x733D40、`BLOCKING_TWEEN_DURATION=0.2`；`MapData.Edge.blockMask`；`TileData.passableMask` |
| **buff** | `Entity.m_buffEffects`(0xF8)、`buffContainer`(0x150)、`m_abilities`(0xC8)；`Buff.m_attribute*`(0x48–0x60)、`m_stackCnt`(0x8C)、`m_triggerTimer`(0x98)、`abnormal*Mask`(0x210–0x230)、`m_derivedBuffs`(0x258)；`BattleController.m_globalBuffs/m_buffPool`(0x68/0x90)、`RecycleBuffNextFrame` 0x3551B50；`LevelData.globalBuffs`(0x58) |
| **路径 / route / checkpoint** | `LevelData.routes/extraRoutes/branches`(0x60/0x68/0x88)；`RouteData.checkpoints`(0x38)、`CheckpointData.type/time/position/reachOffset`(0x10/0x14/0x18/0x20)；`Route.m_targetNextMap/m_checkpointsNextMap`(0x28/0x30)、`GetDistToFinal` 0x5C6DF0、`CheckReached` 0x5C69D0；`Route.Node.*`；`Enemy.m_cachedRoute`(0x338)；`ActionData.useExtraRoute/routeIndex`(0x2C/0x30)；`Scheduler.TryGetEnemyRouteFromBranch` 0x628A50 |

---

## 七、其它已定位但未展开的类

| 类 | 行号 | 用途 |
|---|---|---|
| `CharacterAnimator` / `SpineAnimator` / `UnitAnimator` | 314994 / 316817 / 317861 | 表现层动画（见 `31` 号文档 §三） |
| `Projectile` / `BattleFactory` / `Deck` | 354766 / 356183 / 328822 | 弹道 / 单位工厂 / 卡组 |
| `LevelScriptManager` / `ActionExecutorManager` | — | 关卡脚本与行为动作 |
| `LuaManager` / `LuaEnv` / `ObjectTranslator` | 195002 / 57793 / 52327 | Lua 层（见 `31` 号文档 §三） |
| `Tile`（运行期） / `Map`（运行期） | 351277 / 347758 | 地图运行期对象 |
| **`HashCodeBuilder`** | 103520 | **状态哈希**：`private const float FLOAT_MULTIPLIER = 10000`、`private uint m_curHash; // 0x10`；方法 `Clear()` / `Append(string\|int\|uint\|long\|ulong\|char\|byte\|float\|Vector2\|Vector3\|…)` / `GetCombinedHash()`；RVA 从 0x1AF8EC0 起（都在同一小段，是纯计算，便于整体复刻） |
| **`ClientAntiCheatChecker`** | 318117 | **客户端反作弊周期性抽查**：`m_moveMultiplier`(ObscuredFloat 0x10)、`m_costIncreaseTime`(ObscuredFP 0x28)、`m_checkTimer`(PeriodicTimer 0x50)、`m_checkTimes`(ObscuredInt 0x58)、`m_isValidBattle`(ObscuredBool 0x6C)、`m_errorLog`(ListDict<int,List<object>> 0x78)；静态 `RANDOM_TIME_RANGE`(ObscuredVector2) / `MAX_CHECK_TIMES`(ObscuredInt)；方法 `Init` / **`_CheckEnemyMoveSpeed`** / **`_CheckCostIncreaseTime`** / **`_CheckCharacterAttackTime`** / `_DoCheck` / `_ResetTimer` / `OnFixedUpdate` |

### 7.1 这两条为什么重要

- **`HashCodeBuilder` 是模拟正确性的客观判据**。它把状态序列化成 `uint` 哈希，配合 `BattleController` 的 `m_snapshotBuilder` / `m_playerOperationBuilder` / `ReplayController`，构成"确定性模拟 + 事后校验"的闭环。复刻它即可让模拟器自证。（`FLOAT_MULTIPLIER = 10000` 说明浮点先乘 10000 再取整参与哈希——量化精度是 1e-4。）
- **`ClientAntiCheatChecker` 反过来暴露了"哪些量是权威计算"**：它周期性抽查 **敌人移动速度、费用回复时间、干员攻击间隔** 三项，用 `Obscured*` 类型存参考值（防内存修改），并在 `OnFixedUpdate` 里由 `_DoCheck` 触发。
  - 对模拟的意义有两层：① 这三个量是复刻的**必对项**（错一点就会被查出来）；② 这三个 check 本身是比全局哈希**更细粒度**的验证判据，值得优先反汇编。
  - 注意 `RANDOM_TIME_RANGE`：抽查带随机时间窗，说明它不是固定时刻比对。

## 八、K 清单核验收口后新增/勘误（2026-09-13，详见 `36` 号文档）

**勘误**：
- `m_spRecoverTimer // 0x40` 属 **`Entity.SpController`**（dump 330294），不是 `Entity`；Entity 侧应记 **`m_spController // 0xE0`**（330794）。SP 链：`Entity.m_spController(0xE0)` → `SpController.m_spRecoverTimer(0x40)`。
- `Entity` 表补 **`m_attributes // 0x98`**。

**建议补入本表的类**（本次指令级核验的落点）：

| 类 | TypeDefIndex / 行 | 为什么重要 |
|---|---|---|
| `Torappu.Battle.Consts` | 8381 / 311803 | **全局常量表**：`BLOCK_RADIUS=0.7071`、`TILE_COLLIDE_DISTANCE=0.005`/`_WIDE=0.01`、`FRICTION_FACTOR=0.5`、`UNBALANCE_MIN_SPEED=0.1`、`KNOCKBACK_FACTOR=0.02`、`ROUTE_REACH_DISTANCE=0.05`、`ROUTE_GOPASS_DISTANCE=0.25`、障碍代价 1000/1000000 |
| `BlockBalancer` | 9812 / 388256 | **阻挡偏移**（不是碰撞箱）：`MIN_DIST_BTW_BLOCKEES_SQR=0.01`(=0.1²)、`CLOSE_DIST_BTW_BLOCKEERS=0.4`、`CLOSE_DIST_BTW_BLOCKEES_SQR=0.16`(=0.4²)、`MERGE_FACTOR_OF_SEPARATION=0.2`；`CalculateBlockOffset` RVA 0x7C1050（内含 ×50、1e-05 等常量，调用 `Enemy.get_stableBlockPosition()`）—— 完整算法见 `37_阻挡与阻挡偏移_代码核验.md` |
| `SPFA` / `Route.Node` | 9085 / 9087 | 寻路：`_PostprocessAndMakeNextMapSmoothly` 0x5C9CE0（`row↑col↑` + 就地改写 `nextNode`）、`_RaycastBresenhamLine` 0x5C9F40 |
| `BasicCursor` / `DirectionCursor` | 9077+ | `MoveCheckpoint.CheckReached` 0x5C4D40（`max(0.05, reachDistance)`）、`visitEveryNodeStably // 0x58` |
| `SelectorTrigger` | 9584 / 375083 | **`SEARCH_TARGET_TICK = 3`**（索敌节拍）、`_overrideSearchTargetTick 0x28`、`m_findTargetTicker 0x48` |
| `FilterUtil` | 9493 | `HATRED_WEIGHT_SMALL_ENOUGH_GAP = FP(0.1) // 0x8`、`_Filter_HatredDes` 0x6C67C0（权重 = −hatred）、`FilterType` 79 个值 |
| `AdvancedSelector` / `TargetOptions` / `TargetSelector.ValidateTarget` | 9437 / 9536 / RVA 0x6E0160 | `_forceIgnoreCamouflage // 0xBE`；`excludeAbnormalFlag // 0x14`；迷彩判定在 `ValidateTarget` 的 0x6E043B 处整段可跳过 |
| `PeriodicTimer` / `PrecisePeriodicTimer` | 1381 / 1382 | `Update` 0x1AFB3B0（`remaining≤0` 触发并归零 → `ceil(period/Δt)` 帧）、`ResetButKeepProgress` 0x1AFAE50、`ResetButKeepPastTime` 0x1AFAD80 |
| `PullCastTargets` | 11299 / 462094 | 定时拉：`_pullDuration // 0x24`、`_forceKey // 0x28`、`m_pullRemainingTimeList // 0x30` |
| `AuraAbility.TargetEnterExitHandler` | 448231 | **`m_invalidTarget // 0x30`**、`m_triggerTicker // 0x38`；`TRIGGER_TICK=10` 只节流**无效目标重试** |
| `Entity.SpController` | 8701 / 330294 | `m_spRecoverTimer // 0x40`；`spRecoveryPerSec = GetValue(14) × GetValue(30)` |
| `Nodes.VertifyTarget` | 11832 / 478811 | `[SerializeField] TargetOptions _targetOptions // 0x18`，`Execute` RVA 0xB9A1E0 |

## 相关文件

- `29_cpp层定位与读取流程.md`（工具链与数值精度）
- `31_局内模拟信息完备性排查.md`（完备性判定）
- `30_信息获取渠道索引_按数据层级.md`
