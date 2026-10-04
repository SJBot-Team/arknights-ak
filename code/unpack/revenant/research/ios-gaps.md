# Revenant iOS 支持：事实与缺口清单

针对 joycastle/revenant#3 的调研产物。**只列事实与缺口，不含设计方案**（那是 #7）。

调研范围：`vita-majhong-re`（iOS metadata S-box 脱壳，已攻克）、`2026-06-09-gossip-harbor-re`（iOS IPA 交叉验证 + 实测 ipa 结构）、Revenant 当前源码全量精读、Cpp2IL 源码（`/Users/zengjie/workspace/playground/Cpp2IL`）。

标注约定：

- **[事实]** = 本次实测或笔记中已有 T1/T2 级证据
- **[推断]** = 我的推理，未经验证
- 沿用笔记的证据分级：T1 = 决定性（统计/自洽校验/调用图核实）、T1.5 = 多产物对照、T2 = 采样核验、T3 = 同构推断
- **[已攻克]** = 手工走通过、有脚本与产物，只是没进 Revenant
- **[从未解决]** = 两个项目里都没做过

## 一、已攻克的 iOS 知识清单

### 1.1 IPA 包结构与二进制定位

| # | 事实 | 来源 | 分级 | 状态 |
|---|---|---|---|---|
| 1 | ipa 就是 zip；真身在 `Payload/<App>.app/` 下 | arch-10 §8.1 + 本次实测 | T1 | 已攻克 |
| 2 | **主可执行是瘦启动壳，不含 IL2CPP 代码**。GH 实测 `Payload/GossipHarbor.app/GossipHarbor` = 71,344 B；Vita 实测 `VitaMahjong` ≈ 90KB | arch-10 §8.1、arch-03 §重打包、本次 `zipfile` 实测 | T1 | 已攻克 |
| 3 | **IL2CPP 代码在 `Frameworks/UnityFramework.framework/UnityFramework`**。GH = 104,190,976 B；Vita = 125MB（笔记）/ 实测 `_refs_ios/UnityFramework` filesize 108,052,480 | 同上 | T1 | 已攻克 |
| 4 | metadata 路径 = `Payload/<App>.app/Data/Managed/Metadata/global-metadata.dat`（**无 `assets/bin/` 前缀**，与 Android 不同） | 本次实测两个包 | T1 | 已攻克 |
| 5 | iOS Addressables/bundle 根 = `Data/Raw/aa/ios/`（Android 是 `assets/aa/android/`）。GH 实测该前缀下 307 个条目 | 本次实测 | T1 | 已攻克 |
| 6 | Lua bundle 在 `Data/Raw/aa/ios/lua_assets_assets/scripts/lua/*.bundle`，命名与 Android 同构（`lua_base.bytes_<hash>.bundle`） | 本次实测 | T1 | 已攻克 |
| 7 | 两个包的 `UnityFramework` 都是 **thin arm64 Mach-O**（`0xFEEDFACF`），**不是 fat**；`cryptid=0`（已脱 FairPlay） | 本次 `file` + `otool -l` 实测 | T1 | 已攻克 |
| 8 | 三方 SDK 各自是独立 `.framework`（GH 有 AppLovinSDK / FBSDK*；Vita 另有加固壳 `anortx.framework/anortx`） | arch-03、arch-10 §8.1、本次实测 | T1 | 已攻克 |
| 9 | `Info.plist` 是二进制 plist，`plutil` 可读；含 SKAdNetwork 列表、包名、版本、Facebook/Google 配置、`LSApplicationQueriesSchemes` | arch-03 §样本身份、arch-10 §8.4 | T1 | 已攻克 |
| 10 | Unity 版本可从 iOS 包侧读到（Vita 实测 2022.3.62f2，与 Android 完全一致）| arch-03 §引擎 | T1 | 已攻克（但笔记未记具体读取路径） |

### 1.2 metadata 加密与脱壳

