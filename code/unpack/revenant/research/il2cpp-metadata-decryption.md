# 离线解密 VM 混淆的 IL2CPP global-metadata.dat

调研日期 2026-08-13。目标背景（已确认事实，不在本文重新推导）：`com.cedargames.mysterytown` 1.21.0，arm64-v8a Android，由 PGL Armor 加固（`libpglarmor.so` / `libnms.so` / `libu8t.so`）。metadata 解密器内嵌在 `libil2cpp.so`，入口约 vaddr `0x3577388`，以 64 字节分块调用 `0x32c4504`；`0x32c4504` 是 bytecode dispatcher（`ldrb` 取操作码，`0x1B02224` 的 u16 跳转表索引，`br` 派发，256 个 handler 在 `0x32E252C..0x32E4518`）。文件布局：`0..3` tag / `4..7` payload 长度 / `8..263` 256 字节替换表 / `264..327` 64 字节 bytecode 程序 / `328..` payload。解密正确的判据：payload 前 8 字节为 `CODEPHIL`，紧接 IL2CPP sanity magic `af1bb1fa`。

本文按优先级评估三条路径：（1）用 CPU 模拟器离线跑解密器，绕开对 VM 的理解；（2）从活进程内存 dump 已解密的 metadata；（3）针对 PGL Armor / CODEPHIL / NEP 这些具体保护的公开分析现状。

## 一、离线模拟执行解密器（首选路径）

核心思路：把解密逻辑当黑盒，用 CPU 模拟器把 `libil2cpp.so` 映射进内存，按 AArch64 调用约定构造参数，直接调用解密函数（或其入口 `0x3577388`），让被内嵌的 VM 解释器在模拟器里自己跑完，输出明文。这样完全不需要还原那 256 个 handler 的语义。这条路在中文逆向圈是处理 metadata 加密的标准手法之一（"找到解密逻辑，用 Unicorn 或 Qiling 输入密文输出明文"）。来源 https://cloud.tencent.com/developer/article/2216959 与 https://zhuanlan.zhihu.com/p/654708348

### 1.1 三个可选框架

**unidbg**（https://github.com/zhkl0228/unidbg）：对 Android native so 的模拟最完整，专为"模拟执行 so"设计。它自带 Android linker、syscall、JNI（JavaVM/JNIEnv）与文件系统模拟，底层可选 Unicorn / Dynarmic / Apple M1 hypervisor / KVM 后端，内置带 gdb stub 的调试器、指令 trace、以及针对被模拟 native 代码的内存泄漏检测。加载并调用的最小形态：

```java
DalvikModule dm = vm.loadLibrary(new File("libtmessages.29.so"), true);
dm.callJNI_OnLoad(emulator);
module.callFunction(emulator, "targetFunction", arg1, arg2);
```

来源 https://github.com/zhkl0228/unidbg/blob/master/README.md 。unidbg 处理了本路径最烦的部分——linker 重定位、GOT/PLT、libc 导入、`init_array`、TLS——所以对本任务它是首选。中文社区明确记录了"用 unidbg 断在解密后、dump 出解密段"的做法，来源 https://bbs.kanxue.com/thread-289395.htm 与 https://cloud.tencent.com/developer/article/2216959

**Qiling**（https://github.com/qilingframework/qiling）：基于 Unicorn 的 Python 框架，带 PE/MachO/ELF loader、动态链接器（可加载并重定位共享库）、syscall 与 IO 处理，支持 ARM64，适合模拟 Android native lib。来源 https://github.com/qilingframework/qiling

**Chomper**（https://github.com/sledgeh4w/chomper）：轻量 Unicorn 封装（需 Python 3.9+、Unicorn 2.0.0+），iOS 支持完整、Android 支持有限，需要自备 Android 系统库（不随包发行，从 `rootfs` 仓库获取）。Android 调用示例：

```python
emu = Chomper(arch=ARCH_ARM64, os_type=OS_ANDROID, rootfs_path="rootfs/android")
emu.load_module("rootfs/android/system/lib64/libz.so")
libszstone = emu.load_module(".../libszstone.so")
result_len = emu.call_address(libszstone.base + 0x2F1C8, input_str, input_len, result_buf)
```

