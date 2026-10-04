# -*- coding: utf-8 -*-
"""append_spawns.py — ★1-1 出怪表核对：两种猎狗模板 + 标定命名澄清。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\54_1-1标定对局_复刻报告.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

EXTRA = '''

---

## 三十二、★1-1 出怪表核对：两种猎狗模板，标定命名需澄清

### 32.1 1-1 的完整出怪表（共 16 个 SPAWN）

**wave0 有 3 个 fragment**：`frag0 preDelay=0（帧0）`、`frag1 preDelay=9（帧270）`、`frag2 preDelay=17（帧510）`

**与"猎狗"相关的 4 条**（均在 frag0）：

| action preDelay | ⇒ 帧 | key | routeIndex |
|---|---|---|---|
| 3.0 | **90** | `enemy_1000_gopro_2` | 1 |
| 12.0 | **360** | `enemy_1000_gopro` | 4 |
| 22.0 | **660** | `enemy_1000_gopro_2` | 3 |
| 27.0 | **810** | `enemy_1000_gopro` | 5 |

（其余为 `enemy_1007_slime_2`、`enemy_1027_mob`、`enemy_1028_mocock`、`enemy_1030_wteeth` 等，
分布在 frag1/frag2，帧号≥270，**与本次标定（0~18s）无关**。）

### 32.2 模拟器实际 spawn 事件（0~700 帧）

| 帧 | key | name | hp |
|---|---|---|---|
| **90** | `enemy_1000_gopro_2` | **猎狗pro** | **1700** |
| **360** | `enemy_1000_gopro` | **猎狗** | **820** |
| 660 | `enemy_1000_gopro_2` | 猎狗pro | 1700 |

### 32.3 ★三个关键事实

**(1) 「猎狗」与「猎狗pro」是两种不同敌人**
- `enemy_1000_gopro` ⇒ 名称「**猎狗**」，**hp 820**；
- `enemy_1000_gopro_2` ⇒ 名称「**猎狗pro**」，**hp 1700**。

**(2) 标定表的"猎狗pro 1 / 猎狗pro 2"命名不够准确**
- 标定「帧 94 猎狗pro 1 出现影子」⇒ 对应模拟器**帧 90 的 `gopro_2`（猎狗pro，1700）** ✅ 一致；
- 标定「帧 367 猎狗pro 2 出现影子」⇒ 对应模拟器**帧 360 的 `gopro`（猎狗，820）**
  ⇒ **该敌人实为「猎狗」而非「猎狗pro」** ⚠️
- ⇒ 标定表可能是**按"第几只猎狗类敌人"记数**（1、2），而**未区分具体模板**。

**(3) 出怪时刻吻合良好**
模拟器 90 / 360 vs 标定影子 94 / 367 ⇒ **偏差 −4 / −7 帧**（与此前一致）。

### 32.4 这对匹配的影响
本方的匹配器按"名字包含"配对，而**两个模板的名字都含"猎狗"**
⇒ "芬打猎狗pro（1700血）"与"芬打猎狗（820血）"的事件会被混在一起，
这正是上一轮"后 5 条偏差 26~58 帧"的来源。

**修正方向**：
1. 匹配时**按 key 区分模板**（`enemy_1000_gopro` vs `_2`），
   并把标定的"猎狗pro 1/2"映射为"**猎狗类敌人的第 1 只 / 第 2 只**"（按出现顺序）；
2. 或在标定侧补充 key/模板信息（**需用户确认标定表的命名口径**）。

### 32.5 待确认（需用户）
- 标定表的「猎狗pro 1 / 猎狗pro 2」是"**第几只猎狗类敌人**"的意思吗？
  还是应当区分 `enemy_1000_gopro`（猎狗）与 `enemy_1000_gopro_2`（猎狗pro）两个模板？

### 32.6 下一步
1. 按"**出现序号 + 模板 key**"重写配对，复测；
2. 把"**出怪表（数量/时刻/key/路线）**"作为**关卡层**的必查项写入信息查找链条
   （本轮即因未先核对出怪表而走了弯路）；
3. 之后继续收敛偏差（目标 平均 ≤2 帧、最大 ≤5 帧）。
'''

s = io.open(DOC, encoding='utf-8').read()
if '三十二、★1-1 出怪表核对' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **★1-1 出怪表核对：两种猎狗模板 + 标定命名需澄清（2026-09-15）**：'
       '①**1-1 完整出怪表（16 个 SPAWN）**：wave0 三个 fragment（frag0 帧0、frag1 帧270、frag2 帧510）；'
       '**与猎狗相关的 4 条**：**preDelay 3.0⇒帧90 `enemy_1000_gopro_2`（route1）**、'
       '**12.0⇒帧360 `enemy_1000_gopro`（route4）**、**22.0⇒帧660 `gopro_2`（route3）**、'
       '**27.0⇒帧810 `gopro`（route5）**；其余为 slime/mob/mocock/wteeth，帧号≥270 与本次标定无关；'
       '②**模拟器实际 spawn**：**帧90 `gopro_2` name="猎狗pro" hp=1700**；'
       '**帧360 `gopro` name="猎狗" hp=820**；帧660 `gopro_2` hp=1700；'
       '③**★三个关键事实**：**(1)「猎狗」(`enemy_1000_gopro`, hp820) 与「猎狗pro」(`_2`, hp1700) 是两种不同敌人**；'
       '**(2) 标定的"猎狗pro 1/pro 2"命名不够准确** —— 帧94(模拟90) 确为 `gopro_2` ✓，'
       '但**帧367(模拟360) 实为 `gopro`（猎狗，820）而非"猎狗pro"** ⇒ 标定可能只按"第几只猎狗类敌人"记数；'
       '**(3) 出怪时刻吻合**（模拟 90/360 vs 标定影子 94/367 ⇒ −4/−7 帧）；'
       '④**对匹配的影响**：本方按"名字包含"配对，而**两个模板名字都含"猎狗"** ⇒ '
       '"打猎狗pro(1700)"与"打猎狗(820)"的事件被混在一起，**这正是上轮"后 5 条偏差 26~58 帧"的来源**；'
       '**修正方向**：**(a) 匹配按 key 区分模板**，并把标定"猎狗pro 1/2"映射为"猎狗类敌人的第 1/2 只（按出现顺序）"；'
       '**(b) 或在标定侧补充 key/模板信息**；'
       '⑤**待用户确认**：标定表「猎狗pro 1 / 2」是"第几只猎狗类敌人"之意，还是应区分 `gopro` 与 `gopro_2` 两个模板？'
       '⑥**下一步**：按"**出现序号 + 模板 key**"重写配对并复测；把"**出怪表（数量/时刻/key/路线）**"'
       '作为**关卡层**必查项写入信息查找链条（本轮即因未先核对出怪表而走了弯路）；'
       '⑦**新增 `sim/draft/probe_spawns.py`**；'
       '⑧**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\probe_spawns.py', r'sim\draft')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
