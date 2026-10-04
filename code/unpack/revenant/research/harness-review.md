# Harness 审视：七条方法论对照 Revenant 现状

对照的对象是 revenant 本体加它生成的 skill 合同；运行器（Claude Code / Codex）视为可替换外壳，对话级复放与上下文成本归运行器。审视的直接产物是 ADR-0002（`docs/adr/0002-minimal-set-and-frozen-scan-family.md`）：它记录的是决定，本文记录的是事实与缺口。七条各一段，每段三项：满足了什么、缺什么、证据在哪。凡数字都可以在仓库或 `merge-games-re` 里重新数一遍。

## 0 基线事实

| 事实 | 数值 | 怎么数 |
|---|---|---|
| ADR-0002 之前的 CLI 命令 | 43（ADR-0002 正文写 44） | `feat/self-describe` 分支上 `len(cli.command_table())` |
| ADR-0002 落地后：可分发命令 / 默认可见 / `help --all` | 37 / 14 / 31 | `command_table()`、`visible_commands()`、`visible_commands(show_all=True)` |
| 扩展层（冻结的扫描族）命令 | 6 | `packs probe cell ledger scan naming-stats` |
| 删除的命令 | 7 | `workspace narrow baseline`；`build-indices run-cpp2il ls-apk extract-apks` 并入 `prepare --only` |
| MCP 只读工具 | 18 | `describe.collect_mcp_tools()` |
| CONTEXT.md 主线术语（不含 agent 栈四词与冻结族六词） | 8 | `describe.CORE_TERMS`，测试与 CONTEXT.md 对齐 |
| 测试总数 / 其中冻结族（scan、dig、methodology） | 144 / 64 | `pytest --co` |
| 生成的 skill 行数（未启用 pack） | 120；装了 `harness` extra 时多一张 MCP 工具表，143 | `revenant init` 后 `wc -l .claude/skills/re/SKILL.md` |
| 唯一真实用户 `merge-games-re` | 8 个项目、22 篇项目 note + 7 篇跨游戏文档 | `ls */notes/*.md notes/*.md` |
| note 里出现过的 `revenant` 命令 | 5 条：`prepare` 4、`import-metadata` 4、`lua-extract` 3、`status` 2、`patch-binary` 2 | `git grep -ho "revenant [a-z-]*" -- 'notes/*.md' '*/notes/*.md'` |
| note 里引用过的 MCP 工具 | `re_evidence` 1 次 | 同上，`re_[a-z_]*` |
| 建过 ledger / pack / fingerprint / workspace 标记的项目 | 0 | `find . -name .revenant -o -name ledger` |
| 真正干活的代码 | `_tools/`：`cdph` `cdph-vm` `ifix` `unidbg-metadata`，每款游戏手写的解密与补丁解析 | `ls _tools */_tools` |
| `[metadata] decryptor` 钩子 | 已存在，`config.load_metadata_decryptor()` | `revenant/config.py:261` |
| 四条斜杠命令模板里的退休词汇 | 5 处（`T1` `T3` `(confirmed)` `// Progress:`） | `grep -n "T1\|T3\|(confirmed)\|// Progress" revenant/templates/claude/commands/*.md` |
| `lint` 在 27 篇真实 note 上的误报 | 23 | #29 |

## 1 按能力边界模块化

**满足**：revenant 从不调用模型，运行器在外面——换 model 是零改动；MCP server 只读、与 CLI 共用同一套报告函数（`test_mcp_server_reexports_the_same_reports_not_its_own_logic`）；平台差异（apk / xapk / ipa、ELF / Mach-O）收在 `layout.py` 与 `image.py` 一张表里，`--platform` 切换。

**缺口**：换运行器不是零改动。ADR-0002 只把 skill 的渲染面收窄到核心层加已启用扩展，没有碰渲染器本身：`render_skill()` 是一个函数写死了 Claude 的 front-matter，四条斜杠命令模板不经渲染直接拷贝，且五处退休词汇说明它们不受任何守卫。「运行器可换」目前只是 ADR-0001 的一句话，没有第二个实现来证明接口是干净的。

**证据**：`revenant/describe.py` 的 `render_skill`；`revenant/init.py` `_FILES` 表直接拷贝 `claude/commands/*.md`；退休词汇 5 处见基线表。去处：#30（描述与渲染器拆开，命令模板纳入漂移守卫）；Codex 渲染器留到 ADR-0003。

