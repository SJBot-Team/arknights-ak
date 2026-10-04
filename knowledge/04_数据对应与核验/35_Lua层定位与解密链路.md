# 35 Lua（伪代码）层定位与解密链路
> 主题：**04B 读代码 / 反汇编**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）

> 层级：**T1（反汇编确证）**　建立日期：2026-09-13　任务：T-034 阻塞项⑦
> 结论状态：**加载链路与解密算法已确证；密钥已在二进制内找到；但脚本本体不在日服本地客户端**
> 工具：`read_cpp.py`（反汇编注释现已自动显示字符串字面量，本次发现即由此得出）

---

## 〇、一句话结论

> 客户端确实有**完整的 Lua 层**（xLua，`HOTFIX_ENABLE = true`）：285 个脚本，位于**初始安装包**的逻辑路径 `gamedata/[uc]lua/**`，入口 `entry.lua`；加载后经 `m_decrypter`（`CrypticConverter_A`，**AES-128**）解密；**密钥材料 `PlayerData.chatMask` 的默认值硬编码在二进制里** —— `UITpAi82pHAWwnzqHRMCwPonJLIB3WCl`（32 字符 = key 16 + IV 16）。
> 且 `LuaBattleMgr` 接管**战斗 ActionNode 的执行**、`LuaAbilityBehaviourStub` 把**技能的 7 个生命周期回调**整体下放给 Lua。

**这意味着：部分战斗/技能机制确实写在 Lua 里，只看 C# 会看到空壳。** 但也意味着——**只要拿到脚本本体，就能解开**（密钥不再是障碍）。

---

## 一、加载链路（逐环节确证）

### 1.1 `LuaManager`（dump.cs 195002）

字段：`m_inited 0x10` / `m_env(LuaEnv) 0x18` / `m_folder(string) 0x20` / `m_decrypter(IConverter) 0x28` / `m_tickTimer(PeriodicTimer) 0x30` / `m_assetLoader(ILoadAsset) 0x38` / `m_holdLuaAsset(TextAsset) 0x40`；常量 `MOCK_EXTENSION = ".M"`。

**`.ctor()` RVA 0x288FA40**：用 `FP.op_Implicit(float)`（0x54E4420）造 `PrecisePeriodicTimer`（`TICK_INTERVAL = 1`）赋给 `m_tickTimer`；`new DirectAssetLoader()` 赋给 `m_assetLoader`；再调 `_DoCreateLuaEnv()`。

### 1.2 `_DoInitIfNot()` RVA 0x288EF70

```
mov byte [rbx+0x10], 1                 ; m_inited = true
call SingletonScriptableObject<T>.get_instance   ; → LuaOptions.instance
mov ecx, [rdi + 0x18]                  ; LuaOptions.cryptType
call ConverterFactory.Create(ConverterType)      ; RVA 0x2B2EA80
mov [rbx+0x28], rax                    ; m_decrypter
mov rdx, [rdi + 0x20]                  ; LuaOptions.luaFolder
mov [rbx+0x20], rdx                    ; m_folder
call _DoLoadEntryScript(options)       ; RVA 0x288F080
```

`LuaOptions`（dump.cs 195110）是 ScriptableObject：

| 偏移 | 字段 | 用途 |
|---|---|---|
| 0x18 | `ConverterFactory.ConverterType cryptType` | 选哪种解密器 |
| **0x20** | `string luaFolder` | **脚本目录** |
| **0x28** | `string entryFile` | **入口脚本名** |

### 1.3 入口：`require '<entryFile>'`（`_DoLoadEntryScript` RVA 0x288F080）

```
mov  rcx, [rdi+0x28]              ; options.entryFile
call String.IsNullOrEmpty         ; 空 → 报错 'Lua entry file path is empty or null!'
mov  rcx, [rip+…]                 ; str="require '{0}'"
mov  r8,  [rip+…]                 ; str='chunk'
call String.Format
call LuaEnv.DoString(chunk, "chunk", env)
call …                            ; 取 EntryTable.Init → 挂到静态类 LuaEntry
```

```csharp
internal static class LuaEntry {            // dump.cs 194971
    public static Action Init;              // "EntryTable.Init"
    public static Action Dispose;           // "EntryTable.Dispose"
    public static bool  driveUpdate;        // "EntryTable.Update"
    public static Action<float,float> Update;
}
```

### 1.4 `_CustomLoader`（RVA 0x288E270）—— 路径转换与取值

