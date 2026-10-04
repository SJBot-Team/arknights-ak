# unidbg 在 Apple Silicon 上把 arm64 .so 仿真跑快

针对 `libil2cpp.so`（120 MB）在 unidbg 0.9.9 下加载耗时 2 s、但 DT_INIT 尾跳进 `libanort.so` 的 `xx1` 后十分钟不返回这一现状。
调研日期 2026-08-14，机器 Apple Silicon / macOS 25.6 / Temurin JDK 21.0.4 与 26.0.1（均为 arm64）。
源码基线：`zhkl0228/unidbg` master（`0.9.10-SNAPSHOT`）与 tag `v0.9.9` 逐文件比对，两者在本文涉及的 API 上**完全一致**（唯一差异是 master 给 hypervisor 加了几个寄存器访问，见 `git diff v0.9.9 HEAD -- backend/`）。

## 判定

**换后端能治「慢」，但治不了「不返回」。这是两个问题，必须分开打。**

1. Hypervisor 后端在这台机器上**可用、可自签、不需要付费开发者账号、不需要 root**，已实测通过（见第二节）。它是当前 unidbg 最快的 arm64 后端。
2. 但如果 `xx1` 里是**反调试轮询 / 线程等待 / 定时器自旋**，那它是一个不会自行终止的循环——快 80 倍只意味着「十分钟的空转变成八秒的空转再继续空转」。**换后端不会让一个无限循环收敛。**
3. 真正的解法是**根本不跑那个 init**。unidbg 提供了三条正规路径（`disableCallInitFunction()` / `InitFunctionFilter` / 字节 patch），见第五节。这条是首选。
4. 有一个陷阱必须先说：**`emulator.setTimeout()` 是死代码**，在 0.9.9 和 master 里都从未被读取（第四节）。如果曾指望它兜底，那是无效的。

推荐动作顺序：先做第五节的「跳过 init」，再叠加 Hypervisor 后端提速，最后才考虑 hook 层面的调优。

## 一、四个后端与选择方式

README 只给了定性排序，没有数字：unicorn 后端「support simple console debugger, gdb stub, instruction trace, memory read/write trace」，dynarmic 是「fast backend」，「Support Apple M1 hypervisor, **the fastest ARM64 backend**」，KVM 则是「with Raspberry Pi B4」（<https://github.com/zhkl0228/unidbg/blob/master/README.md>）。

选择方式就是往 builder 里按优先级追加 factory，`BackendFactory.createBackend` 顺序尝试，全部失败则回落到 unidbg-api 内置的 Unicorn 1 后端（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/arm/backend/BackendFactory.java>）：

```java
public static Backend createBackend(Emulator<?> emulator, boolean is64Bit, Collection<BackendFactory> backendFactories) {
    if (backendFactories != null) {
        for (BackendFactory factory : backendFactories) {
            Backend backend = factory.newBackend(emulator, is64Bit);
            if (backend != null) {
                return backend;
            }
        }
    }
    return new UnicornBackend(emulator, is64Bit);
}
```

仓库里的 arm64 示例（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-android/src/test/java/org/telegram/messenger/Utilities64.java>）：

```java
return AndroidEmulatorBuilder
        .for64Bit()
        .setProcessName("org.telegram.messenger")
        .addBackendFactory(new HypervisorFactory(true))
        .addBackendFactory(new DynarmicFactory(true))
        .addBackendFactory(new KvmFactory(true))
        .addBackendFactory(new Unicorn2Factory(true))
        .build();
```

**构造参数 `true` 是 `fallbackUnicorn`，不是「开启多线程」。** 中文资料里常见把它讲成多线程开关，那是错的。源码里它只决定 `newBackendInternal` 抛异常时是吞掉并让下一个 factory 接手（`true`），还是直接把异常抛出去（`false`）。调研阶段建议用 `false`：否则 Hypervisor 没签名时会**静默**退回 Unicorn，你会以为提速失败，其实是根本没用上。

Maven 坐标是四个独立 artifact，`com.github.zhkl0228:unidbg-hypervisor` / `unidbg-dynarmic` / `unidbg-kvm` / `unidbg-unicorn2`（各 `backend/*/pom.xml`）。

### 原生库是否需要自己编

不需要。仓库在 `v0.9.9` 就已经把编好的产物提交进了 resources（`git ls-tree -r v0.9.9 backend`）：

| 后端 | osx_arm64 产物 | 结论 |
|---|---|---|
| hypervisor | `natives/osx_arm64/libhypervisor.dylib` | 已内置，`file` 确认为 Mach-O arm64 |
| dynarmic | `natives/osx_arm64/libdynarmic.dylib` | 已内置 |
| unicorn2 | `natives/osx_arm64/libunicorn.dylib` | 已内置 |
| kvm | **只有 `natives/linux_arm64/libkvm.so`** | macOS 上无产物 |

