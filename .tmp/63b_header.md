# 63b 官方对应检索报告（ArknightR ↔ 官方 Torappu）

> 父文档：`63_ArknightR架构与三例贯通.md`｜证据细目：`63a_ArknightR调用链IL证据细目.md`
> 本文件 = **主会话（AK 知识库会话）交叉核验头** + **子代理原始检索报告全文**（下半部分起）。
> 只读资源：`E:\__file\ak_kb\client_res\il2cpp\dump\dump.cs`（2,030,835 行）+ `GameAssembly.dll`（ImageBase `0x180000000`）。**未访问 `D:\YostarGames\`**。

---

## 〇、交叉核验与勘误（**主会话追加，优先于下文**）

### 0.1 ★ 必须纠正的一条过度声明：帧长常量

子报告 §A7 与 `63` 初稿都提到 ArknightR `SystemConfig.DeltaTime` 与官方常量对得上。**精确结论应当是**：

| 事实 | 证据 | 判定 |
|---|---|---|
| ArknightR `SystemConfig.get_DeltaTime()` 返回 `ldc.r4 0.016666668`（写死在 IL 里） | `mono_il --dis SystemConfig::get_DeltaTime` | ✅ |
| 官方 `Torappu.Battle.Consts.DELAY_SINGLE_FRAME = 0.016666668`（**编译期 const**） | dump.cs **行 294501** | ✅ 二者**数值逐位相同** |
| 官方**运行期步长**不是这个常量，而是 `UnityEngine.Time.fixedDeltaTime`（`GlobalConsts..cctor` @RVA `0x54E4D50`：`call Time.get_fixedDeltaTime()` → `×0.5` → `HALF_FIXED_DELTA_TIME`；`×2^32` → `FIXED_DELTA_TIME_FP` Q32.32） | 子报告 §A7 反汇编 | ✅ |

> ⇒ **正确表述**：「ArknightR 把步长**写死**成 `1/60`，这个数值与官方的一个常量 `DELAY_SINGLE_FRAME` 逐位相同；但**官方运行期步长取自 Unity 工程设置**，二者是否相等取决于工程配置，**不能由常量相同推出运行期步长相同**。」
> ⇒ 因此 `63` §3.1 第 1 条**由「数值级 ✅」降级为「常量数值级 ✅ + 运行期来源不同 🟡」**。这是本次最容易出错的一处，记在此以防后续会话误引。

### 0.2 ★ 本次最强的三条对应（子报告已给，此处提级）

| ArknightR | 官方 | 判据 | 为什么最强 |
|---|---|---|---|
| `DamageInfo` | **`Torappu.Battle.Modifier`（struct，行 352478）** | 字段/结构级：`Source↔m_source`、`Target↔m_target`、`FinalDamage↔m_value`、`Attack↔originAtk`、`ShowCrit↔isCritical`、`Avoid/ForbidAvoid↔ignoreMissFlag(DamageTypeMask)`、`NoFatal↔DAMAGE_IS_UNDEADABLE_THIS_TIME` | **7+ 字段逐一对照**，且有 22 个 flag 常量；比 `AttackInfo` 强（`AttackInfo` 只是它的输入） |
| 逻辑↔视图绑定点 | **`MountPoint`（行 352938）**：`m_transform //0x10` + `m_entity(ObjectPtr<Entity>) //0x18` | 字段/结构级：一个对象同时持有**视图 Transform** 与**逻辑 Entity** 并暴露 `mapPosition/worldPosition/gridPosition/height/faceTo` | 直接回答了"官方怎么把逻辑接到图形层" |
| 属性修正聚合器 | **`Attributes`（行 319487）**：`m_attributeModifiers : HashSet<IAttributesModifier>[] //0x18`、**`m_dirtyMask : long //0x60`** | 字段/结构级 | 官方**有脏标记位图**；ArknightR 是**每 tick 全量重算**（`63a` §1.5）⇒ 这是两者性能/正确性模型的根本差异 |

### 0.3 ★ 主会话补充的两条**机制差异**（子报告未展开，但影响复刻）

