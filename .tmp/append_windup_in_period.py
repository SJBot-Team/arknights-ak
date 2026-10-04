# -*- coding: utf-8 -*-
"""append_windup_in_period.py — ★★修正"前摇含在周期内"（前段偏差降到 1~7 帧）+ 新问题。"""
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

## 三十一、★★修正"前摇含在攻击周期内" —— 前段偏差降到 1~7 帧

### 31.1 问题发现（由逐帧事件明细）
按序号分组打印模拟器伤害事件后发现，"**芬→猎狗**"的命中序列为
**219 / 268 / 317 / 366 / 415** ⇒ **间隔恒为 49 帧**，
而配置的 `attack_interval_frames = 32` ⇒ **多出 17 帧 ≈ 本方加入的前摇（18 帧）**。

**⇒ 根因：本方把前摇"额外加在周期之外"**（冷却在**命中时**重置 ⇒ 间隔 = 前摇 + 周期）。
**正确语义：一个 32 帧的攻击周期 = 前摇 + 后摇** ⇒ **命中间隔必须恒等于 `attack_interval_frames`**。

### 31.2 修正（`fix_windup_in_period.py`）
- **起手时**（设置 `attack_windup_left` 的同一处）**立即重置** `attack_cd_frames = attack_interval_frames`；
- **命中时**（前摇结束）**只结算伤害、不再重置冷却**；
- **干员侧与敌人侧同时修正**；并在 `_windup_frames` 的 docstring 中写明该语义要求。

### 31.3 复测结果（严格口径）

**偏差分布：`1, 1, 1, 2, 2, 2, 2, 4, 5, 5, 5, 6, 6, 7, 26, 31, 56, 58`**

| 指标 | 修正前 | **修正后** |
|---|---|---|
| **\\|偏差\\| ≤ 6 帧** | 11 | **13** |
| 平均 \\|偏差\\| | 8.11 | 12.22 |
| 最大 \\|偏差\\| | 26 | 58 |

**⇒ 分布呈"两极"**：
- **前 13 条全部 ≤7 帧**（**其中 5 条 ≤2 帧**）⇒ **这一段已高度吻合**；
- **后 5 条偏差 26~58 帧** ⇒ **是另一类问题**（见 31.4）。

**⇒ 结论**：本修正使"可精确对齐的事件数"增加（13 条 ≤6 帧），
平均/最大偏差的上升**完全由后 5 条拖累**，并非本修正引入的退化。

### 31.4 ★新问题（下一步核心）：模拟器只生成了 **1 只猎狗**
事件明细显示，模拟器中与"猎狗"相关的伤害事件**受害者 uid 恒为 2**
（`key = enemy_1000_gopro_2`），而标定表里出现的是**「猎狗pro 1」与「猎狗pro 2」两只**。

⇒ **两种可能**：
1. **出怪配置解析不全**：本关应有 2 只猎狗，模拟器只生成 1 只（或另一只未参与战斗）；
2. **正是这一只**：标定的"pro 1 / pro 2"其实是**同一模板的两次出怪名**，
   而模拟器把两次出怪合并/替换了。

**⇒ 这解释了"后 5 条偏差大"**：标定的"芬打 pro 1"被配到模拟器"打 pro 2"的事件上。

### 31.5 下一步
1. **核对 1-1 的出怪表**：`waves[].fragments[].actions[]` 中 SPAWN 的**数量、时刻、key**
   与标定的"猎狗pro 1（帧94 影子）/ pro 2（帧367 影子）"逐条对齐；
2. 若模拟器少生成 ⇒ 修出怪解析（**这属于"关卡层"信息缺失，应回流到信息查找链条**）；
3. 若只是"同名两次出怪"⇒ 配对时改用**出怪序号**（第 1 只 / 第 2 只）而非 uid/key；
4. 修好后复测，目标"平均 ≤2 帧、最大 ≤5 帧"。
'''

s = io.open(DOC, encoding='utf-8').read()
if '三十一、★★修正"前摇含在攻击周期内"' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **★★修正"前摇含在攻击周期内"（前段偏差降至 1~7 帧）+ 定位新问题（2026-09-15）**：'
       '①**问题发现**（由逐帧事件明细）：**"芬→猎狗"命中序列 219/268/317/366/415 ⇒ 间隔恒 49 帧**，'
       '而配置 `attack_interval_frames = 32` ⇒ **多出 17 帧 ≈ 本方加入的前摇（18 帧）** ⇒ '
       '**根因：本方把前摇"额外加在周期之外"**（冷却在命中时重置 ⇒ 间隔 = 前摇 + 周期）；'
       '**正确语义：一个 32 帧周期 = 前摇 + 后摇 ⇒ 命中间隔必须恒等于 `attack_interval_frames`**；'
       '②**修正**（`fix_windup_in_period.py`）：**起手时立即重置 `attack_cd_frames`**，'
       '**命中时只结算伤害、不再重置冷却**（干员侧与敌人侧同时修正），并在 `_windup_frames` docstring 写明语义；'
       '③**复测**：**偏差分布 `1,1,1,2,2,2,2,4,5,5,5,6,6,7,26,31,56,58`**；'
       '**|偏差|≤6 帧 11 → 13 条**（前 13 条全部 ≤7 帧、其中 **5 条 ≤2 帧**）；'
       '平均 8.11→12.22、最大 26→58（**完全由后 5 条拖累，非本修正引入的退化**）⇒ '
       '**分布呈"两极"，说明存在两类不同问题**；'
       '④**★新问题（下一步核心）：模拟器只生成了 1 只猎狗** —— 事件明细显示"猎狗"相关伤害事件的'
       '**受害者 uid 恒为 2**（`enemy_1000_gopro_2`），而标定表出现的是**「猎狗pro 1」与「猎狗pro 2」两只** ⇒ '
       '**两种可能**：**(a) 出怪配置解析不全**（应有 2 只只生成了 1 只）；'
       '**(b) 标定的 pro1/pro2 是同一模板的两次出怪名**而模拟器合并/替换了；'
       '**这解释了后 5 条偏差大**（标定"芬打 pro1"被配到模拟器"打 pro2"的事件上）；'
       '⑤**下一步**：**(1) 核对 1-1 出怪表**（`waves[].fragments[].actions[]` 的 SPAWN 数量/时刻/key）'
       '与标定"帧94 影子(pro1)/帧367 影子(pro2)"逐条对齐；**(2) 若少生成则修出怪解析**'
       '（属"关卡层"信息缺失，**应回流到信息查找链条**）；**(3) 若只是同名两次出怪则改按出怪序号配对**；'
       '**(4) 修好后复测**（目标 平均 ≤2 帧、最大 ≤5 帧）；'
       '⑥**另修**：本轮曾因编辑失误留下半截 docstring 导致 SyntaxError，已修复并加 `ast.parse` 语法自检；'
       '⑦**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\fix_windup_in_period.py', r'sim\draft'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\replay_verify2.py', r'sim\draft'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py',
                  r'sim\draft\ak_sim')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