来源 https://github.com/sledgeh4w/chomper

裸 Unicorn（https://github.com/unicorn-engine/unicorn）只是纯 CPU 模拟器，linker/relocation/syscall 全部要自己写，除非需要极致控制，否则不建议对一个大型 so 从零搭。

### 1.2 AArch64 调用约定（构造一次函数调用）

来源 ARM AAPCS64 https://github.com/ARM-software/abi-aa/blob/main/aapcs64/aapcs64.rst ：前 8 个整型/指针参数用 `X0..X7`（x0..x7）；返回值同样在 `X0`（`X0..X7`）；`X30`=LR 存返回地址；`X29`=FP 帧指针；`SP` 为栈指针，需满足栈对齐约束。构造单次调用时：把参数写入 `X0..X7`，`LR` 设为一个"落地地址"（一段自己映射的、执行到即停的哨兵地址，或用 `count`/`end` 限定），`SP` 指向一块自映射且 16 字节对齐的栈，`PC` 设为解密函数入口，跑到返回后从 `X0` 或输出缓冲区取结果。

Qiling 里同一套的落地形态（映射内存 + 写寄存器 + hook 导入 + `ql.run(begin, end)`）：

```python
ql.mem.map(0x6d5a620000, 65536, UC_PROT_ALL)          # 先映射再访问
ql.arch.regs.write("sp", 0x6d5a620200)
ql.arch.regs.write("x29", 0x6d5a620280)
ql.os.set_api('__strlen_chk', my_strlen, QL_INTERCEPT.CALL)  # stub 导入的 libc
ql.hook_address(cb, base_address + 0xb30)
ql.run(begin=base_address + 0xb80, end=base_address + 0xc08)  # begin/end 圈定单函数
```

来源 https://www.appknox.com/blog/how-to-emulate-android-native-libraries-using-qiling （`ql.run` 的 `begin`/`end`/`timeout`/`count` 参数见 https://github.com/qilingframework/qiling/wiki/Quick-Start-Guide ）。

### 1.3 已知坑（映射 so / 重定位 / 导入 / 环境）

以下均为 Unicorn / unidbg 官方或作者文档记录的真实坑，直接决定这条路能否跑通：