要自己重编也有脚本：hypervisor 一条 `clang++ -framework Hypervisor hypervisor.mm`（<https://github.com/zhkl0228/unidbg/blob/master/backend/hypervisor/src/main/native/hypervisor/build.sh>），dynarmic 需要先建 `zhkl0228/yuzu-dynarmic` 静态库再 `./build.sh osx_arm64`（<https://github.com/zhkl0228/unidbg/blob/master/backend/dynarmic/README.md>）。但本任务用不上。

### KVM 在 macOS 上是死路

`KvmFactory` 的静态块同时卡两道（<https://github.com/zhkl0228/unidbg/blob/master/backend/kvm/src/main/java/com/github/unidbg/arm/backend/KvmFactory.java>）：

```java
private static boolean supportKvm() {
    File kvm = new File("/dev/kvm");
    return kvm.exists();
}
static {
    if (NativeLibraryUtil.getArchitecture() == NativeLibraryUtil.Architecture.LINUX_ARM64 && supportKvm()) {
        org.scijava.nativelib.NativeLoader.loadLibrary("kvm");
    }
}
```

架构必须是 `LINUX_ARM64`，且必须存在 `/dev/kvm`。macOS 两条都不满足，`newBackendInternal` 会直接 `throw new UnsupportedOperationException()`。KVM README 也只列 Linux ARM64 一行，安装步骤是给树莓派 4B 编内核（<https://github.com/zhkl0228/unidbg/blob/master/backend/kvm/README.md>）。**这条路在 Apple Silicon 上明确不通，不用再试。**

### 速度数字

unidbg 官方没有给基准数据。目前唯一见到成体系数字的是一篇中文笔记（M2 Pro / OpenJDK 17，<https://cn-sec.com/archives/5167367.html>）：冷启动 Unicorn ~3200 ms、Dynarmic ~1500 ms、Hypervisor ~800 ms；热调用单次 Unicorn ~120 ms、Dynarmic ~3 ms、Hypervisor ~1.5 ms，结论是「Dynarmic 比 Unicorn 快约 40 倍，Hypervisor 比 Unicorn 快约 80 倍」。

**这是二手来源，没有可复现的 benchmark 代码，数量级参考即可，不要写进结论。** 它与 README 的定性排序方向一致，可以作为「值得一试」的依据，不能作为「必然提速 80 倍」的承诺。同一篇文章的能力矩阵有明确错误（说 Hypervisor 不支持指令级 hook），见下一节的源码反证。

## 二、Hypervisor 后端：本机实测

### 入场券只有一个 entitlement

Apple 的要求是「All process must have the `com.apple.security.hypervisor` entitlement to use Hypervisor API」（<https://developer.apple.com/documentation/hypervisor>）。这个 key 在 macOS 11.0+ 上就是 arm64 `hv_vm_create` / `hv_vcpu_create` 用的那个（<https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.hypervisor>）。

三个容易走岔的地方：

- `com.apple.vm.hypervisor` 是 10.10 引入、**macOS 11.0 起已废弃**的旧 key，Apple Silicon 用不到（<https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.vm.hypervisor>）。
- `com.apple.vm.networking` 是 vmnet 框架的，且是**受限 entitlement**，Apple 明说「restricted to developers of virtualization software. To request this entitlement, contact your Apple representative」（<https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.vm.networking>）。跟 hvf 无关，别被它吓住。
- `com.apple.security.hypervisor` **不是**受限 entitlement，文档里没有任何申请流程，ad-hoc 自签即可。

unidbg 仓库自带的 entitlements 文件恰好只有这一个 key（<https://github.com/zhkl0228/unidbg/blob/master/backend/hypervisor/assets/hypervisor.entitlements>）：

```xml
<dict>
    <key>com.apple.security.hypervisor</key>
    <true/>
</dict>
```

### entitlement 挂在 java 上，不是挂在 dylib 上

这是 JNI 场景最关键的一条。Apple DTS 的原话：「Entitlements are only effective when applied to a main executable... **Apple platforms enforce permissions checks at the process boundary, so it's impossible for a library loaded in your process to have different permissions than the process itself.**」并且明确「It's never correct to do that... At worse, it causes a code signing crash」（<https://developer.apple.com/forums/thread/768184>）。Xcode 文档同样写「Don't apply entitlements to library code」（<https://developer.apple.com/documentation/xcode/creating-distribution-signed-code-for-the-mac>）。

与之吻合的是，unidbg 内置的 `libhypervisor.dylib` **本身不带任何 entitlement**（`codesign -d --entitlements -` 输出为空），而它的 README 要求签的是 `java`（<https://github.com/zhkl0228/unidbg/blob/master/backend/hypervisor/README.md>）：

```bash
cd backend/hypervisor/assets
sudo ./ldid -M -Shypervisor.entitlements "$JAVA_HOME"/bin/java
```

### 本机实测：四组对照

| # | 场景 | `hv_vm_create` 返回 |
|---|---|---|
| 1 | 裸 C 程序，未签名 | `0xfae94007` = **HV_DENIED** |
| 2 | 同一 C 程序，`codesign -s - --entitlements hypervisor.entitlements -f` | `0x00000000` = **HV_SUCCESS** |
| 3 | 系统 Temurin JDK 21 的 `java`，经 JNA 调用 | `0xfae94007` = **HV_DENIED** |
| 4 | JDK 21 整份 Home 拷贝后用 unidbg 自带 `ldid -M -S...` 签 `bin/java` | `0x00000000` = **HV_SUCCESS** |

