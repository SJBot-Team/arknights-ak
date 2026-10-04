# gamedata_akgd 数据来源记录（manifest）

> 目录内为「ArknightsGameData 原始表」+ 少量「社区解包补充表」（2026-09-02 起，
> 因 ArknightsGameData 不含 enemy_database/range 关卡表，补充表来自 tomimi-dev 仓库镜像，
> 见下「补充来源」）。

```json
{
  "来源": "ArknightsGameData (github.com/Kengxxiao/ArknightsGameData)",
  "获取日期": "2026-08-31",
  "版本": "zh_CN（2026-08-18 版）",
  "获取方式": "ak/code/tools/download_parallel.py（6 路并行 1MB 分块下载）",
  "文件": {
    "character_table.json": "干员/单位数据（属性阶段/天赋/技能引用，1368 条目）",
    "skill_table.json": "技能数据（倍率/sp/描述）",
    "buff_template_data.json": "buff 模板（8314 模板，事件-动作模型）",
    "buff_table.json": "buff 索引",
    "enemy_handbook_table.json": "敌人图鉴数据",
    "gamedata_const.json": "游戏常量"
  },
  "核验": "与 PRTS 干员页三方比对一致（安洁莉娜/陈/阿米娅属性，见 knowledge/04/15）",
  "备注": "本地解包验证数据优先（data/gamedata_client/），本目录为远程源备份"
}
```

## 补充来源（2026-09-02，T-026）

**ArknightsGameData excel 58 表不含 `enemy_database.json`（敌人逐级数值）与 `range_table.json`（攻击范围）
——经查 Kengxxiao 主仓及 fork（b331z3bub）均无。敌人逐级数值/攻击形式来自社区解包镜像：**

| 文件 | 来源 | 获取方式 | 内容 |
|---|---|---|---|
| `enemy_database.json` | tomimi-dev（github.com/tanch-p/tomimi-dev）`src/lib/data/enemy/` | jsDelivr CDN 直下（raw.githubusercontent 断连） | 1718 敌人逐级数值：hp/atk/def/res/aspd/range/weight/ms + forms（攻击类型/免疫/抗性） |
| `enemy_skills.json` | 同上 | jsDelivr CDN | 敌人技能定义 |
| `range_table.json` | 同上 | jsDelivr CDN | 攻击范围形状表（rangeId → 坐标集） |

核验：源石虫 enemy_1007_slime 级别0 = 550HP/130ATK/0DEF/1.7s 攻击间隔/重量 0，
级别1 = 2050HP/300ATK，与 PRTS 敌人页「源石虫」级别0/1 完全一致（2026-09-02 抓取比对，见 knowledge/04/26）。

> 注：上述三表原文件与 E 盘仓库 `E:\__file\ak_kb\gamedata\` 同步镜像。

## 版本更新（2026-09-04，T-028/030）

**主仓更新至 Data 26-09-03 / Client 2.7.71（commit cc5bf84）**：已抓取并替换为权威版
（原文件存 `E:\__file\ak_kb\gamedata\latest\`，工作区与 kb 已同步）：

| 文件 | 说明 | 获取方式 |
|---|---|---|
| character_table.json | 1373 干员（含结城理等 5 联动） | download_parallel 分块（raw.githubusercontent+commit sha） |
| skill_table.json | 1810 技能 | 同上 |
| token_table.json | 4 条（陷阱，无干员关联 token） | curl 直下 |
| uniequip_table.json | 7 条增量（无结城理模组） | git blob API（raw 不稳时用） |
| uniequip_data.json | 增量（charEquip 无 4217） | git blob API |
| char_patch_table.json | 增量补丁（无 4217） | git blob API |

> 客户端 anon/*.bin 内同名表经实测为**自定义指针序列化格式（非 FlatBuffers）**——
> OpenArknightsFBS 的 FBS schema 与客户端 anon bin 不匹配（Kengxxiao 用独立工具解析）。
> 主仓 JSON 与本地 prefab/buff 键名互证一致，无需逆向 anon bin。