- **未映射内存**：Unicorn 是纯 CPU 模拟器，访问未映射页会触发 `UC_HOOK_MEM_*_UNMAPPED`。官方 FAQ：要从内存错误优雅恢复，必须在 hook 里先把缺失内存映射好再 `return true`，否则"我们不知道下一步该做什么"。栈、堆、输出缓冲、以及 GOT 指向的外部符号页都要预映射。来源 https://raw.githubusercontent.com/unicorn-engine/unicorn/master/docs/FAQ.md 与 https://github.com/unicorn-engine/unicorn/blob/master/docs/Hooks.md
- **浮点/NEON 未使能**：官方 FAQ 明确"某些指令在某些架构上默认不开启，ARM 上要先设置 VFP 才能模拟浮点指令"。若解密器用到 SIMD（256 字节替换表、64 字节分块很可能走 NEON），不设 `CPACR_EL1` 使能会在第一条 SIMD 指令就异常。来源 https://raw.githubusercontent.com/unicorn-engine/unicorn/master/docs/FAQ.md
- **模拟提前结束且无异常**：FAQ 记录 `uc_emu_start` 可能无异常就停，此时 PC 指向下一条指令；异常时 PC 会同步到所在 basic block 的首指令边界，读 PC 定位会误导。来源同上，及 https://github.com/unicorn-engine/unicorn/issues/534
- **syscall/SVC 无处理**：纯 CPU 模拟器对 `syscall`/`SVC` 无内建 handler，需自行注册。unidbg/Qiling 已代劳大部分。来源 https://raw.githubusercontent.com/unicorn-engine/unicorn/master/docs/FAQ.md
- **TLS / TPIDR_EL0**：AArch64 用 `TPIDR_EL0` 存线程指针，`MRS` 读取。stack canary（`__stack_chk_guard`）通常经 TLS 取，若未初始化 `TPIDR_EL0` 指向的 TCB，函数序言取 canary 时会读未映射内存而崩。Unicorn 暴露了 `UC_ARM64_REG_TPIDR_EL0` 可写（见 `include/unicorn/arm64.h`），需要预置一块 TCB 并把 canary 槽填好。来源 https://github.com/unicorn-engine/unicorn/blob/master/include/unicorn/arm64.h
- **`init` 段 vs `init_array`**：这是本任务最可能踩的坑。命名研究者 nszdhd1 记录：AndroidNativeEmu 只执行了 `init_array`，而目标 ELF 还有 `DT_INIT` 段，"只跑 init_array 根本没解密"，他改框架补上了 `init` 段的执行。加固壳常把自解密放在 `init`。同一文还记录 `AndroidResolver` 用 19 会失败、用 23 才行（旧版走 `__pthread_clone`、新版走 `clone`）。来源 https://nszdhd1.github.io/2022/01/14/%E4%BD%BF%E7%94%A8unidbg%E8%BF%87%E4%BF%9D%E6%8A%A4/ 。腾讯云同一主题也确认："加载 so 会执行 init_array，但目标 ELF 若还有 init 段，只执行 init_array 可能解密不出来，需在模拟器模块里补上 init 段执行"。来源 https://cloud.tencent.com/developer/article/2216959
- **未填的 GOT / 缺失导入**：linker 没解析的外部符号（memcpy 等）会让 GOT 槽为空，调用即跳到 0。unidbg 自带 linker 一般能填；裸 Unicorn/Qiling 要为每个导入的 libc 函数注册 stub（如上例 `set_api`/`hook_address`），或直接映射一份真实 libc。
- **页权限**：某些区段非可写/可执行，Unicorn 会按 MMU 状态拒绝，映射时按需给 `UC_PROT_ALL` 或精确权限。来源 https://raw.githubusercontent.com/unicorn-engine/unicorn/master/docs/FAQ.md

### 1.4 对本任务的适配要点与判断

这条路对本目标特别合适，理由：解密器已定位为**可调用的自包含函数**（入口 `0x3577388`，内部 dispatcher `0x32c4504`），Katy Bold（Il2CppInspector 作者）把这种情形单列为一类可行策略——"当解密逻辑隔离在可调用函数里时，独立加载二进制、直接调用解密函数，无需逆清其内部"。来源 https://katyscode.wordpress.com/2021/02/23/il2cpp-finding-obfuscated-global-metadata/ 。因为 VM 解释器（`0x32c4504` + 跳转表 + 256 handler）在模拟器里会原样执行，我们无需理解任何一个 handler 的语义——这正是相对"人工反虚拟化"的最大优势。

需要注意的现实约束：
- 解密器内嵌在 `libil2cpp.so` 而非独立 lib，且目标被 PGL Armor 加固，`libpglarmor.so`/`libnms.so`/`libu8t.so` 可能在 `init`/`JNI_OnLoad` 阶段做完整性自校验或对 `libil2cpp.so` 的运行时解密。若解密函数依赖这些壳在别处准备好的状态（解密后的代码段、密钥、全局变量），单独把 `libil2cpp.so` 丢进模拟器可能取到未初始化数据。**优先只跑目标函数所需的最小闭包**，用 `hook_mem_unmapped` 边跑边补页、边发现依赖，而不是指望整壳自洽初始化。
- 真正的判据很干净：跑完后检查输出缓冲区前 8 字节是否 `CODEPHIL`、其后是否 `af1bb1fa`。这让"是否跑对"可零歧义地自动验证，非常适合模拟器迭代。

结论：**这是最值得先投入的路径**，unidbg 为首选实现（linker/relocation/init/JNI 已代劳），若遇壳间依赖再退回裸 Unicorn 做精细化的按页补齐。未找到针对"PGL Armor + CODEPHIL"这一具体组合的现成模拟脚本（见第三节），但通用手法与坑位在上述一手来源里都有据可依。

