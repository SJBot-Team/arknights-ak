# 数据结构入门：buff 模板表 / Prefab / 代码层（面向物理本科背景）

> 依据：调零 2026-08-31 指导（`notes/10`）；真实数据取自
> [Kengxxiao/ArknightsGameData](https://github.com/Kengxxiao/ArknightsGameData)（`zh_CN/gamedata/`，2026-08-18 版本）。
> 目的：建立"明日方舟机制在数据里长什么样"的整体图景，并明确哪些需要主理人学习、哪些由 AI 代劳。

## 0. 三层总览（先看图景）

明日方舟的"机制"由三层承载，从易到难：

| 层 | 载体 | 类比（物理实验） | 谁来掌握 |
|---|---|---|---|
| **数据表** | `gamedata/` 下大量 JSON（buff/skill/character/stage…） | 实验方案、配方表、参数表 | **你（重点）+ 我** |
| **Unity 资源** | AssetBundle 里的 Prefab + 组件 | 实验装置清单、乐高拼装 | 你（概念）+ 我 |
| **原生代码** | il2cpp 编译出的二进制（IDA 反编译） | 仪器内部电路/固件（黑盒） | **我代劳** |

游戏运行时 = 引擎读表 + 实例化 Prefab + 代码驱动。**绝大多数机制都写在表里**；
查不到或对不上时，才需要进代码层。

## 1. buff_template 表 —— "规则引擎的规则库"（核心，需掌握 ⭐）

### 1.1 一句话理解
> 战斗里的任何"效果"（干员技能、敌人技能、藏品、地板、异常状态…）底层都是
> **buff**：一个"挂载在目标上、按事件触发、修改状态"的规则包。
> buff_template 表就是这些规则的仓库，**一行 = 一个模板**。

类比：就像你写模拟程序时的 `if 事件 then 改状态` 规则，只是游戏把它做成了
**数据表**——策划改表就能改机制，不用改代码。

### 1.2 真实结构（取自 `zh_CN/gamedata/battle/buff_template_data.json`）

```jsonc
"enemy_hymwr_t": {              // ← 模板 id
  "templateKey": "enemy_hymwr_t",
  "onEventPriority": "DEFAULT",
  "eventToActions": {           // ← 核心：事件 → 动作 映射表
    "ON_TAKE_DAMAGE": [         //   事件："当目标承受伤害时"触发
      { "$type": "Torappu.Battle.Action.Nodes+CheckContainsBuff, Assembly-CSharp",
        "_targetType": "BUFF_OWNER",
        "_buffKeys": ["enemy_hymwr_t[mark]"] },   // 动作① 条件：检查是否已有标记
      { "$type": "Torappu.Battle.Action.Nodes+IfNot, Assembly-CSharp" },  // 动作② 条件：若没有
      { "$type": "Torappu.Battle.Action.Nodes+CreateBuff, Assembly-CSharp",
        "_buff": { /* 嵌套一个完整 buff 定义 */ } }   // 动作③ 行为：创建标记 buff
    ]
  }
}
```

要点：
- **事件**（`ON_TAKE_DAMAGE`、`ON_ATTACK`、`ON_BEING_HIT`…）：像"触发器/中断信号"。
  完整事件名表可在数据中检索（`ON_` 前缀）。
- **动作节点**：像 Simulink/LabVIEW 的积木块，带参数（`_targetType` 打谁、
  `_buffKeys` 引用哪个 buff、`_damageMask` 伤害类型掩码…）。一串动作 = 顺序执行的
  **伪代码** —— 这就是调零说的"**node 伪代码系统**"。
- 节点类型是 C# 类（`Torappu.Battle.Action.Nodes+CreateBuff`）→ 与代码层对应。

### 1.3 属性修改器（buff 最常见的"效果"）

```jsonc
"attributeModifiers": [
  { "attributeType": "ATK",          // 改哪个属性：攻击力
    "formulaItem": "MULTIPLIER",     // 怎么改：乘算（百分比加成）
    "value": 1.0 }                   // 数值：+100%
]
```

- `attributeType`：ATK / DEF / ATTACK_SPEED / MAX_HP / MOVE_SPEED…
- `formulaItem`：ADDITION（加算）、MULTIPLIER（乘算）、FINAL（最终乘算）…
  —— **正好接上 `notes/01_数据基础` 的伤害公式**（加算区/乘算区）。
- 每个 buff 还有：`lifeTime`（持续时间）、`maxStackCnt`（最大叠加层数）、
  `abnormalFlags`（异常状态：眩晕/冻结/浮空…）、`isSilenceable`（可被沉默）等。

### 1.4 为什么你要掌握这张表（学习动机）

- PRTS 的技能描述 = 这张表的"翻译"，翻译**可能不完整**；
  精确的触发时机、判定顺序、叠加规则要查表才有原话。
- 以后"模拟结果 vs 游戏实际"对不上时，查表定位是第一步。
- 建议方法：挑一个熟悉的干员技能，把它的技能 buff 模板完整读一遍（我可带你做）。

## 2. Unity Prefab + Monobehaviour —— 物体的"拼装说明书"（概念需懂）

- 场景里每个对象（干员/敌人/子弹/地板）是一个 **GameObject（游戏对象）**。
- GameObject = 一堆**组件（Component）**拼成：
  - `Transform`（位置/旋转/缩放）
  - `Collider`（碰撞体，**碰撞半径在这**）
  - 各种 **Monobehaviour**（C# 脚本组件，挂载在物体上，如"抛射物""追踪"逻辑）
- 调零说"Monobehaviour 拼拼乐"：一个机制 = 若干组件组合出来。
- 工具：**arknights assets studio**（明日方舟特供版 AssetStudio）提取浏览资源。
- 需求场景：查碰撞半径、干员普攻弹道、攻击范围可视化。

**掌握程度**：只需"组件 = 物体的属性/行为块，参数在组件里"这个心智模型；
具体字段含义按需一起查。

## 3. cpp / il2cpp（IDA）—— 代码层（我代劳）

- 明日方舟用 **il2cpp** 把 C# 逻辑编译成原生机器码（`Assembly-CSharp` 等）。
- 看机制细节 = 用 **IDA** 反编译定位函数。
- 调零的学习路径把它放在最后；对我们目标（复刻已研究清楚的机制、伤害计算）
  **初期基本用不到**——buff 表 + prefab 已覆盖绝大多数。

## 4. 地图数据 —— 影响比机制更大（概念需懂）

- 关卡 = **格子地图**（瓦片类型：可部署/不可部署/高台/地板效果/特殊地形）
  + **波次**（敌人阵容/时间轴）+ **敌人配置** + **行动路线**。
- 调零："很多地图的数据远比机制更影响各种东西"。
- ⚠️ 注意：舟数据中的 `黑流树海地图构造.xlsx` 指**肉鸽（集成战略）关卡之间的连接关系**（节点/路线网络），**不是关卡内地图（格子/波次）数据**；两者不要混淆。关卡内数据以解包 `stage_table.json` / 关卡文件为准。

## 5. 数据源（随版本更新）

[Kengxxiao/ArknightsGameData](https://github.com/Kengxxiao/ArknightsGameData) `zh_CN/gamedata/`：

| 路径 | 内容 | 大小 |
|---|---|---|
| `battle/buff_template_data.json` | **buff 模板总表（本笔记核心）** | ~27 MB |
| `buff_table.json` | buff 总表（引用索引） | 172 KB |
| `excel/character_table.json` | 干员（属性/天赋/技能引用） | ~15 MB |
| `excel/skill_table.json` | 技能定义 | ~11 MB |
| `excel/stage_table.json` | 关卡 | ~20 MB |
| `excel/enemy_handbook_table.json` | 敌人图鉴 | ~1.8 MB |

> 注：该仓库是社区解包整理；游戏客户端本体才是最终权威（后续解包任务涉及）。

## 6. 学习分工（明确）

**【需要你积累学习（用于与游戏内容比对验证）】**
1. buff 模板的字段语义：事件 / 条件 / 动作 / 属性修改器（含加算乘算与伤害公式的衔接）
2. Prefab/组件的心智模型
3. 地图数据（格子/波次/路线）的读法

**【我代劳（你简要了解即可）】**
1. 工具链操作（贝娜量角器 / arknights assets studio / IDA 的使用）
2. il2cpp 逆向、反编译分析
3. 解包技术细节、批量数据抓取与处理、模拟代码实现