第 4 组是决定性的：**unidbg README 里那条 `ldid` 命令在这台机器上原样有效**，而且我没有用 `sudo`（因为签的是拷贝出来的 JDK，写权限本来就有）。`codesign -d --entitlements -` 确认签完后 `com.apple.security.hypervisor` 与 Temurin 原有的五个 `com.apple.security.cs.*` 并存——`ldid -M` 是 merge 语义，不会把 JIT / unsigned-executable-memory 那几个顶掉，这一点对 JVM 能否正常启动很重要。

错误码取自 SDK 头文件 `$(xcrun --show-sdk-path)/usr/include/arm64/hv/hv_kern_types.h`（网页文档只列符号不列数值，<https://developer.apple.com/documentation/hypervisor/hypervisor-errors>）。arm64 与 x86_64 的枚举不同，arm64 版是：

```
HV_SUCCESS 0 / HV_ERROR 0xfae94001 / HV_BUSY 0xfae94002 / HV_BAD_ARGUMENT 0xfae94003
HV_ILLEGAL_GUEST_STATE 0xfae94004 / HV_NO_RESOURCES 0xfae94005 / HV_NO_DEVICE 0xfae94006
HV_DENIED 0xfae94007 / HV_EXISTS 0xfae94008 / HV_UNSUPPORTED 0xfae9400f
```

**缺 entitlement 的表现就是 `HV_DENIED` = `0xfae94007`**，不是 `HV_NO_DEVICE`。Apple 论坛上有开发者因 Xcode 工程里 entitlements 引用被清空而撞到同一个码（<https://developer.apple.com/forums/thread/808360>）。另外流传的 `HV_UNSUPPORTED = 0xfae94fff` 是错的，实际是 `0xfae9400f`。

### 签 JDK 的两个坑

**坑一：只拷 `bin/java` 会坏。** `java` 按 `@rpath/libjli.dylib` 找库，单拷可执行文件会得到 `dyld: Library not loaded: @rpath/libjli.dylib`。正确做法是 `cp -R` 整个 `Contents/Home`，再就地签 `<copy>/bin/java`。

**坑二：不要加 `--options runtime`。** ad-hoc 重签会把 Temurin 的 Developer ID 签名替换掉（TeamIdentifier 从 `JCDTMS22B4` 变 `not set`）。若保留 hardened runtime，library validation 会拒绝 JDK 自带的 Developer-ID 签名 dylib：`'lib/libjli.dylib' not valid for use in process: mapping process and mapped file (non-platform) have different Team IDs`。纯 ad-hoc（不带 `--options runtime`）没有这个问题。`ldid -M` 走的正是这条无 hardened runtime 的路径，所以官方命令是安全的。

无论哪种签法都建议签**拷贝出来的 JDK**，别动系统那份。

### 其他环境约束

- **不需要 root。** 实测以 uid 501 运行即成功；未签名的二进制无论什么 uid 都是 HV_DENIED。
- **沙箱内可用。** Apple 把 hvf 定位为「your entitled, sandboxed, user-space process」（<https://developer.apple.com/documentation/hypervisor>）。
- **Rosetta 下不可用。** Apple 明说 Rosetta 不翻译「Virtual Machine apps that virtualize x86_64 computer platforms」（<https://developer.apple.com/documentation/apple-silicon/about-the-rosetta-translation-environment>）。所以**JDK 必须是 arm64 的**。这台机器上 temurin-19 / 11 / 8 都是 x86_64，选错了会直接白费。JDK 21 和 26 都是 arm64，都验证可用。

### 一个需要预先警觉的差异：16 KB 页

`Backend` 接口的 javadoc 就写明了「Typically 4KB (dynarmic/kvm) or **16KB (hypervisor on Apple Silicon)**」（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/arm/backend/Backend.java>）。原生侧 `hypervisor.h` 硬编码 `#define PAGE_BITS 14 // 16k`，Java 侧 `HypervisorFactory.getPageSize()` 返回 `sysconf(_SC_PAGESIZE)`，在 Apple Silicon 上就是 16384。而 `AbstractEmulator.getPageAlign()` 会优先采用后端的页大小：

```java
public final int getPageAlign() {
    int pageSize = backend.getPageSize();
    if (pageSize == 0) {
        pageSize = getPageAlignInternal();
    }
    return pageSize;
}
```

**[推断，中等置信]** 换成 Hypervisor 后端后，整个仿真器的页粒度从 4 KB 变成 16 KB，`libil2cpp.so` 这种按 4 KB 对齐的大 ELF 的 segment 映射与权限边界会随之变化。这未必出错（unidbg 自己的 Android64Test 就把 Hypervisor 放在候选里），但如果换后端后出现「换 Unicorn 正常、换 Hypervisor 才有的」内存异常，第一嫌疑就是这里，而不是解密逻辑。