| # | 事实 | 来源 | 分级 | 状态 |
|---|---|---|---|---|
| 11 | **GH 的 iOS metadata 未加密**：本次实测 magic = `af1bb1fa` (`0xFAB11BAF`)，version = `0x1f` (31)，size 8,114,944 | 本次实测 | T1 | 已攻克（无需工作） |
| 12 | **Vita 的 iOS metadata 加密 = 位置无关单字节 S-box 代换**（不是块加密、不是 XOR）。body（file offset ≥ 128）逐字节 `plain[i] = INV[cipher[i]]`，一张 256 项双射表 | arch-06 §加密模型 | T1（频率统计 + 自洽重解，不一致=0） | 已攻克 |
| 13 | 加密态 magic = `80 52 1f 6e`（本次实测 `_refs_ios/global-metadata.dat` 头部一致），解密后 = `af1b b1fa 1f00 0000` | arch-06、本次实测 | T1 | 已攻克 |
| 14 | 头 128 字节由壳 `anortx` 的硬编码明文模板 `__data@0x68170` 回填，`[0:4]` 写回 magic | arch-06 §结论先行 | T1 | 已攻克 |
| 15 | **陷阱**：IL2CPP v31 header = 264 B（66×uint32），模板只回填前 128 B；字节 `0x80–0x107`（表 offset/size）走 S-box 解密，**不是模板** | arch-06 §加密模型末段 | T1 | 已攻克 |
| 16 | **P=4 回归损坏**：`recover_sbox_periodic.py -P 4` + `solve_sbox.py` 把 `0x80–0x107` 解错 26 字节，`typeDefinitions` offset（header uint32 #40, file 0xA0）从 `0xa409ec` 变 `0xa409e4`（偏 8）→ 14418 个类名塌缩成 23 个垃圾值。`periodic.dat`/`solved.dat` **勿用** | arch-06 §P=4 陷阱、_session-handoff | T1（三产物 typeDef nameIndex distinct: plain=12298 / periodic=23 / solved=23） | 已攻克（教训） |
| 17 | **验证方法学**：类名健康必须查 **distinct 数量 + 已知类命中**，只查 ASCII/越界会全绿放行坏产物 | arch-06 §P=4 陷阱 | T1 | 已攻克（关键，Revenant 里完全没有） |
| 18 | 单表恢复方法 = 密文频率初值 + **Android 明文锚点投票**（跨平台已知明文攻击）| arch-06 §复现命令、`tools/recover_sbox.py` | T1 | 已攻克 |
| 19 | 残余 ~1% 是**静态盲区**：1622 条坏 name（typeDef 161 / method 715 / field 716 内容坏 + 30 越界），散布在 ~1042 个 distinct 坏 nameIndex；成因是罕见 cipher 频率法定不了值 + iOS 特有类无 Android 对照。多表/已知明文救不了，要 100% 需运行时 dump | arch-06 §残余、_session-handoff | T1 | 已攻克（已知不可静态修） |
| 20 | 质量校验指标：字符串区非 ASCII 字节数 iOS 解密后 = 842 = Android 明文 842（精确相等）；名字集合与 Android 重叠 typeDef 81.8% / method 82.9% / field 84.6% | arch-06 §正确产物质量 | T1/T2 | 已攻克 |
| 21 | 加固厂 = 腾讯 TerSafe2 / Anort；iOS 壳组件 `anortx.framework/anortx`（arm64, cryptid=0），Android 侧是 `libil2cpp.so` 的 `DT_NEEDED: libanort.so` | arch-03 §加固 | T1 | 已攻克 |
| 22 | 同一加固厂在两平台用**不同**方案：Android 是分层 XOR（`0x66` / NEON 块 / DWORD-XOR `0x66666666`），iOS 是 S-box 代换 | arch-03 §加固、arch-06 | T1 | 已攻克 |

### 1.3 已有的 iOS 工具链（`vita-majhong-re/tools/`）

`_refs_ios/cpp2il_out/` 与 `dumper_out/` **都是空目录**（本次实测）——即从未跑出过 iOS 侧的 Cpp2IL 或 Il2CppDumper 产物。所有 iOS 分析都靠下面这些自写脚本：

| 脚本 | 作用 | 可复用性 |
|---|---|---|
| `tools/ios_macho.py` | 完整的 Mach-O arm64 静态分析器：解析 `LC_SEGMENT_64` / `LC_SYMTAB` / `LC_LOAD_DYLIB`，提供 `v2f`/`f2v` 双向映射、`__text` 定位、capstone 反汇编 + adrp/add 字符串注解、adrp+add/adrp+ldr xref 扫描、字节搜索 | **高**。`v2f()` 就是 Revenant `elf.py` 的 Mach-O 对应物 |
| `tools/ios_xref.py` | iOS xref 扫描 | 低。**硬编码**了 `TEXT_OFF=0x8000` / `CSTR_OFF=0x60132f0` 和一个 `~/.claude/jobs/...` 临时路径，一次性脚本 |
| `tools/recover_sbox.py` | 单表 S-box 恢复（正确产物的生成器） | 高，但接口是 CLI 位置参数，需 Android 明文做锚点 |
| `tools/recover_sbox_periodic.py`、`solve_sbox.py`、`fix_sbox_by_index.py`、`fix_periodic_by_index.py`、`polish_sbox_struct.py` | P=4 路线的产物 | **不要复用**（已知回归损坏） |
| `tools/count_overflow.py`、`sbox_audit.py`、`name_audit.py`、`body_diag.py`、`dump_seg.py`、`kpa_analyze.py`、`garble_stats.py`、`analyze_garble.py` | metadata 解密质量诊断 | 中高，但 `count_overflow.py`/`name_audit.py` 有已知盲区（见事实 #17） |
| `tools/decrypt_metadata.py` | **Android** TerSafe2 解密 | 与 iOS 无关，但说明「解密器」这个抽象两平台都需要 |

`ios_macho.py` 的一处**关键前提**（写在 docstring 里）：「vaddr 即 Mach-O 虚拟地址（对无 slide 的 dylib，文件内 `__TEXT` fileoff == vaddr）」——这个前提对 `UnityFramework`（dylib，`__TEXT vmaddr=0`）成立，对主可执行不成立。见第二节。

### 1.4 跨平台同构性（决定工作量的关键判断）

| # | 事实 | 来源 | 分级 |
|---|---|---|---|
| 23 | GH 的 iOS 与 Android **共享同一份托管 C#**，托管层结论可直接平移 | arch-10 §8.3 | T3（同构推断，非逐名核验） |
| 24 | Vita 同理：同 Unity 构建、同程序集集合、metadata 大小差 0.15% | arch-03 §引擎 | T3 |
| 25 | **修正**：arch-10 §8.3 说 iOS/Android「`global-metadata.dat` 一致」——本次实测 **不是字节一致**。GH iOS 8,114,944 B、md5 `fd550386...`；Android 各版本 7,405,152–8,024,928 B，md5 全不同。iOS 多出 iOS 专属程序集（Facebook.Unity.IOS 等），Vita 侧 arch-03 也列了 iOS 独有 dll。「一致」应读作「同一份游戏 C# 源码」，不是同一份文件 | 本次实测 | T1 |
| 26 | 因此 **RVA 不可跨平台复用**：iOS 与 Android 是两次独立的 IL2CPP 编译，方法地址、metadata 索引全不同 | 由 #25 直接推出 | [推断]，但置信度高 |