## 二、从活进程内存 dump 已解密的 metadata

思路完全不同：不解密，等游戏自己在内存里解密好，再把明文抠出来。

### 2.1 Il2CppDumper 本身不解密

Perfare/Il2CppDumper（https://github.com/Perfare/Il2CppDumper）是**静态消费端**：输入是已明文的 `global-metadata.dat` 加 `libil2cpp.so`，输出 `DummyDll/`、`dump.cs`、`il2cpp.h`、`ida.py`/`ghidra.py`、`script.json`。它**不含任何解密能力**，README 原文"Deobfuscating of such files is beyond the scope of this program"，并把加固游戏指向姊妹项目 Zygisk-Il2CppDumper。其 repo 内**没有** `il2cppdumper.py`、也没有 Frida 流程（很多二手博客的误传）。加固游戏的规范讨论见 https://github.com/Perfare/Il2CppDumper/issues/415 。来源 https://github.com/Perfare/Il2CppDumper

### 2.2 运行时 dumper：两类截然不同的产物

- **Zygisk-Il2CppDumper**（https://github.com/Perfare/Zygisk-Il2CppDumper）：Zygisk 模块，运行时注入游戏进程，因在解密之后进程内运行，可"bypass protection, encryption and obfuscation"，产物是写到 `/data/data/<pkg>/files/` 的 **`dump.cs`**（不是原始 metadata 字节）。要求 **Magisk v24+ 且开启 Zygisk**（即需 root）。
- **frida-il2cpp-bridge**（https://github.com/vfsfitvnm/frida-il2cpp-bridge）：Frida/TypeScript 模块，遍历活的 IL2CPP runtime，**完全不需要 `global-metadata.dat`**，也**不产出原始 metadata 字节**，`--cs-output` 输出 C# 源码。要"原始 `.dat` 文件"时它是错的工具。

### 2.3 通用 Frida：定位并抠出明文 blob

两个一手脚本，都确认 sanity magic `0xFAB11BAF` 在文件偏移 0 处按小端存为字节 `AF 1B B1 FA`，其后一个 version dword：

- **盲扫内存**：CameroonD/Il2CppMetadataExtractor（https://github.com/CameroonD/Il2CppMetadataExtractor）与 k0tayan/FridaDumpGlobalMetadata（https://github.com/k0tayan/FridaDumpGlobalMetadata）。关键调用：`Process.enumerateRanges(...)` 枚举可读段 → `Memory.scan(base, size, "AF 1B B1 FA", { onMatch(){...} })` 找头 → 由头部字段推算大小（k0tayan 读 `address.add(0x8).readU32()` 并校验各段 offset/size 连续；CameroonD 默认 pattern `"af 1b b1 fa 1? 00 00 00 00"`，并支持 `--offset`/`--size`）→ `send("metadata", address.readByteArray(size))` 回传落盘。命令：`python dump-metadata.py [-o OFFSET] [-s SIZE] [-p PATTERN] package_name`。要求 Frida + frida-server（设备端，通常需 root）+ 对应 `libil2cpp.so`。来源 https://github.com/CameroonD/Il2CppMetadataExtractor/blob/master/README.md
- **hook loader（更稳）**：Il2CppInspector 作者推荐 hook `il2cpp::vm::MetadataLoader::LoadMetadataFile`（调用链 `il2cpp_init → Runtime::Init → MetadataCache::Initialize → MetadataLoader::LoadMetadataFile`），`Interceptor.attach(..., { onLeave(retval){...} })` 取返回指针，按 `Il2CppGlobalMetadataHeader` 计算长度后 `readByteArray` 导出。因在 loader 返回明文之后读，天然绕过磁盘加密。来源 https://katyscode.wordpress.com/2021/02/23/il2cpp-finding-obfuscated-global-metadata/ 。兜底可用全堆 dumper fridump（https://github.com/Nightbringer21/fridump）。

### 2.4 设备条件与免 root 可能

