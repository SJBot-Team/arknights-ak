# data/ —— 数据层（结构化数据，按来源分目录）

> 数据文件按来源分目录存放，**不混放**；每目录带 manifest（来源、获取日期、版本、校验和）。
> 本地备份/解包验证过的数据（`gamedata_client/`）优先于 ArknightsGameData（`gamedata_akgd/`）——能本地取到的不再依赖远程。
> 衍生表（`derived/`）为整理产物，注明来源数据。

## 目录

| 目录 | 来源 | 内容 | manifest |
|---|---|---|---|
| `gamedata_akgd/` | ArknightsGameData（GitHub） | character/skill/buff/enemy_handbook 等原始表 | 待建 |
| `gamedata_client/` | 客户端解包验证 | 从客户端资源提取并经核验的数据（碰撞半径等） | 待建 |
| `derived/` | 衍生整理 | UOEP 全干员表 CSV 等 | 待建 |

## manifest 格式（每个数据目录内 `manifest.json` 或 `来源.md`）

```json
{
  "来源": "ArknightsGameData (github.com/Kengxxiao/ArknightsGameData)",
  "获取日期": "2026-08-31",
  "版本": "zh_CN 2026-08-18",
  "校验和": "sha256: ...",
  "说明": "character_table.json 等"
}
```