## 二、Mach-O vs ELF 的 RVA 语义差异

`revenant/elf.py` 的全部逻辑建立在四个 ELF 前提上，逐条对照 Mach-O：

| ELF 前提（`elf.py` 位置） | Mach-O 实况 | 是否成立 |
|---|---|---|
| 文件以 `\x7fELF` 开头（`elf.py:98`、`binary.py:50-55`） | Mach-O 魔数 `0xFEEDFACF`（64 位 LE 文件里字节序为 `cf fa ed fe`）；fat 是 `0xCAFEBABE`（大端存储） | **不成立** |
| 段来自 program header 的 `PT_LOAD` 项（`elf.py:68-91`、`elf.py:118-141`） | Mach-O 用 load commands 里的 `LC_SEGMENT_64`（cmd = `0x19`）；没有 program header 概念，也没有 `p_type` | **不成立** |
| 段结构字段 `p_vaddr/p_offset/p_filesz/p_memsz/p_flags` | 对应 `vmaddr/fileoff/filesize/vmsize/initprot|maxprot`（语义近似但布局完全不同：`LC_SEGMENT_64` 在 cmd 头后 `+8` 是 16 字节 segname，`+24` 起是 4 个 u64） | 概念可映射，解析代码全不可用 |
| 可执行判定用 `p_flags & PF_X`（`elf.py:34`，`PF_X=0x1`） | Mach-O 用 `initprot & VM_PROT_EXECUTE`（`0x4`，**位值和 ELF 的 `PF_X=0x1` 恰好相反**：ELF 的 `0x4` 是可读，Mach-O 的 `0x4` 是可执行） | **不成立，且是静默错误风险** |

额外的 Mach-O 特有语义差异：

1. **RVA 基址取决于 filetype [事实，本次实测]**
   - `UnityFramework`（`MH_DYLIB`）：无 `__PAGEZERO`，`__TEXT vmaddr = 0x0`、`fileoff = 0`。所以 **VA == RVA == 文件偏移（在 `__TEXT` 内）**。GH 实测：`__TEXT vmaddr=0x0 vmsize=0x52f4000 fileoff=0 filesize=86,982,656`；`__DATA vmaddr=0x52f4000 fileoff=86,982,656`。Vita 的 `UnityFramework` 同样 `__TEXT vmaddr=0x0`。
   - `GossipHarbor`（`MH_EXECUTE`）：有 `__PAGEZERO vmaddr=0x0 vmsize=0x100000000`，`__TEXT vmaddr = 0x100000000`。这里 **VA ≠ RVA**，RVA = VA − 0x100000000。
   - 结论：IL2CPP 目标（UnityFramework，dylib）的 RVA 语义碰巧最简单；但**「基址 = 第一个非 `__PAGEZERO` 段的 vmaddr」这个减法不能省**，否则某天遇到 IL2CPP 静态链进主可执行的包（老版 Unity、或不用 UnityFramework 的构建）会整体偏 4GB。
2. **段 vs 节的映射粒度分歧 [事实，读 Cpp2IL 源码]**：Cpp2IL 的 `MachOFile.MapVirtualAddressToRaw`（`LibCpp2IL/MachO/MachOFile.cs:101-113`）按 **section**（`Sections64`）映射，而 `elf.py` 与 `tools/ios_macho.py:73` 都按 **segment** 映射。段内 section 之间有对齐填充 gap；落在 gap 里的地址，按 segment 映射会返回一个「合法但无意义」的偏移，按 section 映射会报错。两种做法对 `__text` 内的地址结果相同。[推断] 这是未来 Revenant 与 Cpp2IL 输出对不齐的一个潜在 off-by-gap 来源。
3. **chained fixups（dyld 链式重定位）[事实，读 Cpp2IL 源码]**：现代 iOS 二进制用 `LC_DYLD_CHAINED_FIXUPS` 取代传统 rebase/bind。文件里的指针字段**不是最终值**，是打包的 chain entry（target + next + bind 位）。Cpp2IL 在 `ApplyChainedFixups()`（`MachOFile.cs:170-242`）里就地改写整个缓冲区把它们还原成真指针。**任何直接读文件里 u64 指针的代码（如 `elf.py:175 read_u64_at_rva`）在 Mach-O 上会读到未修正的 chain entry，得到垃圾地址。** ELF 侧没有对应问题（`libil2cpp.so` 的 RELA 在正常静态分析中一般不需要预先应用）。
4. **fat / universal binary [事实]**：格式存在（Cpp2IL 有 `MachOUniversalFile` 支持，`LibCpp2IlBinaryRegistry.cs:40-43` 注册了 `0xBEBAFECA` 检测）。但**本次实测的两个包都是 thin arm64**——App Store 分发的 ipa 早已单架构。[推断] fat 拆分是低概率路径（只有从 Xcode 构建产物或模拟器包取二进制时才会遇到），不是 iOS 支持的必要前置。
5. **`__TEXT` 是只读 + 代码在 `__TEXT,__text` 节**：`elf.py` 没有节的概念，`disasm.py` 也从不查节，靠 RVA 直接读。[推断] 这一点对 iOS 反而不构成阻碍。
6. **符号来源不同 [事实]**：ELF 有 `.dynsym`；Mach-O 的导出在 `LC_DYLD_INFO(_ONLY)` 的 export trie（Cpp2IL `MachOExportTrie.cs`）或 `LC_SYMTAB`。Revenant 目前不读符号表，所以此项暂不构成缺口，但 `ios_macho.py` 的 `nearest_sym` 依赖它。

