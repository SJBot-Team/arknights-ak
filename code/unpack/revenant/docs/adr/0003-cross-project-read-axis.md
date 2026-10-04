# `lint` 长出仓库根与机读输出，终态词汇脱离扩展门控；Workspace 不回来

ADR-0002 删掉 Workspace 时记过一条观察：「没有任何项目建过 ledger、pack、fingerprint 或 workspace 标记」。这条至今成立——第一份真实的领域包仍然不存在，没有人跑过 `scan`。但 `merge-games-re` 在 2026-08 手工造了一个**别的**东西：`_tools/econ-loop/`，九款 × 十维 = 90 格的覆盖矩阵，外加每维一份跨游戏汇总，261 行传感器 + 181 行控制器 + 112 行阻尼器 + 一份 `matrix.yaml`。它的单位是 **note**，不是 scan cell；pack、probe、slot、cell 一个都没用。目前五维已满（`econ-cross-01` 到 `05`，53 篇 note）。

我们决定承认「跨项目、以 note 为单位的读取」是一条真实的轴，并且只给它最小的骨头：`revenant lint` 加 `--json` 与 `--repo`，四态终态词汇从扩展门控里挪到常开的一半。**不复活 `workspace` 命令，不解冻广度扫描族，矩阵的定义仍然留在项目里。**

## ADR-0002 哪一条变了

**没变的**：Workspace 的前提（多个项目跑 scan、内置 pack 有人维护、两次目击才提拔）一条都不成立。它是建立在扫描族之上的第二层假设，扫描族仍然冻着，删除与冻结都继续有效。`merge-games-re` 仍然只是普通的一层目录，不是术语意义上的 Workspace。

**变了的**：ADR-0002 隐含假设「跨项目的视图没人需要」。这条被证伪了——需要它的人自己造了一个。造出来的东西与被删掉的 Workspace 不是同一件事，所以不能用「Workspace 回来了」来读这份 ADR。

## 它重造了 revenant 已经有的两样东西

**一、lint 的结构检查，靠正则刮人读输出。** `_tools/econ-loop/sensor.py:108`：

```python
line_re = re.compile(r"^\s+(error|warning)\s+(\S+)\s+(\S+?):(\d+)")
```

`revenant lint` 只有格式化过的 stdout，没有机读形式，所以传感器只能刮。而且它要按项目 `subprocess` 循环调（`sensor.py:110`），因为没有任何工作区层面的入口。`lint` 内部其实早就是结构化的——`LintReport` 与 `Finding(path, line, severity, rule, message)` 都是 dataclass，缺的只是第二个渲染器。

**二、终态词汇，而且是 lossy 的。** econ-loop 只有 `filled` / `partial` / `unavailable` 三态；revenant 有四态（已填且达标 / 已填但证据不够 / 查过确认不存在 / 证据够不到）加 `input_missing` / `output_doubtful` 两种够不到的来源，加 `server_side` 等缺口标记。

三态的代价在 `econ-cross-05` 里能直接看到：Travel Town 的订单系统整个由服务端持有，Merge Cooking 与 Mystery Town 是 Luban 配置未提取——两者都被记成 `unavailable`，但补救完全不同。用四态写，前者是「证据够不到 + `server_side`」，补不了；后者是「证据够不到 + `input_missing`」，而 `input_missing` 的定义本来就是「补上输入后应当自动回队」——Luban reader 落地那天，那些格子自己重新排队。混成一态就看不出这个差别，而这正是回路要靠状态来调度的地方。

## 决定的三件事

**一、`lint --json`。** 一个结构两个渲染器：`LintReport` 加一个 `as_json()`，`format_report()` 不动。**不写第二个格式化器**——两份输出各自漂是必然的，#37 已经用生成文件教过一次。JSON 里除了 findings，还带每篇 note 声明的终态（有标记时），因为那是事实不是检查结果。

**二、`lint --repo`。** 扫仓库根以下的每个项目。上界复用 #51 那条：走到含 `.git` 的那一层为止，找不到 `.git` 就只有本项目。**与 harness 查找同一条规矩**——revenant 里「上一级」只能有一种含义，两套边界规则比没有边界更糟。这条规矩因此从 `describe` 挪进 `config`，两个特性共读一份，而不是一个特性伸手去够另一个特性的私有函数。