## 2 组合优先于重写

**满足**：新游戏 = `revenant init` + 放包 + `prepare`，八个 merge 项目就是这么起的；解密差异走 `[metadata] decryptor` 钩子（代码而非配置，理由写在 `config.py:268`）；新领域 = 一份声明式 pack。

**缺口**：新包格式、新镜像格式、新指纹标记表都要改代码。上一轮曾议定要开「格式注册表 / 钩子模块」与「指纹标记改数据文件」两张票；这次审视后按 ADR-0002 **不开**前者（decryptor 钩子已覆盖 `merge-games-re` 全部真实需求：cdph、unidbg 都是解密器，新包格式没出现），后者随 fingerprint 观察化一并处理。真正的组合失败在另一处：这个用户的工作发生在 `_tools/` 里的手写代码，revenant 没有给这类代码一个落点，也不需要——ADR-0002 判定「深挖与解密」是主线，而它本来就是代码。

**证据**：`_tools/` 四个目录 vs 0 个 ledger；`revenant.toml` 里唯一被用到的项目级配置是 `[lua]` 与 `[metadata]`。去处：#28（fingerprint 观察化，标记表随之处理）；钩子注册表按 ADR-0002 明确不开。

## 3 全链路可追溯、可复放

**满足**：ledger 记探针运行（带 `probe_set_hash` 与 `index_version`）、判断、`ran`；`dig converge` 强制每个候选交代去向（`test_converging_requires_every_retrieved_candidate_to_be_accounted_for`）；brief 落盘到 `.revenant/briefs/`；`describe` 与生成的 skill 带版本戳，`status` 报漂移。

**缺口**：没有「这一轮 agent 看到了什么」的事件流；scan 与 dig 不发 run id，判断字段没有 `via` 来源标记，绕开 `revenant cell` 直接改 `ledger/*.json` 不留痕。这三项上一轮议定为三张票（事件流与 run id、`via` 标记、brief provenance），**这次随扫描族一并冻结**：它们要追溯的东西（scan 的每一轮）在没有第一份真实 pack 之前不会发生。dig 保留的两个动作已经各自留痕：`open` 写 `digs.json`，`converge` 写死胡同与 note 引用。

**证据**：`revenant/ledger.py` 的 `FACT_FIELDS` / `JUDGEMENT_FIELDS`；`.revenant/digs.json` 结构见 `dig.DigTask.to_json`；0 个项目建过 ledger，所以事件流今天没有可记的对象。去处：ADR-0002「冻结」段，解冻条件是第一份真实领域包在至少一款游戏上跑过。

## 4 让确定性系统包住不确定性模型

**满足**：判断只能经 `revenant cell` 写入并经校验（非法状态、缺来源维、越过天花板的档位都被拒或警告，`test_illegal_state_is_rejected` 等）；`scan` 不开 socket（`test_scan_calls_no_model`）；`lint` 机械核对「引用的 RVA 真的存在」——这是唯一能抓到瞎编地址的手段；MCP 全部只读（`test_all_mcp_tools_are_readonly`）。

**缺口**：**头号缺口是闸本身建立在推断上。** `fingerprint.decide_corpus()` 从一张写死的标记字符串表推出「这是 HybridCLR / 是 xLua」，`scan` 拿这个结论当硬闸；加固厂抹掉一个字符串，闸就朝危险方向失效——放行一次全零命中的扫描，而零命中会被记成「查过、确认不存在」。同源打分的权重与路径排序是看过 8 款游戏结果之后调出来的。ADR-0002 的处置是把 fingerprint 降为观察清单：只陈述引擎版本、构建路径、清单声明的程序集与 metadata 的差集、`.bytes` 字面量、原生库导出符号，判定与同源由 agent 读观察后作出；`narrow` 与 `baseline` 随之删除。第二个缺口是「墙」：agent 有完整 shell，能绕过门直接编辑 ledger 文件——上一轮定的对策（缺 `via` 视为手写、不计 coverage）随扫描族冻结。第三，dig 原有的停滞检测（看进展不看花费）设计是对的，但它依赖一个没人搭的无人值守循环，这次移除，有循环时再回来。