## 三、Hook 能力矩阵（以源码为准）

这张表全部从源码里的 `UnsupportedOperationException` 直接读出，比任何二手资料可靠。

| 能力 | UnicornBackend / Unicorn2 | Dynarmic | Hypervisor(64) |
|---|---|---|---|
| `CodeHook`（逐指令） | 支持 | **抛 UnsupportedOperationException** | 支持，但走硬件单步 |
| `BlockHook`（基本块） | 支持 | **抛 UnsupportedOperationException** | **抛 UnsupportedOperationException** |
| `ReadHook` / `WriteHook` | 支持，范围任意 | **抛 UnsupportedOperationException** | 支持，但**受硬件 watchpoint 槽位数限制** |
| `EventMemHook`（非法访问） | 支持 | 支持 | 支持 |
| `InterruptHook`（SVC） | 支持 | 支持 | 支持 |
| `debugger_add`（`emulator.attach()`） | 支持 | **空实现，静默失效** | 支持（硬件断点） |
| `emu_stop()` | 支持 | 支持 | 支持 |
| `registerEmuCountHook` | 仅 Unicorn2 支持 | 不支持（基类抛异常） | 不支持（基类抛异常） |

依据：

- Dynarmic 的四个 hook 全是一行 `throw new UnsupportedOperationException();`，`debugger_add` 是空方法体（<https://github.com/zhkl0228/unidbg/blob/master/backend/dynarmic/src/main/java/com/github/unidbg/arm/backend/DynarmicBackend.java>）。
- Hypervisor 的 `BlockHook` 同样直接抛异常（<https://github.com/zhkl0228/unidbg/blob/master/backend/hypervisor/src/main/java/com/github/unidbg/arm/backend/HypervisorBackend.java>）。
- Hypervisor 的 `ReadHook` / `WriteHook` 走 `installWatchpoint`，槽位数来自 `hypervisor.getWRPs()`，用满即 `throw new UnsupportedOperationException("Max WRPs: " + watchpoints.length)`；断点同理受 `getBRPs()` 限制（<https://github.com/zhkl0228/unidbg/blob/master/backend/hypervisor/src/main/java/com/github/unidbg/arm/backend/hypervisor/HypervisorBackend64.java>）。**这意味着 `ElfUnpacker` 那种「给整个代码段挂 WriteHook」的玩法在 Hypervisor 上做不到**——那是范围性 hook，不是几个 watchpoint 能覆盖的。
- `registerEmuCountHook` 在 `AbstractBackend` 里默认 `throw new UnsupportedOperationException()`，只有 `Unicorn2Backend` 覆写（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/arm/backend/AbstractBackend.java>）。

三条直接影响本任务的推论：

1. **Dynarmic 上你已有的 memory-write hook 与 CodeHook 会直接抛异常。** 如果解密流程依赖 write hook 抓中间结果，Dynarmic 不能用。
2. **Hypervisor 上 CodeHook 虽然实现了，但它是硬件单步。** `hook_add_new(CodeHook...)` 内部走 `CodeHookEscaper` + `hypervisor.enable_single_step(true)`，每条指令一次 VM exit。第二节测得的速度优势会被这个吃干净，很可能比 Unicorn 的 CodeHook 还慢。而且它是全局独占的，重复注册直接 `IllegalStateException`。
3. **`emulator.attach()` 在 Dynarmic 上是静默失效的**，不会报错也不会断下。调试请留在 Unicorn2。

好消息是 unidbg 默认只装 `EventMemHook` 和 `InterruptHook` 两种（`AbstractARMEmulator` 构造函数），这两种所有后端都支持，所以「不挂自定义 hook 时」三个后端都能跑起来。

## 四、Hook 成本与「限时执行」

### BlockHook 确实远比 CodeHook 便宜

这一条有 Unicorn 官方 FAQ 的直接背书（<https://github.com/unicorn-engine/unicorn/blob/master/docs/FAQ.md>）：慢的典型原因是「Instrumenting every instruction executed / Instrumenting every memory access」，给出的处方是「Optimize your program with less instrumentation, e.g. by using **`UC_HOOK_BLOCK` instead of `UC_HOOK_CODE`**」，并指出「Updating PC is a very large overhead (**10x slower in the worst case**)」——装了 `UC_HOOK_CODE` 之后，其覆盖范围内的 PC 必须处处同步，QEMU 的 TB 无法整块跑完。

unidbg 侧两个 Unicorn 后端都把 `BlockHook` 直通到 `UC_HOOK_BLOCK`（`Unicorn2Backend:248`、`UnicornBackend:240`），所以这个优化在 unidbg 层面是可用的。**你观察到的「加了逐指令 CodeHook 后更慢得多」完全符合上游文档的预期，不是配置错误。**

中文社区对 unidbg trace 的专项优化也印证这个量级：看雪《魔改 unidbg：极致的 trace 速度提升》报告在普通代码上提速数十倍、在 OLLVM+VMP 上 100 倍以上，手段是反汇编结果按数组下标缓存、异步缓冲写日志、把格式化移出热循环（<https://bbs.kanxue.com/thread-290570.htm>）。换句话说，CodeHook 的成本大头一部分在 Unicorn 的 PC 同步，另一部分在 unidbg 自己每条指令的 JNI 往返 + Capstone 反汇编。