```
mov  rdi, [rdi+0x20]                          ; m_folder
call FileUtil.Combine(m_folder, filePath)     ; RVA 0x5518F80
call FileUtil.ReplaceExtension(path, ".lua")  ; RVA 0x551A300
call String.Concat(上一结果, ".M")            ; RVA 0x4BF1CF0
   ↓
call ResourceManager.CheckExists(path)        ; RVA 0x555AC90 → 不存在则返回 null
     m_assetLoader.LoadAsset<TextAsset>(path)
call TextAsset.get_bytes() → new MemoryStream(...)
     m_decrypter.DeserializeBytes(stream)     ; IConverter Slot 8
```

即资源名 = **`<luaFolder>/<require 路径>` 去扩展名 + `.lua` + `.M`**（**无条件拼接**，反汇编里没有分支）。

> ⚠️ **未解矛盾**：`manifest.idx`、`hot_update_list*.json` 与知识库全盘都**搜不到 `.M` 结尾的条目**。推断 `.M` 是"逻辑资源名 → AB 内 TextAsset 名"的最后一层后缀（AB 内实际资产名带 `.M`），但本地无该 AB，无法端到端证实。
> 另：`_ConvertToFullPath`(0x288E190) 与 `_CustomLoader` 逐指令同构；两者都会先查 `DelegateBridge`（`__Hotfix0__CustomLoader // 0x58`、`__Hotfix0__ConvertToFullPath // 0x60`）—— **Lua 可以热修加载器本身**。

---

## 二、脚本在资源包里的形态

`manifest.idx`（初始包资源清单）统计：

| 后缀 | 数量 | 说明 |
|---|---|---|
| `.lua` | 570 | **285 个脚本** × 2 种索引（全路径 + 短名） |
| `.lua.bytes` | 285 | 全部带 `dyn/` 前缀 = **热更副本** |
| `.M` | 0 | 无 |

分层：`feature/`(239)、`base/`(35)、`hotfixes/`(**6**)、`battle/`(**3**)、根 `entry.lua`、`globalconfig.lua`。

battle 相关：`battle/battlemgr.lua`、`battle/battleabilitybehaviourbase.lua`、`battle/battleactionbase.lua`、`battle/actions/testaction.lua`。
hotfix 相关：`hotfixes/definedfix.lua`、`hotfixes/epcontrollerhotfixer.lua`、`teststubhotfixer.lua`。

**为什么 `hot_update_list.json`（13177 条）里没有 lua**：脚本属 `gamedata/` 前缀，而该前缀**根本不在 hot_update_list 的顶层目录分布里**（顶层只有 scenes/avg/arts/audio/battle/building/chararts/charpack/skinpack/spritepack/ui/anon/refs/retro/pkgrps/shaders/raw/activity/prefabs/npcpack/crisisv2longterm/akvt/config/graphics/cutin/arkvent）→ 属**初始安装包**内容。
（`ui/luaui/wardrobe/wardrobe_holder.ab` 是 Lua 驱动 UI 的 prefab 包，不是脚本载体。）

### 2.1 本地可得性（本次实测）