- frida-server 标准路子需推到 `/data/local/tmp` 并以 root 运行；CameroonD README 声称"若 Frida 权限足够则未必需 root"，但对市面成品游戏实际仍需 root。来源 https://github.com/CameroonD/Il2CppMetadataExtractor
- Zygisk-Il2CppDumper / ZygiskFrida（https://github.com/lico-n/ZygiskFrida）：需 root + Magisk v24+ + Zygisk。
- **唯一真正免 root 路子 = 重打包注入 Frida Gadget**。官方文档：Gadget 是被 app 自身加载的共享库，通过"patching the application or its libraries"注入；Android 包管理器只拷贝 `lib*.so`，故配置文件命名如 `libgadget.config.so`；Gadget 的 Script/ScriptDirectory 可无 server 自主跑 dump 脚本。来源 https://frida.re/docs/gadget/ 。objection 自动化此流程（`objection patchapk`：apktool 解包→加 `libfrida-gadget.so`+config→smali 注入 `System.loadLibrary`→zipalign 重签）。来源 https://github.com/sensepost/objection/wiki/Android-APK-Patching

### 2.5 加固对抗（对本目标最关键）

免 root 重打包会改签名，任何签名/完整性自校验（Play Integrity、`getPackageInfo(...signatures)` 比对）都会跳；很多成品游戏还做代码段磁盘/内存 checksum 比对、模拟器检测、Frida 检测（扫 `/proc/self/maps` 找 `frida`/`gadget`/`gum-js-loop`、探测 27042/27043 端口、查 `/data/local/tmp/frida-server`）。来源 https://darvincitech.wordpress.com/category/anti-frida/ 与 ZygiskFrida README https://github.com/lico-n/ZygiskFrida 。对 PGL Armor 这类硬壳，较可靠组合是 **root + Zygisk 注入 + 延迟 hook metadata loader**（在进程内、解密之后运行，既绕磁盘加密又绕磁盘/内存 checksum）。反检测手段：重命名 Frida 产物与端口、延迟注入避开启动期检查、smali 里 patch 掉检测。

结论：内存 dump 是**最省事、成功率最高**的路，但强依赖一台 root 设备且能扛住 PGL Armor 的反调试/反 Frida。它与第一节的模拟路互补：模拟路完全离线、无需设备、不触发任何运行时反制，但工程量更大。

## 三、针对 PGL Armor / CODEPHIL / NEP 的公开分析现状

本节结论以"负面结果"为主，且负面结果本身高价值——它推翻了"PGL Armor 是加固壳"这一前提。

### 3.1 PGL Armor / libpglarmor.so —— 极可能是误认，实为 Pangle 广告 SDK

**关键发现（高置信度）：PGL = Pangle，字节跳动的移动广告网络（穿山甲海外品牌）。`libpglarmor.so` 是 Pangle 广告 SDK 的标准 native 库，不是商业 Android 加固壳。** 最详细的公开分析（buchodi 对 Pangle SDK 加密的破解）列出该 SDK 的 native 库：`libpglarmor.so`（约 61KB，密码学 wrapper，实现广告统计/行为事件的 `cypher:4` ECIES 路径，由 `PglCryptUtils.java` 调用）、`libnms.so`（约 281KB，网络）、`libtobEmbedPagEncrypt.so`（设备指纹 AES）、`libtt_ugen_layout.so`（广告布局引擎）。SDK 由字节经 `artifact.bytedance.com` 分发。来源 https://www.buchodi.com/your-duolingo-is-talking-to-bytedance-cracking-the-pangle-sdks-encryption/ 、https://github.com/bytedance/pangle-sdk-demo 、https://www.pangleglobal.com/integration/integrate-pangle-sdk-for-android 。`libpglarmor.so`+`libnms.so` 的组合在广告变现类 APK 的样本分类中反复出现（如 Hybrid Analysis 的 GTV-Live 与 VPNIFY MOD 样本），并在游戏开发者关于 Android 16KB page 对齐的抱怨中被归因于穿山甲 SDK。来源 https://hybrid-analysis.com/sample/3407fad8ea78a5c071c5a9bbd08794f9ac8b01c443c939c8c40c1e4da9b036be/67fb50cbeb6368153d0684aa 、https://forums.solar2d.com/t/recompile-your-app-with-16-kb-native-library-alignment/357351?page=3

