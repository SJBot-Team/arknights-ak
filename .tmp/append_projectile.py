# -*- coding: utf-8 -*-
"""append_projectile.py — ★记录"弹道"机制与缺失项（用户补充）。"""
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

## 二十七、★用户补充的机制：远程攻击的"弹道"必须建模

### 27.1 用户原话（2026-09-15）
> 「远程攻击需要考虑**是否为存在弹道的远程攻击**。如果为弹道，
> **子弹出现的位置（同干员不同皮肤可能不同）**、**子弹和敌人的追击过程**均需要被考虑。」

### 27.2 对模拟器的直接含义
| 类型 | 时序 |
|---|---|
| **近战**（如芬） | 出手 →（**前摇**）→ **立即命中** |
| **远程·无弹道** | 出手 →（前摇）→ 立即命中 |
| **远程·有弹道**（如月见夜可能属此类） | 出手 →（前摇）→ **生成子弹**（**起始位置依干员/皮肤**）→ **子弹飞向目标（追击过程，含飞行时间）** → **到达才结算命中** |

⇒ 因此 **"远程命中"的时刻 ≠ "出手时刻"**，而是**晚一个飞行时间**，
且该时间**与距离相关**（敌人移动时还需**追踪**）。

### 27.3 标定表里的直接证据
| 标定帧 | 事件 |
|---|---|
| 432 | 猎狗pro 2 ｜ **芬 命中**（近战） |
| **438** | 猎狗pro 2 ｜ **月见夜 远程命中** |

⇒ 同一次交战中，**"远程命中"比"近战命中"晚 6 帧**。
若两者出手时刻相近，则 **6 帧 ≈ 弹道飞行时间**（可作为弹道速度的标定锚点）。

### 27.4 数据层调查结果（`sim/draft/probe_projectile.py`）
| 检查项 | 结果 |
|---|---|
| 干员表直接字段 | ❌ **无 `projectileId`**（仅有 `rangeId`＝攻击范围） |
| **`skill_table.json`** | ✅ **含 `projectile` 738 处**（如 `projectile_delay_time:0`、弹道 id） |
| **`character_table.json`** | ✅ 含 20 处，形如 `{"key": "projectile", "value": "projectile_chr_orchd2_t"}` ⇒ **弹道挂在技能/天赋的 blackboard** |
| 皮肤表 | ⚠️ `skin_table.json` 不在 `gamedata/`（文件名/位置待查） |
| **模拟器** | ❌ **完全未处理弹道**（`projectile`/`bullet`/`pending_damage` 均 0 处） |

⇒ **结论**：**普攻弹道（若存在）与前摇一样，数据表不直接提供** ⇒ 必须按用户提示建模；
技能弹道则可通过 `blackboard.projectile` 关联到弹道 id。

### 27.5 建模方案（下一轮实施）
1. **新增"投射物"实体**：`{src, dst, pos, speed, born_frame, payload}`
   - **起始位置**：由"发射点偏移"决定（**依干员与皮肤** ⇒ 以配置表建模，默认取干员中心/攻击点）；
   - **飞行**：每帧朝"目标当前位置"推进（**追踪**）；
   - **到达**：`dist ≤ 阈值` 时**结算伤害**并从场上移除；
2. **接入点**：`_do_attack` 中判断"本次攻击是否带弹道"：
   - 带弹道 ⇒ **生成投射物**（伤害延后到到达帧结算）；
   - 不带 ⇒ 立即结算（现状）；
3. **参数来源**：
   - **弹道速度/延迟**：优先取 `blackboard.projectile_delay_time` / 弹道表；
     普攻若查不到 ⇒ 由标定反推（**当前锚点：6 帧**）；
   - **发射点偏移**：按干员/皮肤配置（默认 0，后续按素材校准）；
4. **对轴验证**：用"帧 438 月见夜远程命中"与"帧 432 芬命中"的 6 帧差校准飞行时间，
   再用其它远程事件交叉验证。

### 27.6 与既有工作的关系
- 本轮此前已定位"**缺少攻击前摇**"（干员 0.55 / 敌人 0.10 个攻击周期）并显著改善偏差；
- **"弹道"是下一个独立的时序机制**，二者叠加才能解释"远程事件"的全部延迟；
- 按机制 5（信息查找链条），**"单位是否带弹道 + 弹道参数"应补进链条的"单位层"**。
'''

s = io.open(DOC, encoding='utf-8').read()
if '二十七、★用户补充的机制' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **★用户补充机制：远程"弹道"必须建模（含起始位置依皮肤、飞行追击）2026-09-15**：'
       '①**用户原话**：「远程攻击需要考虑**是否为存在弹道的远程攻击**。如果为弹道，'
       '**子弹出现的位置（同干员不同皮肤可能不同）**、**子弹和敌人的追击过程**均需要被考虑」；'
       '②**对模拟器的含义**：**近战/无弹道远程**＝出手→（前摇）→立即命中；'
       '**有弹道远程**＝出手→（前摇）→**生成子弹（起始位置依干员/皮肤）**→**飞向目标（追击，含飞行时间）**'
       '→**到达才结算命中** ⇒ **"远程命中"时刻 ≠ "出手时刻"**，且与距离相关；'
       '③**标定表的直接证据**：**帧432「猎狗pro2｜芬 命中」（近战）** vs **帧438「猎狗pro2｜月见夜 远程命中」** '
       '⇒ **同一次交战中"远程命中"比"近战命中"晚 6 帧**，若出手相近则 **6 帧 ≈ 弹道飞行时间**（可作标定锚点）；'
       '④**数据层调查**（`sim/draft/probe_projectile.py`）：**干员表无 `projectileId`**（仅 `rangeId`）；'
       '**`skill_table.json` 含 `projectile` 738 处**（如 `projectile_delay_time`）；'
       '**`character_table.json` 含 20 处**（形如 `{"key":"projectile","value":"projectile_chr_orchd2_t"}`）'
       '⇒ **弹道挂在技能/天赋 blackboard**；皮肤表 `skin_table.json` 不在 gamedata（待查）；'
       '**★模拟器完全未处理弹道（projectile/bullet/pending_damage 均 0 处）** ⇒ **这是一个缺失项**；'
       '⑤**建模方案**：**(a) 新增"投射物"实体** `{src,dst,pos,speed,born_frame,payload}`，'
       '**起始位置由"发射点偏移"决定（依干员与皮肤，配置化）**，**每帧朝目标当前位置推进（追踪）**，'
       '`dist≤阈值` 时结算伤害并移除；**(b) 接入 `_do_attack`**：带弹道则生成投射物（延迟结算），'
       '不带则立即结算；**(c) 参数来源**：优先取 `blackboard.projectile_delay_time`/弹道表，'
       '普攻查不到则由标定反推（**当前锚点 6 帧**）；**(d) 对轴验证**用帧438/帧432 的 6 帧差校准飞行时间；'
       '⑥**与既有工作的关系**：已定位的"**缺少攻击前摇**"（干员0.55/敌人0.10）是第一个时序机制，'
       '**"弹道"是第二个独立时序机制**，二者叠加才能解释远程事件的全部延迟；'
       '并按机制 5 把"**单位是否带弹道 + 弹道参数**"补进**信息查找链条的单位层**；'
       '⑦**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\probe_projectile.py', r'sim\draft')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
