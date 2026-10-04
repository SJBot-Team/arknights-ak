# 如何阅读 buff_template 表（完整指南）

> 数据：`ak/_raw/gamedata/buff_template_data.json`（27MB，8314 个模板，2026-08-18 版本）
> 配套：`buff_table.json`（buff 索引）、`buff_stats.json`（统计报告）、`ak/scripts/analyze_buff_table.py`（统计脚本）
> 前置：先读 `notes/11_数据结构入门_buff与prefab.md`

## 1. 先鸟瞰：整张表有多大、怎么不迷路

- **8314 个模板**、**102 种事件**、**1121 种节点类**。
- 模板 id（templateKey）按**前缀**分类，这就是第一层索引：

| 前缀 | 数量 | 含义 |
|---|---|---|
| `enemy_*` | 2485 | 敌人技能/机制（如 `enemy_hymwr_t`） |
| `trap_*` | 543 | 陷阱/装置（如 `trap_450_icetea`） |
| `rogue_*` | 335 | 肉鸽（集成战略）藏品/效果 |
| `sandbox_*` | 205 | 沙盘模式 |
| `legion_*` | 195 | 军团模式 |
| `halfIdle_*` | 149 | （挂机？） |
| 干员缩写 | 各 20~50 | 如 `chiave_t_1`（贾维）、`blaze2_*`（煌2）、`kalts2_*`（凯尔希2） |
| `damage_*` / `dragon_fire` 等 | 少量 | 通用机制 |

> 查机制时：先猜前缀（干员名/敌人名/机制名）→ 再在表里搜。

## 2. 一个模板只有 4 个顶层字段（解剖一行）

每个模板固定只有 4 个字段，**全部模板都有**：

```jsonc
{
  "templateKey": "chiave_t_1",        // ① 模板 id（整表的 key）
  "effectKey": "",                    // ② 效果名（多为空，日志用）
  "onEventPriority": "DEFAULT",       // ③ 事件优先级（DEFAULT 占 99%；特殊机制才改）
  "eventToActions": { ... }           // ④ 核心：事件 → 动作列表
}
```

所以"读表"= 读 `eventToActions`：**什么事件发生 → 依次执行哪些动作**。

## 3. 事件词汇表（102 种，先记核心 12 个）

| 事件 | 含义 | 出现次数 |
|---|---|---|
| `ON_BUFF_START` | buff 生效时（最常用） | 4429 |
| `ON_BUFF_TRIGGER` | buff 周期性触发时 | 1993 |
| `ON_BUFF_FINISH` | buff 结束时 | 1355 |
| `ON_TAKE_DAMAGE` | 承受伤害时 | 612 |
| `ON_OWNER_FINISH` | 拥有者退场时 | 240 |
| `ON_OUTPUT_DAMAGE` | 造成伤害时 | 233 |
| `ON_OWNER_KILLED` | 拥有者被击杀时 | 202 |
| `ON_CALCULATE_DAMAGE` | 伤害结算过程中 | 195 |
| `ON_APPLIED_MODIFIER` | 被施加属性修改时 | 125 |
| `ON_SKILL_START` / `ON_SKILL_FINISH` | 技能开启/结束时 | 115 / 94 |
| `ON_OWNER_BORN` / `ON_OWNER_POST_BORN` | 出场时 | 44 / 24 |

其余按需查 `buff_stats.json` 的 `events` 段。

## 4. 节点词汇表（1121 种，分三类理解）

### 4.1 控制流（if / else / 顺序）
| 节点 | 含义 |
|---|---|
| `IfElse` | 条件分支（最常用，2174 次） |
| `IfNot` | 条件取反 |
| `AlwaysNext` | 无条件继续（顺序执行） |
| `IfConditions` | 多条件组合 |
| `Dice` | 概率判定 |

### 4.2 条件判断（Check / Filter / Is）
| 节点 | 含义 |
|---|---|
| `CheckContainsBuff` | 检查是否持有某 buff |
| `CheckBlocked` / `CheckTargetInRange` | 是否阻挡 / 目标在范围内 |
| `CheckAbnormalFlag` | 是否处于某异常状态 |
| `FilterByBlackboardValue` / `FilterByTargetHpRatio` | 按变量 / 血量比例过滤 |
| `IsDamage` / `IsHeal` | 判定伤害/治疗类型 |
| `CheckUnitAlive` / `CheckUnitCurrentMode` | 存活 / 当前形态 |

### 4.3 行为动作（Create / Apply / Damage / Modify）
| 节点 | 含义 |
|---|---|
| `CreateBuff` / `CreateBuffById` / `CreateBuffInRange` | 创建 buff（核心动作） |
| `FinishBuff` / `FinishBuffsById` | 结束 buff |
| `AdvancedApplyDamage` / `FixedValueDamage` / `DamageViaMaxHpRatio` | 造成伤害（高级/固定值/按最大生命） |
| `AOEDamage` / `EmitProjectile` | 范围伤害 / 发射弹道 |
| `AtkScaleUp` / `DamageScale` / `BlockDamage` | 攻击力放大 / 伤害缩放 / 抵挡伤害 |
| `ModifySp` / `ModifyCost` | 修改技力 / 部署费用 |
| `TriggerAbility` / `TriggerEnemySkill` | 触发技能 |
| `InstantKill` | 直接击杀 |
| `SwitchMode` | 切换形态 |
| `CreateEffect` | 创建表现特效（不参与数值） |
| `PlayAudio` / `LogExtraBattleInfo` | 音效 / 日志（可忽略） |