**明确的负面结果：**
- **不存在名为 "PGL Armor" 的 Android 加固产品的任何公开分析。** 搜 `"PGL Armor" android protector` 只命中 pgl-armor.com（美国防弹衣厂商，无关）。来源 https://pgl-armor.com/
- **没有任何公开来源把 `libpglarmor.so` 关联到腾讯乐固/legu/御安全、网易易盾、梆梆、娜迦、爱加密、顶象或任何 VMP 系加固壳。** 这些厂商的壳有各自已知且不同的特征（`libshella-*.so`、`libDexHelper.so`、`libexec.so`/`libexecmain.so`、`libnesec.so`、`libdxbase.so`），均不匹配。
- **没有任何公开文章描述 `libpglarmor.so` 内部有 VM/bytecode 解释器，也没有描述它触碰 IL2CPP metadata。**
- `libu8t.so`：**零公开命中**，任何地方（含上述 Pangle 库清单）都未记录，其 Pangle 归属未确认。

**需要提醒调用方的重要含义**：若样本的 IL2CPP metadata 解密器确为 VM 混淆，`libpglarmor.so` 很可能是**巧合共存**（几乎每个变现休闲游戏都带的广告 SDK 加密库），而非真正的保护者。VM 更可能就在 `libil2cpp.so` 自身（与已确认事实一致——解密器内嵌于 `libil2cpp.so`），或在另一个未命名的库里。"PGL Armor 是加固壳"这个归属在写入正式笔记前应重新核实。注意这与已给定事实并不冲突：题面已定位解密器在 `libil2cpp.so` 内，本节只是提示不要把 `libpglarmor.so` 当成解密器的来源去分析。

### 3.2 CODEPHIL magic —— 无任何公开分析

**负面结果（高置信度）。** 单独搜 `"CODEPHIL"` 及与 `il2cpp`/`metadata`/`unity`/`global-metadata` 组合，只命中无关实体：Codephil Inc.（菲律宾/麻省的包装机械公司）、codephil-columbia（编程教育非营利）、以及从不提及该字符串的通用 IL2CPP 文章。grep.app 被限流（429）无法查询，GitHub code search 需登录。**没有任何加固壳、SDK 或工具公开关联到"`CODEPHIL` 8 字节头紧接 IL2CPP sanity magic"这一特征。** 就公开信息而言，这是一个未记录、极可能是自研/内部的标记——更像某工作室构建流水线的 per-studio 标签，而非现成加固产品的签名。来源 https://www.codephilinc.com/ 、https://github.com/codephil-columbia

### 3.3 NEP / HTPX / libhtpseek.so —— 无公开分析、无公开解包器

**负面结果（高置信度）。** `"libhtpseek.so"`、`"htpseek"`、`"nep_export"`、`".nep_export_d_ab_all_block_lz4"`、`"ab_all_block_lz4"`、中文 `"NEP 加固"`/`HTPX 解包` 均无相关命中，只有无关项目（OISF 的 libhtp HTTP parser、HTSlib、HDF5 的 NEP）。**无厂商识别、无文章、无解包器公开存在。** 已知的公开背景：该游戏是 Merge Cooking: Theme Restaurant，发行商 Happibits（新加坡注册，HAPPIBITS TECHNOLOGIES PTE. LTD.，UEN 202029436N，2020-09-23 成立）。鉴于把资产 blob 嵌入 ELF section、外加自研 `HTPX`/RC4/LZ4 容器，这更像**自研资产打包方案**而非商业加固——与完全没有厂商宣传或第三方分析相符。与网易 NeoX 的 `NPK`（LZ4+RC4）命名相似只是表面，无证据关联。来源 https://play.google.com/store/apps/details?id=com.merge.cooking.theme.restaurant.food 、https://www.sgpbusiness.com/company/Happibits-Technologies-Pte-Ltd