**证据**：`revenant/fingerprint.py` 的 `decide_corpus` / `same_origin` / `HYBRIDCLR_MARKERS`；`revenant/scan.py` 读 `fp.corpus` 决定是否拒绝；#28 的「抹标记」复现用例。去处：**#28**（fingerprint 降为观察清单，吸收 F18 与「闸改闸事实」票）——这是本文所有缺口里唯一的安全性问题，也是 #27 之后优先级最高的一张。

## 5 上下文是运行时资源

**满足**：skill 是从代码渲染的，命令表、档位、状态、切面各只有一处来源，两条结构守卫（引用的命令必须可分发、退休词汇不得出现）由测试执行；skill 分成「生成的 `re`」与「手写的 `re-project`」两个文件，谁维护什么一眼可见；ADR-0002 之后 skill 只渲染核心层加已启用扩展，未启用 pack 的项目里扫描族六个词与六条命令一处不出现。

**缺口**：skill 仍有 120 行（带 MCP 工具表 143 行），超过 80 行的代理指标（`status` 现在报警，不阻断）——超出的部分是手写的 practice 文本，它没有按「什么时候需要读」分段。brief 各段没有来源与字节数（上一轮的 provenance 票，随扫描族冻结）。四条命令模板不受任何守卫，见第 1 条。

**证据**：`revenant status` 输出 `alarm: skill is 120 lines > 80`（或 143）；`tests/test_describe.py` 两条守卫；`tests/test_command_tiers.py` 的可见性用例。去处：#30 处理命令模板与渲染器；practice 文本分段没有票，等 #30 落地后看 skill 行数再定。

## 6 依赖与生命周期必须显式

**满足**：pack 有 `requires` 边（只警告不阻断，`test_unmet_requires_edge_is_reported_not_enforced`）、版本号、显式的 `enabled` 列表；探针集或索引版本变化会让格子失效（`test_index_version_change_makes_every_cell_stale`）；`prepare` 用完成标记而不是目录存在判断步骤是否做过，`--keep-going` 不把失败洗成绿色。

**缺口**：关掉一个 pack 时它的 ledger 怎么办没有定义；pack.yaml 不声明 schema 版本与兼容的 revenant 范围。两项上一轮各定了做法（ledger 留盘、从统计消失、重启用即恢复；不匹配拒绝加载），这次随扫描族冻结。删除 Workspace / Candidate pool / Reflow 顺带解掉了一个生命周期问题：`reflow.invalidate_for_probe_change` 会跨项目让结论失效，而「哪些项目算一个 workspace」靠一个没人建过的标记文件。

**证据**：`revenant/pack.py` `discover()`（注意：`enabled` 为空时它仍解析内置包，与自己的 docstring「never auto-detected」不一致——这次没有改它，可见性改在 `describe.collect_project` 与 `cli.visible_commands` 上按 `[packs] enabled` 非空判断）；`git log -- revenant/workspace.py revenant/reflow.py` 可找回删掉的代码。去处：ADR-0002「冻结」段（pack schema / 停用语义两张票）。

## 7 开放生态必须配合治理

**满足**：pack 是唯一插件形态，只有内置 `example`，全部经 git 审阅；probe 必须是模式不能是精确类名（`test_probes_must_be_patterns_not_exact_class_names`），这是 pack 能复用到下一款游戏的最低门槛。

**缺口**：没有签名、兼容矩阵、弃用机制。上一轮定的是**生态不开放**——pack 是工作室内部资产，签名与供应链明确列为范围外；这次进一步：在第一份真实的 24 槽位领域包写出来之前，pack 机制整体冻结，不再往上加功能。「治理」今天的形态就是 ADR-0002 里写死的解冻条件：第一份真实的包被写出来并在至少一款游戏上跑过，不是「有时间了」。

**证据**：`revenant/packs/` 只有 `example`；0 个项目启用过 pack；ADR-0002 Consequences 段。去处：无票，等 F22（第一份真实领域包从哪来、在哪款首跑）。

## 8 小结

七条里三条（1、5、7）的缺口都指向同一件事：为一份还没写出来的领域包提前搭了完整的一层，而唯一的真实用户走的是解密与深挖那条线。ADR-0002 的回答是收窄默认可见面而不是删代码：核心 14 条、查询 17 条按需列出、扩展 6 条随 pack 启用、7 条删除。第 4 条的头号缺口（闸建立在推断上）是唯一的安全性问题，去 #28；第 1、5 条的运行器边界去 #30；第 3、6 条的追溯与生命周期随扫描族冻结，条件写死在 ADR-0002。
