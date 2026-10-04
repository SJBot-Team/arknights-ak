# 客户端资源解析：buff 模板 AssetBundle（组件层面）

> 目标：从客户端资源文件（合规只读副本）验证 gamedata 数据，理解 GameObject/组件层面的承载形态。
> 2026-08-31 完成：`buff_template_holder.ab` 成功解包，与 `gamedata\buff_template_data.json` 双源比对一致。

## 1. 工具链（arknights assets studio 生态）

| 工具 | 仓库 | 用途 |
|---|---|---|
| **Ark-Studio**（明日方舟特供版 AssetStudio） | [isHarryh/Ark-Studio](https://github.com/isHarryh/Ark-Studio)（v0 已弃用，新框架在 v1 分支） | 资源库管理 + AB 解包 GUI（浏览对象/预览文本/图片/音频） |
| **Ark-Unpacker**（Ark-Studio 前身，批量解包） | [isHarryh/Ark-Unpacker](https://github.com/isHarryh/Ark-Unpacker)（v5.x） | 批量解包 AB；**解决明日方舟 v2.5.04+ 的自定义 LZ4AK 压缩** |
| UnityPy（Python 库） | pypi `UnityPy` | 程序化解析 Unity 资源（本会话主用） |
| OpenArknightsFBS / Ark-FBS-Py | MooncellWiki / isHarryh | FlatBuffers schema 解码（TextAsset 类数据用） |

## 2. 明日方舟 AB 压缩：LZ4AK（已破解）

- 明日方舟 v2.5.04+ 的 AB 用**自定义 LZ4AK** 压缩：把 LZ4 块每个 token 的
  `literal_length`（低 4 位）与 `match_length`（高 4 位）**互换**后再标准 LZ4 解压。
- 实现：`ak/scripts/ak_lz4ak.py`（独立版，源自 Ark-Unpacker，BSD-3）。
- 用法：`CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak` 注册后 UnityPy 即可解析。

## 3. buff_template_holder.ab 的结构（已实证）

- 含 1 个 **MonoBehaviour**（`buff_template_holder`，13.5MB）—— 游戏数据表以 MonoBehaviour 承载。
- MonoBehaviour 数据格式（已破解）：
  ```
  [int32 条目数] 然后每条目 =
    [int32 键长][键(=templateKey)]
    [变长头部: 事件数等字段]
    [(int32 JSON长][JSON(事件节点数组)]) × 事件数   ← eventToActions 的每个事件一个 JSON 段
  条目间 = [int32 0] + 对齐填充（使键长 4 对齐）
  ```
- **JSON 内容与 `gamedata\buff_template_data.json` 完全一致**（已验证 damage_block[all]、
  enemy_hymwr_t、periodic_damage[not_env]、chiave_t_1 等；事件节点 $type/参数逐字段相同）。
- 即：**客户端以"键 + JSON 段"存 buff 模板；gamedata 是它的完整展开**——双源可互证。

## 4. chiave_t_1 双源比对结论（2026-08-31）

二进制 JSON（1771B）= gamedata eventToActions：
```
ON_BUFF_START:
  [ CheckContainsDeckBuff (_key: "supmech_t[flag]", _target: BUFF_OWNER),
    CreateBuff (_buff: ATK/DEF MULTIPLIER value 0.0 loadFromBlackboard, 可无限叠加) ]
```
内容完全一致 ✅。二进制 ↔ gamedata 互证成立。

## 5. 脚本

- `ak/scripts/unpack_ab.py`（AB 解析入口）、`ak/scripts/ak_lz4ak.py`（LZ4AK 解压）
- `ak/scripts/parse_buff_holder*.py`（格式探索各版本；v8 可解析前 3 条，尾部变体未穷尽）
- 原始副本：`E:\__file\ak_kb\client_res\buff_template_holder.ab`
- 中间产物：`E:\__file\ak_kb\downloads\`（mono raw bin / 分析文本）
