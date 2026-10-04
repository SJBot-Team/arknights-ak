# Cpp2IL 在百 MB 级 Mach-O 上的判定实验

对应 ticket [#10 判定实验：Cpp2IL 能否处理百 MB 级 Mach-O](https://github.com/joycastle/revenant/issues/10)。
实测日期 2026-07-27，机器 macOS 26.5.2 / Apple Silicon / 64 GB RAM。
Cpp2IL 构建：`~/workspace/playground/Cpp2IL/publish/osx-arm64-self-contained/Cpp2IL`，版本 `2022.1.0+e66a74bb`。

## 判定

**通过。** Gossip Harbor 的 ipa 走完了 Cpp2IL 全流程，产物数量与质量与 Android 侧持平。ipa 支线不需要先给 Cpp2IL 打性能补丁，#7 是「适配」而不是「先修上游」。

唯一失败的是 `nativemethoddetector` 这一个 processing layer，去掉它即可，代价是 native method 检测缺失（见下）。

## 一、实测数据

样本：`../2026-06-09-gossip-harbor-re/com.mergegame.icookie_3.91.0_und3fined.ipa`
- 二进制 `Payload/GossipHarbor.app/Frameworks/UnityFramework.framework/UnityFramework`，99 MB（103,969,216 B），thin arm64
- metadata `Payload/GossipHarbor.app/Data/Managed/Metadata/global-metadata.dat`，7.7 MB，明文，Cpp2IL 报 `IL2CPP Metadata version 31.1`
- Unity 版本 2022.3.62f2（读 `Payload/GossipHarbor.app/Data/globalgamemanagers` 头部字符串）

| pass | 结果 | 墙钟 | 峰值 RSS | 产物 |
|---|---|---|---|---|
| `--output-as isil` | 成功 | 55.8 s | **15.7 GB** | 6,681 文件 / 56 程序集 |
| `--output-as diffable-cs --use-processor attributeinjector,nativemethoddetector,stablenamer` | **失败** | 2,530 s | **26.1 GB** | 0（异常后不输出） |
| `--output-as diffable-cs --use-processor attributeinjector,stablenamer` | 成功 | 39.1 s | 2.4 GB | 5,929 文件 |

阶段分解（isil pass）：metadata 初始化 77 ms → codereg/metareg 启发式命中 357 ms（`codereg=0x53EBF68, metareg=0x54BA560`）→ binary 初始化 35 ms → **application model 创建 38.4 s** → 输出 16.9 s。时间与内存的大头都在 application model，与格式无关。

Android 侧同版本对照（`../2026-06-09-gossip-harbor-re/_refs/3.91.0/cpp2il_out`）：IsilDump 6,597 / DiffableCs 5,868。iOS 侧分别是 6,681 / 5,929，**略多**——多出的是 `Unity.Notifications.iOS` 一类 iOS 专有程序集。没有系统性缺失。

## 二、抽样质量

IsilDump 是真实 ARM64 反汇编，方法体非空：

```
Method: System.Void .ctor(System.String fileName)
	0x03060C10 STP X24, X23, [X31 - 0x40]!
	0x03060C2C ADRP X21, 0x2E66000
	0x03060C40 BL 0x2BE7ED4
```

DiffableCs 与 Android 侧逐字段对照（`Assembly-CSharp/DictFileStorage.cs`）：

| | iOS | Android 3.91.0 |
|---|---|---|
| Token | `0x2000105` / 字段 `0x4000543` | **完全相同** |
| RVA | `0x3060C10` | `0xBD1910` |
| 字段偏移 | `0x20` / `0x28` | `0x10` / `0x14` |

**Token 是跨平台稳定的锚点，RVA 与字段偏移不是。** 字段偏移差 2 倍是因为 Android 侧那个 ABI 是 32 位——指针宽度差异，不是布局差异。这条对 #7 的「apk 与 ipa 结果可交叉验证」那一问是直接输入：**能交叉验证的键是 Token，不是 RVA。**

## 三、唯一的失败点：`nativemethoddetector`

```
[Fail] Processing layer nativemethoddetector threw an exception:
System.Exception: Could not find section for virtual address 0xA1EC4F4.
Lowest section address is 0x4000, highest section address is 0x6143278
   at LibCpp2IL.MachO.MachOFile.MapVirtualAddressToRaw  (MachOFile.cs:107)
   at Cpp2IL.Core.Utils.NewArm64Utils.GetArm64MethodBodyAtVirtualAddress (NewArm64Utils.cs:33)
   at ...NativeMethodDetectionProcessingLayer.Process (NativeMethodDetectionProcessingLayer.cs:44)
```

三点观察：

1. **这是 `research/ios-gaps.md` 第 2 条预测的 section-vs-segment 映射分歧的第一次实证。** Mach-O 侧按 section 映射会对越界/落 gap 的地址抛异常，ELF 侧按 segment 映射只会静默返回一个无意义偏移——同一份代码在两种格式上一个炸一个不炸。
2. 但这一例**不是** gap 问题：`0xA1EC4F4` 远高于最高 section 地址 `0x6143278`，地址本身就出了二进制。是 native method 检测在跟一批不指向代码的指针，ELF 侧靠「静默返回垃圾」蒙混过去了。
3. **代价极不对称**：带这一层跑 2,530 s / 26 GB 然后抛异常、整轮不输出；去掉后 39 s / 2.4 GB 出全量。

`revenant/scripts/run_cpp2il_isil.sh:92` 硬编码了 `--use-processor attributeinjector,nativemethoddetector,stablenamer`，这是 #7 的一个具体改动点：**Mach-O 路径需要能去掉 processing layer**。

## 四、推翻既有笔记：ApplyChainedFixups 不是瓶颈

`vita-majhong-re/notes/arch-06:79` 记「对 iOS 125MB Mach-O 卡在 Applying reloc（性能瓶颈）」。实测推翻。

先看两个样本的形态差异（`otool -l`）：

| | GH UnityFramework | Vita UnityFramework |
|---|---|---|
| 重定位形式 | `LC_DYLD_INFO_ONLY`（传统 rebase/bind） | `LC_DYLD_CHAINED_FIXUPS` |
| 段数 | 3 | 5 |
| 加密 | 无 `LC_ENCRYPTION_INFO_64` | 有，`cryptid=0`（已脱壳） |

**GH 根本没有 chained fixups**——所以 GH 的成功并不覆盖那条代码路径。于是单独测：拿 Vita 的 120 MB Mach-O 配 GH 的合法 metadata 喂进去（metadata 先于 binary 初始化，binary 读完 fixups 后才会因找不到 codereg 报错，正好只测 fixups 阶段）：

```
[Verb] [Library] 	Applying chained fixups...Applied 785969 chained fixups.
        0.57 real       327 MB maximum resident
```

**785,969 个 fixup，整个进程 0.57 秒。** `ApplyChainedFixups` 不是瓶颈，一次也不是。静态核对也支持这个结论：Vita 的 fixup 表 `datasize=434,680`、753 个 16 KB 页、`pointer_format=6`（`DYLD_CHAINED_PTR_64_OFFSET`），Cpp2IL 的 `MachOFile.cs:170-242` 对 format 6 有正确分支，`Next == 0` 有终止条件，不存在死循环。

[推断，中等置信] 旧笔记记录的停顿更可能发生在紧邻的「Searching Binary for Required Data」——在 metadata 不正确时，codereg/metareg 的启发式搜索会退化成全二进制扫描。日志上这两行相邻，容易误归因。旧笔记用的还是 `net10.0` 的 Debug dll，也比这里的 self-contained release 慢。

## 五、Vita 的真实阻断点是 metadata，不是格式

用 Vita 已解密的 `_refs_ios/global-metadata.decrypted.dat` 正常跑：

```
System.IndexOutOfRangeException: Index was outside the bounds of the array.
   at LibCpp2IL.Metadata.Il2CppMetadata..ctor (Il2CppMetadata.cs:56)
        0.24 real
```

0.24 秒即挂在 metadata 构造函数里——**S-box 解密尚未完全正确**，连格式解析都没过，更谈不上跑到 fixups。这与 `notes/arch-06` 自己记的「index 越界」一致。

结论：Vita 这个靶子在 iOS 侧卡的是**加固厂的 metadata 加密**，属于 #7 里「metadata 解密如何插拔」那一问，不是 Cpp2IL 的能力边界。**Revenant 的 ipa 支线不该被 Vita 的解密进度绑架**——GH 这类未加固包已经能全流程跑通。

## 六、给 #7 的输入（不在本票内做设计）

1. Cpp2IL 命令行**不需要新增格式开关**，`--force-binary-path` 直指 `UnityFramework` 即可（魔数自动嗅探，日志确认 `Using binary type Mach-O File`）。
2. **需要新增的是 processing layer 的按格式裁剪**——至少在 Mach-O 上摘掉 `nativemethoddetector`。
3. 资源门槛需要写进文档：**isil pass 峰值 15.7 GB**。16 GB 机器会 swap，8 GB 机器跑不动。这是产品化的硬约束，Android 侧同样适用（同一阶段耗内存，与格式无关）。
4. 跨平台交叉验证的锚点是 **Token**，不是 RVA、不是字段偏移。
5. `section` vs `segment` 映射分歧是真的，且**在 Mach-O 上表现为抛异常而非静默错值**——Revenant 自己的 `elf.py` 若照搬 segment 映射，会得到 Mach-O 上「不报错的错地址」。

## 复现

```bash
D=/tmp/gh-ios && mkdir -p "$D/out"
unzip -o -j ../2026-06-09-gossip-harbor-re/com.mergegame.icookie_3.91.0_und3fined.ipa \
  'Payload/GossipHarbor.app/Frameworks/UnityFramework.framework/UnityFramework' \
  'Payload/GossipHarbor.app/Data/Managed/Metadata/global-metadata.dat' -d "$D"

C=~/workspace/playground/Cpp2IL/publish/osx-arm64-self-contained/Cpp2IL
/usr/bin/time -l "$C" --force-binary-path "$D/UnityFramework" \
  --force-metadata-path "$D/global-metadata.dat" \
  --force-unity-version 2022.3.62f2 --output-to "$D/out" --output-as isil

/usr/bin/time -l "$C" --force-binary-path "$D/UnityFramework" \
  --force-metadata-path "$D/global-metadata.dat" \
  --force-unity-version 2022.3.62f2 --output-to "$D/out" \
  --output-as diffable-cs --use-processor attributeinjector,stablenamer
```

产物（253 MB IsilDump + DiffableCs）留在临时目录，未收编进仓库。
