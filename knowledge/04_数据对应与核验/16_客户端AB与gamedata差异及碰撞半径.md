# 客户端 AB vs ArknightsGameData：差异清单与碰撞半径提取
> 主题：**04A 取数 / 解包流程**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）
> 层级：**T2（数据/流程整理类（未含强代码证据））**　建立日期：2026-08-31（头部 6 行内日期）　任务：—　｜　**头部为 2026-09-30 自动回填**，推断项已标注

> 2026-08-31 实证。数据源：`E:\__file\ak_kb\client_res\`（客户端资源只读副本，合规）。
> **2026-09-01 更新：备份已全部用国服（CN，V076/26-07-21）资源覆盖**（此前为日服 V072，版本不同步）。
> 结论先行：**gamedata 是数值表（数据层），客户端 AB 是表现层+组件层——大量机制相关组件信息只有客户端有。**

## 1. 客户端 AB 有而 gamedata 没有的信息

| 类别 | bundle 数量 | 内容 | 对模拟的价值 |
|---|---|---|---|
| **battle/**（prefab、enm_pfb_0~30） | 585 | **敌人/干员 GameObject 组件树**、碰撞体（CircleCollider2D/CapsuleCollider2D）、HitPoint/Combat/Skills/Talents/SpecialPoint 锚点 | ⭐⭐⭐ 碰撞半径、攻击判定点、阻挡逻辑 |
| **charpack/**（char_xxx） | 440 | 干员本体 prefab（Body/Attack/Direction/Trigger/Modes…+ 碰撞体） | ⭐⭐⭐ 干员碰撞半径 |
| **prefabs/** + battle/prefabs/[uc]* | 12+ | 弹道/技能/全局 buff/装备 prefab（[uc] 前缀暂未取得） | ⭐⭐ 弹道与技能表现组件 |
| arts/ + chararts/ + spritepack/ | 854 | 立绘/Spine 动画/贴图/特效 | ⭐ 表现层 |
| audio/ | 54 | 语音/音效 | 低 |
| ui/ + scenes/ + shaders/ | 475 | 界面/场景/着色器 | 低 |

## 2. 碰撞半径提取（已实证流程）

- 干员：`charpack/char_xxx.ab` → GameObject 根 → **CircleCollider2D.m_Radius**（单位=格）
  - 例：**贾维（char_349_chiave）m_Radius = 0.25**
- 敌人：`battle/enm_pfb_N.ab`（31 块）→ 60 个敌人/块
  - 例：enm_pfb_0 中 CircleCollider2D 半径 0.1 / 1.0 / 1.5；CapsuleCollider2D 0.2×0.4（offset -0.1）
- 脚本：`ak/scripts/inspect_prefab.py`（GameObject 树 + Collider + MonoBehaviour 引用）

## 3. 本轮已解出的资源（2026-08-31）

| 文件（ak_kb\client_res） | 内容 | 状态 |
|---|---|---|
| buff_template_holder.ab | buff 模板数据（键+JSON 段，与 gamedata 一致） | ✅ |
| battle_pack_common.ab | 战斗界面 UI | ✅ |
| config_common.ab | 界面配置 MonoBehaviour | ✅ |
| char_349_chiave.ab | 贾维 prefab（碰撞 0.25 + 组件树） | ✅ |
| char_1012_skadi2.ab | 斯卡蒂2 prefab（Body/HealAura/S1S2S3…） | ✅ |
| enm_pfb_0.ab | 60 个敌人 prefab + 碰撞体（0.1~1.5） | ✅ |
| hot_update_list(.json/.runtime) | bundle 清单（2708 项） | ✅ 已分析 |

## 4. 暂不尝试（失败项，按用户要求登记）

- `battle/prefabs/[uc]*`（projectiles/globalbuffs/skills/equips 等）：路径含 `[uc]` 特殊字符，备份失败 → **暂不尝试**
- MonoBehaviour 脚本类名解析：脚本定义在跨 bundle 的 MonoScript 中 → **暂不尝试**
- manifest.idx：加密/二进制索引，无直接用途 → **暂不尝试**

## 5. 后续可快速扩展

- 批量备份 charpack（440 个）→ 提取全部干员碰撞半径表
- 备份 enm_pfb_1~30 → 全部敌人碰撞半径
- 需要时解决 `[uc]` 路径问题（URL 编码 / 转义）后再取弹道/技能 prefab

## 6. 全量组件提取完成（2026-09-01，国服 V076）

- **全部备份**：charpack 458 个（10.7MB）+ enm_pfb 35 块（12.3MB）→ `client_res\charpack\`、`client_res\enm_pfb\`
- **碰撞半径全表**：`downloads\collider_report.json`（`scripts\extract_colliders.py` 生成）
  - **干员**：458 个全部主碰撞体 = CircleCollider2D **半径 0.25**（特殊形态另有 0.8~1.7 等）
  - **敌人**：★**2026-09-15 以"逐敌 GameObject 根上的 Collider2D"重测（口径更正）** —— **2123 个敌人**（38 个 bundle 全解析成功）的实测分布为：
  - **`0.1`：2070 个（97.5%）**、`0.09`：1、`0.25`：6、`0.3`：18、`0.35`：1、`0.4`：2、**`1.48`：2**（`enemy_2119_dyshhj*`）
  - ⇒ **原作中"敌人受击半径≈0.1"几乎是普遍实情**，仅极少数例外；
  - ⚠️ **旧记录（0.1/0.5/1.0/1.5/2.0/2.5/3.0…，计数上千）口径有误**：那是把 **非敌人对象/子树/胶囊体**一并计入的结果，**不能用于"逐敌半径"**；
  - 数据与可复现脚本：**`ak/data/derived/enemy_colliders.json`**、**`ak/scripts/export_all_enemy_radii.py`**（UnityPy + `scripts/ak_lz4ak.py` 的 LZ4AK 解压器）。

## 7. 组件层 ↔ 伪代码层互动抽样（enemy_sfden_invisible 隐身敌人）

```
组件层：CircleCollider2D（碰撞半径，如 0.5）──物理──▶ 与干员碰撞体(0.25)发生阻挡判定
    │
    ▼ 阻挡状态变化
伪代码层：ON_OWNER_BLOCKEE_CHANGED / ON_BUFF_START 事件触发
    │
    ▼ CheckBlocked（条件节点）
    ├─ 被阻挡 → FinishDerivedBuff → 结束隐身
    └─ 未阻挡 → CreateBuff(abnormalFlags: [INVISIBLE]) → 隐身状态
    │
    ▼ overrideEffectKey: common_invisible
组件层：SpriteRenderer 等表现组件切换（隐身穿透/显形）
```

**这就是模拟计算所需的完整闭环**：碰撞体（组件）→ 阻挡物理 → 事件 → 伪代码行为 → 表现（组件）。
同类联动：攻击锚点（Attack/Direction/Arrow 子物体）→ TriggerAbility/EmitProjectile 节点；
SpecialPoint（出手点）→ 弹道起点；碰撞半径 → 寻路/阻挡/位移判定。
