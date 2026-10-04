# -*- coding: utf-8 -*-
import io

p = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\30_信息获取渠道索引_按数据层级.md'
s = io.open(p, encoding='utf-8').read()
n = 0

def rep(old, new):
    global s, n
    if old in s:
        s = s.replace(old, new, 1)
        n += 1
    else:
        print('未命中:', old[:60])

# §5.1 三条已解决
rep('| **随机算法与种子派生** | `RandomFactory.Create` 的 `DEFAULT(=0)` 具体算法未反汇编；`LevelData.randomSeed` → `BattleController.m_randomSeed` 的派生未查明。**没有这条，任何涉及概率（闪避/暴击/buff 随机）的模拟都无法与游戏对齐** |',
    '| ~~随机算法与种子派生~~ | ✅ **已攻克**（2026-09 更新）：见 **`04/34_随机数与确定性复刻.md`**（含定 tick 下的确定性结论）。本行原记"未反汇编"**已过期** |')
rep('| **定长 tick 内的执行顺序** | `BattleController` 的 `m_modules` 遍历顺序、各 `OnFixedUpdate` 的先后，决定同帧多事件的结算次序 |',
    '| ~~定长 tick 内的执行顺序~~ | ✅ **已有结论**：见 **`04/38`（阻挡/索敌/仇恨）** 与 **`04/39`（伤害/死亡/buff/事件/模块）**，排序键＝`(floor(时间/0.001), uid)`；`m_modules` 的**固定遍历序**仍是推断项（见 `04/60`） |')
rep('| **阻挡判定与阻挡偏移** | K-003/004；`notes/17` 与 `skill/AK_KNOWLEDGE.md` 均标需客户端反编译。**现已具备反汇编能力** |',
    '| ~~阻挡判定与阻挡偏移~~ | ✅ **已解决**：权威规则见 **`04/37_阻挡与阻挡偏移_代码核验.md`**（半径 0.7071 + 每 3 帧扫描 + `CalculateBlockOffset` 四步 + 0.2s tween）；`K-003/004` 收口情况见 `04/36` |')

# §二 LZHAM 工具链
rep('| LZHAM bundle 工具链 | — | — | 🔴 UnityPy 暂不支持 LZHAM |',
    '| LZHAM bundle 工具链 | — | — | ✅ **已解决（2026-09-29）**：客户端 bundle 标记为 LZHAM、**实际算法是 LZ4AK** ⇒ 注册 `C.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = ak_lz4ak.decompress_lz4ak`（`ak\\code\\tools\\ak_lz4ak.py`）后 **UnityPy 可直读**，见 `04/71 §4.1` |')

# §5.3 结构性缺口：模拟层
rep('| **模拟层为空** | `sim/` 仅 `README.md`；`code/sim` 0 文件 |',
    '| ~~模拟层为空~~ | ✅ **已不成立（2026-09-29）**：`ak\\sim\\draft\\ak_sim\\` 已成型（时间层 `04/71`、对齐现状 `04/73`、一键对照 `t200_align_report.py`、冒烟 `smoke_test.py`）；本行原记"仅 README"**已过期** |')

# §5.2 关卡索引
rep('| `stage_table.json` | 本地缺失（anon bin 未逆向；OpenBachelorS 有未取） |',
    '| `stage_table.json` | 🟡 本地仍缺（anon bin 未逆向；**OpenBachelorS `res/excel/stage_table.json` 已有未取**）；实操中改用 **MAA `stages.json`（617 关）+ prts+ `map/`（3480）** 替代 |')

# §四 PRTS_map
rep('| **PRTS_map** `https://map.ark-nights.com` | 历史地图出怪路线图 | — | 🔴 连接失败(000)，待复查 |',
    '| **PRTS_map** `https://map.ark-nights.com` | 历史地图出怪路线图 | — | 🔴 **2026-09-29 复测仍不可达**：`web_fetch`×3 / `Invoke-WebRequest` / `curl --tlsv1.2` 全部 TLS 被重置（DNS 正常、TCP 443 可连）——见 `04/75` |')

io.open(p, 'w', encoding='utf-8').write(s)
print(f'04/30 已更新 {n} 处')
