# OpenBachelorS —— 明日方舟本地服务器模拟（外部项目参考）
> 主题：**04A 取数 / 解包流程**（本域按主题的虚拟分组，索引见 `04/00_目录.md §三之二`；文件路径未变）
> 层级：**T2（数据/流程整理类（未含强代码证据））**　建立日期：2026-09-13（头部 6 行内日期）　任务：—　来源：GitHub `pfyy/OpenBachelorS`（用户「晶晶」提供），2026-09-13 克隆至 `code/e　｜　**头部为 2…

> 来源：GitHub `pfyy/OpenBachelorS`（用户「晶晶」提供），2026-09-13 克隆至 `code/external/OpenBachelorS/`（depth=1）。
> 性质：社区项目（Python 3.12 + Poetry），**明日方舟本地服务器模拟**（README 自称 "For PvZ Online" 实为掩人耳目；源码 bp_* 全部为方舟协议）。31 stars，2026-01 创建，2026-09-12 更新。
> 版本：客户端 **2.7.71**、resVersion 26-09-09、funcVer V070、当期危机合约赛季 `crisis_v2_season_5_1`（`conf/version.json`）。
> 核验状态：T2（社区实现可信，未逐项代码核验）；本项目为**独立第三方实现**，非官方。

## 1. 项目能提供的知识（对本知识库的价值）

| 价值 | 内容 | 位置 |
|---|---|---|
| ⭐⭐⭐ **游戏资源表完整清单与本地读取路径** | `res/excel/` 下的表名全集（character/stage/enemy_handbook/crisis_v2/roguelike_topic/climb_tower/sandbox_perm/activity/skin/charword/uniequip/building/gacha/campaign/medal/story 等） | `src/openbachelors/const/filepath.py` |
| ⭐⭐⭐ **作战回放（Battle Replay）机制** | 回放按 `sav/replay/{encode_stage_id}.json` 存储（文件或 DB 两实现）；`encode_stage_id/decode_stage_id/encode_battle_replay/decode_battle_replay` 在 `util/helper.py` | `util/battle_replay_manager.py` |
| ⭐⭐ **协议层实现** | 各业务路由处理器 `bp_*.py`：账号/干员/培养/抽卡/基建/危机合约(crisisV2)/肉鸽(rlv2)/生息演算(sandboxPerm)/卫戍协议(tower)/活动/剧情/商店/邮件/社交 | `src/openbachelors/bp/` |
| ⭐⭐ **资源获取途径** | `tool/asset_downloader.py`（aria2c 多线程）+ `tool/version_updater.py` + `tool/res_locker.py`；版本清单 `conf/version*.json` | `src/openbachelors/tool/` |
| ⭐ **战斗日志/回放工具** | `util/battle_log_logger.py`、`util/battle_replay_manager.py` | `src/openbachelors/util/` |
| ⭐ **时间控制** | `util/faketime.py`（活动/卡池时间模拟） | 同上 |
| ⭐ 区服支持 | `const/region.py`（CN/EN 等）；`bp_u8.py`（U8 SDK）、`bp_yostar.py`（悠星） | `src/openbachelors/` |
| ⭐ 调试控制台 | OBS Console 运行时改玩家数据（如 `char char_1035_wisdel --level 1`）；干员 ID 格式 `char_XXXX_name` 与 gamedata 一致 | `doc/how_to_use_console.md` |

## 2. 对模拟还原的意义

1. **关卡数据权威入口**：`res/excel/stage_table.json` = 关卡配置（地图/波次/敌人），可由 `asset_downloader` 按版本下载 —— 与 ArknightsGameData 同源但**按客户端版本直取**，比等 GitHub 更新更快。
2. **战斗回放格式**：客户端上传的实战回放（含操作序列/帧数据）——是"局内战斗如何按数据推演"的**实证样本**，可与我们的 sim 对照。
3. **协议理解**：bp_rlv2/bp_crisisV2/bp_tower 等给出各模式**服务器侧的关卡与进度数据结构**，帮助理解模式参数（如合约 tag、肉鸽节点）。
4. 合规提示：此项目为第三方服务器模拟，**仅作学习参考**；我们仍遵守客户端合规准则（不改原客户端、数据优先 ArknightsGameData/本地备份）。

## 3. 待办（可选深入）

- [ ] 读 `util/helper.py` 中回放编解码实现，整理回放数据格式（→ knowledge/02 或 04）
- [ ] 用 `asset_downloader` 逻辑提取 `stage_table.json` 对照 data/gamedata_akgd（建立关卡数据标准获取流程）
- [ ] 从 bp_rlv2/bp_crisisV2/bp_tower 提取模式参数结构（补充 knowledge/00 模式常识）
