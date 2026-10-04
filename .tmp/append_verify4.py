# -*- coding: utf-8 -*-
"""append_verify4.py — ★人工对应表建立 + 暴露"冷却/前摇交互"仍未正确（断点）。"""
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

## 三十四、★人工对应表（可信基线）+ 暴露"冷却/前摇交互"仍未正确

### 34.1 人工对应表（`replay_verify4.py`）
按机制 3 的决策，把配对规则改为**人工对应表**：
`(标定帧, 说明, 类别, 目标, 序号)`，其中
- 类别 ∈ `spawn`（敌方出现）/ `dmg_enemy`（我方命中）/ `dmg_ally`（我方受伤）/ `kill`；
- 目标 ∈ `EN1/EN2`（敌方第 1/2 只）或 `ALLY`；
- 序号 = **同类事件中的第 n 次**。

程序先由事件流构造**索引表** `{(类别,目标): [帧...]}`，再按对应表逐条取帧比较。
**⇒ 彻底消除了自动配对的歧义，得到可复现的偏差指标。**

### 34.2 ★索引表本身暴露两个严重错误（修正前）

| 事件 | 实机（标定）间隔 | **模拟器间隔（修正前）** | 判定 |
|---|---|---|---|
| **猎狗打芬**（dmg_ally） | **42.5 帧** | **4 帧**（39 个事件！） | ❌ 严重错误 |
| **芬打猎狗**（dmg_enemy） | **32 帧** | **18 帧** | ❌ 错误 |

**根因**：**"起手处重置冷却"的改动没生效**（上一轮的替换只匹配了 2/4 处）
⇒ `attack_cd_frames` 递减到 0 后**不再增加** ⇒ **每帧都满足"可攻击"**
⇒ **命中间隔退化成"前摇帧数"**（干员 18、敌人 4）。

### 34.3 修正后（补上"起手即重置冷却"）

| 事件 | 实机 | **修正后模拟器** | 判定 |
|---|---|---|---|
| dmg_enemy（芬打猎狗） | 32 | **49**（250/299/348/397/446/475） | ❌ 仍偏（=32+17≈32+前摇） |
| dmg_ally（猎狗打芬） | 42.5 | **45**（246/291/336/381/426…） | ⚠️ 接近 |

**统计**：可对齐 17/18；≤6 帧 1 条；平均 72.71；最大 155。

### 34.4 分析（当前断点）
按代码推演，**命中间隔应为 `前摇 + (interval − 前摇) = interval`**，
但实测 `dmg_enemy` 间隔为 **49 = 32 + 17**（多了一个前摇），说明
**`attack_cd_frames` 与 `attack_windup_left` 的实际交互与推演不符**：

可能原因：
1. **起手那一帧的 `cd` 递减顺序**：`cd -= 1` 发生在"起手重置"**之前**，
   导致重置后的 `cd` 又立刻被减，或反之 ⇒ 产生 1~2 帧偏差（不足以解释 17 帧）；
2. **"命中后 `windup` 置 None" 的那一帧**，`cd` 已经 ≤0 ⇒ **该帧又立即起手并重置 `cd = 32`**
   ⇒ 等价于"前摇被算了两遍" ⇒ **间隔 = 前摇 + 32**（**49 = 17 + 32，吻合！**）；
3. 即：**命中帧与"下一次起手帧"重合**，使前摇"额外"叠加了一次。

**⇒ 修正方向（下一轮）**：
- 把"前摇"与"冷却"改为**单一状态机**：`atk_state ∈ {IDLE, WINDUP, COOLDOWN}`，
  **命中后直接进入 COOLDOWN，且冷却剩余 = `interval − 前摇`**（而不是重置为完整 `interval`）；
- 或等价地：**起手时记录 `atk_start_frame = frame`**，
  命中判定用 `frame - atk_start_frame >= windup`，
  冷却判定用 `frame - atk_start_frame >= interval` ⇒ **同一时间基准、不可能叠加**。

### 34.5 下一步
1. 按 34.4 的"单一状态机/统一时间基准"重构普攻时序，复测（目标：`dmg_enemy` 间隔 = 32、
   `dmg_ally` 间隔 ≈ 42.5）；
2. 随后偏差指标应显著下降（当前多项 +29~+155 皆为该叠加所致）。
'''

s = io.open(DOC, encoding='utf-8').read()
if '三十四、★人工对应表' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **★人工对应表（可信基线）+ 暴露"冷却/前摇交互"仍未正确（断点）2026-09-15**：'
       '①**按机制 3 决策改用人工对应表**（`replay_verify4.py`）：'
       '`(标定帧, 说明, 类别, 目标, 序号)` —— 类别∈`spawn/dmg_enemy/dmg_ally/kill`、'
       '目标∈`EN1/EN2/ALLY`、序号=同类事件第 n 次；程序先建**索引表** `{(类别,目标):[帧...]}` 再逐条比较'
       '⇒ **彻底消除自动配对歧义，得到可复现的偏差指标**；'
       '②**★索引表本身暴露两个严重错误（修正前）**：**猎狗打芬 实机 42.5 帧 vs 模拟器 4 帧（39 个事件！）**；'
       '**芬打猎狗 实机 32 帧 vs 模拟器 18 帧** ⇒ **根因：上一轮"起手处重置冷却"的改动没生效**'
       '（替换只匹配 2/4 处）⇒ `attack_cd_frames` 递减到 0 后不再增加 ⇒ 每帧都"可攻击" ⇒ '
       '**命中间隔退化成"前摇帧数"**（干员 18、敌人 4）；'
       '③**修正后**：dmg_ally 间隔 45（**接近 42.5** ✓）、dmg_enemy 间隔 **49**（=32+17，仍多一个前摇 ✗）；'
       '**统计：可对齐 17/18、≤6 帧 1 条、平均 72.71、最大 155**；'
       '④**分析（当前断点）**：按代码推演"命中间隔应 = 前摇 + (interval − 前摇) = interval"，'
       '但实测 49 = 32 + 17 ⇒ 疑因**"命中帧"与"下一次起手帧"重合**，'
       '使前摇"额外"叠加一次（49 = 17 + 32 吻合）；'
       '⑤**修正方向（下一轮）**：把"前摇+冷却"改为**单一状态机** `atk_state ∈ {IDLE,WINDUP,COOLDOWN}`，'
       '命中后直接进入 COOLDOWN 且**冷却剩余 = `interval − 前摇`**；'
       '或等价地用**统一时间基准**：`atk_start_frame`，命中判 `frame−start ≥ windup`、'
       '冷却判 `frame−start ≥ interval` ⇒ **不可能叠加**；'
       '⑥**下一步**：按 ④⑤ 重构普攻时序并复测（目标 `dmg_enemy` 间隔=32、`dmg_ally`≈42.5），'
       '随后偏差指标应显著下降（当前 +29~+155 皆为该叠加所致）；'
       '⑦**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\replay_verify4.py', r'sim\draft'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py',
                  r'sim\draft\ak_sim')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