**结论：定位自旋点时不要用全模块 CodeHook，用 BlockHook 或把 CodeHook 的 `begin`/`end` 收窄到几十条指令。**

### 超时：`setTimeout()` 是死代码

`Emulator` 接口上有这个方法，javadoc 写得很正经（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/Emulator.java>）：

```java
/**
 * @param timeout  Duration to emulate the code (in microseconds). When this value is 0, we will emulate the code in infinite time, until the code is finished.
 */
void setTimeout(long timeout);
```

`Backend.emu_start` 也确实有 `timeout` 形参。但 `AbstractEmulator` 里这个字段**只有写、没有读**——全仓库对 `timeout` 字段的引用只有声明（`:59`）、`attach()` 里清零（`:189`）、setter（`:292-293`）三处，而真正的调用点是（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/AbstractEmulator.java>）：

```java
backend.emu_start(begin, until, 0, 0);
```

`v0.9.9` 与 master 完全一样（`git show v0.9.9:...AbstractEmulator.java` 第 375 行）。**所以 `emulator.setTimeout(...)` 在 0.9.9 上是彻底无效的。**

即使它有效，也只对 Unicorn 后端管用：Unicorn 的 `emu_start` 会把 `timeout` 透传给 `unicorn.emu_start`，而 Dynarmic 与 Hypervisor 的 `emu_start` 把 `timeout` 和 `count` 两个参数**直接丢弃**：

```java
// DynarmicBackend / HypervisorBackend，两者写法相同
public final synchronized void emu_start(long begin, long until, long timeout, long count) {
    this.until = until + 4;
    dynarmic.emu_start(begin);   // hypervisor.emu_start(begin);
}
```

可用的兜底手段只剩三个，按可靠性排序：

1. **另起线程调 `emulator.getBackend().emu_stop()`。** 这是 unidbg 自己用的手法——`AbstractEmulator.emulate()` 在 debug 日志开启时会注册一个 shutdown hook，里面正是 `backend.emu_stop()`。三个后端都实现了 `emu_stop`。
2. **Unicorn2 专属的 `registerEmuCountHook(n)`。** 仓库示例 `ThreadTest.java:25` 写着 `emulator.getBackend().registerEmuCountHook(10000); // 设置执行多少条指令切换一次线程`。但它的实现是每 n 条指令抛一个 `ThreadContextSwitchException`，本质是线程调度点，不是超时，滥用会打乱 thread dispatcher。
3. **窄范围 BlockHook 里自己数块数**，超过阈值就 `emu_stop()`。成本远低于 CodeHook 计数。

## 五、绕开 init：三条正规路径

这是本任务真正的解法。先把加载/初始化的判定逻辑抄清楚（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-android/src/main/java/com/github/unidbg/linux/AndroidElfLoader.java>）：

```java
protected final LinuxModule loadInternal(LibraryFile libraryFile, boolean forceCallInit) {
    LinuxModule module = loadInternal(libraryFile);
    resolveSymbols(!forceCallInit);
    if (callInitFunction || forceCallInit) {
        for (LinuxModule m : modules.values().toArray(new LinuxModule[0])) {
            boolean forceCall = (forceCallInit && m == module) || m.isForceCallInit();
            if (callInitFunction) {
                m.callInitFunction(emulator, forceCall);
            } else if (forceCall) {
                m.callInitFunction(emulator, true);
            }
            m.initFunctionList.clear();
        }
    }
    ...
}
```

**先纠一个常见误解：`vm.loadLibrary(file, false)` 并不跳过 init。** 那个 `false` 是 `forceCallInit`，而 `callInitFunction` 字段的默认值是 `true`（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/spi/AbstractLoader.java>）：

```java
protected boolean callInitFunction = true;
```

所以 `if (callInitFunction || forceCallInit)` 依然成立，init 照跑。传 `false` 唯一的作用是 `forceCall` 为假，此时 `LinuxModule.callInitFunction` 会因为「还有未解析符号」而提前返回：

```java
void callInitFunction(Emulator<?> emulator, boolean mustCallInit) throws IOException {
    if (!mustCallInit && !unresolvedSymbol.isEmpty()) {
        for (ModuleSymbol moduleSymbol : unresolvedSymbol) { log.info("... symbol is missing before init ..."); }
        return;
    }
    ...
}
```

也就是说，`loadLibrary(file, false)` 能否跳过 init，取决于是否**碰巧**有符号没解析上，这是运气不是控制。真正的开关是下面三条。

### 路径 A：全局关掉 init（最粗暴，最省事）

`Memory extends IO, Loader, StackMemory`（`Memory.java:11`），所以 `Loader` 上的方法直接挂在 `emulator.getMemory()` 上（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/spi/Loader.java>）：

```java
void disableCallInitFunction();
void setCallInitFunction(boolean callInit);
```

用法：