## 三、metadata 加密的多样性

**已知变体清单（全部有实测证据）：**

| 变体 | 样本 | 平台 | 机制 |
|---|---|---|---|
| 无加密 | Gossip Harbor 3.91.0 ipa / 3.63–3.92 apk | iOS + Android | 明文，magic `0xFAB11BAF` 直读 |
| TerSafe2/Anort **Android** 版 | Vita Mahjong 3.28.1 apk | Android | 分层：magic `0x12724394`；`[8..0x1000)` 单字节 XOR `0x66`；`[0x1000..0x5000)` NEON 块加密；`[0x11000..end)` 每 64KB 块前 0x4000 字节 DWORD-XOR `0x66666666` |
| TerSafe2/Anort **iOS** 版 | Vita Mahjong 3.28.0 ipa | iOS | magic `0x6e1f5280`；头 128 B 模板回填 + body 单字节 S-box 代换 |

**这是加固厂方案还是游戏自选？——[事实 + 推断]**

- [事实] 同一加固厂（TerSafe2/Anort）在两个平台上用了**完全不同的机制**，且 Android 侧是分层分区、iOS 侧是全 body 均质代换。这排除了「一个厂 = 一种算法」的简单模型。
- [事实] GH 与 Vita 是两家不同发行商（Microfun vs Meevii/Learnings），GH 完全不加固，Vita 两端都加固。
- [推断，中等置信] **加密方案由加固厂决定，是否加固由游戏方决定**。厂商内部还按平台/版本分方案（Anort 类名里出现 `MetadataFile_v27_v29`，暗示厂商自己就有多个版本化的 metadata 处理实现——arch-03 §加固）。
- [推断] 除 TerSafe2 外，市面上还有 Ijiami/爱加密、梆梆、腾讯乐固、网易易盾等 Unity 加固方案，各有自己的 metadata 变换；此外大量游戏用自研的简单 XOR/AES-CBC 头部加密。**总数无法枚举**。

**解密器需要多大的插拔空间？——[推断]**

从已知三例归纳，一个解密器需要能表达的自由度至少包括：

1. **识别**：加密态的 magic 不是 `0xFAB11BAF`，且每种方案的 magic 不同（`0x12724394` / `0x6e1f5280`）。识别只能靠「magic 指纹表 + 逐个试解」。
2. **分区**：Android TerSafe2 需要按 file offset 分 4 个区、每区不同算法、还有 64KB 周期性块内偏移。iOS 版则是「头 128 B 特判 + body 均质」。
3. **外部依赖**：iOS S-box 恢复需要**同游戏的 Android 明文 metadata 作为已知明文锚点**，还需要从壳二进制（`anortx`）里提取头模板（`__data@0x68170`）。这不是纯函数式的 `decrypt(bytes) -> bytes`，它需要额外输入。
4. **产物验收**：解密不是二值成功/失败，Vita 的正确产物也只有 ~99% 正确。必须配质量门（distinct nameIndex 数、已知类命中、字符串区非 ASCII 计数与参照对比）。
5. **运行时逃生口**：arch-06 明确记录「要 100% 走运行时 dump（越狱/模拟器抓 `il2cpp_init` 后内存）」。任何静态解密器都有天花板。

**Revenant 当前的插拔空间 = 零 [事实]**：`revenant/metadata.py:50-53` 在 sanity 不等于 `0xFAB11BAF` 时直接 `raise`；`revenant/binary.py:58-63` 的 `_looks_like_metadata()` 用同一 magic 做提取时的筛选，加密的 metadata 会被当成「没找到」。全代码库无 `decrypt` 相关钩子（唯一的 `decrypt` 在 `lua.py:85`，是 Lua blob 的 XOR，与 metadata 无关）。**注意这是 Android 侧就已存在的缺口**——Vita 的 Android 版也进不了 Revenant。

## 四、Cpp2IL 在 Mach-O 上的可行性

**[事实，读源码]** Cpp2IL **原生支持** Mach-O，无需额外参数：

- `LibCpp2IL/LibCpp2IlBinaryRegistry.cs:35-43` 注册了两个 handler：`Mach-O File`（魔数 `0xFEEDFACE`/`0xFEEDFACF`）与 `Universal Mach-O File`（`0xBEBAFECA`，取 `.BestMachOFile`）。**格式是自动从魔数嗅探的**，`--force-binary-path` 直接指向 `UnityFramework` 即可，现有的 `run_cpp2il_isil.sh` 参数集不需要新增开关。
- `LibCpp2IL/MachO/` 有 26 个源文件：段/节/符号表/导出 trie/chained fixups/universal 全都实现了。
- CPU 类型 → 指令集映射齐全（`MachOFile.cs:47-59`：X86_32 / X86_64 / ARM_V7 / ARM_V8）。
- **但源码自带警告**：`MachOFile.cs:68` 无条件打印 `"Mach-O Support is experimental. Please open an issue if anything seems incorrect."`；`:66` 对 32 位 Mach-O 打印「未经测试」。
- `MachOFile.cs:124-127` 的 `GetRva(pointer) => pointer; //TODO?` —— **对 dylib（`__TEXT vmaddr=0`）正确，对带 `__PAGEZERO` 的主可执行会错 4GB**。这与第二节的分析吻合。
- `ApplyChainedFixups` 的 bind 分支是 `//TODO: Bind.`（`MachOFile.cs:213`）——只做 rebase，不做 bind。[推断] 对 IL2CPP 的内部指针（都是 rebase）够用，对跨库导入指针不够。

