# 收窄到最小集合：核心 / 查询 / 扩展 / 删除四层，广度扫描族冻结

Revenant 长到 44 条命令、11 个领域术语时，唯一的真实用户（`merge-games-re`，八个项目、22 篇 note、三份跨游戏研究）实际只用过 5 条命令（`prepare` `import-metadata` `lua-extract` `status` `patch-binary`）和 1 个 MCP 工具，没有任何项目建过 ledger、pack、fingerprint 或 workspace 标记；真正的工作发生在每款游戏手写的解密代码里，而路线图的下一步（拿到三款游戏的脚本层）是深挖与解密，不是广度扫描。我们决定按「一个没接触过本仓库的人 + Claude Code，从空目录到对第 9 款游戏产出第一篇 note 不超过一天、不读源码」这一判据收窄产品，把命令表分成四层，并**冻结**而非删除广度扫描族。

## 四层

- **核心**（默认可见，14 条）：`init status prepare find-binary find-metadata import-metadata patch-binary lua-extract seed-src fingerprint dig lint describe help`。
- **查询**（`help --all` 才列；agent 走 MCP，CLI 版给人和脚本）：`disasm evidence lookup search xrefs callgraph find-asm cfg field-scan metadata-info lua-list lua-get lua-grep lua-refs lua-bridge list-bundles extract-scenes`。
- **扩展**（`[packs] enabled` 非空时才出现在命令表与 skill）：`packs probe cell ledger scan naming-stats`。
- **删除**：`workspace narrow baseline`；`build-indices run-cpp2il ls-apk extract-apks` 并入 `prepare --only <step>`。

代理指标（skill 不超过 80 行、默认命令不超过 15 条、术语不超过 6 个）只在 `status` 里报警，不作为闸——这张地图已经两次撤回过用代理变量做闸的决定。

## 族级处置及理由

**广度扫描族冻结**（Domain pack / Slot / Facet / Cell / Probe / Ledger；`scan probe cell ledger packs naming-stats`）。这一族在 #1 地图上经过八张票的 grilling、已实现并有 139 个测试，但它成立的前提——「一份 24 槽位的领域包反复用在多款游戏上」——至今没有第一份真实的包。没有包，六个术语对使用者只是负担；删掉则等于作废经过审议的决定。所以等证据：代码与术语保留，默认不渲染，在第一份真实 pack 出现之前**不再往这一族加功能**（事件流与 run id、判断字段的 `via` 来源标记、brief 的 provenance 段、pack 的 schema 与兼容范围、pack 停用语义，五项一并冻结）。届时再决定它回主线还是退役。

**Workspace / Candidate pool / Reflow 删除**。它们的前提（多个项目跑 scan、内置 pack 有人维护、两次目击才提拔）是建立在扫描族之上的第二层假设，一个都不成立。「候选池两次目击」这条规则曾被设计并撤下，原因是没有第一层；代码留在 git 历史。`merge-games-re` 从此就是普通的一层目录，不是术语意义上的 Workspace。

**Fingerprint 降为观察清单**。原实现从写死的标记字符串表推出「这是 HybridCLR / 是 xLua」并把结论用作 `scan` 的硬闸；加固厂抹掉一个字符串，闸就朝危险方向失效（放行一次全零命中的扫描）。同源打分的权重与路径排序规则是在看过 8 款游戏结果之后调出来的，是过拟合。改为只输出观察：引擎版本、构建路径、清单声明的程序集与 metadata 的差集、`.bytes` 字面量（路线图第 6 条实测比清单差集可靠）、原生库导出符号。判定与同源由 agent 读观察后作出。`narrow` 与 `baseline` 随之删除。

**Dig 只留开与收**。`open`（业务问题 + 完成判据 + 入口线索）与 `converge`（逐条勾判据、每个候选交代去向）是深挖的价值所在；`tick / round / queue` 与停滞检测依赖一个「每轮 tick」的无人值守循环，那个循环没人搭。停滞检测「看进展不看花费」的设计是对的，有循环时再回来。

**四条斜杠命令保留但纳入漂移守卫**。`re-scaffold / re-deep / re-verify` 是复原主线，`re-map` 是唯一真被用过的广度动作的形状（人驱动、不接 scan）。发现时四条全部在教已废止的词汇（`T1` `T3` `(confirmed)` `// Progress:`），与 #25 同病；保留的前提是它们与 skill 受同一套守卫。

**`lint` 保留并修**。27 篇真实 note 上 23 个误报（`## 来源` 标题不认、`[Lua坐实]` 等别名不认），但「引用的 RVA 真的存在」是唯一能机械抓到瞎编地址的手段。

**不做钩子注册表**。`[metadata] decryptor` 钩子已覆盖 `merge-games-re` 的全部真实需求（cdph、unidbg 都是解密器）；新包格式出现之前不需要 layouts / image 注册表。

## Considered Options

- **删除扫描族**：最干净，但作废八张经过审议的决定，且下次要重新吵一遍词。
- **保留全部在主线**：违反判据；一个新人面对 44 条命令与 11 个词，第一天不可能产出 note。
- **把冻结族挪到单独的 CONTEXT 文件**：为一个冻结的东西开第二个 context，不值。

## Consequences

- `revenant describe` 与生成的 skill 只渲染核心 + 已启用扩展；`merge-games-re` 八个项目需各跑一次 `describe --render claude`。
- 上一轮审视 harness 时议定的 10 张票，只开 4 张（评估文档 + 本 ADR、fingerprint 观察化、lint 修、渲染器拆分 + 命令模板守卫），5 张随扫描族冻结，1 张（钩子注册表）不开。
- 解冻条件写死为一件事：**第一份真实的领域包被写出来并在至少一款游戏上跑过**。不是「有时间了」。
