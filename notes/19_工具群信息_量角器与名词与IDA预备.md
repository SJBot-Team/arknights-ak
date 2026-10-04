# 工具群信息：贝娜量角器 + 基础名词 + IDA/il2cpp 预备（2026-09-02）

## 一、贝娜量角器（已找到并应用）

- **位置**：`E:\QQ\贝娜的量角器 2026.3.26.zip`（已解压到 `E:\__file\ak_kb\downloads\量角器\`）
- **原理**：buff 伪代码→中文翻译器。核心 = 字典：
  - `anne_dictionary.json`（358 行）：target/event/abnormal/attribute/element/formula/
    damage_type/compare/sp_type/unit_type/side_type/finish_reason 等**全枚举→中文**
  - `bena_dictionary.json`：buff 名前缀翻译（活动/干员代号）
- **用法**：读 buff 模板 → 按字典把枚举替换成中文 → 可读伪代码
- **已应用**：`ak/scripts/translate_buff.py`（字典驱动的自动翻译器）——实测 chiave_t_1 /
  enemy_sfden_invisible 输出流畅中文伪代码（"当Buff开始时→检查是否被阻挡→创建Buff(隐匿)"）
- **附带解决**：element 枚举 **DARK=凋亡**（此前 K-013 搜"凋亡"失败的原因）

## 二、基础名词（工具群提供，必学；与字典相互印证）

| 名词 | 含义 | 对应字典/代码 |
|---|---|---|
| **黑板** | Buff 机制里存数据的"局部变量区"；技能/特性以黑板传参给 Buff | Blackboard（notes/12、13） |
| **能力** | 技能/特性/特质/部分藏品特效的统称 | `Torappu.Battle.Abilities.*`（1cc3 脚本：MeleeAttack/UberEffectEmitter/GlobalAuraAbility） |
| **调整值** | 对生命/技力/费用/目标生命的修改实例：一次伤害、+1SP、-3费都是调整值 | Modifier（字典 modifier_target_type: HP/SP/COST/LIFE_POINT/EP） |
| **角色类单位** | 干员、召唤物、装置（部署地面、通常不移动） | unit_type: CHARACTER |
| **敌人类单位** | 敌人、乌萨斯平民、自走车、心烛等移动单位 | unit_type: ENEMY（+PROJECTILE 弹道类） |

> 注：1cc3.bin 脚本名与名词对照——`Torappu.Battle.Abilities.MeleeAttack` = 干员"能力"组件、
> 群名词"调整值"即 JSON 里的 `_modifier`/伤害实例 → 名词体系贯穿三层。

## 三、IDA / il2cpp 预备（任务 2：资料同步）

### 背景（调零共识）
阻挡相关机制只能从 il2cpp 入手；看 IDA = 逆向 il2cpp 编译的原生代码。

### 前置知识
1. 明日方舟用 **il2cpp** 把 C#（Assembly-CSharp → Torappu.*）编译成原生代码（libil2cpp.so / il2cpp 元数据）
2. 需要两样东西：**代码本体**（il2cpp 二进制）+ **元数据 global-metadata.dat**（类/方法/字段的符号表）
3. IDA 是反汇编/反编译工具；先 dump 符号 → 再在 IDA 里定位函数 → 读逻辑

### 简单工具（初步搜集）
| 工具 | 用途 |
|---|---|
| **Il2CppDumper**（Perfare，经典） | il2cpp dump：输入 libil2cpp + global-metadata → 输出 C# 伪代码结构（类/方法/字段） |
| **IL2CPP-Dumper**（DeftSolutions-dev，111★） | 新版单 exe 运行时 dump（Windows x64，为终末地做但通用） |
| **Il2CppInspector** | 解析元数据 + 生成 IDA 脚本（帮助 IDA 识别类型） |
| **IDA Pro** | 反编译（调零推荐；社区有便携版） |
| **1cc3.bin**（调零已给） | 脚本类名定义（MonoScript），配合 prefab 解析——已实证 |

### 典型流程（待调零细讲后实践）
1. 提取 `libil2cpp.so` + `global-metadata.dat`（从客户端/更新包）
2. Il2CppDumper dump → C# 结构伪代码
3. IDA 打开 libil2cpp，用 dump 结果定位类/方法
4. 由字段/方法名（如 CheckBlocked、BlockDamage）反查机制实现

### 参考链接
- [Il2CppDumper（Perfare）](https://www.repoportal.com/en/perfare-il2cppdumper)、[Il2CppDumper 详解实战](https://blog.csdn.net/weixin_28836989/article/details/163147584)
- [Unity 手游逆向：Il2CppDumper 解析定位](https://blog.csdn.net/weixin_29015483/article/details/162186951)
- [明日方舟 修改教学 (HOOK) - 52pojie](https://www.52pojie.cn/forum.php?mod=viewthread&tid=1007314)
- [IDA + il2cpp API 动态调用](https://blog.csdn.net/weixin_33709219/article/details/85592651)