**实际跑过的证据：**

| 项目 | 证据 | 结论 |
|---|---|---|
| vita-majhong-re | arch-06 §关键路径：「Cpp2IL：`.../Cpp2IL.dll`，需 `DOTNET_ROLL_FORWARD=LatestMajor`；**对 iOS 125MB Mach-O 卡在 "Applying reloc"**（性能瓶颈，非解密问题，故 `cpp2il_out` 为空）」 | **跑过，失败/卡死**。本次实测 `_refs_ios/cpp2il_out/` 与 `dumper_out/` 均为空目录，与笔记一致 |
| 2026-06-09-gossip-harbor-re | `_refs/` 下只有 8 个 Android 版本目录，无 iOS 产物；arch-10 §8 的 iOS 分析全靠 `plutil`/`strings`/`otool` | **从未跑过** |

**「Applying reloc」的定位 [事实 + 推断]**：Cpp2IL 的 Mach-O 路径里没有 "Applying reloc" 字样，最接近的日志是 `MachOFile.cs:173` 的 `"\tApplying chained fixups..."`。[推断，高置信] 笔记里的「Applying reloc」就是它。该循环对每个 fixup 做一次 `ReadReadable<MachODyldChainedPtr64Rebase>` + `WriteWord`，在 100MB+ 二进制上是数百万次带反射/装箱开销的读写——**这是纯 CPU 性能问题，不是格式不支持**。

**净结论：Cpp2IL on Mach-O 属于「已知可行但从未跑通」——既不是「已攻克」也不是「从未解决」，是唯一一个悬而未决的中间态。** 未验证的关键问题：卡死是永久 hang 还是「慢到没人等」？是否只影响 Vita 那个 125MB 加固包，还是所有百 MB 级 UnityFramework 都一样？GH 的 104MB 未加密包**从未试过**，是最便宜的判定实验。

## 五、Revenant 代码中的 Android 硬编码点清单

按「假设了什么」分类。**全部经 `文件:行号` 核查。**

### 5.1 包格式假设（只认 zip/apk/xapk）

| 文件:行号 | 内容 | 假设 |
|---|---|---|
| `revenant/config.py:77-87` | `xapk_path()` 只扫 `.xapk` / `.apk` 后缀 | 游戏包只有这两种后缀；`.ipa` 会被完全忽略（后果：`revenant status` 报 "game package present: NO"，`prepare` 在 `cli.py:252` 直接退出） |
| `revenant/config.py:90-101` | `_read_xapk_manifest()` 只读 XAPK 的 `manifest.json` | 包名/版本来自 XAPK manifest；iOS 侧对应物是 `Info.plist`（`CFBundleIdentifier` / `CFBundleShortVersionString`），且是二进制 plist |
| `revenant/config.py:120-137` | `detect_package()` / `detect_version()` 只走 XAPK manifest，否则回落 `com.unknown.il2cppgame` / `0.0.0` | 同上。iOS 包会全程用 fallback 身份 |
| `revenant/config.py:142-167` | `detect_unity_version()` 扫 `assets/bin/Data/globalgamemanagers` 与 `assets/bin/Data/data.unity3d`，且外层必须是 zip-of-apk | iOS 对应路径是 `Payload/<App>.app/Data/globalgamemanagers`（无 `assets/bin/` 前缀）；后果：Unity 版本回落到 `2022.3.0f1`，进而喂给 Cpp2IL 的 `--force-unity-version` 是错的 |
| `revenant/config.py:210-214` | `apks_dir()` 硬编码目录名 `_apks` | 命名层面的 Android 味（功能无碍） |
| `revenant/config.py:218-221` | `binaries_dir()` docstring 写「libil2cpp.so and metadata」 | 文档性 |
| `revenant/binary.py:264-284` | `extract_all_apks()` 只解 `.xapk` 里的 `.apk` | ipa 无「内层包」概念（结构是目录树，不是 zip-in-zip） |
| `revenant/binary.py:287-297` | `list_apk_contents()` 用 `zipfile` + `libil2cpp`/`global-metadata`/`managed`/`metadata` 关键词 | zip 可用（ipa 也是 zip），但关键词漏 `UnityFramework` |
| `revenant/cli.py:356-368` | `cmd_ls_apk` 要求 `xapk_path()` 非空，否则 "No XAPK found" | 同 `config.py:77` |
| `revenant/cli.py:370-380` | `cmd_extract_apks` 同上 | 同上 |
| `revenant/cli.py:252-255` | `cmd_prepare` 前置检查 "No .apk/.xapk found in the project root" | 整条流水线的入口闸门 |
| `revenant/init.py:18` | `_DIRS = ["_apks", ...]` | scaffold 出来的目录名 |
| `revenant/init.py:76` | init 提示 "drop the game .apk / .xapk here" | 文档性 |
| `revenant/templates/revenant.toml:5` | 注释「AUTO-DETECTED from the APK/XAPK you drop」 | 文档性 |
| `README.md:25,30,36` | "drop the game .apk / .xapk here"、`extract-apks` 步骤名 | 文档性 |

### 5.2 二进制/metadata 定位假设

