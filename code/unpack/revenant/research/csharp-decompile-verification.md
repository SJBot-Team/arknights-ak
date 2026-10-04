# 从 ARM64 汇编重建的 C#：能否自动验证语义等价

调查日期 2026-08-15。场景：Unity IL2CPP 手游，arm64-v8a，10 万–16 万个带 RVA 的方法，
LLM 读 ISIL/汇编重建 C#。问题：**"这段重建对不对"能不能机器判定？**

证据强度：
- **T1 实测** — 本次调查在本机真实游戏产物上直接跑出来的数据
- **强** — 官方文档 / 一手论文 PDF 提取 / 工具源码
- **中** — 有信誉的博客、仓库 issue、单一未复核的一手来源
- **弱** — 论坛、推断、无文献支撑的机制假设

## 对成本模型的影响

### 结论

**"全量、形式化、语义等价"的自动验证不可行，而且差两个数量级；
但"抽样、经验性、可量化准确率"的自动评测完全可行，成本比预想低一个数量级。
两者之间还存在一个被低估的中间层：不需要 oracle 的元数据一致性检查，
它在 IL2CPP 场景下是精确的，而在通用 C 反编译场景下根本不存在。**

四条决定性发现：

1. **免费 ground truth 是本次调查最重要的结果。** 一个真实商业手游的 12.8 万个 RVA 里，
   **77.8% 来自源码公开的程序集**（Mono BCL 47.7% + UnityEngine 21.2% + 第三方 OSS 8.9%），
   只有 17.9% 是游戏自有代码。可以**零标注成本**得到数万对 (原始 C# 源码, 真实 IL2CPP ARM64 汇编) 样本，
   直接测出流水线准确率——不需要任何等价性证明器。已具体验证配对成立（见 §2.2）。
2. **形式化等价验证在规模上差两个数量级，不是"贵"而是"没有"。**
   公开文献对真实二进制的最高纪录是 seL4 的 **234 个函数**（有原始 C 源码、受限 C 方言、-O1）。
   按诚实的二进制级速率外推 15 万方法需要 **770 CPU-年**、13.5 万–24.3 万美元，
   而且**工具本身不存在**——CMU SEI 用两个 DoD 财年做更容易的 C↔x86-64 版本，形式化那一半始终没跑通。
3. **不要用 recompile-and-diff 当通过/不通过的闸门，但要用它当重排序信号。**
   这是文献里效果最大的单一手段：Decaf 用"重编译产物与原二进制的字节距离"给 32 个候选重排序，
   功能正确率从 **59.1% → 83.9%**（+24.8pp）。相比之下纯多模型投票只有 +3–4pp。
4. **IL2CPP 有 C 反编译场景没有的精确一致性检查。** 元数据给出签名、字段偏移、
   字符串字面量表、调用目标 RVA——这些都是**可精确机器核对、不需要 oracle** 的。
   C 反编译研究里 55–68% 的等价率下降来自用户自定义类型推断失败，这条在 IL2CPP 上直接消失。

### 成本量级对比

| 方案 | 覆盖 | 成本 | 可信度 |
|---|---|---|---|
| 全量人工复核 12,089 个游戏方法 | 100% | 按专家 4.1 分钟/方法（下限）到 39 分钟（现实）算，**830–7,900 人时** | 高 |
| 全量形式化等价验证 | 理论 100% | **770 CPU-年 + 一个不存在的工具**（ARM64↔C# 等价检查器） | 不可得 |
| 全量 recompile-and-diff 当闸门 | 前置条件不可知，18 种配置组合要暴力搜 | 搭流水线 4–12 人周，大概率拿不到稳定信号 | 未验证 |
| **元数据一致性检查（L0）** | **100%，全自动** | 建流水线 **1–2 人周**，之后零边际成本 | 精确（只判"错"，不判"对"） |
| **OSS ground truth 标定（L2）** | 标定集 300–1000 个，全自动打分 | 建流水线 **1–2 人周**，之后每轮 **0 人时** | 中高（有置信区间） |
| **抽样人工复核（L4）** | n=385 分层抽样 | **128 人时**（约 20 分钟/方法）；迭代期用 SPRT 只要 35–40 个样本 | 高，有 Wilson 区间 |
| Frida 录制回放差分（L5） | 按需，热点方法 | 每个方法数小时，需过反调试 | 最高 |

**最省的替代方案：L0 + L2。** 前者抓 LLM 最常犯、后果最严重的错（幻觉 API、抄错常量、漏调用），
后者把"准确率"变成一个可以随时重跑的 CI 指标。两者加起来 2–4 人周建设、之后零人工，
把人工复核从"每个方法都看"降到"一次 128 人时的标定 + 每轮 35–40 个样本的 SPRT 门控"。

### 推荐的验证栈

| 层 | 做什么 | 覆盖 | 成本 | 性质 | 详见 |
|---|---|---|---|---|---|
| **L0** | 元数据一致性硬门：签名/字段偏移/调用目标 RVA/字符串字面量/常量集合 | 100% | 近零 | **精确**，只能证伪 | §5.1 |
| **L1** | 结构排序信号：BB/边/循环/调用数 vs ARM64 CFG；Roslyn IL vs Cpp2IL CIL；codealign | 100% | 低 | 排序，不门控 | §5.2 |
| **L2** | OSS ground truth 离线考卷，300–1000 个方法，每次改 prompt 重跑 | 标定集 | 一次性 1–2 人周 | 可比的准确率数字 | §2.7 |
| **L3** | N=8～32 采样 + recompile-through-IL2CPP 字节距离重排序 | 高价值子集 | 高 | **文献里 ROI 最高的单一手段** | §5.3 |
| **L4** | 分层抽样人工复核 n=385，Wilson 区间；迭代期 SPRT n≈35 | 抽样 | 128 人时 | 最终数字 | §5.4 |
| **L5** | frida-il2cpp-bridge 录制真实调用回放 | 热点 | 每方法数小时 | 行为确认 | §4.7 |

（另有一条无文献支撑但便宜的试点：泛型实例化对的交叉一致性，见 §5.5。）

## 一、recompile-and-diff：不能当闸门，但应该当重排序信号

**判断：作为"通过/不通过"的等价性判定——不可行。作为候选重排序信号——可行，且是文献里效果最大的手段。**

### 1.1 前置条件：一半能满足，一半不可知

| 条件 | 状态 | 证据 |
|---|---|---|
| 确定 Unity 精确版本 | 能。`strings libil2cpp.so \| grep -E '20[0-9]{2}\.[0-9]+\.[0-9]+[abfp][0-9]+'`；或读 `globalgamemanagers` | T1（本仓库 `research/cpp2il-macho-verdict.md` 已用此法定位 2022.3.62f2） |
| 复现 IL2CPP 转换器 | 能。`il2cpp.exe` 可独立调用：`--convert-to-cpp --compile-cpp --platform --architecture --configuration --generatedcppdir` | 中（[katyscode IL2CPP Part 1](https://katyscode.wordpress.com/2020/06/24/il2cpp-part-1/)） |
| 复现 C++ 编译器 | 能。Unity 每版锁定 NDK：6000.0+ → r27c，2022.3 LTS → r23b，2021.3 LTS → r21d | 强（[Unity Manual: Android supported dependency versions](https://docs.unity3d.com/6000.2/Documentation/Manual/android-supported-dependency-versions.html)） |
| IL2CPP 阶段确定性 | 是。"same input code will result in the same C++ generated code, every time" | 强（[Cpp2IL Wiki: IL2CPP Basics](https://github.com/SamboyCoding/Cpp2IL/wiki/IL2CPP-Basics)） |
| C++ 编译阶段确定性 | 有保留。同一 wiki 紧接着："how the C++ compiler chooses to compile that code can change" | 强（同上） |
| 原包的 stripping 等级 | **不可知**。Low/Medium/High 无法从产物直接读出 | — |
| 原包的 C++ Compiler Configuration | **不可知**。Release vs Master（Master 开 LTO） | 强（[Il2CppCompilerConfiguration.Master](https://docs.unity3d.com/ScriptReference/Il2CppCompilerConfiguration.Master.html)） |
| 原包的 Code Generation 选项 | **不可知**。Runtime Speed vs Size and Build Time | 强（[Unity Manual: Introduction to IL2CPP](https://docs.unity3d.com/6000.3/Documentation/Manual/il2cpp-introduction.html)） |

后三项构成至少 3×3×2 = 18 种组合的搜索空间，每种都要跑一次完整 IL2CPP + NDK 构建。

### 1.2 byte-for-byte 不可能，三个结构性原因

**(a) metadata usage index 是全局数组下标。** IL2CPP 生成的 C++ 里字符串字面量、TypeInfo、MethodInfo
的引用走 `il2cpp_codegen_initialize_method(N)`，N 是**按整个构建编号的数组下标**；
每个方法首次执行时按自己的 metadata usage range 惰性初始化。在只含一个方法的小工程里重编，N 必然不同。
（强：[Cpp2IL Wiki: IL2CPP Data Structures](https://github.com/SamboyCoding/Cpp2IL/wiki/IL2CPP-Data-Structures)；
katyscode Part 1 的生成代码示例 `Console_WriteLine_m22F0...(_stringLiteral331919585E3D6FC59F6389F88AE91D15E4D22DD4, L_3, NULL)`）

**(b) 调用目标偏移是全局布局的产物。** 方法名 mangling 含签名哈希、本身可复现，但 `bl` 的目标偏移取决于整个 .so 的函数布局。

**(c) 泛型共享与内联决策是全程序级的。** 小工程里的决策必然和整包不同。

所以只可能做**归一化 diff**（抹掉立即数、调用目标、寄存器分配，比较 opcode 序列/CFG 形状），
或者**字节距离**（下节）——都不是等价性证明。

### 1.3 有人做成过：retro game 的 matching decompilation

基础设施成熟：[decomp.me](https://www.decomp.me/faq)（在线 compile→objdump→diff 循环）、
[asm-differ](https://github.com/simonlindholm/asm-differ)（支持 MIPS/PPC/**AArch64**/ARM32/SH/m68k）、decomp-permuter。

**这个 oracle 确实能驱动 LLM。** Bruno Macabeus 2026 年的实测是最直接的一手数据
（中：[Can LLMs Really Do Matching Decompilation? I Tested 60 Functions](https://macabeus.medium.com/can-llms-really-do-matching-decompilation-i-tested-60-functions-to-find-out-4e39b0ae4288)）：

- Claude Sonnet 4.6，60 个函数（30 个 GBA/agbcc + 30 个 N64/IDO），每组 3 轮
- **74% 达到 byte-match**（最好一轮 80%），**88% 的函数三轮结果一致**
- 纯程序化工具（m2c + permuter）单独只解决 SA3 的 0%、AF 的 4 个函数——**提升几乎全部来自 LLM**
- 近一半的 match 出现在第一次尝试；第 3 次还没中，后续成功率掉到约 1/4
- 每函数最多 12 次尝试、10 分钟硬超时；6 轮基准跑了约 10 天

**但这不能直接搬。** GBA/N64 用的是几乎不做全程序优化的老编译器，单个函数可独立编译；
IL2CPP 是 Roslyn→il2cpp→clang 三级流水线，中间那级的输出依赖全程序 metadata 编号。差别是种类，不是量级。

**社区侧的效率参考**（T1，直接从仓库统计）：

| 项目 | 函数数 | LOC | 贡献者 | 耗时 |
|---|---:|---:|---:|---|
| zeldaret/oot | 13,829 | 431,117 | 96 | 630 天到 100% |
| zeldaret/mm | 17,284 | 533,335 | 80 | 7.8 年 |
| n64decomp/sm64 | 4,560 | 135,710 | — | 约 175 天 |
| diasurgical/devilution | 2,604 | 120,426 | 58 | 约 1 年 |

折算约 **0.1–0.23 函数/人日**（业余兼职）。三条注意：这是 byte-matching 的上界难度；
贡献者是兼职，全职吞吐大概高 3–10 倍；**OoT 和 Devilution 都有符号泄漏**
（Devilution README 明确感谢 PS1 符号文件提供"file names, functions, structures, variables"）——
这和你的 `global-metadata.dat` 是同一类优势，所以这些项目是公允的类比。

### 1.4 应该怎么用：当重排序信号，不当闸门

这是本节的核心修正。**Decaf**（[arXiv 2605.11501](https://arxiv.org/abs/2605.11501)，Shypula/Bastani/Schwartz）
在 ExeBench stripped `-O2` 上的结果（强）：

| 配置 | 功能正确率 | 精确字节匹配 |
|---|---:|---:|
| N=1 单次生成 | 59.1% | 38.0% |
| **N=32 + 重排序** | **83.9%** | **70.9%** |
| Oracle 上界 | 88.3% | — |
| 对照 Idioms | 26.0% | 19.1% |

**重排序器包含"重编译候选与参考二进制的字节距离"。** 这就是 recompile-and-diff——
只是用法不是"匹配就通过、不匹配就拒绝"，而是"在 32 个候选里挑字节距离最小的那个"。
**+24.8pp 是整个文献里单一手段的最大增益**，对比纯多模型一致性投票只有 +3–4pp（见 §5.3）。

对 IL2CPP 这个信号应该**更强**，因为 IL2CPP 的 codegen 高度模板化、确定性好。
代价是要复现目标的精确工具链（§1.1 的三个"不可知"项）——但注意：
**当重排序信号用时，配置猜错的代价是信号变噪，不是判错**。这比当闸门宽容得多。

**一个未验证但值得记的变通**：Il2CppDumper 的 `DummyDll` 是 "Complete DLL restore (except code)"，
签名齐全、方法体为空，可被 dnSpy/ILSpy 加载（强：[Il2CppDumper README](https://github.com/Perfare/Il2CppDumper)）。
理论上可把候选 C# 编译成引用 DummyDll 的小程序集再喂给 `il2cpp.exe`，
得到目标方法自己的 ARM64、调用目标全指向空桩，然后算字节距离。
**没人验证过，我也没验证。** 风险：il2cpp 可能拒绝空方法体的程序集，或为它们生成 stub 从而改变内联决策。

## 二、免费 ground truth：可行，是最高价值的发现

**判断：可行（有条件）。三个条件：许可、泛型一对多、版本锁定。**

### 2.1 实测：一个真实商业游戏里有多少源码公开的代码

**T1 实测**，样本 `2026-06-09-gossip-harbor-re/_refs/3.91.0/cpp2il_out`（Gossip Harbor 3.91.0，
58 个程序集，`rva_index.json` 共 128,246 条）：

| 来源 | 方法数 | 占比 | 源码 | 可再分发 |
|---|---:|---:|---|---|
| Mono BCL：mscorlib / System / System.Core / System.Xml / System.Data / Mono.Security | 61,204 | **47.7%** | [Unity-Technologies/mono](https://github.com/Unity-Technologies/mono)，分支 `unity-<ver>-mbe` | **是**（MIT） |
| UnityEngine.* + Unity.* | 27,238 | **21.2%** | [UnityCsReference](https://github.com/Unity-Technologies/UnityCsReference) | **否**（Reference-Only） |
| 第三方 OSS：Newtonsoft.Json / DOTween / spine-unity / SharpZipLib | 11,386 | **8.9%** | GitHub | 部分（DOTween、spine 非 OSI） |
| **小计：源码公开** | **99,828** | **77.8%** | | |
| Assembly-CSharp(+firstpass)（游戏自有） | 22,958 | 17.9% | 无 | 否 |
| 闭源 SDK：AppsFlyer / MaxSdk / Facebook.Unity / com.microfun.* | 5,460 | 4.3% | 无 | 否 |

跨游戏交叉验证（并行调研，T1，三个真实包）：

| 游戏 | Unity | 元数据中方法数 | 有唯一 RVA |
|---|---|---:|---|
| Matching Story | 2021.3.29f1 | 120,845 | 111,480（92.3%） |
| Disney Solitaire | 2021.3.56f2 | 121,168 | 104,142（86.0%） |
| MagicManor | 2022.3.20f1 | 106,524 | 93,485（87.8%） |

**每逆一个游戏都自带一套近 10 万方法的免费考卷**，而且这些方法和游戏自有代码走**完全相同**的
IL2CPP + clang 流水线、相同优化等级、相同 stripping 配置——分布匹配度比任何合成基准都好。

**可再分发的部分约 33,000–46,000 个方法/游戏**（BCL + MIT 第三方）。

### 2.2 配对正确性：已具体验证，两处

**Newtonsoft.Json（T1，我直接核对）**：`DiffableCs/Newtonsoft.Json/.../JsonTextReader.cs` 的私有方法
与上游 [JamesNK/Newtonsoft.Json](https://github.com/JamesNK/Newtonsoft.Json/blob/master/Src/Newtonsoft.Json/JsonTextReader.cs) 逐一核对：
`BlockCopyChars`、`EatWhitespace`、`EnsureChars`、`FinishReadQuotedNumber`、`FinishReadStringIntoBuffer`、
`MatchValueWithTrailingSeparator`、`CreateUnexpectedCharacterException`、`ConvertUnicode`、`IsSeparator`、
`ParseNumber` —— **10/10 存在，签名逐字一致**，含
`private static void BlockCopyChars(char[] src, int srcOffset, char[] dst, int dstOffset, int count)`。
这些是不会出现在公开 API 文档里的内部细节，签名级一致意味着函数边界确实保留了。

**UnityEngine.Vector3.Lerp（T1，并行调研在 Matching Story 上）**：RVA `0x2C4A20C`，16 条 ARM64 指令：

```
fmov s7, #1.0 ; fcmp s6, #0.0 ; fmin s6,s6,s7 ; fmov s7, wzr
fsub s3,s3,s0 ; fsub s4,s4,s1 ; fsub s5,s5,s2 ; fcsel s6,s6,s7,pl
fmul s3,s3,s6 ; fmul s4,s4,s6 ; fmul s5,s5,s6
fadd s0,s0,s3 ; fadd s1,s1,s4 ; fadd s2,s2,s5 ; ret
```

与 [UnityCsReference @2021.3.29f1 的 Vector3.cs](https://raw.githubusercontent.com/Unity-Technologies/UnityCsReference/2021.3.29f1/Runtime/Export/Math/Vector3.cs) 完全对应，
`Mathf.Clamp01` 被内联（`fmin`/`fcsel` 那一对）。

**UnityCsReference 与 shipped assembly 的对应度**：按 tag 拉 `2021.3.29f1`，
类型名匹配 **1,442 / 1,485 = 97.1%**，残差 2.9% 全是 `delegate` 声明和编译器注入的
`EmbeddedAttribute`/`IsReadOnlyAttribute`——实际对应度接近 100%。（T1）

**mscorlib（T1）**：目录结构含 `Mono/`、`Unity/`、`Locale.cs`、`SR.cs`，确认是 Unity 的 Mono fork。
`System.String.GetHashCode`（RVA `0x18625B0`）编译出经典双累加器 DJB2，含 `mov w8, #0x1505`(5381)
与 `movz/movk` 装载 `0x5D588B65`(1566083941)，与
[Unity mono 的 referencesource string.cs](https://raw.githubusercontent.com/Unity-Technologies/mono/unity-2021.3-mbe/mcs/class/referencesource/mscorlib/system/string.cs) 逐字一致。

### 2.3 RVA 覆盖率：完整，残差可完全解释

**这是本次调查最强的单一结果（T1，两个游戏共 242,013 个方法）**：

| | Matching Story | Disney Solitaire |
|---|---:|---:|
| 有 RVA | 92.25% | 85.95% |
| 无 RVA：泛型类型的成员 | 4.17% | 7.22% |
| 无 RVA：abstract / interface | 2.70% | 4.98% |
| 无 RVA：泛型方法 | 0.88% | 1.85% |
| **无 RVA：无法解释** | **0** | **0** |

**每一个非泛型、非抽象、在 stripping 后存活的方法，都恰好有一个已知 RVA 的 ARM64 函数。零例外。**

注意 `RVA: -1` 是 Il2CppDumper 在 `methodPointer == 0` 或方法为 abstract 时的渲染，
**不是"被裁剪"的标记**——被裁剪的方法在元数据里根本不存在。

### 2.4 内联不破坏配对（对我早前判断的修正）

这条最反直觉，但有直接测量支撑（T1）：`Mathf.Clamp01` 被内联进 `Vector3.Lerp` 了，
**同时它自己仍以独立函数存在于 RVA `0x2C478C8`**，7 条指令，与源码精确对应。
原因：IL2CPP 把每个方法都写进 per-assembly 的方法指针表，这迫使 C++ 编译器保留一份 out-of-line 副本。

旁证：111,480 个有 RVA 的方法占据 111,480 个**互不相同**的地址——该构建**没有做 identical code folding**。
（注意：某些 IL2CPP 构建会折叠空的 `Start`/`Update` 桩，这个包没有。）

**所以内联让调用方的方法体变大变难（被内联的逻辑在源码标注里是缺席的），但从不摧毁被调用方自己的配对。
任务难度上升，标注完整性不下降。**

### 2.5 坑，按严重程度排序

**(a) 版本识别比预想难得多——最主要的工程成本。**（强，T1：对 DummyDll 跑 `monodis`）

| 程序集 | 元数据里的 AssemblyVersion |
|---|---|
| UniTask / VContainer / MessagePipe / UnityEngine.CoreModule / Unity.TextMeshPro | **`0.0.0.0`** |
| Newtonsoft.Json | `13.0.0.0` |
| mscorlib | `4.0.0.0` |

`global-metadata.dat` **结构上确实保留**四段版本号加 8 字节 public key token
（`Il2CppAssemblyNameDefinition { …, int major, minor, build, revision, byte[8] public_key_token }`，
强：[Il2CppDumper MetadataClass.cs](https://raw.githubusercontent.com/Perfare/Il2CppDumper/master/Il2CppDumper/Il2Cpp/MetadataClass.cs)），
但**源码分发的 UPM 包根本没写 `AssemblyVersion` 特性**（UniTask、VContainer、MessagePipe、TMP、
Cinemachine、Addressables、Unity.Mathematics、Zenject，以及全部 UnityEngine）→ 版本信号为零。
预编译 NuGet DLL 只锁定 major/minor（`13.0.0.0` 覆盖 13.0.1/13.0.2/13.0.3）。
`AssemblyInformationalVersion`（真正的产品版本）**不可恢复**——Il2CppDumper 只对类型/字段/方法发射自定义特性，从不发射程序集级的。

回退手段，按可靠性排序：
1. **字符串字面量**。部分库硬编码版本常量——DOTween 有 `public static readonly string Version`
   （T1：本地 DiffableCs 确认该字段存在），其值是 cctor 里的字符串字面量，落在元数据字面量表里，
   `stringliteral.json` 可直接 grep。
2. **API 表面指纹**。用保留下来的类型/方法集合去 diff 一组预构建的参考版本。通用解法，是真实工作量。
3. **Unity 版本容易且精确**，直接锁定 UnityEngine 和 BCL——也就是最大的两块池子。

**次生问题**：源码分发的库从游戏自己的工程编译，`asmdef` 的 `versionDefines` 让代码逐游戏而变。
UniTask 一家就 gate 在 `UNITASK_ASSETBUNDLE_SUPPORT`、`UNITASK_PHYSICS_SUPPORT`、
`UNITASK_DOTWEEN_SUPPORT`、`ENABLE_IL2CPP`（11 处）、`SUPPORT_VALUETASK` 及 36 处 `!UNITY_2019_1_OR_NEWER`；
Cinemachine 更糟（`CINEMACHINE_PHYSICS` 67 处）。
**"UniTask v2.5.11"不是一个标注，而是每个 define 集合一个标注。**
预编译 DLL 的库（Newtonsoft、protobuf-net、MessagePack core、DOTween core）没有这个问题，跨游戏 bit-identical。

**(b) High 等级 stripping 会改方法体——对 BCL 尤其致命。**
Unity 官方明确，High 等级下 UnityLinker "edits method bodies in order to further reduce code size"，
具体是 "removing unreachable branches, inlining field-access methods, and removing empty calls"，
且**明确指向 .NET Class Library 程序集**——正是你最大的 MIT 池子。
（强：[Unity Manual: Managed code stripping](https://docs.unity3d.com/2020.1/Documentation/Manual/ManagedCodeStripping.html)）
IL2CPP 默认是 **Low**，Low/Medium 不做这些。产物里没有直接读出 stripping 等级的办法，
所以这是 BCL 样本上的**静默标注污染风险**。缓解：统计检测（BCL 方法的反汇编长度系统性短于参考构建）。

**注意区分**：普通 stripping 是**整体删除方法**，不是留空方法体。T1 实测：
`UnityEngine.Mathf` 在 Matching Story 里保留 54 个方法、Disney Solitaire 里 65 个，
缺的 12 个（`SmoothDampAngle`×3、`Gamma`、`HalfToFloat`、`FloatToHalf`…）**在元数据里完全不存在**。
存活的方法完好正确。所以 stripping **缩小样本池但不污染标注**——High 等级除外。

**(c) 泛型一对多。** Unity 官方：引用类型和整数/枚举类型共享实现，
"does not share generic method implementations when T is a value type because the size of each value type will differ"
（强：[IL2CPP Internals: Generic sharing](https://unity.com/blog/engine-platform/il2cpp-internals-generic-sharing-implementation)）。

T1 实测（Matching Story，179,932 个具名原生函数）：
**8,156 个泛型方法定义展开成 66,154 个额外原生函数**。最严重的：`Dictionary<,>..ctor` → **792 个**；
`List<>.Sort` → 488；`List<>.CopyTo` → **399**。引用类型确实折叠了（`List<object>` 吸收所有引用类型），
值类型逐形状分开。**但 105,622/113,778（92.8%）的定义仍是 1:1。**

**Full Generic Sharing 没有解决这个问题**——MagicManor 是 2022.3.20f1（FGS 已存在），
仍有 315 个不同的 `List<>.CopyTo` 函数、13,591 个多实例化定义产生 90,295 个额外函数。
FGS 是 AOT 无法预测时的 fallback，不是特化 codegen 的替代。

对泛型密集的库影响巨大：**UniTask.dll 51.5% 无 RVA，UniTask.Linq.dll 91.6%，MessagePipe 71.9%**——
且已验证成因是泛型而非 stripping（UniTask 的 1,687 个无 RVA 方法：1,463 个在泛型类型里、
137 个泛型方法、87 个 abstract，**0 个无法解释**）。对比 Newtonsoft.Json 只有 10.2%、Unity.TextMeshPro 4.4%。

处理：建标定集时排除泛型成员。**T1 实测**：全库只有 8.9% 的签名带 `<>`；
在候选标定池（mscorlib + System + System.Core + Newtonsoft.Json，44,592 个方法）里
**88.9%（39,660 个）是非泛型的**——排除泛型后样本池仍远超需要。

**(d) UnityEngine 有 1/3 是 native binding。**（中：对 `Runtime/` + `Modules/` 非 Editor 部分做正则普查，
1,215 文件、15,624 个方法声明）**67.4% 有真实托管方法体，32.6% 是 `extern` / `[MethodImpl(InternalCall)]`。**
后者在 dump 里仍有 RVA，但方法体只是 icall thunk——
例：`Transform.get_position`（RVA `0x354F0C8`）是托管包装，调用 `get_position_Injected`（RVA `0x354F124`）才是真正的 stub。
Matching Story 里有 330 个 `_Injected` 方法。**必须过滤掉 `extern` 方法**：它们的"标准答案"是一个无体声明，属于无标注噪声。

**(e) BCL 源码被 `#if` 重度分割。** `FEATURE_RANDOMIZED_STRING_HASHING`、`WIN32`、`MONO`、`BIT64`…
**ground truth 必须是按实际构建 define 预处理之后的文本**，不是原始文件。搞错会静默污染标注。

**(f) 许可。** UnityCsReference 是 Unity Reference-Only License：
"The terms of use do not permit you to modify or redistribute the C# code (in either source or binary form)"。
内部评测无碍，**但不能公开发布包含 UnityEngine 源码的数据集**。DOTween 是自定义非 OSI 许可，spine-csharp 需 Spine 授权。

**(g) 编译器生成成员。** T1：Matching Story 约 5,000 个 `<…>b__` lambda、2,216 个 `DisplayClass` 闭包类型、
1,429 个 async/iterator `d__` 状态机，约占 5–8%。它们没有具名源码方法，标注是 lambda 体或生成的 `MoveNext`。
（本地 Gossip Harbor 数据一致：Assembly-CSharp 里编译器生成类型占 8.2%。）

**(h) 混淆与加密。** 三个 dump 名字都是干净的；`2026-08-13-merge-games-re` 下另外 8 个游戏
`global-metadata.dat` 均为明文（magic `af1bb1fa`，version 31）。但防护是真实存在的商品：
FairGuard 明确售卖元数据加密 + 无导出表 SO 加壳来对抗 Il2CppDumper
（中：[FairGuard](https://fairguard.github.io/2021/03/25/encrypt_global-metadata)）；
本仓库 `research/il2cpp-metadata-decryption.md` 已记录一例 PGL Armor VM 加密。
**关键：混淆器压倒性地针对游戏自有程序集，不动 mscorlib/UnityEngine/第三方 DLL**
（改名会破坏反射和序列化）——而 ground truth 池恰好就是后者。元数据**加密**则是逐游戏的通过/跳过闸门。

**(i) 别漏掉两件事**：检查 `lib_burst_generated.so`（Burst job 体是原生的，不在 libil2cpp.so 里）；
检查 HybridCLR（`com.code-philosophy.hybridclr`），它给 libil2cpp 打补丁加解释器，
意味着**游戏的一部分 C# 根本没被 AOT 编译**。

### 2.6 有人建过这个数据集吗：没有

（强，穷尽性否定检索）arXiv 全文 `all:"IL2CPP"` → **0 结果**。
HuggingFace dataset 搜 `il2cpp` → **空**。GitHub 无相关数据集构造仓库。
唯一挂 IL2CPP 名号的 ML 产物是 [Ornith-1.0-9B-IL2CPP-Decompiler](https://huggingface.co/pubertcs/Ornith-1.0-9B-IL2CPP-Decompiler)，
用另一个 LLM 生成的 5,000 条训练、数据集未公开、示例代码跑的还是正向——不是 ground truth（弱）。

领域现状是 C-on-x86-64：[LLM4Decompile](https://arxiv.org/abs/2403.05286)、
[Decompile-Bench](https://arxiv.org/abs/2505.12668)（230 万对，C/C++，x86-64）、
[ExeBench](https://github.com/jordiae/exebench)、[DecompileBench](https://arxiv.org/abs/2505.11340)。
ARM64 覆盖很薄且只有 C。最接近的结构类比是 Dart AOT（2026 年，仅 x86-64），
其 related work 列举了 C、Go、Fortran、OCaml，**从未提及 C#、.NET、CIL、Unity 或 IL2CPP**。

**"ARM64 + AOT 编译的托管语言"这一格是空的。没人在那里发过东西。**

### 2.7 建标定集的配方

Cpp2IL 的 `DiffableCs` 已经直接给出
`[Address(RVA = "0x1B7AD3C", Offset = "0x1B7AD3C", Length = "0x3C")]`——
**精确的函数字节区间，免费**。这正是 Decompile-Bench 花 450 GB 插桩编译才拿到的映射。
（T1：Gossip Harbor 78,376 个 Address 特性，全部带非零 Length；并行调研的另一包 79,047 个，同样全部非零。）

1. `revenant prepare` → Cpp2IL DiffableCs + Il2CppDumper `script.json`
2. 从 `libil2cpp.so` strings 读 Unity 版本；checkout 对应 UnityCsReference tag 和 `unity-<ver>-mbe` mono 分支
3. 按 程序集 + 命名空间 + 类型 + 方法签名 join；按 `[Address]` 的 RVA/Length 切 ARM64
4. 过滤：`extern`、泛型类型成员、编译器生成、`#if` 歧义区域
5. **先只做 Mono BCL**——最大、MIT、可用 Unity 版本精确锁定、且没有逐游戏 define 问题。
   单个游戏就能出约 3 万条干净配对。

**去重要诚实**：BCL 方法集在同 major 版本的两个游戏间重合 **97.2%**，跨 major **89.9%**。
加第五个游戏只增加几百个**新的源码方法**，不是几千。多游戏真正给的是
"同一源码方法在不同 Unity 版本 / stripping 等级 / 内联上下文下的编译产物"——
这是合法的数据增强（类比 LLM4Decompile 的 O0–O3 变体），但不能当成唯一覆盖率上报。

## 三、LLM 辅助反编译：现有研究与评测方法

### 3.1 三个数字决定预期

1. **玩具基准说约 70%。** SK²Decompile 在 HumanEval-Decompile（单个自包含 C 函数，O0–O3）上 **69.0%** re-executability。
2. **真实世界基准说 1–22%。** CODEFUSE-DEBENCH 最好的"反编译器 + LLM"组合达到
   **73.8% 可重编译，但只有 22.3% 有任何程序级行为重合、1.2% stdout 精确匹配**——约 50pp 的"可用性悬崖"。
3. **最接近 IL2CPP 的类比（Dart AOT）说 3–6%。** pass@1 **3.12–6.36%**，约 200 条汇编指令处有硬能力悬崖。

第 1 与第 3 之间的差距是本节对本项目最重要的信息。所有头条数字来自的基准，其性质 IL2CPP/ARM64 都不具备。

### 3.2 SOTA 全景

| 场景 | 最好成绩 | 来源 |
|---|---:|---|
| 手写自包含 C，HumanEval-Decompile，O0–O3 均值 | **69.0%** | [SK²Decompile](https://arxiv.org/abs/2509.22114) |
| 同上，仅 O0 / 仅 O3 | 86.6% / **57.5%** | 同上 |
| ExeBench REAL-O2 stripped，N=32 + 重排序 | **83.9%** | [Decaf](https://arxiv.org/abs/2605.11501) |
| 同上，N=1 | 59.1% | 同上 |
| 真实 OSS-Fuzz 函数，覆盖率等价 | **41.8%**（Hex-Rays）/ 16.4%（LLM4Decompile） | [DecompileBench](https://arxiv.org/abs/2505.11340) |
| 真实 Windows DLL（WeChatWin.dll） | **39.7%** | [SALT4Decompile](https://arxiv.org/abs/2509.14646) |
| 真实多架构程序，程序级行为 | 22.3% 部分 / **1.2% 精确** | [CODEFUSE-DEBENCH](https://arxiv.org/abs/2605.29490) |
| Coreutils/Binutils 热替换 + 差分修复 | **99.5%+** 函数级 | [PCodeTrans](https://arxiv.org/abs/2603.14855) |
| **Dart AOT（托管、AOT 编译）** | **3.12–6.36% pass@1** | [arXiv 2607.06125](https://arxiv.org/abs/2607.06125) |
| **Java 字节码反编译（成熟工具，全元数据）** | **78% 语义等价**（Procyon） | [Harrand et al., SCAM 2019](https://arxiv.org/abs/1908.06895) |

**Java 那一行值得单独盯着看**：成熟的托管字节码反编译器、有完整元数据、语义鸿沟比 IL2CPP 小得多，
在真实项目的自有测试套件下语义等价率也只到 **78%**。这是托管场景的实际天花板参考。
同一组工作还证明**反编译器多样性可利用**——meta-decompiler Arlecchino 靠组合互相不一致的反编译器
拿下 37.6% 此前无法处理的类。这支持前端用 ensemble（Cpp2IL + Ghidra + IDA 视图）而不是单一来源。

### 3.3 难度预测因子：方法长度，而不是算法复杂度

Dart AOT 论文的这张表是全部文献里对本项目最直接相关的（强）：

| 汇编长度 | 任务数 | 可解 | 比例 |
|---|---:|---:|---:|
| <50 行 | 25 | 12 | **48%** |
| 50–100 | 49 | 12 | **24%** |
| 100–200 | 61 | 11 | **18%** |
| 200–500 | 17 | 1 | **6%** |
| >500 | 2 | 0 | **0%** |

"assembly sequence length is the strongest predictor of task difficulty (p=0.001),
with a capability cliff at approximately 200 instructions"。
**关键补充：传统复杂度指标（圈复杂度、嵌套深度）预测力可忽略（|ρ|<0.25）**——
难度由编译信息损失驱动，不是源码算法复杂度。

**对照本项目的实测分布（T1，Gossip Harbor，Length/4 = 指令数）**：

全部 78,376 个带 `[Address]` 的方法：

| 分位 | p25 | p50 | p75 | p90 | p95 | p99 |
|---|---:|---:|---:|---:|---:|---:|
| 指令数 | 4 | 25 | 69 | 147 | 230 | 617 |

累计：≤16 条 36.9%，≤32 条 56.5%，≤64 条 73.3%，≤128 条 86.6%，**≤200 条 93.8%**，≤400 条 97.9%

只看游戏自有代码（Assembly-CSharp，12,089 个）：

| 分位 | p25 | p50 | p75 | p90 | p95 | p99 |
|---|---:|---:|---:|---:|---:|---:|
| 指令数 | 20 | 86 | 140 | 203 | 317 | 1,014 |

累计：≤64 条 45.2%，≤128 条 65.8%，**≤200 条 89.6%**，≤400 条 96.6%。总计 5.6 MB 机器码。

**难度分布是有利的：93.8%（游戏代码 89.6%）在悬崖以内。**
但也意味着剩下 10% 的长方法必须走单独的、更贵的流程（更多上下文、分段重建、人工介入），
不要用同一套 prompt 硬扛。这也是**标定集必须按长度分层抽样**的原因——
否则会被大量 4 指令的 getter 稀释出一个虚高的准确率。

（Assembly-CSharp 方法构成，T1：常规方法 77.7%、编译器生成类型 8.2%、构造函数 6.9%、
属性访问器 6.3%、事件访问器 1.0%，共 1,039 个类。**约 14% 是公式化样板**，基本不需要 LLM 也不需要复核。）

### 3.4 优化等级的代价

| 系统 | O0 → O3 |
|---|---|
| SK²Decompile | 86.59 → 57.52（**−29pp**） |
| LLM4Decompile | 67.07 → 28.32（**−39pp**） |
| Idioms | 70.73 → 10.62（**−60pp**） |
| Hex-Rays RSR | 0.706 → 0.513（−27%） |

Unity/il2cpp/clang 移动端典型是 `-O2`/`-Os`。**预期适用 27–39pp 的惩罚，不是 O0 的数字。**

### 3.5 哪些指标不能用

论文的态度异常明确，而且有直接实验证据：

- **Dart AOT（最强证据，直接反相关）**：decompiler-v3 的 CodeBLEU **0.671 → 0.722**（p=0.001）、
  compile@1 **25.1% → 41.1%**，而 **pass@1 反向移动，3.90% → 3.12%**。
  原话："pass@k must be adopted as the primary evaluation metric for neural decompilation."
- **可重编译率是近乎无用的正确性代理**。Agent4Decompile 消融：L1+L2（语法+编译）成功 **99–100%**，
  L3（执行）只有 **32–42%**——**57–68pp 的鸿沟**。CODEFUSE-DEBENCH 独立测得约 **50pp** 悬崖。
- **CodeAlign**（Dramko/Le Goues/Schwartz）：CodeT5 的完美对齐率只有 **8.56%**，
  而 CodeBERTScore 给它 **0.868–0.890**——高估约 10 倍。
- **LLM4Decompile 的论证**：编译抹掉变量名并重排逻辑，即使**正确**的输出编辑相似度也只有 6–14%。
  "A 15 ES score may seem low, yet the decompiled function and the source code are highly aligned."

注意 [BinMetric](https://www.ijcai.org/proceedings/2025/0858.pdf)（IJCAI 2025）仍然只用 CodeBLEU 打分——
把那些数字当作对正确性无信息量的。

### 3.6 能搬过来的评测机制：全都是"塞回原程序 + 用真实负载驱动"

四种机制，值得逐一研究：

**(a) DecompileBench —— 函数替换 + 覆盖率等价**（[arXiv 2505.11340](https://arxiv.org/abs/2505.11340)，
中科院信工所 + 清华 + 北大，[代码](https://github.com/vul337/DecompileBench)）
23,400 个来自 130 个 OSS-Fuzz 程序的真实函数。**Coverage Equivalence Rate**：
把重编译的候选**替换回原程序**，跑 fuzzer 种子语料，比对**分支覆盖模式**。
明确理由：*符号执行因路径爆炸失败；单元测试忽略全局状态与堆操作*。

**(b) PCodeTrans —— 原位热替换 + 断点对齐差分追踪**（[arXiv 2603.14855](https://arxiv.org/abs/2603.14855)，
清华 + 武大 + 信工所）**显式拒绝 QEMU/Unicorn 仿真**，改用运行时重定位把单独编译的函数热替换进原二进制；
再用 GDB 在配对执行上同步断点、比对归一化的变量值与控制流标记。
结果是文献最好：函数级编译 **100%**，行为等价 **99.55%/99.89%**（未 strip）、**96.84%/98.38%**（stripped）。

**(c) CODEFUSE-DEBENCH —— Frida 差分动态追踪**（[arXiv 2605.29490](https://arxiv.org/abs/2605.29490)，
**蚂蚁集团** + 清华 + 西电）240 个原子测试函数 × 8 维源文件 → 640 个二进制，
2 编译器 × 5 优化 × 2 调试模式 × **4 架构 {x86, x64, ARM32, ARM64}**。
Frida agent 注入活进程，拦截调用并 dump **ARM64 上的 x0–x7**。

**对本项目最重要的两条结论**：
- **跨反编译器的功能性差异是 20×，跨 LLM 只有 1.6×。** 工程投入应该砸在前端，不是模型。
- **ARM64 明确更难**：约 **30%** 的修复尝试落入**链接阶段**失败，而 x86/x64/ARM32 只有 4.2–8.2%，
  原因是 `ADRP+ADD` 重定位习语——被归类为**不可逆的上游损失**。
  另外类型系统崩溃占全部修复错误的约 **19%**。

**(d) PRD**（[arXiv 2202.12336](https://arxiv.org/abs/2202.12336)）—— 只重编译目标函数再拼回去，
**92.9%** 的情况产出测试等价的二进制。上面三者的思想祖先。

**空白**：没有人把 QEMU/Unicorn/angr harness 当一等的 IO 等价 oracle 用在规模上。
PCodeTrans 明确拒绝了仿真，DecompileBench 和 DEBENCH 用进程内替换和 Frida。
**这是个开放的位置，而本仓库已有的 unidbg 基础设施位置很好**（但见 §4.3 的负面证据）。

### 3.7 IL2CPP 相对 stripped C 的优势与劣势

**更容易（这条被低估，而且很大）**：
- `global-metadata.dat` 保留类型名、方法名、字段名、完整签名、类继承、泛型实例化、特性、
  字符串字面量、字段偏移。**SK²Decompile 的整个第二阶段（"Skin"，标识符命名）在 IL2CPP 上是免费的。**
- Idioms 最难的指标——**UDT nominal accuracy，在 ExeBench 上只有 5.6–6.4%**——在 IL2CPP 上约等于 100%。
  而 UDT 在 C 场景造成 **55–68% 的严格等价率下降**。
- CODEFUSE-DEBENCH 里占 19% 的**类型系统崩溃**失败类基本被消除。
- **ground truth 可制造**：用已知 C# 自建 Unity 工程走 IL2CPP，得到完美配对，
  且工具链版本可对齐目标。前无古人。

**更难（这条也被低估）**：
- **信息不只是丢失，还有添加。** IL2CPP 产物里塞满了源码里没有对应物的运行时脚手架：
  `il2cpp_codegen_*` 调用、null 检查、数组边界检查、类型检查/转换助手、泛型共享 thunk、
  `Il2CppMethodPointerTable` 间接、静态构造器守卫。
  **现有基准全都把编译建模成"有损"，没有一个建模成"有损 + 有增"。模型必须学会删掉大量汇编。**
  这是我预期 IL2CPP 更像 Dart（3–6%）而不是 C（69%）的主要理由——在项目特定工作展开之前。
- ARM64 有 §3.6(c) 的 30% 链接失败区间；所有头条数字都是 x86-64。

### 3.8 "能不能单独重编译并运行一个 C# 方法"

**机械上可以。** Roslyn 可以把单个方法编进合成类、引用 Cpp2IL/Il2CppDumper 产出的 dummy 程序集，反射调用。

**但那是容易的一半。** 难的一半和 ExeBench 为 C 解决的问题完全相同：
dummy DLL **没有方法体**，任何进入游戏其余部分的调用都返回不了东西。
需要的正是 ExeBench 的**合成依赖桩 + IO 样例生成**——
而即便 ExeBench 也只让 **约 15%（450 万里的 70 万）** 的 C 函数变得可执行。
游戏代码依赖更密（Unity API、单例、可变全局状态），预期比例相当或更差。

**所以 re-executability 这条主线在 IL2CPP 上基本断掉。**

## 四、形式化等价性验证：不可行

**判断：全量（10 万–16 万）不可行，差两个数量级。抽样子集有条件可行但性价比低。**

### 4.1 公开纪录：234 个函数

| 工作 | 证明了什么 | 规模 | 耗时 |
|---|---|---|---|
| **seL4 二进制验证**（Sewell/Myreen/Klein, PLDI 2013） | 完整 C↔**ARMv7 二进制** refinement，机器检查 | 9,500 行 C → 11,736 条 ARM 指令；**-O1: 260 函数，234 成功，0 失败，26 中止** | **59 分钟**（-O1）；**4h23m**（-O2，仅 **145 成功、18 失败、62 中止**） |
| **Alive2**（PLDI 2021） | LLVM **IR** 每个 pass 的有界 refinement | SQLite3: 12.2K 次配对检查 → **2,314 证明，38 错误，2,102 超时，100 OOM，7,543 不支持** | 6.37 小时 |
| **Semantic Program Alignment**（PLDI 2019） | **x86-64** 跨向量化的循环等价 | 56 个基准，目标 **15–149 条指令**；55/56 通过 | **中位数 45.0 CPU-小时**/例（最大 1,166） |
| **DDEC**（OOPSLA 2013） | x86 单循环等价 | 11 个基准，**13–79 条指令**；4/11 需人工改写 | 0.13 秒 – **12,889 秒** |
| **DiffKemp**（ICST 2021） | **非形式化**——CFG 匹配 + 手写变更模式 | **5,319 函数 / 149,030 行** | **8 分 44 秒** |

**关键否定：没有任何公开工作对真实二进制形式化验证过超过约 260 个函数。**
seL4 是纪录保持者（234 个成功），而且要求原始源码、手工受限的 C 方言
（无嵌套循环、无栈变量取地址、受限函数指针）、-O1。
把优化提到 -O2，成功率掉到 145/259 且有 18 个硬失败，作者归因于
"loop unrolling, loop invariant code motion and other loop structure optimisations"。

唯一摸到几千函数的工具（DiffKemp）**是靠放弃 SMT 和可靠性做到的**。
它自己的脚注承认"one can construct artificial programs that the described method would claim
semantically equal although they are not"，而且在 42 个真实 Linux 重构提交上，
对真正相等的函数也只确认了 **50%**。

两个补充数据点说明这一族有多脆：
- **LLREVE 在真实代码上**：DiffKemp 的实验 4，30 个真实 kernel/musl 函数，
  LLREVE "crashed for a large number of programs"，**恰好 1 次比较成功，其余全在 30 秒超时**。
- **Alive2 的失败分类**是 IR 级规模化等价的诚实图景：SQLite3 上约 19% 证明、约 17% 超时、
  **约 62% 含工具无法建模的特性**（主要是函数指针和库语义）。
  求解器超时从 1 分钟提到 5 分钟，结果变化不到 5%——这些是硬失败，不是不耐心。

### 4.2 最对口的工作：CMU SEI 的自认失败

Klieber & Svoboda，[Semantic Fidelity of Decompilers](https://www.sei.cmu.edu/documents/5964/Semantic-Fidelity-of-Decompliers_81yqaAk.pdf)（DoD 资助）。
场景严格更容易：x86-64、未 strip、未混淆、**有原始源码作 ground truth**。原话：

> "We are planning to use SeaHorn to formal verification of equivalence,
> **but we don't have it fully working yet**. So, we are doing **randomized testing** instead."

理由："Comparing the logs is **impractical for existing verification tools in the unbounded case**"，
而他们的有界变通 "**can give false counterexamples to equivalence**"——循环仅被重构时会给出假反例。

改用随机测试的结果（Ghidra，SPEC2006，2,650 个函数 × 1,000 次试验）：
**29% 全部运行等价，49% 全部不等价，18% 混合，5% 工具崩溃**。
分套件"全等价"率从 **14%（sjeng）到 53%（bzip2）**。
仅仅"产出语法有效的 C"这一步，FY22 平均成功率 **68%**（ffmpeg 23,053 个函数 → 57%；git 6,832 → 39%）。

对比一个反差（中，SEI 转引 Liu & Wang, ISSTA 2020）：在 2,504 个合成 `-O0` 测例上
（平均 243 行，**无 struct/union/array/pointer**），Ghidra **93% 正确反编译**。
**同一个工具，真实优化代码上约 29%。** 正确性是"反编译器 × 输入"的性质，不是反编译器的性质。

### 4.3 IL2CPP 特有的额外障碍

要对一个 IL2CPP 方法做符号执行或差分测试，必须建模：隐式 `this` 首参与末尾的
`const RuntimeMethod* method` 参数、`il2cpp_codegen_initialize_method(N)` 的惰性初始化副作用、
GC 堆对象布局、`Il2CppClass` vtable 虚调用、`IL2CPP_RUNTIME_CLASS_INIT` 静态构造器。

**unidbg 路线是干净的否定。**（强，一手检索）
`repo:zhkl0228/unidbg il2cpp` → **0 issues**；全站 `unidbg il2cpp` → **0 issues, 0 repos**；
中文检索返回两个完全不相交的文献体（unidbg 教程讲 JNI/签名 SO；IL2CPP 教程讲 Il2CppDumper/IDA/Frida），没有交集。
unidbg 用在 IL2CPP 上时**只用于元数据解密的叶子函数**（`MetadataLoader::LoadMetadataFromFile` 附近），从不碰运行时。

最接近的真实尝试是一次**有记录的失败**：
[frida-il2cpp-bridge discussion #625](https://github.com/vfsfitvnm/frida-il2cpp-bridge/discussions/625)——
有人把 `libil2cpp.so` 打包进自己的 app 以躲反 Frida，然后发现
"**without the full Unity game process loaded**"就没法追踪目标逻辑。至今无人回答。

本仓库自己的测量给出决定性证据：`research/unidbg-performance.md` 记录 `libil2cpp.so` 约 2 秒加载完，
但 `DT_INIT` 跳进 `libanort.so` 的 `xx1` 后**十分钟不返回**；
`research/ios-gaps.md` 记录厂商是 **Tencent TerSafe2 / Anort**。

### 4.4 成本数学

**模型 A —— Churchill PLDI'19（二进制级，无源码，≤149 指令函数中位 45 CPU-小时）。**
这是本项目的正确模型：机器码、无源码、真实优化器输出。

| 范围 | CPU-小时 | 64 vCPU 上 | 成本（现货约 $0.02/vCPU-h） |
|---|---:|---|---|
| 150,000 方法 | **6,750,000**（770 CPU-年） | **12 年** | **13.5 万–24.3 万美元** |
| 1,600（1%） | 72,000 | 47 天 | 1,400–2,600 美元 |
| 100 | 4,500 | 3 天 | 90–160 美元 |

**模型 B —— seL4（有源码、受限 C 方言、ARMv7、-O1，约 15 秒/函数）。**
朴素外推 15 万方法约 2,540 CPU-小时、单核 106 天、约 50 美元。**但这个数字是用
(a) 原始源码、(b) 无嵌套循环的手工受限方言、(c) 枚举 padding 与某个循环的人工绕过、
(d) -O2 下只有 56% 成功率和 18 个硬失败** 换来的。Revenant 一条都不具备。

15 秒与 45 CPU-小时之间的鸿沟，完全由"有没有源码、能不能约束输入语言"解释。

**无论哪种，算力都不是约束，工具存在性才是。** 在 100–1,600 方法量级上算力账单只有 100–2,600 美元，
是噪声。真正的账单是建一条不存在的 ARM64↔C# 等价流水线——而 SEI 花两个 DoD 财年做更容易的
C↔x86-64 版本，形式化那一半从没跑通。

### 4.5 一个认知问题

即使形式化等价验证能跑通，它回答的也不是最重要的问题。
重建 C# 的价值在于**可读、可理解、能支撑后续分析**。
一个把 `for` 写成 `while`、把三元展开成 if-else 的重建是语义等价的；
但如果它把某个业务常量抄错了，等价性检查只会说"不等价"，不会说错在哪、错得严不严重。
**"哪里错了"比"是否等价"更有价值，而前者需要的是 ground truth 对比和元数据核对，不是定理证明。**

### 4.6 分项判定

- **(a) 全量形式化等价：不可行。** 差两个数量级，且工具不存在。
  文献报告的每一种失败模式（循环重构、指针别名、间接/虚调用、缺失被调用方、无法建模的库语义）
  在这里都**更糟**：二进制被混淆加固，重建出的 C# 永远不会重编译成匹配的 ARM64，
  IL2CPP 的虚分派和泛型膨胀正是 Alive2 有 62% 归类为"不支持"的那些构造。
- **(b) 抽样形式化（100–1,600）：有条件可行，价值低。** 算力免费。
  条件：限定在自包含、无循环或有界循环、无指针、无副作用、不调用任何东西的方法——
  算术助手、哈希、位操作、小状态机。这一类大概是 15 万里的**个位数百分比**。
  不值得为它建专用流水线；要做形式化点检，就针对你已经怀疑的单个方法手工做。
- **(c) 仿真差分（unidbg/unicorn/QEMU）：不推荐。** 否定证据强且一致（§4.3）。
  在仿真器里立起 `il2cpp_init` + 解密元数据 + Boehm GC + JNI 是个大工程，
  而它的产物——一个没有合法 `Il2CppObject*` 可传的可调用方法——在活进程里是免费的。
- **(d) 活进程 Frida 差分：有条件可行，是唯一值得建的。** 见下。

### 4.7 唯一值得建的动态方案：录制回放

[frida-il2cpp-bridge](https://github.com/vfsfitvnm/frida-il2cpp-bridge) 的能力（强，读源码 `lib/structs/method.ts`）：
- `invokeRaw` **直接调用方法自己的原生代码**（不走 `il2cpp_runtime_invoke`）——正是你在重建的那段 ARM64。
  非静态方法会前置实例指针，inflated 泛型会后置 `MethodInfo*`。
- `Il2Cpp.trace(true)` 在 `virtualAddress` 挂 `Interceptor`，记录 RVA、每个参数名/值、返回值。
- **实例来自堆扫描**：`Il2Cpp.gc.choose(SystemType)` 和 `Il2Cpp.MemorySnapshot.capture()`。
  这就是"合法对象图从哪来"的答案——从活堆里捞，而不是合成。

**一个修正**：RVA 映射是**单向**的。`get relativeVirtualAddress()` 能从方法句柄拿到 RVA，
但**没有从裸 VA/RVA 构造 `MethodInfo` 的文档化途径**——查找是
`image.class("Ns.Type").method("Name").overload(...)`。所以要从 `[Address(RVA=...)]` 脚手架走到活的可调用对象，
得先从 Il2CppDumper/Cpp2IL 产物建一个反向索引。一次性脚本，不是阻塞项，但是真实工作量。

**推荐设计：录制回放，不是合成调用。** 用 `Il2Cpp.trace(true)` 在真实游玩中捕获
`(RVA, 参数, 返回值)` 三元组——游戏免费提供真实对象图——然后离线在 .NET 下回放对比重建的 C#。
这正是 DecompileBench 和 PCodeTrans 实际做的事（塞回真实程序、用真实负载驱动），
而且它消解了杀死其他所有方案的输入生成问题。
剩余的真实工作：序列化引用类型参数（tracer 只**打印**，不序列化）。

条件：(1) root 设备 + 打过补丁的 frida-server（如 [Florida](https://github.com/Ylarod/Florida)）或 Zygisk 注入；
(2) 逐游戏绕过 TerSafe2/Anort 的 Frida 检测；(3) 建反向 RVA 索引；
(4) 接受覆盖率受负载限制（一次游玩可能只触及 5–20% 的方法，且严重偏向热路径）；
(5) 处理畸形调用导致的进程死亡，以及已记录的参数追踪偶发 `access violation`。

## 五、退而求其次：应该落地的方案

### 5.0 先看行业基准：没有人信任反编译器输出

这是本节的前提。**专业逆向的通行做法不是"验证反编译输出"，而是"把它当可读但不可信的视图，
再用动态手段确认具体结论"。** 三家主流工具的官方立场都很明确。

**Hex-Rays / IDA**（强，官方文档）。没有笼统的免责横幅，但三处说得很清楚：
- [失败分类](https://docs.hex-rays.com/8.5/user-guide/decompiler/failures)列出五类失败，
  **"incorrect output text" 是其中之一**。立场是目标而非保证：
  "The current focus is on producing a correct output for any correct function.
  The decompiler should not crash, fail, or produce incorrect output for a valid input.
  Please file a bugreport if this happens."
- [FAQ](https://docs.hex-rays.com/9.0/user-guide/decompiler/faq)：
  **"In general, if the input information (function types) is incorrect, the output will be incorrect too."**
  举的例子极具警示性：把真实签名 `int func(int,int,int)` 声明成 `int func(void)`，
  **参数计算会从输出里完全消失**——这正是本项目最该警惕的静默丢代码模式。
  失败页另一句："A wrong type can wreak havoc very easily."
- 官方设计意图是**不可重编译**：输出为人类阅读速度优化，不为保真度优化；死代码消除是有意的，
  会让输出看起来比汇编"少"。
- [限制](https://docs.hex-rays.com/9.1/user-guide/decompiler/limit)：
  "exception handling is not supported"、"type recovery is not performed"、
  "global program analysis is not performed"。

**Ghidra**（强，但证据在源码里而不是免责声明里）。**NSA 没有发布笼统的"尽力而为"声明**——
不要引用不存在的东西。真正的证据更强：**反编译器会把正确性告警写进自己的输出**
（`Funcdata::warningHeader()`，[decompile/cpp/](https://github.com/NationalSecurityAgency/ghidra/tree/master/Ghidra/Features/Decompiler/src/decompile/cpp/)）：

| 告警 | 位置 | 错误类别 |
|---|---|---|
| `"Cannot assign parameter locations for this function: Prototype may be inaccurate"` | coreaction.cc:5264 | 签名错 |
| `"Type propagation algorithm not settling"` | coreaction.cc:5764 | 类型错 |
| `"Exceeded maximum allowable instructions: Some flow is truncated"` | flow.cc:404 | **丢代码** |
| `"Recovered jumptable eliminated as dead code"` | funcdata_block.cc:740 | **丢代码** |
| `"Creating undefined varnodes in (possibly) reachable block"` | funcdata_block.cc:325 | 凭空造值 |
| `"Bad switch case"` / `"Calculation of case label failed"` | jumptable.cc | switch 错 |

帮助页原话（`DecompilerOptions.html`）：
"if the user's explicit variable is labeling something that isn't really an explicit variable…
the Decompiler may incorrectly consider the stack location as dead and **start removing live code**."
`DecompilerConcepts.html`："The Decompiler may also merge varnodes that could just as easily exist as
separate variables. This is called **speculative merging**."
Ghidra 还自带 `FindPotentialDecompilerProblems.java`——一个官方脚本，专门找反编译器可能在撒谎的地方。

Issue 量级（强，GitHub API 实测）：`Feature: Decompiler` 标签共 **799 个 issue**（417 open），
其中 **98 个匹配 "incorrect"**、92 个匹配 "wrong"。
代表性例子：[#6275](https://github.com/NationalSecurityAgency/ghidra/issues/6275)
"Incorrect x86 decompilation produces empty loop"——
*"See empty loop in the decompiler view, while ASM view has a bunch of instructions"*；
[#8995](https://github.com/NationalSecurityAgency/ghidra/issues/8995) 26 个 SLEIGH 语义 bug，
一个**处理器规格**的 bug 静默污染该架构上的每一次反编译。AArch64 相关的反编译器 issue 有 30 个。

**Binary Ninja**（强，最坦白的厂商）。
[官方博客](https://binary.ninja/2024/06/19/restructuring-the-decompiler.html) 原话：
"we recently discovered that the goto redirection has problems with soundness"、
**"condition graph resolution may not be sound when any goto statements are introduced into the code."**
自家 7,000 个生成用例上 BN 4.0 与重写版的通过率：

| 类别 | BN 4.0 | 新解析器 |
|---|---:|---:|
| Complex Control | **75.7%** | 100% |
| Data Flow | **76.4%** | 100% |
| Complex Loops | **41.2%** | 99.8% |
| Complex Switch | **45.6%** | 100% |

一个在售的商业反编译器，在自家测试集的复杂循环用例上约 58% 语义错误。
（Vector 35 声明这些用例是对抗性的、"not designed to be representative of normal code"，
所以当"不可靠性演示"引用，别当领域错误率。）
文档里还有逐特性告警："Splitting a variable manually can cause IL and decompilation to be incorrect"；
变量合并 UI 直接把选项分成 sound / valid / **"potentially unsound"**；
`analysis.extractTypesFromMangledNames`（默认 **True**）"can lead to recovering inaccurate parameters"。

**Vector 35 自己的验证方法就是本问题的答案**：直接发射 AArch64 机器码、**在真实 CPU 上跑**、
再与 LLIL/MLIL/HLIL 模拟器的结果做差分。对着真值执行做差分行为测试。

**从业者实际怎么验证**（强：[Votipka et al., USENIX Security 2020](https://arxiv.org/abs/1912.00317)，
16 名 3–21 年经验的职业逆向工程师，70 分钟观察式访谈）。经典引述（P04V）：

> "A few of my friends generally argue that this is a mistake because
> **Hex-Rays can be wrong, and disassembly can't be**. And this is generally true,
> but **Hex-Rays is only wrong in specific ways**."

论文发现："REs are also able to recognize situations where the inaccuracies are common
and **can switch analysis granularities to verify results (N=5)**."

验证手段与人数（共 16 人）：

| 手段 | N |
|---|---:|
| **跑代码验证假设** | **13** |
| **调试器执行（探查内存、控制执行）** | **12** |
| 逐行读代码 | 9 |
| **用高级语言重写该片段并对比输出** | **8** |
| 抓包 / 文件监控 | 8 |
| 扫数据流路径 | 8 |
| 动态改注册表值 | 7 |
| 扫控制流路径 | 7 |
| 手工 fuzz | 6 |
| **patch 二进制强制走某条路径** | **5** |
| 找公开参考实现来对比 | 5 |
| 手工符号执行（Z3） | 2 |

Blowfish 那个例子是模板：认出算法 → 下载开源实现 → 对比结构 →
**把参考实现和恶意样本都跑在一个全零文件上** → "we can then verify on this sample data
whether it's real Blowfish or if it's been modified."
另外两条观察值得记：**"we did not observe any participants reading more than 50 lines of code"**；
**"Begin with static methods and finish with dynamic."**

Google Project Zero 的 Ian Beer
（[iOS zero-click radio proximity exploit](https://projectzero.google/2020/12/an-ios-zero-click-radio-proximity.html)）
在专家层面是同一形状：DTrace 插桩确认静态读数、`zprint` 经验性确认泄漏假设、
内核调试器**改写** TLV 观察 panic、Wireshark 做线级确认。读 → 假设 → 建 harness → 观察真实行为 → 才相信。

中文实践共识一致（中，二手）：
[知乎 软件逆向工程原理](https://zhuanlan.zhihu.com/p/1895058545218668227) 把动态分析定位为静态分析的必要补充；
[看雪 IL2CPP 逆向初探](https://bbs.kanxue.com/thread-278275.htm) 等一致认为
Il2CppDumper 能可靠恢复结构（类名/方法名/字段偏移）但**方法体逻辑无法完整还原**；
CSDN 上关于 AI 辅助逆向的表述最直白：
*"AI的分析结果不能作为最终结论，所有由AI发现的关键漏洞或逻辑，都必须经过人工复核验证"*。

**这一节对本项目的含义**：不要把"自动等价验证不可行"当坏消息——
**整个行业本来就没有这个东西，而且照样在工作。** 差别只在于，
本项目要在 10 万量级上工作，所以需要把"专家凭经验知道 Hex-Rays 在哪些具体方式上会错"
这件事，替换成可量化、可重跑的抽样指标。这正是 §5.1–5.4 的内容。

**一个反差值得单独记住**：同一个 Ghidra，
在 2,504 个合成 `-O0`、无指针/结构体/数组的测例上 **93% 正确反编译**（中，SEI 转引 Liu & Wang ISSTA 2020），
在真实优化过的 SPEC2006 上只有 **29% 全部运行等价**（强，SEI 实测）。
**正确性不是工具的性质，是"工具 × 输入难度"的性质。IL2CPP 产物是优化过的、泛型密集的、ARM64 的——难的那一端。**

### 5.1 L0：元数据一致性硬门（100% 覆盖，近零成本，精确）

这是本报告对本项目性价比最高的一节，因为 IL2CPP 给了 C 反编译项目没有的东西。
Il2CppDumper 产出 `DummyDll/`（完整签名）、`dump.cs`（签名、字段偏移、方法偏移、类型定义索引）、
`il2cpp.h`、`script.json`、**`stringliteral.json`（"contains all stringLiteral information"）**。

| 检查 | 怎么做 | 抓什么 |
|---|---|---|
| 类型检查通过 | 候选 C# + DummyDll 作引用，Roslyn 编译 | 幻觉 API、签名错 |
| 签名/元数比对 | 参数个数、类型、返回类型 vs 元数据 | 结构性误读 |
| 字段访问解析 | `ldr/str [obj, #off]` vs DiffableCs 的 `FieldOffset` | 读写错字段 |
| **调用目标匹配** | 重建 C# 里每个调用 ↔ 方法 RVA 区间内每条 `bl/blx` 的目标，目标 RVA 反查方法 | **漏调用、多调用、调错方法** |
| **字符串字面量集合** | 汇编引用的 `_stringLiteral*` ↔ `stringliteral.json` ↔ 重建 C# 的字符串常量 | 抄错文案、编造字符串 |
| **数值常量与 switch case 集合** | 汇编立即数与跳转表 ↔ 重建 C# 字面量 | **抄错业务参数**（游戏逆向最要命的一类错） |

这一层是**精确的、不需要 oracle 的**：重建里出现一个该方法任何 `bl` 都没指向过的调用，就是错的，毫秒级可证。
它只能证伪、不能证真——但它抓得住 LLM 最常犯、后果最严重的错。

**注意可编译性作为代理有多弱**：CODEFUSE-DEBENCH 测得可重编译率比真实行为重合高约 **50pp**；
DecompileBench：Hex-Rays 0.583 可重编译 vs 0.418 等价。
**把编译成功当必要条件，不当充分条件。**

### 5.2 L1：结构排序信号（100% 覆盖，低成本，不门控）

- **BB 数 / 边数 / 循环数 / 调用数 vs ARM64 CFG**。没有研究验证它们作为正确性 oracle，
  但作为**相似度**信号有强证据：BinDiff 给每个函数的签名恰好是
  **(基本块数, 边数, 调用数)** 三元组，相似度约为
  50% flowgraph MD-index 差 + 25% 匹配边 + 15% 匹配块 + 10% 匹配指令，
  且其算法明确包含 "String references"、"Loop count matching"、"Call sequence matching"。
  **所以调用图边匹配和字符串字面量匹配正是工业标准差分器用的东西**——用作 triage 有充分先例，别叫它"验证"。
- **Roslyn IL vs Cpp2IL CIL 的往返比对**。Cpp2IL 的 `dll_il_recovery` 输出确实产出 CIL
  （ARM64 → ISIL → CFG + 支配树 → 迭代精化 → `IlGenerator.GenerateIl()`）。
  IL-vs-IL 比 C#-vs-ARM64 容易得多：同指令集、同类型系统、无寄存器分配、无调用约定。
  **但注意 Cpp2IL 作者自陈"The decompiled CIL is pretty messy right now"**——
  它是**噪声参考，不是 ground truth**。正确用法是不对称的：**大幅 IL 分歧是值得人工复核的证据；
  IL 一致是正确性的弱证据。** 当排序信号用，不当闸门。
- **codealign**（[arXiv 2501.04811](https://arxiv.org/abs/2501.04811)，
  "Fast, Fine-Grained Equivalence Checking for Neural Decompilers"，Dramko/Le Goues/Schwartz）：
  定义指令级的**等价对齐**——告诉你两个函数**哪些部分**等价，而不是一个无量纲的相似度分数。
  以"比符号执行快得多"为设计目标，**不需要编译也不需要执行**，
  **大函数也 <1 秒**（纯 Python），对比符号执行动辄 2 小时。
  报告精度：self-align 99.9%、同题不同实现 95.9%、不同题 100%，共 12 个假阳。
  局限：对副作用顺序不可靠、忽略类型、不支持不可归约 CFG 与 `goto`、假设算法相同。
  **如果只读一篇论文来建评测 harness，读这篇。**

### 5.3 L3：多采样 + 机械重排序（不是投票）

**这是文献里 ROI 最高的手段，而且和"多模型投票"是两回事。**

**投票不可靠**（强，四条独立证据）：
- ["When LLMs Agree, Are They Right?"](https://arxiv.org/abs/2607.08065)（26.5 万样本）：
  一致性与正确性的 Spearman ρ 只有 **0.20–0.59**。
  **一致度 ≥0.8 时（覆盖 gpt-4.1 的 77% 案例），错误率仍有 48%。**
  而且相关性对最强模型最差。GPT-4.1 和 Claude 都错时，**50–71% 选了同一个错误答案**。
- ["Correlated Errors in LLMs"](https://arxiv.org/abs/2506.07962)（ICML 2025）：
  两个模型出错时一致率约 **60%**（随机基线 33%）；**100% 的 HuggingFace 模型对超过基线**。
  致命的一条：**越准的模型越相关。** 多模型一致性随模型变强而**变差**。
- ["Wisdom and Delusion of LLM Ensembles"](https://arxiv.org/abs/2510.21513)：
  oracle 上界比最好单模型高 **+83%**，但**基于共识的选择一贯劣于朴素基线**，
  而**基于多样性的选择能拿回上界的 95%**。
- [Universal Self-Consistency](https://arxiv.org/abs/2311.17311)（去掉执行后的直接类比）：
  代码任务上只比 greedy 高 **+3 到 +4pp**。

**最能说明问题的一条框架性结果**：["Large Language Monkeys"](https://arxiv.org/abs/2407.21787)——
GSM8K 上 Llama-3-8B 的**覆盖率**（正确答案出现在候选池里）从 79.8%@100 升到 **95.3%@10,000**，
而**多数投票只从 38.7% 升到 39.8%**。**约 55pp 的鸿沟，100 倍算力也填不上。**
原话："All sample selection methods fail to reach the coverage upper bound and saturate before reaching 100 samples."

**反复采样可靠地让正确答案"在池子里"，一致性可靠地找不到它。你的问题是一个选择问题，不是生成问题。**

**LLM-as-judge 打的是似然度，不是正确性**：CodeJudge（SOTA 代码评判器）在
**玩具、自包含、有自然语言 spec** 的函数上二分正确性准确率也只有
**80.6%（HumanEval-X）/ 74.6%（BigCodeBench）/ 68.3%（APPS）**。
决定性结果（[arXiv 2607.05904](https://arxiv.org/abs/2607.05904)）：自我博弈下评判器报告的通过率
**0.72 → 0.94，而真实准确率纹丝不动停在 0.20**，假阳率 0.719，**三评判器 ensemble 仍接受 55% 的假阳**。
**缓解措施便宜且应无条件采用：强制评判器在看到候选之前先提交自己的重建——假阳率从 0.719 降到 0.012。**

**对比重排序**：Decaf 的 N=32 + 机械重排序（含字节距离）给 **+24.8pp**。
**用途差一个数量级。**

结论：**用 N 个采样制造多样性（给 L3 重排序扩大候选池），不要用来投票。**
采样预算 5–10 个自适应分配即可，不是 40——
[Adaptive-Consistency](https://arxiv.org/abs/2305.11860) 在准确率损失 <0.1% 下省最多 7.9×。

**唯一可以放心投票的地方：名字。** 变量/方法名恢复没有 oracle 可丢，名字有近似规范形式，
且 SOTA 本来也只有约 50%（DIRE 35.9%、DIRTY 38.0%、VarBERT 50.7%）。那里随便投。

### 5.4 L4：抽样人工复核

**样本量**（二项比例，95% 置信，N=100,000）：

| 精度 | p=0.5（无假设） | p=0.9 | p=0.95 |
|---|---:|---:|---:|
| ±10% | 97 | **35** | 19 |
| ±5% | **385** | **139** | 73 |
| ±3% | 1,068 | 385 | 203 |
| ±1% | 9,604 | 3,458 | 1,825 |

两点必须内化：**有限总体校正在这里毫无价值**（±5% 时 385 → 383，省 2 个）；
**按 p=0.9 而不是 p=0.5 规划，样本量降 2.8 倍**（385 → 139）。后者轻微循环——
用两阶段设计：先看 50 个拿 p̂，再定主样本量。

**报 Wilson 区间，绝不报点估计**（Wald 在边界附近会给出 [0.94, 1.02] 这种荒唐结果）：

| n | 通过 | p̂ | Wilson 95% CI | 宽度 |
|---:|---:|---:|---|---:|
| 30 | 28 | 0.933 | **[0.787, 0.982]** | 0.195 |
| 100 | 90 | 0.900 | [0.826, 0.945] | 0.119 |
| 385 | 346 | 0.901 | **[0.867, 0.927]** | 0.060 |
| 100 | 100 | 1.000 | [0.963, 1.000] | 0.037 |

**n=30 太小，撑不起任何值得说的结论。**

**零失败时的三倍律**：95% 上界约 3/n。声称错误率 <1% 需要 **300 次连续干净复核**；
<0.1% 需要 **约 3,000 次**，且第一次失败就归零。**别承诺 <0.1%。**

**分层（Neyman 分配）**：`n_h ∝ N_h·S_h`。n=400 时的实测设计效应 0.807，约省 19% 样本。
但**要卖的理由不是省 19%，是结论的正确性**——IL2CPP 的方法总体被平凡的属性 getter 主导，
不分层的样本会产出一个好看但对没人关心的方法毫无信息量的头条数字。
按指令数分层给出可辩护的分复杂度准确率。

**单方法耗时**（强，三项独立研究）：

[RE-Mind](https://www.usenix.org/system/files/sec22-mantovani.pdf)（USENIX Sec 2022，72 名参与者，16,325 分钟插桩活动）
给出最好的逐函数数据。专家中位耗时随基本块数变化：1 BB → **0.26 分钟**；16 BB → **9.1 分钟**；
14 个函数（96 BB）合计 57.2 分钟，**均值约 4.1 分钟/函数**（新手 210.4 分钟，3.7×）。
关键观察：专家做完时只访问了 **48.2%** 的基本块，且对已访问块的 **22% 在 2 秒内就否掉**——
**专家靠不读代码取胜；强制穷尽阅读的流程达不到专家速率。**

[Yakdan et al.](https://net.cs.uni-bonn.de/fileadmin/ag/martini/Staff/yakdan/dream_oakland2016.pdf)（IEEE S&P 2016）
Hex-Rays 下的中位任务耗时 18.6–57.4 分钟（且**只统计成功完成的任务**，是乐观值）。
Votipka et al. 转引：**<150 行的反编译片段，平均 39 分钟**回答常见恶意软件分析问题。

代码审查作为旁证（中）：检查速率上限 <500 行/小时；**正式检视平均 200 行九小时（约 22 行/小时）**——
这是最接近"对着汇编仔细核对语义等价"的类比，也是最清醒的一条。

**规划值：平凡方法 5 分钟，典型 20 分钟，大方法 40–60 分钟。**

**成本表：**

| n | @10 分钟 | @20 分钟 | @40 分钟 |
|---:|---:|---:|---:|
| 100 | 16.7 h | 33.3 h | 66.7 h |
| **139**（±5% @ p≈0.9） | 23.2 h | **46.3 h** | 92.7 h |
| **385**（±5% @ p=0.5） | 64.2 h | **128 h** | 257 h |
| 3,000（零失败 <0.1%） | 500 h | 1,000 h | 2,000 h |

**n=385 @ 约 20 分钟 ≈ 128 人时 ≈ 一个工程师 3–4 周。** 这是甜点：无假设的 ±5%，
如果准确率真有约 90%，则免费得到 ±3%。

**迭代期用 SPRT。** Wald 序贯检验（H₀ 失败率 5% vs H₁ 15%，α=0.05, β=0.10）
**期望样本量约 34–39**，对比区间估计的 139–385。边界：n=40 时 ≤1 失败接受、≥7 拒绝；
n=100 时 ≤7 / ≥12。**改 prompt/换模型用 SPRT 门控，最后跑一次固定 n 的研究出正式数字。**

**全量人工复核的对照**：15 万方法按专家 4.1 分钟算是 **6,810 人时（3.8 人年）**，
按现实的 20 分钟算 **33,333 人时（18.5 人年）**，按 Yakdan 的 39 分钟算 **65,000 人时（36 人年）**。
即使最乐观的专家速率也是约 4 人年。**这不是"抽样是捷径"，是"抽样是唯一可行的东西"。**

### 5.5 试点：二进制内交叉验证（新颖，无文献，值得试点）

**这一节证据最弱，我没找到任何把二进制内冗余当正确性 oracle 的研究。** 机制本身是真实的：

IL2CPP 为每个泛型实例化发射独立原生函数（引用类型部分共享），
所以 `List<Foo>.Add` 和 `List<Bar>.Add` 产出几乎相同的 ARM64，主要差别在类型元数据指针。
Il2CppDumper 的 `dump.cs` 和元数据使用表能识别哪些原生函数对应同一泛型定义的实例化。
**这给出免费的、有标注的近重复配对**：独立重建两者，重建出的 C# 方法体（模掉类型参数）不一致就是强错误信号，
成本只有第二次推理。

**这是二进制内版本的自一致性——而且它绕开了 §5.3 的相关误差问题，
因为冗余是产物的性质，不是模型采样分布的性质。**

第二个信号是**调用点一致性**：被多处调用的方法受所有调用点约束（参数个数、寄存器使用、返回值消费）。
IL2CPP 上不需要**推断**签名（元数据给了），所以有用的方向是反过来的：
**用元数据签名检查各调用点的重建在如何使用被调方上是否互相一致。**

第三个是**重复函数检测**：BinDiff 的哈希匹配（字节相同）、素数签名匹配（指令顺序无关）、FLIRT 签名
都能廉价识别结构相同的函数。两个原生函数哈希相同而流水线重建出不同结果，至少有一个是错的。

**诚实评估：好主意，没有文献支撑。** 但试点很便宜——取 200 对泛型实例化，独立重建，
测分歧率，并在同一批上把分歧与人工判定的正确性做相关。
**这个试点约 70 人时就能告诉你这个信号的精度，而且是真正新颖的。**

### 5.6 Token 成本：不是瓶颈

**T1 实测**：`IsilDump/Assembly-CSharp` 36 MB / 12,089 个方法 ≈ **3.0 KB 反汇编文本/方法 ≈ 约 1k token**。
加类型上下文、被调方签名，实际输入约 5–20k token/方法。

| 价位（$/M 输入, 输出） | 6k in / 2k out，单方法 | 100,000 方法 |
|---|---:|---:|
| $15 / $75 | $0.240 | **$24,000** |
| $3 / $15 | $0.048 | **$4,800** |
| $1 / $5 | $0.016 | $1,600 |
| $0.25 / $1.25 | $0.004 | $400 |

批量折扣与 prompt 缓存（同类方法共享的元数据/类型上下文缓存率很高）大约能压到三成，
所以中间价位的典型情形约 **1,400 美元跑完 10 万方法**。
N=8 自一致性把输出成本乘 8 倍，但输入侧大部分被缓存吸收。

**对照人工复核 10 万方法的费用：**

| 时薪 | 5 分钟/方法 | 15 分钟 | 39 分钟（Yakdan） |
|---|---:|---:|---:|
| $60/h | $500k | $1.5M | $3.9M |
| $150/h | $1.25M | $3.75M | $9.75M |

**这个不对称就是全部结论：LLM 重建 10 万方法的成本是 10²–10⁴ 美元，
人工验证同样 10 万方法是 10⁵–10⁷ 美元——差三到四个数量级。**
而 n=385 的抽样复核按 $150/h、20 分钟/方法算约 **$19,000**；
全量自动一致性检查的成本约等于零。
**模型调用不是约束，验证才是**——这正是本调查的前提。

## 六、行动建议

1. **先做 L0 的元数据一致性检查**（调用目标 / 字符串字面量 / 常量集合 / 字段偏移）。
   一到两周能出，立刻抓到最贵的错误类型，而且这是 IL2CPP 相对通用反编译的独有优势，不用白不用。
2. **建 OSS ground truth 标定集**：先只做 Mono BCL，从 mscorlib + Newtonsoft.Json 里
   **按指令数分层**抽 300 个非泛型、非 extern、非编译器生成的方法，配上游预处理后的源码，
   跑一遍现有 prompt，拿到第一个真实准确率数字。
   **在这一步之前，任何关于"方法论成本"的讨论都是空的。**
3. **不要把 recompile-and-diff 当闸门；如果做，做成重排序信号**（N=8～32 候选 + 字节距离排序）。
   这是文献里效果最大的单一手段（+24.8pp），且当排序用时配置猜错只让信号变噪、不会判错。
4. **人工复核用 n=385 分层抽样跑一次拿正式数字（128 人时），迭代期用 SPRT（n≈35–40）门控。**
   报 Wilson 区间。**预先书面登记失败判定标准**，并让两名复核者独立评分一个重叠子集以公布评分者间一致度——
   **全部认知风险都在"什么算对"上，不在算术上。**
5. **不要用 LLM-as-judge 或多采样一致性当验收闸门。** 若用评判器，强制先提交自己的重建
   （假阳率 0.719 → 0.012）、随机化位置、绝不让生成模型评判自己的输出。
6. **可以试点的新东西**：泛型实例化对的交叉一致性（约 70 人时），以及
   frida-il2cpp-bridge 的**录制回放**（用 `Il2Cpp.trace` 抓真实调用，离线在 .NET 回放）——
   后者是唯一在文献里被反复验证有效的动态范式（塞回真实程序 + 真实负载驱动）。
7. **可以承诺的话术**："300 次干净分层复核 → 错误率 <1%，95% 置信"，约 100 人时。
   **不能承诺** "<0.1%"——那需要 3,000 次连续干净复核，第一次失败即归零。

## 附录：未闭合的缺口

本次调查（含四个并行子调研）耗尽了会话的 WebSearch 配额（200/200）。以下未覆盖或需复核：

- **D-Helix（USENIX Sec 2024）的函数计数与逐函数超时**——PDF 403。
  它是现存最接近"你要建的东西"的设计（RECOMPILER 重编译 + SYMDIFF 符号差分），值得单独一次抓取。
  已知梗概：Clang 只能重编译 24.9% 的 Ghidra 函数，RECOMPILER 提到 **72.4%（40,129 个）**；
  SYMDIFF 能分析其中 **91.3%**；**2 分钟 SMT 超时**；净验证覆盖约 **66%**。
- **Agent4Decompile 的头条数字有冲突**：两次独立检索分别得到 50.3%/40–46% 与 84–97%。以直接抓取的低值为准，需复核。
- **Liu & Wang ISSTA 2020 的"93% 正确反编译"是二手**（经 SEI 转引），发布前需核对 ACM 原文。
- **中文非 arXiv 来源未覆盖**：CNKI/知网、软件学报、计算机学报、腾讯玄武/奇安信/360 的安全博客。
- **§5.5 的二进制内冗余提案没有文献支撑**，是有据可依的机制假设，不是既有实践。已按弱证据标注。
- **BinDiff/Diaphora/BinSim 是相似度工具而非等价性工具**这一表述未找到可引用的论文原话，属背景推断。
- **Unity IL2CPP internals 博客（403）与泛型共享手册页（404）本次未能直取**，
  §2.5(c) 的泛型共享机制细节按中等置信度处理。