```java
Memory memory = emulator.getMemory();
memory.setLibraryResolver(new AndroidResolver(23));
memory.disableCallInitFunction();                       // 关键：必须在 loadLibrary 之前
DalvikModule dm = vm.loadLibrary(new File(".../libil2cpp.so"), false);
Module module = dm.getModule();
// 直接按导出符号或 base+offset 调用解密例程
```

`callInitFunction=false` 且 `forceCallInit=false` 时，上面那段 `if` 整块不进，DT_INIT 与 init_array **一次都不会执行**。

代价：全局生效，依赖库（libc 之类）的构造器也不跑。对「只想调一个自包含解密例程」的场景通常没问题，但如果解密例程读的全局表恰好由某个 init 填，会得到全零。这一点必须实测验证，别假设。

### 路径 B：按地址逐个筛（最精准，推荐）

`LinuxModule.callInitFunction` 在每个 init 入口前都问一次 filter（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-android/src/main/java/com/github/unidbg/linux/LinuxModule.java>）：

```java
while (!initFunctionList.isEmpty()) {
    InitFunction initFunction = initFunctionList.remove(0);
    long initAddress = initFunction.getAddress();
    if (initFunctionFilter != null && !initFunctionFilter.accept(emulator, initAddress)) {
        continue;                      // 跳过这一条 DT_INIT / init_array 项
    }
    ...
    initAddress = initFunction.call(emulator);
}
```

接口只有一个方法（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/spi/InitFunctionFilter.java>）：

```java
public interface InitFunctionFilter {
    boolean accept(Emulator<?> emulator, long address);
}
```

装配方式很隐蔽——**loader 是从 `LibraryResolver` 上做 `instanceof` 取的**，没有单独的 setter（`AndroidElfLoader:634-639`）：

```java
InitFunctionFilter initFunctionFilter = null;
if (libraryResolver instanceof InitFunctionFilter) {
    initFunctionFilter = (InitFunctionFilter) libraryResolver;
}
```

所以要让自己的 resolver 同时实现这个接口：

```java
class MyResolver extends AndroidResolver implements InitFunctionFilter {
    MyResolver(int sdk) { super(sdk); }
    @Override
    public boolean accept(Emulator<?> emulator, long address) {
        Module m = emulator.getMemory().findModuleByAddress(address);
        // 放行普通库，只掐掉 libil2cpp.so 的 init
        return m == null || !"libil2cpp.so".equals(m.getName());
    }
}
memory.setLibraryResolver(new MyResolver(23));
```

这是最推荐的一条：不改字节、不影响别的模块、可以按地址精确到单个 init_array 条目。

### 路径 C：字节 patch，把入口改成 `ret`

ARM64 的 `ret` 是 `0xD65F03C0`。要在 init 跑之前动手，就得先注册 `ModuleListener`（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/ModuleListener.java>）：

```java
public interface ModuleListener {
    void onLoaded(Emulator<?> emulator, Module module);
}
```

`onLoaded` 在 `loadInternal` 早于 init 调用点触发，所以这里是唯一能「先于 init 改代码」的窗口：

```java
memory.addModuleListener((emu, module) -> {       // 必须在 loadLibrary 之前注册
    if ("libanort.so".equals(module.getName())) {
        // 把 xx1 的第一条指令改成 ret，让 DT_INIT 的尾跳立刻返回
        emu.getMemory().pointer(module.base + 0xXXXX).setInt(0, 0xD65F03C0);
        // 等价写法：emu.getBackend().mem_write(module.base + 0xXXXX, new byte[]{(byte)0xC0,0x03,0x5F,(byte)0xD6});
    }
});
```

同一个 listener 里还可以补状态，比如把缺失的符号手工登记回去（仓库示例 `QDReaderJni.java:87`）：

```java
@Override
public void onLoaded(Emulator<?> emulator, Module module) {
    if ("libcrypto.so".equals(module.name)) {
        Symbol s = module.findSymbolByName("DES_set_key", false);
        if (s != null) module.registerSymbol("DES_set_key_unchecked", s.getAddress());
    }
}
```

`registerSymbol(String, long)` 定义在 `Module` 抽象类上（`Module.java:140`），用来给「跳过 init 后没被动态注册上」的符号补一个地址。

### 补充手段：inline hook 与 stub 依赖库

如果不想跳过整个 init、只想让其中某个函数立刻返回：

- **Dobby（unidbg 内置，64 位支持最好）**，`Dobby.getInstance(emulator)` 后 `replace(symbol 或 address, callback)`；`ReplaceCallback.onCall` 返回 `HookStatus.LR(emulator, returnValue)` 表示「不执行原函数，直接以该返回值回到 LR」，`HookStatus.RET(emulator, originFunction)` 表示继续执行原函数（`HookStatus.java:18,23`；<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/hook/ReplaceCallback.java>）。
- **HookZz** 接口另有 `wrap`（观察前后但保留原逻辑）与 `instrument`（单地址 DBI）（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/hook/hookzz/IHookZz.java>）。
- **xHook** 走 PLT/GOT，专治「替掉某个 libc 导入」，注意必须调 `refresh()` 才生效（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/hook/xhook/IxHook.java>）：