### 3.4 VM 混淆 metadata 解密器的公开技术取向

公开资料在"反虚拟化/devirtualization"上很薄，压倒性地偏向**运行时捕获而非静态还原**：

- Katy's Code（Il2CppInspector 作者）是英文圈权威参考：trace `il2cpp_init → Runtime::Init → MetadataCache::Initialize → MetadataLoader::LoadMetadataFile`，与上游 IL2CPP 源码 diff，差异即为加密；随后要么把解密例程 lift 进独立 harness/Il2CppInspector 插件，要么（作者自己在评论里的兜底）**hook `LoadMetadataFile` 返回值、从内存 dump 明文**，完全绕过算法。明确**不涉及模拟或反虚拟化**。来源 https://katyscode.wordpress.com/2021/02/23/il2cpp-finding-obfuscated-global-metadata/
- **内存 dump 是中文论坛共识首选**：52pojie（frida-il2cppDumper 内存 dump 无视 metadata 加密；从内存获取未保护 IL2CPP 可执行文件）、看雪 IL2CPP 逆向初探、腾讯云 global-metadata 解密（扫内存找 magic→解析头算大小→dump）。点名工具：Zygisk-Il2CppDumper、frida-il2cpp-bridge、GameGuardian。来源 https://www.52pojie.cn/thread-1559859-1-1.html 、https://bbs.kanxue.com/thread-278275.htm 、https://cloud.tencent.com/developer/article/2216959
- **GuidedHacking** 有一个最接近"模拟解密器"的配方——在 ARM 模拟器下跑 app 并捕获解密缓冲区。来源 https://guidedhacking.com/threads/how-to-deal-with-obfuscated-global-metadata-dat.17954/ 、https://guidedhacking.com/threads/il2cpp-global-metadata-dumper-full-decrypted-emulator-armeavi-v7a.18350/
- **加固方视角**（了解对手）：FairGuard 的 metadata 加密方案文，以及开源示例方案 badApple001/Il2cppEncrtypt。来源 https://fairguard.github.io/2021/03/25/encrypt_global-metadata 、https://github.com/badApple001/Il2cppEncrtypt
- **真正的 devirtualization**：**找不到任何 IL2CPP 专门的公开文章。** 最接近的可迁移材料是通用的 OLLVM 反混淆（Quarkslab 用 Miasm 还原 OLLVM 程序）。来源 https://blog.quarkslab.com/deobfuscation-recovering-an-ollvm-protected-program.html 。结论：**没有人公开推荐去反虚拟化一个 Unity metadata 解密器——公开答案永远是 hook-and-dump，模拟是次选。**

## 总评与建议路线

三条路对本目标的取舍：

1. **离线模拟（首选，最契合）**：解密器已定位为可调用自包含函数，判据（`CODEPHIL`+`af1bb1fa`）可自动验证，完全离线、不触发任何运行时反制。用 unidbg 起步（linker/重定位/`init`/JNI 已代劳），重点盯 §1.3 的坑，尤其 `init` 段（非仅 `init_array`）、VFP 使能、TLS/canary、按页补齐壳间依赖。此路与公开取向（hook-and-dump 为主）不同，属较少人走但对"函数已隔离"场景最直接的路，且 Katy Bold 明确把它列为一类可行策略。
2. **内存 dump（最省事，成功率最高，但需硬件与对抗）**：hook `MetadataLoader::LoadMetadataFile` 返回后读明文，或扫内存找 `AF 1B B1 FA`。需 root 设备 + 扛住 PGL Armor 反调试/反 Frida，较稳的是 root+Zygisk+延迟 hook。是模拟路的互补与交叉验证手段。
3. **反虚拟化（不推荐）**：无 IL2CPP 专门公开先例，工程量最大，且前两条已能得到明文，无必要理解 256 个 handler。

一个应回填到调查前提的更正：**"PGL Armor" 很可能不是加固壳，而是 Pangle（字节穿山甲）广告 SDK 的库**；解密器在 `libil2cpp.so` 内（与已知事实一致），不应把 `libpglarmor.so` 当作解密来源去分析。
