# 本地游戏资源地图：MAA 与 prts+（赛博塑料）

> 主理人提示：这两个程序的 resource 主要用于**图像识别/名称对照**，不含 buff_template 数值机制
> （已实测确认无 buff_template/attributeModifiers/blackboard 关键词）。但其中两类数据对模拟计算有价值：
> ① 干员/敌人 ID 与名称对照（含攻击范围坐标）；② 关卡格子坐标（Arknights-Tile-Pos）。

## 1. MAA（MaaAssistantArknights）—— `D:\__soft\MAA\resource\`

| 文件/目录 | 用途 | 对我们的价值 |
|---|---|---|
| `battle_data.json`（683KB） | 干员 ID↔多语言名（中/英/日/韩/繁）+ 职业/位置/稀有度/rangeId；`ranges` 攻击范围坐标表（73 条） | ⭐⭐ 干员权威对照（1370 条）+ 攻击范围坐标（伤害计算用） |
| `stages.json`（808KB） | 617 个关卡：AP 消耗、code、掉落表 | ⭐ 掉落/关卡索引 |
| `item_index.json` | 物品 ID↔名称 | ⭐ 物品对照 |
| `recruitment.json` | 公招池数据 | 低 |
| `infrast.json` | 基建数据 | 低 |
| `version.json` | 当期活动/卡池/资源更新时间 | 低（可判断资源新旧） |
| `Arknights-Tile-Pos/`（4177 关） | **每关格子地图**：code/name/height/tiles[]（buildableType/heightType/isEnd/isStart/tileKey） | ⭐⭐⭐ 关卡内地图数据（地图/寻路模拟基础） |
| `tasks/`、`template/` | 图像识别任务与模板（OCR 用） | 低（识别用） |
| `roguelike/` | 肉鸽各主题的识别资源 | 低 |
| `copilot/` | 作业 JSON（关卡操作序列） | 中（可参考关卡配置） |
| `onnx/` | 图像识别模型 | 低 |
| `global/` | 外服差异化资源 | 低 |

## 2. prts+（赛博塑料）—— `D:\__soft\ak\prts+\_internal\resource\`

| 文件 | 用途 | 价值 |
|---|---|---|
| `battle_data.json`（397KB） | 干员对照（同 MAA 类型，版本略旧） | ⭐ |
| `level_code_mapping.json` / `level_name_mapping.json` | 关卡代码↔名称/关卡 ID 对照 | ⭐⭐（关卡 ID 解析） |
| `operator_mapping.json` | 干员图像识别映射 | ⭐（干员名↔头像） |
| `avatar_26_1_27.zip`（84MB）+ `avatar/`（1645）| 干员/敌人头像图 | 低（识图） |
| `map/`（3480）、`resource.zip`（170MB） | 地图/头像图包 | 低 |

## 3. 更新方式（主理人要求记住）

- **MAA 资源更新**：走 MAA 官方源 `https://api.maa.plus/MaaAssistantArknights/api/...`（国内可直连，非 GitHub）。
  参考：`D:\__soft\MAA\cache\etag.json` / `last_modified.json` 记录了已用的更新端点；MAA.Updater.exe 负责更新。
- **prts+ 更新**：GitHub 仓库（需镜像，见下）。
- **游戏数据（Kengxxiao/ArknightsGameData）**：GitHub，见下载策略。

## 4. 下载策略备忘（主理人无梯子，GitHub 优先镜像）

1. **优先本地**：先查 MAA/prts+ resource 是否已有；更新走 maa.plus 源。
2. **GitHub 小文件（<1MB）**：`raw.githubusercontent.com` 单请求可行。
3. **GitHub 大文件**：`raw.githubusercontent.com` 单连接易断 → 用 `ak/scripts/download_parallel.py`（6 线程 1MB 分块）；
   或 `api.github.com` + `Accept: application/vnd.github.raw+json`（偶尔能整下）。
4. **镜像备选**：jsDelivr（单文件限 20MB）、gh-proxy.com / ghfast.top（不稳定）。
5. **大文件多次失败**：及时告知主理人，由主理人决定是否用梯子。

## 5. 已知教训

- `chiave` = **贾维**（Chiave，5★先锋）—— 干员 ID 对照以 `battle_data.json` / PRTS 为准，勿凭印象。
- 关卡内地图数据（格子）在 MAA `Arknights-Tile-Pos/`，而非舟数据的"黑流树海地图构造"（那是肉鸽关卡连接关系）。

## 6. 游戏客户端资源结构（只读摸底，2026-08-31）

> 合规提示：见 `docs/合规声明_游戏客户端.md` —— 客户端仅可只读**资源文件**，其余禁止；非必要不触碰。

- 国服客户端：`D:\__soft\Arknights\`；日服：`D:\YostarGames\Arknights_JP\`
- `Arknights_Data\`（Unity 标准布局）：`il2cpp_data/`（游戏逻辑原生代码，**未授权不读**）、
  `globalgamemanagers`、`level0~13`、`resources.assets`、`sharedassets*.assets`（+`.resS`）—— 主资源文件
- **`Arknights_Data\StreamingAssets\AB\`：AssetBundle 资源目录**（干员模型/prefab/贴图/特效等）
  —— GameObject/组件层面数据的来源，对应调零说的「arknights assets studio 特供版」读取对象
- 说明：gamedata 数值表（buff/干员/技能/敌人）已全部优先从 ArknightsGameData 获取（`ak\_raw\gamedata\`）；
  客户端资源仅在做组件层面比对时按需只读。