1. **5% 保底**：官方物理伤害有 `MIN_ATK_FACTOR = 0.05`（`BattleFormula..cctor` @`0x3586D00` 实测 `movss [0x5D66D54]`→FP），即
   `dmg = max(FinalAtk − max(0, def − DefIgnoreFixed)×(1 − DefIgnoreRate), **FinalAtk × 0.05**)`。
   而 ArknightR `Unit::se3` 的两条分支（`63a` §2.3，IL 原文）**只做 `Max(atk*scale, atk-def)` 与负值钳 0，没有 `FinalAtk×0.05` 的保底项** ⇒ **这是 ArknightR 与官方的一处真实数值差异**，复刻时**不能**照抄 ArknightR。
2. **伤害类型枚举值不对应**（实测 Constant 表）：

   | ArknightR `DamageTypeEnum`（TD53） | 值 | 官方 `DamageType`（行 311985） | 值 |
   |---|---|---|---|
   | `Normal` | **0** | `PHYSICAL` | **1** |
   | `Magic` | **1** | `MAGICAL` | **2** |
   | `Real` | **2** | `PURE` | **3** |
   | `Element` | **3** | `HEAL` | 4 |
   | — | — | `ELEMENT` | **5** |

   ⇒ **成员语义一一对应，但数值整体错位**（ArknightR 0-based 且把 `HEAL` 走 `DamageInfo.IsHeal` 布尔另开一路，官方是枚举里的独立值）。任何"按枚举整数直接对照"的做法都会错。
   （ArknightR 侧另有 `StateEnum{Move=0,Die=1,Attack=2,Idle=3,Default=4,Start=5,Stun=6}`、`DirectionEnum{Up=0,Down=1,Left=2,Right=3}`、`UnitTypeEnum{无=0,先锋=1,近卫=2,狙击=3,重装=4,术士=5,辅助=6,医疗=7,特种=8}` — 判据：`enumvals.py` 读 Constant 表。）

### 0.4 ★ 最重要的一条否定结论（对知识库目标影响最大）

**官方客户端没有"表字段 = 类名 → 反射实例化"这一套**（子报告 §H，否定证据 3 条：`Activator.CreateInstance` 24 处全在 UI/网络层、战斗层 0 处；`Type.GetType(string)` 仅 3 处且只服务 JSON 反序列化；`buff_type` 0 命中）。
官方实际是 **1310 个 `Nodes.* : ActionNode` 子类 + `Blackboard` 数据对 + `ActionNode.Execute(Blackboard, SourceType, ref Snapshot)` + 枚举 switch**。

> ⇒ **对 `40`/`63` 的工程建议必须加一句限定**：「`Type` 列 = 类名反射」是 **ArknightR 的工程范式**，可以作为**我们自建工具**的设计参考，但**它不是官方机制**，因此**不能**用它去反推官方 gamedata 的字段语义（不能假设 `buff_type` 里有类名）。官方侧的等价物是 `BuffData.buffKey`/`templateKey` → `Blackboard` → `ActionNode` 树。

### 0.5 子报告需谨慎处的登记

| 位置 | 问题 | 处理 |
|---|---|---|
| 子报告 §G 末注（dump.cs 323939/323942/323948） | 行号→类解析器把这几行归给 `Buff.BuffContainer`，子代理自评"语义可疑" | ✅ 已按其自评**不作结论引用**；后续若要引用须先人工确认类归属 |
| 子报告 §E2「拉/推混合」 | 只到"字段 + 调用链"层，未反汇编 `Enemy.OnTick`/`_MoveToBlockPosition` 写 Transform 的确切位置 | 🟡 保留为待查（`63` §5 已登记） |
| 子报告 §A7 末尾 | `xref OnTick/FixedUpdate` 双双 0 命中 ⇒ 静态调用链到此为止 | 🔴 已登记为卡点（需动态 hook 或 `DelegateBridge` 注册点反查） |
| 子报告环境说明 | 子代理实测时走了 `课设\comp_physics\.venv` 的 python；主会话侧实测该 venv 无 pefile，改把 `pefile/capstone` 装进了 Anaconda python（`PYTHONUTF8=1` 后 pip 才不报 GBK 错） | ✅ 两条路径现均可用；环境变更已登记 |

---
---

# 以下为子代理原始检索报告全文