```java
IxHook xHook = XHookImpl.getInstance(emulator);
xHook.register("libil2cpp.so", "clock_gettime", callback, true);
xHook.refresh();
```

- **缺失依赖库可以用 `VirtualModule` 顶上**：继承它、在 `onInitialize` 里往 `symbols` map 塞假符号，再 `register(emulator.getMemory())`，loader 就会拿这些符号去解析导入而不是报错（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-api/src/main/java/com/github/unidbg/virtualmodule/VirtualModule.java>；现成例子见 `virtualmodule/android/SystemProperties.java`）。**如果最终决定连 `libanort.so` 都不加载，这就是把它整个换成壳子的办法。**

### 顺带一提：unidbg 自带脱壳器

`com.github.unidbg.linux.unpack.ElfUnpacker` 的类注释就是干这个的（<https://github.com/zhkl0228/unidbg/blob/master/unidbg-android/src/main/java/com/github/unidbg/linux/unpack/ElfUnpacker.java>）：

```
Dump 针对 init_array 加密的 so 文件
First before load so:  memory.addModuleListener();
Then in onLoaded method:
    if ("libxxx.so".equals(module.name)) {
        new ElfUnpacker(libxxxFileData, outFile).register(emulator, module);
    }
```

它给只读代码段挂 `WriteHook`，在 `InitFunctionListener.onPostCallInitFunction` 时把被 init 改写过的字节回写成一个新的 .so。如果 `libil2cpp.so` 的解密例程本体是被 init 解密出来的，这个类能直接帮你把解密后的镜像 dump 成文件，之后就再也不用跑 init 了。**注意它依赖范围性 `WriteHook`，因此只能在 Unicorn/Unicorn2 后端上用**（见第三节）。

`InitFunctionListener` 本身也可以单独用来定位是哪一条 init 卡住（`module.setInitFunctionListener(...)`，`Module.java:185`），它会报出 `initFunction` 地址和 index——这比挂 CodeHook 便宜得多，应该是排查的第一步。

## 六、加固 / 反作弊 so 的 init 不返回：社区经验

unidbg 仓库里有若干形态相同的 issue：

- **#330「程序一直在死循环」**：全量日志显示反复 `openat(/dev/urandom) → read(count=1) → close`，几百次没有进展。根因是一次读一个字节的随机数循环（<https://github.com/zhkl0228/unidbg/issues/330>）。
- **#331 卡在 `munmap`**：`libmetasec_ml.so`，trace 到 `pthread_clone` 之后就停在 `munmap`。形态是**init 起了工作线程而 unidbg 没有调度它**，主流程等一个永远不会跑的线程（<https://github.com/zhkl0228/unidbg/issues/331>）。
- **#360「File IO 程序卡住，CPU100%」**：Windows 和 macOS 上都能复现，不抛异常，纯自旋（<https://github.com/zhkl0228/unidbg/issues/360>）。
- 同族的 init 失败还有 #348、#396、#523（`Illegal JNI version: 0xffffffff` 来自 `callJNI_OnLoad`）、#740。

被记录得最完整的是 `libmsaoaidsec.so`（移动安全联盟）。看雪的分析显示它的 `.init_proc` 会：滚动异或解密字符串 → 对 `0..0x26A04` 做加载期 CRC32 → 通过 `sub_1B924()` **拉起若干检测线程**，分别每 2 s 读 `/proc/self/stat` 查 TracerPid、扫 `/proc/self/maps` 与 `/proc/self/task` 匹配 `frida-agent` / `gum-js-loop`、每 3 s 查 ADB/USB 属性、周期性重算同一段代码的 CRC；退出路径是 `mmap` 一页 RWX、写入内联的 `exit_group(0)` 再跳过去（<https://bbs.kanxue.com/thread-291377.htm>、<https://bbs.kanxue.com/thread-291403.htm>、<https://zhupite.com/sec/libmsaoaidsec.html>）。

**这些轮询线程与定时循环正是 unidbg 里「init 永不返回」的直接来源。** 归纳出的根因分类：

1. 单字节 `/dev/urandom` 忙等
2. `pthread_create` 起线程，unidbg 不调度 → 主流程阻塞在 `futex` / `munmap`
3. `clock_gettime` / `gettimeofday` 计时循环
4. 读 `/proc/self/maps`、`/proc/self/status`、`/proc/self/task` 做反 Frida / 反调试
5. TracerPid ptrace 检查
6. 某个 syscall 返回值不合期望，代码无限重试

**`libanort.so` 是商业反作弊运行时，形态与上述第 2、3、4、5 类高度吻合。** 十分钟不返回、且没有异常抛出，最符合的假设是「init 起了轮询线程或进了定时自旋」，而不是「在做一件很慢但会结束的事」。