| 文件:行号 | 内容 | 假设 |
|---|---|---|
| `revenant/binary.py:22` | `ANDROID_LIB_PATH = "lib/arm64-v8a/libil2cpp.so"` | IL2CPP 二进制叫 `libil2cpp.so` 且在 `lib/<abi>/` 下 |
| `revenant/binary.py:23` | `ANDROID_METADATA_PATH = "assets/bin/Data/Managed/Metadata/global-metadata.dat"` | metadata 在 `assets/bin/` 下（iOS 是 `Payload/<App>.app/Data/`） |
| `revenant/binary.py:26-30` | `ALT_LIB_PATHS` 三条全是 `lib/<abi>/libil2cpp.so` | 无 iOS 候选路径 |
| `revenant/binary.py:31-35` | `ALT_METADATA_PATHS` 三条，最宽松的是裸 `global-metadata.dat` | 裸路径**碰巧不匹配** ipa 内的 `Payload/.../global-metadata.dat`（`zipfile` 的成员名是全路径，`member not in zf.namelist()` 直接 miss，见 `binary.py:67-68`） |
| `revenant/binary.py:50-55` | `_looks_like_elf()` 判 `b"\x7fELF"` | **提取时的类型闸门**：Mach-O 会被判为「不是二进制」，即使路径命中也会被丢弃（`binary.py:191`、`:217`） |
| `revenant/binary.py:58-63` | `_looks_like_metadata()` 判 magic `\xAF\x1B\xB1\xFA` | 加密的 metadata（任何平台）都会被判为「没找到」 |
| `revenant/binary.py:80-117` | `find_libil2cpp()`：直接路径只试 `lib/arm64-v8a/libil2cpp.so` 与 `libil2cpp.so`，包搜索只认 `.xapk`/`.apk`（`:108`） | 函数名、路径、格式三重 Android 绑定 |
| `revenant/binary.py:120-156` | `find_global_metadata()`：同上（`:147` 只认 `.xapk`/`.apk`） | 同上 |
| `revenant/binary.py:184-222` | `_extract_libil2cpp_from_apk` / `_from_xapk`：`_looks_like_elf` 硬校验；xapk 路径按 `arm64`/`base` 关键词挑内层 APK（`:208`） | ABI split 是 Android 独有概念 |
| `revenant/binary.py:199-222` | xapk 路径下**没有** `_looks_like_elf` 之外的兜底 | — |
| `revenant/scripts/run_cpp2il_isil.sh:58-59` | `BIN="$(ls -1 _binaries/*-libil2cpp.so ...)"` | **文件名后缀硬编码**。Mach-O 缓存文件若不叫 `*-libil2cpp.so` 就找不到（缓存名由 `binary.py:47` 的 `f"{digest}-{suffix}"` 决定，suffix 在 `:189`/`:215` 硬编码为 `"libil2cpp.so"`） |
| `revenant/scripts/run_cpp2il_isil.sh:8-9,25-27` | 版本/Unity 版本从 `config.detect_version()` / `detect_unity_version()` 取 | 继承 5.1 的 iOS 检测失败 |

### 5.3 ELF 格式假设（RVA 映射与反汇编）

| 文件:行号 | 内容 | 假设 |
|---|---|---|
| `revenant/elf.py`（整个模块） | 模块名与 docstring「ELF segment mapping」 | 唯一的 RVA→文件偏移实现，无格式分派 |
| `revenant/elf.py:15-17` | `PF_X=0x1 / PF_W=0x2 / PF_R=0x4` | ELF 段权限位；Mach-O 的 `VM_PROT_EXECUTE` 是 `0x4`（值冲突，见第二节） |
| `revenant/elf.py:20-34` | `RvaMapping` 的字段全是 ELF 术语（`segment_vaddr/offset/filesz/memsz/flags`），`is_executable` 用 `& PF_X` | 数据结构本身绑定 ELF |
| `revenant/elf.py:46-59` | `map_rva_to_file_offset()` 只有 pyelftools / 手工 ELF 两条路径 | 无 Mach-O 分支 |
| `revenant/elf.py:62-91` | `_map_with_pyelftools()`：`elf.iter_segments()` + `p_type != "PT_LOAD"` 过滤 | pyelftools 只解析 ELF |
| `revenant/elf.py:94-159` | `_map_manually()`：`ident[:4] != b"\x7fELF"` 抛错（`:98-99`），随后按 `e_phoff`/`e_phentsize`/`e_phnum` 遍历 program header | 手工解析器完全是 ELF64/ELF32 布局 |
| `revenant/elf.py:162-172` | `read_rva_bytes()` 走上面的映射 | 传染 |
| `revenant/elf.py:175-179` | `read_u64_at_rva()` 直读文件里的 u64 | **在 Mach-O 上读到未应用 chained fixups 的 chain entry**（见第二节第 3 点） |
| `revenant/elf.py:182-190` | `format_mapping()` 输出 `PT_LOAD #N, vaddr=..., filesz=...` | 面向用户/agent 的字符串泄漏 ELF 术语 |
| `revenant/elf.py:12` | `from .binary import BinaryLocation, find_libil2cpp`（`find_libil2cpp` 在此被 re-export，`disasm.py:30-36` 从 `.elf` 导入它） | 模块耦合：换格式要同时动 `elf.py` 与 `disasm.py` 的 import |
| `revenant/disasm.py:5-8` | docstring「auto-detected from the target ELF's e_machine」 | — |
| `revenant/disasm.py:52-54` | `EM_ARM = 40` / `EM_AARCH64 = 183` | ELF `e_machine` 常量；Mach-O 用 `cputype`（`CPU_TYPE_ARM64 = 0x0100000C`） |
| `revenant/disasm.py:57-67` | `elf_machine()`：非 ELF 头一律**静默回落 AArch64**（`:64-65`） | 对 iOS arm64 **碰巧是对的**，但是靠运气不是靠判断；且完全掩盖了「这不是 ELF」的事实 |
| `revenant/disasm.py:251-266` | `disassemble()` 用 `elf_machine(binary_path)` 选架构 | 同上 |
| `revenant/disasm.py:453-462` | `build_method_analysis()`：`find_libil2cpp()` + `map_rva_to_file_offset` + `read_rva_bytes` | 三重传染 |
| `revenant/disasm.py:637-641` | `simple_disasm_report()`：同上 | 同上 |
| `revenant/cfg.py:150-160` | `_fallback_insns()`：`from .binary import find_libil2cpp` + `from .elf import read_rva_bytes` | 同上 |
| `revenant/mcp_server.py:30,32` | 导入 `find_libil2cpp` / `elf_machine` | — |
| `revenant/mcp_server.py:359-365` | `re_find_binary` 的输出硬写 `"libil2cpp.so\n  path: ..."` | agent 看到的字符串固定说 libil2cpp.so |
| `revenant/mcp_server.py:332` | `re_disasm` docstring「reads libil2cpp.so directly」 | 文档性 |
| `revenant/mcp_server.py:405,421` | `re_status` 用 `elf_machine()` 报架构，输出 `"libil2cpp.so extracted"` | 同上 |
| `revenant/cli.py:200,208` | `cmd_status` 同样报 "libil2cpp extracted" | 同上 |

