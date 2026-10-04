# 绑定 Claude Code 作为唯一 harness，放弃 harness/model 无关性

Revenant 原本把 Reasonix + deepseek-pro 作为默认 agent，`revenant init` 会铺 `reasonix.toml`（含 provider、`[permissions]`、`[sandbox]`）、`REASONIX.md` 和 `.reasonix/` 下的技能与命令。我们决定删掉这条路，`init` 只生成 Claude Code 的落地物（`CLAUDE.md`、`.claude/skills/re/`、`.claude/commands/re-*.md`、`.claude/settings.json`），并接受由此带来的 harness 锁定。

理由是**生态而非模型**：deepseek 那条路上缺少成熟的 agentic 基建——技能自动加载、斜杠命令、权限模型、sandbox 都得自己造，`reasonix.toml` 里那套 `[permissions]` 本质上是在重造 Claude Code 已有的能力，维护它的成本换不回等价体验。需要说明的是，这是**工程判断，不是对照实验结论**：我们没有做过 deepseek 与头部模型在 ISIL→C# 复原任务上的定量对比，因此本决策不应被引用为"deepseek 模型能力不足"的证据。

## Considered Options

- **多 harness 支持**（`revenant init --harness claude|codex|reasonix`）：保留退路，但要长期维护三套权限/命令映射，而实际只有一个 harness 被日常使用，另外两套是无人测试的死代码。
- **同时做 Claude Code 与 Codex 两个 target**：Codex 侧不做命令与权限、只保 MCP + `AGENTS.md`，收益仍然低于维护成本。MCP server 本身是标准 stdio 协议，Codex 用户可零成本自行接入，无需我们铺文件。

## Consequences

- **权限语义弱化**（有意接受）：Reasonix 的 `write_file=src/*` 是**白名单**——不在名单里就写不了；Claude Code 的 `permissions.allow` 是**免确认**——不在名单里仍可写，只是会弹确认。迁移后 agent 的写入范围实际上从"受限"变成"受提示"，`.claude/settings.json` 只保留 allow（免打扰），不逐条翻译原来的 deny 清单。需要硬约束时应另找兜底手段（如 git 层）。
- **已存在的项目目录不做自动迁移**：手动删除旧目录里的 `.reasonix/` 和 `reasonix.toml`，重跑 `revenant init` 即可；`init` 只铺文件，不碰 `_apks/ _binaries/ src/ notes/` 等数据目录。
- **对外口径**：README 与 PyPI description 表述为 "driven by any MCP-capable coding agent (ships with Claude Code skills/commands)" —— MCP server 谁都能接，但只有 Claude Code 的定制层由本仓库维护。

## 修订（2026-08-19）：加上 Codex，前提变了一条，判断没变

本 ADR 的标题说「唯一 harness」，现在是两个。变的是一条**前提**，不是那两条判断。

**没变的**：不做 harness 无关的抽象层，不维护多套权限映射。`Renderer` 协议一直在那儿（`describe.py`），加第二个实现不是加抽象层——两个渲染器读同一份 `Description`，方法论只有一份。**Reasonix 不回来**：它被删的理由是生态缺失，那条至今成立。

**变的**：「只有一个 harness 被日常使用，另外两套是无人测试的死代码」。现在有了真实的第二个使用者（外部用户），死代码那条不再成立。

### 当初否决的方案与现在做的，不是同一个

本 ADR 的 Considered Options 里否决过「同时做 Claude Code 与 Codex 两个 target，Codex 侧不做命令与权限、只保 MCP + `AGENTS.md`」，理由是「收益仍然低于维护成本」。那个判断建立在一条**当时没有核实的假设**上：Codex 只有用户级配置，给不了项目级落地物。实测（codex-cli 0.147.0，全程用隔离的 `CODEX_HOME`）**这条假设是错的**：