社区的通行做法与第五节完全一致：能不跑就不跑；必须跑就用 hook 把反调试 / 起线程 / CRC 那几个子函数掐掉，保留真正初始化状态的部分；用 `emulator.attach()` 下断点定位自旋指令，然后按地址 patch。hook 的选型顺序是「业务级 → xHook（导入表）→ Dobby/HookZz（具体函数）→ CodeHook（只在极小范围内，最后手段）」（<https://cn-sec.com/archives/5205710.html>、<https://blog.seeflower.dev/archives/67/>）。

证据强度说明：#330 / #331 / #360 只坐实了**症状**和 syscall/线程**特征**，维护者并未在帖内给出修复；第五节那些 API 是从仓库源码与自带测试直接读出的（强证据），而「实践中怎么用」来自看雪 / cn-sec 等社区文章（中等强度）。

## 七、给本项目的行动顺序

1. **先验证「跳过 init 是否可行」，这是最高杠杆的一步。** 用路径 B 的 `InitFunctionFilter` 把 `libil2cpp.so`（以及 `libanort.so`）的 init 全部 `return false`，然后直接按地址调解密例程。如果解密结果正确，问题当场结束，后端根本不用换。成本：不到一小时。
2. **若第 1 步产出全零或崩溃**，说明解密例程依赖 init 建立的全局状态。此时改用路径 B 的细粒度筛选：只掐 `libanort.so` 的 init（那是反作弊，几乎肯定与解密无关），保留 `libil2cpp.so` 自己的。
3. **若仍需要跑 `libanort.so` 的 init**，先用 `module.setInitFunctionListener(...)` 打出到底停在哪个 init 地址（成本近似为零），再在那个地址附近挂**窄范围** BlockHook 定位自旋块，最后用路径 C 把该函数 patch 成 `ret`。**全程不要用全模块 CodeHook。**
4. **提速单独做，不要和第 1–3 步混在一起。** Hypervisor 后端已验证可用：拷一份 arm64 JDK，`ldid -M -Shypervisor.entitlements <copy>/bin/java`，builder 里 `addBackendFactory(new HypervisorFactory(false))`（**调试期用 `false`**，避免静默回落）。注意页大小会变 16 KB，若只在 Hypervisor 下出现内存异常，从这里查起。
5. **需要范围性 memory-write hook 的环节（比如 `ElfUnpacker` 脱壳）必须留在 Unicorn2 上**，Hypervisor 的 watchpoint 槽位不够，Dynarmic 根本不支持。合理的分工是：Unicorn2 负责一次性的分析与脱壳，Hypervisor 负责之后的批量重复执行。
6. **不要在 `emulator.setTimeout()` 上浪费时间**，它是死代码。要兜底就另起线程调 `backend.emu_stop()`。

## 复现

entitlement 与签名的四组对照：

```bash
S=/tmp/hv && mkdir -p $S && cat > $S/t.c <<'EOF'
#include <Hypervisor/Hypervisor.h>
#include <stdio.h>
int main(void){ hv_return_t r = hv_vm_create(NULL);
  printf("hv_vm_create -> 0x%08x\n", (unsigned)r);
  if (r == HV_SUCCESS) hv_vm_destroy(); return 0; }
EOF
xcrun -sdk macosx clang -arch arm64 -framework Hypervisor -o $S/t $S/t.c
$S/t                                    # -> 0xfae94007  HV_DENIED

git clone --depth 1 https://github.com/zhkl0228/unidbg.git $S/unidbg
ENT=$S/unidbg/backend/hypervisor/assets/hypervisor.entitlements
codesign -s - --entitlements $ENT -f $S/t
$S/t                                    # -> 0x00000000  HV_SUCCESS

# JVM 侧：整份拷贝 + unidbg 自带 ldid
cp -R /Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home $S/jdk-hv
$S/unidbg/backend/hypervisor/assets/ldid -M -S$ENT $S/jdk-hv/bin/java
codesign -d --entitlements - $S/jdk-hv/bin/java | grep hypervisor
```

用 JNA 直接从 JVM 探 hvf（不需要编译 unidbg，`jna` 用本地 `~/.m2` 里的即可）：

```java
public interface Hv extends Library {
    Hv INSTANCE = Native.load("/System/Library/Frameworks/Hypervisor.framework/Hypervisor", Hv.class);
    int hv_vm_create(Pointer config);
    int hv_vm_destroy();
}
// 系统 java  -> 0xfae94007 HV_DENIED
// $S/jdk-hv/bin/java -> 0x00000000 HV_SUCCESS
```

源码断言可用 grep 直接复核（clone 后在仓库根目录）：

```bash
grep -n "UnsupportedOperationException" backend/dynarmic/src/main/java/com/github/unidbg/arm/backend/DynarmicBackend.java
grep -n "BlockHook" backend/hypervisor/src/main/java/com/github/unidbg/arm/backend/HypervisorBackend.java
grep -n "emu_start(begin, until" unidbg-api/src/main/java/com/github/unidbg/AbstractEmulator.java
grep -rn "\btimeout\b" unidbg-api/src/main/java/com/github/unidbg/AbstractEmulator.java
git diff v0.9.9 HEAD --stat -- backend/ unidbg-api/src/main/java/com/github/unidbg/arm/backend/
```