**三、终态词汇脱离扩展门控。** `describe.collect_methodology()` 现在把 `cell_states` / `reach_sources` / `gap_markers` 关在 `with_extension` 后面，把这三样挪到常开的一半，**`facets` 留在门后**。

这不是给扫描族加功能，理由有两条。其一，这套词汇一直住在 `methodology.py`，不在 `ledger.py` 也不在 `scan.py`——它在共享层已经很久了，被门控的只是它的曝光。其二，四态回答的是「关于这个问题我们知道什么」，这件事与问题来自 pack 槽位还是来自一篇 note 无关；Cell 只是它的一种载体。Facet 不同——「固定六段作答」是 pack 机制本身，留在门后是对的。

`CONTEXT.md` 里四态目前写在 **Cell** 词条下、「广度扫描（冻结中）」一节里，要把它提到共享层，Cell 词条改为引用它。

## 边界：什么留在项目里

按「不含游戏事实」这条线切：

- **留项目**：有哪些维度、有哪些游戏、每一格算不算完成的判据、控制器的优先级顺序、阻尼器的基线策略。这些是「我们选择研究什么、怎么排班」的事实，与 revenant 无关。`matrix.yaml` 不进 revenant。
- **进 revenant**：note 里的终态标记怎么读、结构怎么校验、跨项目怎么汇总。都是机制。

判据是老的那条：换一个完全不同的题目（不做经济系统，做反作弊），revenant 这一侧一行都不用改，项目那一侧整份 `matrix.yaml` 要重写。

## 标记格式与迁移

econ-loop 用的是 `<!-- econ-cell: game=X dim=01 status=filled -->`。revenant 认一个通用形式，状态取四态词汇。代价要写清楚：**53 篇 note 的标记要改一次**（sed 级），传感器的四项结构校验里有三项可以直接删掉（标记存在、标记与路径一致、有「## 数据来源」节），只剩「数值摘要表」那一项是它自己的。

不做兼容层。两种标记并存的那一天起，「哪个是权威」就没有答案了。

## Considered Options

- **复活 `workspace` 命令**。它的前提仍然不成立，而且它绑在扫描族上——复活它等于从后门解冻。真实需求是「读」，不是「提拔候选」。
- **只加 `--json`，其余不动**。能让传感器不刮 stdout，但它仍要按项目循环，仍要维护第二套三态词汇。修了最浅的一刀。
- **把维度矩阵放进 revenant**。九款十维是这一轮研究的事实，进了 revenant 就是把游戏事实写进工具，正是 #47 / #50 两轮反复划掉的线。
- **给 note 定义第二套状态词汇**。传感器自己的设计文档里就写着「与仓库既有的 `revenant lint` 规则同源，不引入第二套标准」——它已经知道这是坏主意，只是当时没有第一套可用。

## Consequences

- 传感器缩水：正则刮 stdout 那段与三项结构校验删掉，`subprocess` 循环换成一次 `lint --repo --json`。控制器与阻尼器不受影响。
- 53 篇 note 的标记迁移一次，一次性成本。
- `describe` 的 JSON 与渲染的 skill 会多出三段词汇。**skill 行数会涨，而 ADR-0002 的 80 行代理已经在 161 行报警。**这是本决策最实在的代价，接受它的理由是代理是告警不是闸（ADR-0002 明文），而写 note 的 agent 需要知道用哪几个状态才能写出标记。涨多少要在实现时量，不预估。
- 命令数不变。按 `CONTEXT.md` 的规矩，新增本应落 query 层；这里连新增都没有，只是给一条核心命令加两个开关。
- 广度扫描族的解冻条件不变：**第一份真实的领域包被写出来并在至少一款游戏上跑过。**本 ADR 不构成解冻，也不为解冻加分。
- 本 ADR 只处理跨项目读取这一条轴。经济分析暴露的另外五个缺口（Luban 解码器、配置表查询面、字段名归一化、FlatBuffers 批量路径与多态盲区、配置表引用计数）属于 query 层的增补，各自单开，不在这里定。