| 通道 | 项目级 | 零用户配置 | 加载方式 |
|---|---|---|---|
| `.codex/skills/<name>/SKILL.md` | 是 | 是 | 按需——name + description 进 `<skills_instructions>` 目录，正文给文件定位符，选中才读 |
| `AGENTS.md` | 是 | 是 | 常驻——从 git 根往下逐级拼接，深的覆盖浅的；`AGENTS.override.md` 优先；上限 `project_doc_max_bytes`，默认 32 KiB |
| `.codex/config.toml` 的 `[mcp_servers.*]` | 是 | **否** | 需仓库授信 |
| 自定义 prompt（斜杠命令） | **否** | — | 只有 `~/.codex/prompts/` |

`.codex/skills/` 是 Claude skill 的**直接对等物**，不是折中——同样的 name + description 按需模型。所以否决时设想的「只保 MCP + AGENTS.md」那个残缺形态，根本不是现在要做的东西。

`AGENTS.md` 沿目录树上溯这一条，让 #51 那个「仓库根一份服务九个子项目」的布局在 Codex 上照样成立。

### 一个让代价大幅下降的事实

**生成物是项目无关的。** 实测：六个命令带不带项目上下文都逐字节相同；skill 也一样（11,531 字节，零行差异）。原因是 `desc.project` 在 `_skill_markdown` 里只喂一件事——`with_extension`，即有没有启用领域包，而领域包按 ADR-0002 是冻结的、至今一份不存在。

所以「每个项目渲染一份」是 Claude Code 文件查找规则的产物，不是内容的需要。第二个 harness 因此不带来第二份内容要维护。

### 决定的四件事

**一、`init` 两套都铺，不加 `--harness` 开关。** 本 ADR 否决 `--harness` 的理由是「维护三套权限映射」，而现在的形状不是那个：Codex 侧连权限映射都不做（见第四条）。开关会长期存在并且需要被记住，两个文本文件只要几 KB。

**二、六个命令在 Codex 上落成六个按需 skill。** 项目级没有 prompt 通道，这是唯一可行的形态。代价写进 `CONTEXT.md` 的 Command 词条：**「入口」那层语义丢了**——人敲 `/re-deep X` 是确定执行，模型按 description 自选是概率性的。

**三、MCP 的授信是人的动作，revenant 只打印指引。** `.codex/config.toml` 要仓库在 `$CODEX_HOME/config.toml` 里被标 `[projects."<路径>"] trust_level = "trusted"` 才生效（未授信时 `codex mcp list` 报「No MCP servers configured」）。授信的语义是「我允许这个仓库启动进程」，工具替用户授信自己方向是反的；这也与 revenant「只写项目目录内」的既有承诺一致。`status` 可以报「配置在但没授信」——那是报告不是代劳。

**四、Codex 侧不铺权限。** `sandbox_mode` / `approval_policy` 并不在项目配置的禁用键里（禁的是 `openai_base_url` / `chatgpt_base_url` / `model_provider(s)` / `notify` / `profile(s)` / `otel` / `apps_mcp_product_sku`），但仍然不做。上面 Consequences 里那条「权限语义弱化（有意接受）」已经吃过一次亏——白名单换成免确认；再铺一套语义不同的声明就是第三种语义。而且它要授信才生效，生成一份默认不生效的权限文件比不生成更容易误导。

### 修订带来的后果

- 漂移守卫两套都查，判据是**文件在不在**（`.claude/skills/re/SKILL.md` 或 `.codex/skills/re/SKILL.md`），不引入「这个项目用哪个 harness」的配置项——那又是一个要记得维护的状态，而文件存在与否是自证的。做法同 `harness_location`：靠找文件，不靠声明。
- `AGENTS.md` 是 Codex 上的 `re-project` 覆盖层（`init` 只在不存在时创建），并且**该进记忆登记表**（ADR-0005）：它常驻且有 32 KiB 硬上限，是「容量本身就是设计约束」的第三个实例。
- **对外口径要改**：README 现在写「shipped skill, slash commands and permissions target **Claude Code**」，需要改成两个 harness 各自支持到什么程度——特别是 Codex 侧没有斜杠命令、没有权限。
