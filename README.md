# 明日方舟解包与模拟知识库（ak）

> ⚠️ **客户端合规准则（用户 2026-08-31 郑重声明）**：禁止读取游戏客户端除资源文件外的任何数据；禁止修改客户端任何数据；数据优先经 ArknightsGameData；非必要不触碰客户端。详见 `meta/合规声明_游戏客户端.md`。

> ⚠️ **自动打图 / 账号合规准则（用户 2026-09-14 声明，与上条同等重要）**：登录须**逐次**获用户同意且仅限指定账号，
> 禁止使用登录界面未保存的账号；**禁止动用除「理智」外的任何账号资源**，禁止打开仓库/基建/抽卡/商店等界面（误触立即退出）；
> 练度或模组不匹配时**禁止自行提升**，须请示用户换号或提供助战；顶号/断线后重新登录需**再次同意**。
> 详见 `meta/合规声明_自动打图与账号.md`。

> 工作区：`C:\Users\23922\Documents\ds_harness\ak` ｜ E 盘镜像/数据仓库：`E:\__file\ak_kb\`（会话优先访问）
> 用途：学习解包知识拆解《明日方舟》→ 建立游戏机制知识库 → 编程模拟还原特定游戏情景 → 支持计算与寻找解法。

## 目录结构（分层架构，2026-09-02 重构）

| 层 | 目录 | 内容 | 使用者 |
|---|---|---|---|
| ① 知识层 | `knowledge/` | **文本知识唯一权威源**（仿 PRTS 领域分类，条目含来源+核验状态） | AI 与用户 |
| ② 数据层 | `data/` | 结构化数据（按来源分目录 + manifest）：gamedata_akgd / gamedata_client / derived | 模拟器/核验 |
| ③ 代码层 | `code/` | tools（跨会话工具脚本）/ unpack（解包解析）/ sim（模拟源码） | AI |
| ④ 模拟层 | `sim/` | draft（搭建中）/ testing（测试中）/ reference（已核验参考） | AI |
| ⑤ 元知识层 | `meta/` | 解包经验 / 搭建经验 / 流程规范 / 合规声明（与游戏知识无关） | AI 复用 |
| 组合知识层 | `composed/` | **T3 组合/推导知识**（所有执行者可写，保留来源链+假设，非权威） | 执行 agent |
| ⑥ 原始素材 | `raw/` | 互联网抓取原始存档（去冗余后仅保留文本/必要文件）：prts/bilibili/zhoudata/client_res | 证据源 |
| ⑦ Skill | `skill/` | AI 快速上手提示词（由 knowledge/ 派生，定期生成） | 任意 AI 会话 |

> 旧目录（notes/_raw/scripts/docs/data/operators）为迁移前结构，内容已复制到新层，**待去冗余清理**（走 trash 流程）。

## knowledge/ 导航（仿 PRTS 领域）

见 `knowledge/README.md`（00 游戏总览 / 01 基础数据 / 02 作战机制 / 03 外部学习 / 04 数据对应与核验 / 05 舟数据）。

## 关键约定

1. **来源标注**：外部内容（PRTS/B站/本地文件）简单比对无误 → 注明出处入 knowledge；核验状态三档（✅解包验证 / 🟡待核验 K-### / 🔴需IDA）；见 `meta/流程规范.md`。
2. **信度分层与写权限**：T1（✅代码验证）/T2（🟡高信度社区）/T3（❌组合推导）；**knowledge/ 仅主会话与解包程序可改**；组合知识写 `composed/`（所有执行者可写，格式见 composed/README）。
3. **数据来源**：本地可取的（gamedata_client）优先于远程 ArknightsGameData；manifest 记录来源。
4. **模拟环境**：引用知识需在环境 README 注明 knowledge 条目；按成熟度放 sim/draft|testing|reference。
5. **基建**：仅了解、非模拟重点（用户定）。
6. **跨会话**：任意会话可复用 `code/tools/` 全部工具与 `meta/` 经验；任务登记见 `management/tasks_registry.md`。

## 学习内容速览（截至 2026-09-02）

- PRTS 全文体系（新人入门/游戏数据基础/作战机制 + 23 子页面 + 75 干员页）→ knowledge/00/01/02
- ArknightsGameData 数据（character/skill/buff/enemy_handbook）→ data/gamedata_akgd；客户端资源只读备份 → raw/client_res（另有 E 盘 ak_kb）
- 客户端解包验证：碰撞半径全表、buff 模板 AB、组件层闭环 → knowledge/04
- B 站机制学习：等灯等灯（26 篇）/ 神祇读神奇（9 篇+10 场录播）/ 调零（2 篇）→ knowledge/03（100+ 可量化规则）
- 舟数据（用户本地）比对 → knowledge/05
- 待解包核验清单：K-001~024 → knowledge/04/23
- **外部数据源导航**（PRTS/特米米/露托/PRTS_map/少人wiki + 与解包对比）→ data/数据源导航.md
- **游戏模式与极限玩法常识**（来源=用户，待确认）→ knowledge/00_游戏总览/游戏模式与极限玩法.md

## 仓库收录范围（Public 仓库）

本仓库是 `ak` 工作区的**公开发布子集**，收录原则为「文本知识 / 源码 / 结构化数据 / 文字证据」：

| 收录 | 说明 |
|---|---|
| `knowledge/` `meta/` `composed/` `glossary/` `axis/` `skill/` `docs/` | 知识库、元知识与流程规范、组合推导区、词表、共用轴表 |
| `sim/` `code/` `scripts/` | 模拟环境源码、解包与识别工具、抓取脚本 |
| `data/` `raw/` `_raw/` | 结构化数据与互联网原始文字存档（不含聊天记录） |
| `.tmp/` 下的 `*.py`、`*.md`、`*.txt`、`*.json` 等 | 会话过程脚本（截图、录像等中间产物不入库） |

**不入库**（体积或隐私原因；完整副本保留在本地工作区与 `E:\__file\ak_kb\`）：

- 截图与录像（`.tmp/*.png`、`.tmp/*.mp4`，合计数 GB）
- 第三方克隆与源码：`code/external/OpenBachelorS`、`sqlcipher*`
- Python 虚拟环境 `.venv/`
- **QQ 聊天记录导出**（`scripts/output/`、`code/tools/output/`、`_raw/qq/`）
- 二进制办公文档（`*.xlsb` / `*.xlsx`；其文本转储保留在 `raw/zhoudata/dump/`）

**脱敏说明**：发布前已把个人标识（账号尾号、游戏 UID、本机 QQ 号、玩家名）统一替换为 `****`；原始文本备份留在本地 `.tmp/preredact_backup/`（不入库）。

## 数据来源与版权

- 游戏数据（`data/gamedata_akgd/`、`_raw/gamedata/`）来自公开数据仓库 **ArknightsGameData**（<https://github.com/Kengxxiao/ArknightsGameData>）与本机客户端**只读**备份；版权归 **上海鹰角网络（Hypergryph）** 所有，本仓库仅作学习研究用途，**不得商用**。
- 社区资料（`knowledge/03_外部学习/`、`raw/bilibili/`）版权归原作者，正文已标注出处与链接。
- 本仓库**代码**以 MIT 许可发布（见 `LICENSE`）；上述第三方数据与资料**不适用**该许可。
