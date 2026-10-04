# GitHub 明日方舟解包/代码逻辑项目调研 + 调零新对话要点（2026-09-01~02）

## 一、调零新对话关键解答（已自动读取，18 条新消息）

1. **「Deck」语义解答（重大）**：*"Deck 是玩家的意思（你就是个 Deck），DeckBuff 是对玩家部署费用、
   玩家手里所有干员、玩家生命值等东西的 buff"*
   → **`CheckContainsDeckBuff(supmech_t[flag])` = 检查"玩家（Deck）是否拥有支援机械标记"**
   → 贾维天赋逻辑 = "玩家拥有支援机械时，贾维攻防+7%"——疑问①解决 ✅
2. **阻挡半径/偏移知识库不完备**（调零指出，待补）
3. 调零建议先补充已有机制、数据互核；**阻挡相关只能从 IDA（il2cpp）入手**，可看
   **hjhk258 的专栏**和"神奇的补充"；不看 il2cpp 几乎没辙
4. 用户策略：先解容易的，捋顺已知机制后再解 il2cpp 核验
5. 用户 09-02 待问调零：量角器获取渠道、il2cpp 前置门槛与现成辅助工具

## 二、GitHub 项目筛选（学习参考价值排序）

| 项目 | ★ | 用途/学习点 |
|---|---|---|
| **DeftSolutions-dev/IL2CPP-Dumper** | 111 | **il2cpp 辅助工具**（Windows x64 单 exe 自动 dump 类/字段/方法，为终末地做但通用）→ 回答"看 IDA 前置门槛/现成工具" |
| **MooncellWiki/torappu** | 13 | 权威资源提取：FlatBuffer schema 解析、manifest 处理、版本对比（Python 3.13，uv） |
| isHarryh/Ark-Unpacker / Ark-Studio | 665/227 | 已掌握的核心工具链（LZ4AK 解压、AB 解包） |
| **djpadbit/Arknights-RE** | 41 | 抓包(MITM) + 资产解密 + 代码逆向（含风险警告，谨慎） |
| **hjhk258/ArkEnemiesList** | 0 | 调零推荐人：敌人列表项目（Vue）；另有 **assembly-differ**（程序集版本对比，"拖进软件看新东西"疑似指此） |
| Aloento/Arknights | 169 | 干员资源仓库 |
| ArknightsAssets/ArknightsAssets2 | 64 | 资源仓库（cn/en/voice 分支） |
| OneBST/GGanalysis | 242 | 抽卡概率分析（数值分析参考） |
| hanmin0822/RaphaelScriptHelper | 272 | 游戏脚本框架（含明日方舟，自动化参考） |

## 三、贝娜量角器

两轮 web 搜索（含 B 站/知乎）均只有贝娜干员测评，**未找到该工具** → 按用户约定**放弃搜索**；
用户已向调零询问获取渠道（待回复）。

## 四、下一步（与调零共识）

1. 先补容易的：阻挡半径/偏移数据（组件层）、已知机制互核
2. 用 IL2CPP-Dumper 类工具准备 il2cpp 前置（调零：阻挡相关需 IDA）
3. 参考 torappu/Arknights-RE 的资产与代码分析思路