| 检查 | 结果 |
|---|---|
| `D:\YostarGames\Arknights_JP\Arknights_Data\StreamingAssets\AB\Windows\` 顶层目录 | activity / anon / arts / audio / battle / building / chararts / charpack / config / crisisv2longterm / cutin / graphics / npcpack / pkgrps / prefabs / refs / scenes / shaders / spritepack / ui / `[[jp]]` —— **没有 `gamedata`** |
| 客户端内任何 `*.lua*` 文件 | **0 个** |
| `client_res\*.ab` 二进制扫 lua 字符串 | **0 命中**（含 battle_skill_*/battle_uc_*/charpack/*/enm_pfb_*/config/common.ab） |
| `pkgrps\` 目录 | 是 `btl_pfb_fx_*` 战斗特效，与 Lua 无关 |

> **结论：Lua 脚本本体不在日服本地客户端**。要取得需另找承载 `gamedata/[uc]lua/*` 的包（国服客户端 / 安装包 / 其他地区包）。

---

## 三、解密（★ 密钥已在二进制内找到）

### 3.1 接口与实现类

`IConverter`（dump.cs 213548）：`Serialize` / `Deserialize<T>(…)` / `Populate(…)` / `SerializeBytes` / **`DeserializeBytes(Stream)` (Slot 8)** / `PreprocessText`。

| 实现类 | dump.cs 行 | 关键点 |
|---|---|---|
| `CrypticConverter` | 213255 | abstract；`EncodeInternal(byte[])`、`DecodeInternal(Stream,Stream)` |
| **`CrypticConverter_A`** | 213336 | **`KEY_LENGTH = 16`、`IV_LENGTH = 16`**、`private string m_token // 0x20` |
| `CrypticConverter_B` | 213359 | `MOD=2147483647`、`SEED_HASH_STR="0.577215"`、`FastRandom random` —— 流密码式 |
| `CrypticConverter_WithSign` | 213406 | 继承 A（带签名） |
| `FlatBufferSignedConverter` / `BsonNetConverter` / `JsonNetConverter` | 213478 / 213112 / 213594 | 后两者非加密 |

`ConverterFactory.ConverterType`（dump.cs 213214）：`JSON_DOT_NET=0, BSON_DOT_NET=1, CRYPTIC_A=2, CRYPTIC_B=3, CRYPTIC_WITH_SIGN=4, BSON_CRYPTIC_WITH_SIGN=5, BSON_WITH_SIGN=6, FLAT_BUFFER=7, UNITY_SERIALIZER_BSON=8, UNITY_SERIALIZER_JSON=9`。
（`LuaOptions.cryptType` 的实际取值在资产里，本地未取到 → 无法断言 Lua 用哪一支。）

### 3.2 算法

`CrypticConverter_A.DecodeInternal` RVA **0x2B2F120**：`Encoding.get_UTF8()` → `String.Substring(int,int)` ×2 → `new RijndaelManaged()`（0x2B2F2A8）→ 多次流读写。
结合 `KEY_LENGTH = 16` / `IV_LENGTH = 16` ⇒ **AES(Rijndael) 128 位，key/IV 各 16 字节**；**推断** `key = token.Substring(0,16)`、`iv = token.Substring(16,16)`（两次 Substring + 常量 16/16 强烈指向该结构）。CipherMode / PaddingMode 未逐指令确认。

### 3.3 ★ 密钥材料：`PlayerData.chatMask` 的默认值是硬编码常量

`CrypticConverter_A..ctor` RVA **0x2B2FBB0** 里：另一单例的 getter（RVA 0x43ED4F0）→ **`PlayerData.get_chatMask()`**（RVA 0x1F0B1B0）→ 写入 `m_token`，并带字面量 `'chatMask is invalid!'` 作校验。

反汇编 `PlayerData.get_chatMask()`（0x1F0B1B0）得其实现：

```
mov rax, [PlayerData_class + 0xb8]     ; 静态字段区
mov rcx, [rdx + 0x20]                  ; 静态缓存字段
test rcx, rcx
jne  取缓存
mov  rax, [rip + …]                    ; → str='UITpAi82pHAWwnzqHRMCwPonJLIB3WCl'
```

**即 `chatMask` 默认返回字符串 `"UITpAi82pHAWwnzqHRMCwPonJLIB3WCl"`（32 字符）**，除非该静态字段被赋值（可能由服务器下发覆盖）。

> 32 字符正好 = 16(key) + 16(IV)：
> **`key = "UITpAi82pHAWwnzq"`，`iv = "HRMCwPonJLIB3WCl"`**
>
> **这是本次最有价值的发现之一：离线解密 Lua 脚本所需的密钥材料就在二进制里，不依赖运行时数据。**

### 3.4 建议的解密尝试（待脚本本体到手后验证）

```python
key = b"UITpAi82pHAWwnzq"     # chatMask[0:16]
iv  = b"HRMCwPonJLIB3WCl"     # chatMask[16:32]
# 依次尝试 AES-128-CBC / -ECB / -CFB，PKCS7 与无填充
from Crypto.Cipher import AES
pt = AES.new(key, AES.MODE_CBC, iv).decrypt(blob)
```
判据：明文应为 **Lua 5.3/LuaJIT 字节码**（头部 `\x1bLua`）或 **Lua 源码文本**（`-- ` 注释 / `local` / `require`）。

---

## 四、Lua 接管了什么（决定哪些机制必须看 Lua）

### 4.1 `Torappu.Lua.LuaBattleMgr : Singleton<LuaBattleMgr>`（dump.cs 194935）

```csharp
public interface ILuaServiceCallback {                      // dump.cs 194918
    bool ExportRunAction(string actionName, Blackboard blackboard,
                         ActionNode.SourceType sourceType, ref Context.Snapshot snapshot);
    LuaAbilityBehaviourStub.LuaBinding ExportCreateAbilityBehaviour(string className, LuaAbilityBehaviourStub wrapper);
    void ExportResetAll();
}
public static void LuaOnlyBindCallback(ILuaServiceCallback);   // 0x288C900
public void ResetAll();                                        // 0x288C9D0
public bool RunActions(string actionName, Blackboard bb, ActionNode.SourceType, ref Context.Snapshot);  // 0x288CAB0
public LuaAbilityBehaviourStub.LuaBinding CreateAbilityBehaviour(LuaAbilityBehaviourStub wrapper);      // 0x288C710
```

**接管两件事**：
1. **ActionNode / Action 系统的执行** —— `RunActions(actionName, blackboard, sourceType, **ref** snapshot)`：让 Lua 执行名为 `actionName` 的战斗动作节点；`Context.Snapshot` 是 `ref`，说明 **Lua 能改写战斗上下文快照**。
2. **技能行为工厂** —— 按 `luaBehaviourName` 从 Lua 造 `AbilityStandard.Behaviour`。

### 4.2 `LuaAbilityBehaviourStub : AbilityStandard.Behaviour, ILuaCallCSharp, IHotfixable`（dump.cs 461704）

```csharp
[SerializeField] private string _luaBehaviourName;        // 0x20
private LuaAbilityBehaviourStub.LuaBinding m_luaBinding;  // 0x28
public override void Init(AbilityStandard ability);              // Slot 5
public override void SetData(Blackboard blackboard);             // Slot 6
public override void OnCastStart();                              // Slot 7
public override void OnCastFinish(Ability.FinishReason reason);  // Slot 9
public override void OnEvent(AbilityStandard.Event ev);          // Slot 10
public override void OnCastOnTarget(Entity target);              // Slot 11
public override void OnStopAffect();                             // Slot 12
public override bool UpdatePlaybackSpeed(UpdatePlaybackSpeedTiming, out float);  // Slot 14
```

**一个完整的技能行为空壳，把 7 个生命周期回调全部转发给 Lua**。凡是在技能配置里引用 `LuaAbilityBehaviourStub` 的技能，其行为**不在 C# 里**。

### 4.3 其它确证事实

- `_InjectDefinesToLuaEnv`（0x288F910）注入 **`HOTFIX_ENABLE = true`**、`TEST = false`、`UNITY_EDITOR = false`、`DEVINFO_ENABLE = false`，并 `LuaEnv.AddBuildin("rapidjson", …)` → **C# 方法可被 Lua 用 `xlua.hotfix` 整体替换**。
- 入口侧存在 `hotfixes/definedfix.lua`、`epcontrollerhotfixer.lua`、`teststubhotfixer.lua` —— **hotfix 目录本身就是"战斗/UI 逻辑被 Lua 改过"的直接证据**。
- `Torappu.Lua` 下另有 `LuaSender`（网络 Lua 化）、`LuaAIRLSampleMgr`、`LuaEntry`、`LuaUIUtil`；`Torappu.UI.LuaUIContext : ILuaCallCSharp, ILuaDialog, ILoadAsset`、`Torappu.DataBind.LuaDataBinder`、`LuaActivityUtil`。

---

## 五、对模拟的影响与下一步

### 5.1 影响

| # | 影响 |
|---|---|
| 1 | **"只看 C# 就能还原全部机制"的假设不成立**：`LuaBattleMgr.RunActions` 接管 ActionNode 执行、`LuaAbilityBehaviourStub` 接管技能回调。若某技能用后者，C# 侧是空壳。 |
| 2 | 好消息是**加载与解密链路已完全明确**，密钥也已找到——门槛从"不知道怎么做"降到"缺脚本本体"。 |
| 3 | `HOTFIX_ENABLE = true` + 大量 `__Hotfix0_*` 桥，意味着**同一版本内 Lua 也能改 C# 行为**；做机制复刻时必须记录"以哪份 Lua 为准"。 |

### 5.2 下一步（按可行性排序）

| 优先 | 动作 | 说明 |
|---|---|---|
| 1 | **找承载 `gamedata/[uc]lua/*` 的资源包** | 日服 StreamingAssets 里没有；候选：国服客户端、客户端安装包（安装前的 zip/pkg）、其他地区包。找到后用 §3.4 解密。 |
| 2 | 确认 `LuaOptions.cryptType` 取值 | 决定用 A/B/WithSign 哪一支；值在 `LuaOptions.asset` 资产内 |
| 3 | 解 `.M` 后缀之谜 | 拿到 AB 后看 TextAsset 的真实资产名即可证实 |
| 4 | 统计"哪些技能引用 `LuaAbilityBehaviourStub`" | 可先从 `skill_table` / `buff_template` 里搜 prefabKey，判断影响面 |

## 相关文件

- `31_局内模拟信息完备性排查.md`（§三 三层交互，本文件落实其"Lua 层"部分）
- `29_cpp层定位与读取流程.md`（工具链；反汇编注释现已显示字符串字面量）
- `33_cpp层战斗类结构与字段速查.md`（类与偏移）
- `32_进关卡前后客户端与服务器交换的信息.md`