### 5.4 metadata 解析假设

| 文件:行号 | 内容 | 假设 |
|---|---|---|
| `revenant/metadata.py:4` | docstring 写死 `assets/bin/Data/Managed/Metadata/...inside the APK` | 文档性 |
| `revenant/metadata.py:17` | `METADATA_SANITY = 0xFAB11BAF` | 只接受明文 |
| `revenant/metadata.py:49-53` | sanity 不匹配即 `raise ValueError` | **无解密钩子**；这是平台无关的缺口（Vita 的 Android 包同样进不来） |
| `revenant/metadata.py:54-66` | 硬编码 header 布局（偏移 8/12/16/20 = stringLiteral 四元组） | 该布局在 v24–v31 稳定，[推断] 与平台无关，但**没有版本分派**；arch-06 揭示 v31 header 是 264 B / 66 字段，Revenant 只读了前 24 B |
| `revenant/cli.py:455`、`:684`、`mcp_server.py:380` | 打印 sanity | 无「加密态」这一诊断分类 |

### 5.5 资源/AssetBundle/Lua 路径假设

| 文件:行号 | 内容 | 假设 |
|---|---|---|
| `revenant/assets.py:17-21` | docstring 写死两种 Android 布局 | 文档性 |
| `revenant/assets.py:40` | `BASE_APK = f"{PACKAGE}.apk"` | 承载 bundle 的包叫 `<package>.apk` |
| `revenant/assets.py:44-48` | `BUNDLE_ROOTS = ("assets/aa/android", "assets/aa/Android", "assets/Bundles/Android")` | **三条全是 Android**；iOS 实测是 `Payload/<App>.app/Data/Raw/aa/ios` |
| `revenant/assets.py:87-93` | `_detect_bundle_root()` 只在这三条里选 | 同上 |
| `revenant/assets.py:96-121` | `find_base_apk()` 只扫 `_apks/` 下 `.apk` 结尾的文件（`:107`） | ipa 不会被扫到 |
| `revenant/assets.py:136-162` | `list_bundles(apk_path, ...)` 用 `zipfile` 打开「apk」 | zip 层面 ipa 兼容，但入口拿不到路径 |
| `revenant/assets.py:180-184` | `_member_path()` 按 `<root>/<group>/<name>` 拼 | iOS 层级更深一层（`lua_assets_assets/scripts/lua/`），[推断] group 划分语义会变 |
| `revenant/assets.py:241-251`、`:419-441` | `extract_bundle` / `extract_scenes` 全走 `find_base_apk()` | 传染 |
| `revenant/lua.py:77-80` | `is_lua_bundle_entry()`：`.bundle` 结尾 + 名含 `lua` | **实测在 iOS 上仍成立**（`lua_base.bytes_<hash>.bundle` 在 `.../lua_assets_assets/scripts/lua/` 下）。这条是唯一天然跨平台的 |
| `revenant/lua.py:129-142` | `extract_scripts(apk_path)` → `_base_apk()` → `find_base_apk()` | 入口被 5.5 上面几条卡死 |
| `revenant/lua.py:375-382` | `lua_status()` 报 `lua_bundles_in_apk` | 同上 |
| `revenant/lua.py:386-392` | `_base_apk()` 报错文案 "Base APK not found in _apks/" | 同上 |
| `revenant/cli.py:384-388`、`:269-270` | CLI 层同样依赖 `find_base_apk()` / `lua_bundles_in_apk` | 同上 |

**统计**：约 60 个硬编码点，分布在 12 个文件。其中**结构性阻断点只有 7 个**（其余是文档、命名、或被这 7 个传染的下游）：

1. `config.py:77-87` —— 包发现只认 apk/xapk
2. `binary.py:22-35` —— 路径常量表全 Android
3. `binary.py:50-55` —— ELF 魔数闸门
4. `binary.py:58-63` + `metadata.py:50-53` —— 明文 metadata 闸门
5. `elf.py` 整模块 —— 无格式分派的 RVA 映射
6. `assets.py:44-48` —— bundle 根常量表全 Android
7. `run_cpp2il_isil.sh:58` —— `*-libil2cpp.so` 文件名 glob