> 完整列表见 `buff_stats.json` 的 `nodes` 段。**认识节点=认识游戏的"指令集"**，看多了自然熟。

## 5. 属性修改器：与伤害公式的接口

`CreateBuff._buff.attributes.attributeModifiers` 里的三要素：

- `attributeType`（改哪个量）：ATK(237)、ATTACK_SPEED(107)、DEF(91)、MAX_HP(76)、MOVE_SPEED(71)、MAGIC_RESISTANCE(35)、SP_RECOVERY_PER_SEC(29)、BLOCK_CNT(23)、DEF_PENETRATE、MASS_LEVEL（重量）、TAUNT_LEVEL（嘲讽）……
- `formulaItem`（怎么改，4 种运算）：`MULTIPLIER`（乘算，360）、`ADDITION`（加算，314）、`FINAL_SCALER`（最终乘算，65）、`FINAL_ADDITION`（最终加算，17）
  → 对应伤害公式的**加算区 / 乘算区 / 最终区**（见 `notes/01`）
- `value`（数值）：可为固定值或 `loadFromBlackboard: true`（从"黑板"变量取，如技能等级成长值）

**Blackboard（黑板）**：buff 机制里大量出现的概念——模板执行时的"临时变量区"（技能等级、充能层数、目标选定结果等都放这里），`AssignValueToBB` / `BlackboardAdd` / `FilterByBlackboardValue` 等节点读写它。可以理解为**函数内的局部变量**。

## 6. 完整例子精读

### 例 A：`chiave_t_1` —— 纯属性型（最简单）

```jsonc
"eventToActions": {
  "ON_BUFF_START": [                       // buff 一生效就做：
    { "$type": "…+CheckContainsDeckBuff", "_key": "supmech_t[flag]" },  // ①条件：是否已有"支援机械"标记
    { "$type": "…+CreateBuff", "_buff": {  // ②动作：创建属性 buff
        "attributes": { "attributeModifiers": [
            { "attributeType": "ATK", "formulaItem": "MULTIPLIER", "value": 0.0, "loadFromBlackboard": true },
            { "attributeType": "DEF", "formulaItem": "MULTIPLIER", "value": 0.0, "loadFromBlackboard": true } ] },
        "buffKey": "chiave_t_1[stack]",
        "overrideType": "STACK", "maxStackCnt": -1,   // 可无限叠加
        … } }
  ]
}
```
读法：**生效时若已有标记 → 给自身叠一层 攻防加成**（数值从黑板取）。注意 `ON_BUFF_START` 列表里的两个动作是"先条件后动作"的隐式顺序——没有 `IfElse` 时，条件节点失败会中断后续。

### 例 B：`damage_block[all]` —— 单事件单动作（抵挡伤害）

```jsonc
"ON_TAKE_DAMAGE": [ { "$type": "…+BlockDamage" } ]
```
读法：**承受伤害时 → 抵挡伤害**（格挡/护盾类机制的通用模板）。

### 例 C：`enemy_hymwr_t` —— 事件驱动 + 嵌套（见 notes/11）

读法：**承受伤害时 → 若还没有标记 → 挂上标记**（标记型机制：首次受伤触发一次，之后不再触发）。

## 7. 阅读方法论（从"游戏机制"到"模板"的查询路径）

1. **定位关键词**：机制名/干员名/敌人名/效果类型（如"眩晕""反伤""藏品"）→ 猜 `templateKey` 前缀
2. **快速搜索**：`python -c "import json; d=json.load(open(r'ak\_raw\gamedata\buff_template_data.json',encoding='utf-8')); print([k for k in d if '关键词' in k][:20])"`
3. **读 eventToActions**：先列事件（何时触发）→ 再按序读动作（条件→行为）
4. **追踪引用**：`CreateBuff._buff.buffKey` 里的 `[xxx]` 后缀是"变体"；`templateKey: "empty"` 表示该 buff 无自身模板，纯靠属性
5. **对照实测**：把读到的逻辑与游戏内表现/PRTS 描述比对，不一致再深挖

## 8. 常用查询脚本（ak/scripts/analyze_buff_table.py 之外）

```python
import json
D = json.load(open(r"ak\_raw\gamedata\buff_template_data.json", encoding="utf-8"))
# 按模板 id 查
print(json.dumps(D.get("enemy_hymwr_t"), ensure_ascii=False, indent=1))
# 模糊搜
print([k for k in D if "眩晕" in k or "stun" in k])
```
