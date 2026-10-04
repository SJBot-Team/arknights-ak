# 数值链：从 buff 模板到具体数值（以 chiave_t_1 为例）
> 层级：**T2（主要来自 PRTS 与数据表）**　建立日期：**—（待补）**　任务：—　｜　**头部为 2026-09-30 自动回填**，推断项已标注

> 问题：buff 模板里 `attributeModifiers` 的 `value` 是 0.0 且 `loadFromBlackboard: true`，
> 具体数值到底在哪？—— 答案：**数值不在模板里，在"黑板"（干员天赋/技能定义）里**。

## 1. 三层数值链（核心心智模型）

```
┌─────────────────────────────────────────────────────────┐
│ ① buff_template_data.json    逻辑层：做什么、何时做      │
│    value: 0.0, loadFromBlackboard: true                 │
│    （数值留空，声明"从黑板读"）                          │
└──────────────────────────┬──────────────────────────────┘
                           │ 运行时加载
┌──────────────────────────▼──────────────────────────────┐
│ ② Blackboard（黑板）     临时变量区                      │
│    技能等级 / 天赋阶段 / 潜能 → 决定具体数值             │
└──────────────────────────┬──────────────────────────────┘
                           │ 来源
┌──────────────────────────▼──────────────────────────────┐
│ ③ 数据来源表            数值仓库                         │
│    character_table.json  干员天赋的 blackboard 数组      │
│    skill_table.json      技能每级 levels[].blackboard    │
└─────────────────────────────────────────────────────────┘
```

类比：模板 = "公式"（x 倍攻击），黑板 = "代入的 x 值"，来源表 = "x 值表"。

## 2. blackboard key 的约定（关键）

`attributeModifiers` 里 `loadFromBlackboard: true` 且**没有显式 key** 时，
黑板的 key = **属性名小写**：`ATK → atk`、`DEF → def`、`ATTACK_SPEED → attack_speed`…
（技能里则常用语义化 key：`atk_scale`、`duration`、`cost`…）

## 3. 实证走查：贾维（Chiave，5★先锋）天赋「技工专长」

### ① 模板层（buff_template_data.json / chiave_t_1）
- `ON_BUFF_START` → 条件节点：`CheckContainsDeckBuff`（`_key: "supmech_t[flag]"`）→ 动作：`CreateBuff` 生成 `chiave_t_1[stack]`
- 该 buff：`ATK MULTIPLIER value 0.0 loadFromBlackboard` + `DEF MULTIPLIER value 0.0 loadFromBlackboard`
- `maxStackCnt: -1`（无限叠加）、`overrideType: STACK`（按层叠加）

> ⚠️ **「支援机械」与 `[deck]` 语义的修正（2026-08-31 用户确认）**
> - **支援机械 = 带「支援机械」tag 的一星干员**（已从 character_table 验证，共 8 名）：
>   Lancet-2 / Castle-3 / THRM-EX / 正义骑士号 / Friston-3 / PhonoR-0 / CONFESS-47 / GALLUS²。
>   贾维天赋"场上每有一名【支援机械】干员，攻防+7%"即指这些小车上场数——**常规玩法机制**。
> - 模板中的 `CheckContainsDeckBuff` / `supmech_t[flag]` 与 `[deck]` 变体模板
>   （chiave_t_1[deck] 等 5 个，另见 `notes/12`）的**确切语义待验证**：
>   用户查证 2026 愚人节活动「黑色博士坠落」（变格玩法）中并无贾维/支援机械内容；
>   "deck" 可能是代码层内部机制名或未启用活动数据，**勿再断言为"卡组玩法专属"**。

### ② 数值层（character_table.json / char_349_chiave / talents[0]）
天赋「技工专长」文案：*"场上每有一名【支援机械】干员，自身的攻击力和防御力+7%"*
blackboard（按 精一/精二/潜能4 分 4 个候选）：

| 阶段 | respawn_time | atk | def |
|---|---|---|---|
| 精一 | 0.4（-60%） | 0.07 | 0.07 |
| 精一+潜4 | 0.4 | 0.09 | 0.09 |
| 精二 | 0.25（-75%） | 0.11 | 0.11 |
| 精二+潜4 | 0.25 | 0.13 | 0.13 |

### ③ 合成结果
场上每有一名支援机械 → 叠一层 `chiave_t_1[stack]`：
攻击力 ×(1 + 0.07×层数)、防御力 ×(1 + 0.07×层数)（精二时 0.11）。
与游戏内文案完全一致 ✅

## 4. 技能侧：数值按等级成长（skchr_chiave_2「火焰剥离」）

`skill_table.json` 中技能每级一个 `levels[i].blackboard`：

| LV | cost | atk_scale | magic_resistance | duration |
|---|---|---|---|---|
| 1 | 10.0 | 2.2 | -0.1 | 5.0 |
| 2 | 10.0 | 2.3 | -0.1 | 5.0 |
| 3 | 10.0 | 2.4 | -0.1 | 5.0 |
| 4 | 11.0 | 2.5 | -0.1 | 6.0 |
| … | … | … | … | … |

技能 buff 模板（如 `skill_xxx` 系列）里 `loadFromBlackboard: true` 的节点
读取这些 key → **技能等级决定了最终数值**。

## 5. 查"具体数值"的固定流程

1. 在 `buff_template_data.json` 找到机制模板（读条件/效果）
2. 看 `value` 是否 `loadFromBlackboard` → 若是，记下属性/黑 key
3. **反查引用**：在 `character_table.json`（天赋 talents[].candidates[].blackboard）
   或 `skill_table.json`（levels[].blackboard）里搜对应干员/技能
4. 读 blackboard 数值（注意按阶段/等级/潜能分支）
5. 与游戏内文案（description 字段）交叉验证

## 6. 注意点

- `MULTIPLIER 0.07` 的语义 = ×(1+0.07)，即 **+7%**（见 notes/01 伤害公式乘算区）
- `maxStackCnt` / `overrideType: STACK` 决定能否叠层；`lifeTimeType: INFINITY` 决定持续时间
- description 字段 = 游戏内文案，是**官方人话解释**，可优先阅读再对照模板
- 同一数值可能有多个分支（精英化/潜能/技能等级），模拟时务必取对分支

## 7. 数据文件

- `ak/_raw/gamedata/buff_template_data.json`（逻辑层）
- `ak/_raw/gamedata/character_table.json`（天赋数值：13.6 万字符级…实为 14.8MB，1368 干员）
- `ak/_raw/gamedata/skill_table.json`（技能数值，11.4MB）
- `ak/_raw/gamedata/chiave_trace.json`（本次走查存档）