## 六、iOS 专属的额外能力需求

按「已攻克 vs 从未解决」分列——两类的工作量差一个量级。

### 6.1 已攻克，只是没进 Revenant（移植工作）

| 能力 | 已有的东西 | 缺什么 |
|---|---|---|
| ipa/`.app` bundle 结构解析 | 本次实测 + arch-10 §8.1 的完整路径清单 | 一个「iOS 包布局」常量表 + 解包入口，与现有 zip 代码同构 |
| 定位真正的 IL2CPP 二进制（跳过 71KB 启动壳） | 事实 #2/#3：规则是「`Frameworks/*.framework/` 下最大的那个 Mach-O」或直接认 `UnityFramework` | 判定逻辑本身；`_looks_like_elf` 要换成格式嗅探 |
| Mach-O 段解析 + VA→file offset | `vita-majhong-re/tools/ios_macho.py:34-87`（`_parse` + `v2f`/`f2v`），已在 100MB+ 真包上跑通 | 移植进 Revenant + 补 `__PAGEZERO` 基址减法 + 权限位语义修正 |
| Mach-O 反汇编 | `ios_macho.py:109-137`（capstone ARM64 + adrp/add 字符串注解） | Revenant 的 `disasm.py` 已有更完整的 capstone 层，只需换 `elf_machine()` 的架构探测 |
| Mach-O xref 扫描 | `ios_macho.py:140-192`（位运算解 adrp，比全 capstone 快） | Revenant `xrefs.py` 走的是索引路径，[推断] 关系待评估 |
| Info.plist 读取 | arch-03/arch-10 都用 `plutil` 读出了包名/版本/SKAN 列表 | Python 侧用 `plistlib.loads(fmt=FMT_BINARY)`，标准库自带，无外部依赖 |
| Frameworks 遍历 | arch-03 §变现栈（144 个 @rpath 依赖）、arch-10 §8.1 | 只是 zip 路径遍历 |
| iOS Addressables/Lua bundle 定位 | 本次实测 `Data/Raw/aa/ios/`，Lua 命名规则与 Android 同构 | 加常量 + 层级适配 |
| **iOS metadata S-box 解密** | `tools/recover_sbox.py` + arch-06 全套方法学与陷阱 | 需要 Android 明文锚点这个外部输入；Revenant 无「多包并置」概念 |
| 解密质量验收 | arch-06 §正确产物质量的四个指标（distinct nameIndex / 已知类命中 / 字符串区非 ASCII 计数 / 与参照的名字重叠率） | Revenant 完全没有任何 metadata 质量检查 |

### 6.2 从未解决（真缺口）

| 能力 | 状态 | 说明 |
|---|---|---|
| **Cpp2IL 在百 MB Mach-O 上跑通** | **从未成功**。Vita 卡在 chained fixups；GH 从未尝试 | 这是整条 iOS 流水线的**唯一 hard blocker**——没有 Cpp2IL 产物就没有 IsilDump / DiffableCs，`build-indices`、`seed-src`、`re_search`、`re_type_info`、`re_find_asm`、`re_cfg` 全部失效，Revenant 退化成一个反汇编器 |
| chained fixups 的应用 | Revenant 侧零实现 | 影响任何读文件内指针的路径（`elf.py:175`）；Cpp2IL 内部已做，但 Revenant 自己的 RVA 读取是独立代码路径 |
| 加密 metadata 的通用解密框架 | 零实现（两平台通病） | 见第三节 |
| fat binary 拆分 | 零实现 | [推断] 低优先级，实测两包都是 thin |
| Mach-O 符号表 / export trie | 零实现 | Revenant 现在不用符号，[推断] 非阻断 |
| iOS Unity 版本探测 | 零实现 | `Payload/<App>.app/Data/globalgamemanagers` 未验证过（本次未做，`config.py:148` 的两个候选路径都不匹配 iOS） |
| 运行时 dump（越狱/模拟器） | 零实现，arch-06 明确点名为「100% 正确性的唯一出路」 | 超出 Revenant「静态只读 harness」的定位 |

### 6.3 不是缺口的（澄清）

- **FairPlay 脱壳**：实测两包 `cryptid=0`，都是已脱壳的第三方分发包。[推断] 从 App Store 直接下载的原始 ipa 会有 `cryptid=1` 且 `__TEXT` 加密，静态分析完全不可行——但这属于「取样问题」，不是 Revenant 的能力缺口。**前提是：iOS 支持隐含「样本必须是已脱壳包」这个未言明的约束。**
- **托管层结论跨平台复用**：arch-10 §8.3 证明托管层结论可平移，但事实 #25/#26 说明 **RVA/索引不可复用**。所以「有了 Android 分析就不用做 iOS」只对结论成立，对地址不成立。

## 七、规模判断

**结构性阻断点 7 个**（第五节末），其中 6 个是「换常量表 + 加格式分派」级别的工作，已有可移植的参考实现（`ios_macho.py`）。**唯一真正的未知数是 Cpp2IL 在 Mach-O 上的可行性**——它在 Vita 上卡死过一次，在 GH 上从未试过。

第二大风险是**加密 metadata 无插拔点**，但这是 Android/iOS 通病，与 iOS 支持正交（Vita 的 Android 包今天也进不了 Revenant）。

推荐的最便宜判定实验：拿 GH 的 `UnityFramework`（104MB、未加密、metadata 明文 v31）直接喂给现有的 Cpp2IL 命令行，看是产出还是卡死。这一个实验决定 iOS 支持是「一周的适配」还是「先要给 Cpp2IL 提性能补丁」。
