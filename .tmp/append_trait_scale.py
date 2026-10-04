# -*- coding: utf-8 -*-
"""append_trait_scale.py — ★★★发现"领主特性 atk_scale 0.8（远程×0.8）"未应用。"""
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

## 四十九、★★★三个关键机制查明：敌人属性正确、"13 vs 9"解密、"领主特性 atk_scale"缺失

### 49.1 敌人属性核对（`enemy_database.json`）
| key | name | hp | atk | def | res | **moveSpeed** | baseAttackTime |
|---|---|---|---|---|---|---|---|
| `enemy_1000_gopro` | **猎狗** | **820** | **190** | 0 | 20 | **1.9** | 1.4 |
| `enemy_1000_gopro_2` | **猎狗pro** | **1700** | **260** | 0 | 20 | **1.9** | 1.4 |

⇒ **复刻中已正确应用**：`move_speed = 1.9`、`attack_interval_frames = 42`（1.4×30，与标定"猎狗打芬 42.5 帧"吻合）、
`hp=820/1700`、`atk=190/260`、`def=0`。

### 49.2 ★「13 vs 9」之谜完全解开（芬 def = 330）
物理伤害规则：`dmg = max(atk − def, atk × 0.05)`；两只敌人的 atk 都低于芬的 def 330
⇒ 都走 **5% 保底**：
- **猎狗pro**（atk 260）⇒ `260 × 0.05 = 13` ✅ **正是标定的 13**
- **猎狗**（atk 190）⇒ `190 × 0.05 = 9.5 → 9` ✅ **正是标定的 9**

⇒ **标定表中"同一敌人伤害由 13 降到 9"实为"两只不同敌人"** ——
**与用户所指出的"混淆了猎狗与猎狗pro"在数值上完全吻合**。

### 49.3 ★★★发现缺失机制：月见夜「领主」特性的 `atk_scale 0.8`
```json
月见夜 trait = {"candidates":[{"blackboard":[{"key":"atk_scale","value":0.8}]}]}
```
- 职业为 **WARRIOR / `subProfessionId = lord`（领主，远程近卫）**；
- 该特性语义：**远程攻击时攻击力 ×0.8**（近战目标时按全额）；
- **而 `combat.py` 与 `engine.py` 中 `trait` 出现 0 处** ⇒ **本特性完全未被处理**。

### 49.4 由此修正"第 2 只死得太早"的因果
| 端 | 432 芬 | 438 月见夜 | 累计 | 结果 |
|---|---|---|---|---|
| **实机** | 325 | **569 × 0.8 = 455** | **780 < 820** | **不致死** ✅ |
| 本方（缺特性） | 325 | 569 | **894 > 820** | **439 即死** ❌ |

⇒ 实机接着在 **464 芬再打 325** ⇒ 累计 **1105 > 820** ⇒ **击杀** ✅
**完全解释标定「432 命中 / 438 月见夜命中 / 464 芬击杀」**。

### 49.5 下一步
1. **实现"特性（trait）的 `atk_scale`"**：在远程攻击时按 `atk_scale` 缩放（近战目标按全额）；
   - 判据可用"目标距离"（如 `> 1.0` 视为远程攻击）或"目标是否在自身相邻格"；
   - 参数化并保留开关；
2. 同时把"**特性/trait**"纳入信息查找链条的**单位层**（呼应用户前提 1：单位关联机制须全量提取）；
3. 复测：预期 `kill 猎狗` 由 439 推迟到 ~464、**帧 464 偏差收敛到 ≤5**，
   且 `dmg 猎狗←芬` 出现**第二次**命中；
4. 目标 **平均 ≤2 帧、最大 ≤5 帧**。
'''

s = io.open(DOC, encoding='utf-8').read()
if '四十九、★★★三个关键机制查明' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **★★★三个关键机制查明：敌人属性正确、"13vs9"解密、"领主特性 atk_scale"缺失（2026-09-15）**：'
       '①**敌人属性核对**：`enemy_1000_gopro`（**猎狗**）hp820/atk190/def0/res20/**moveSpeed 1.9**/bat 1.4；'
       '`enemy_1000_gopro_2`（**猎狗pro**）hp1700/atk260/def0/res20/**1.9**/1.4 ⇒ '
       '**复刻中已正确应用**（`move_speed=1.9`、`attack_interval_frames=42`〔与标定"猎狗打芬 42.5 帧"吻合〕、'
       'hp/atk/def 均对）；'
       '②**★「13 vs 9」之谜完全解开**（芬 def=330）：物理伤害 `max(atk−def, atk×0.05)`，'
       '两只敌人 atk 均低于芬 def ⇒ 都走 5% 保底：**猎狗pro 260×0.05 = 13** ✅、**猎狗 190×0.05 = 9.5→9** ✅ '
       '⇒ **标定"同一敌人伤害由 13 降到 9"实为"两只不同敌人"**，'
       '**与用户指出的"混淆猎狗与猎狗pro"在数值上完全吻合**；'
       '③**★★★发现缺失机制：月见夜「领主」特性 `atk_scale 0.8`** —— '
       '其 `trait = {blackboard:[{key:"atk_scale", value:0.8}]}`、职业 WARRIOR/`lord`（远程近卫）⇒ '
       '**语义为"远程攻击时攻击力 ×0.8"**；而 **`combat.py` 与 `engine.py` 中 `trait` 出现 0 处 ⇒ 完全未处理**；'
       '④**由此修正"第2只死得太早"的因果**：**实机"432 芬325 + 438 月见夜455(=569×0.8) = 780 < 820 ⇒ 不致死"**，'
       '接着 **464 芬再打 325 ⇒ 1105 > 820 ⇒ 击杀** ✅ **完全解释标定"432命中/438月见夜命中/464芬击杀"**；'
       '而本方缺该特性 ⇒ "325+569=894>820 ⇒ 439 即死"❌；'
       '⑤**下一步**：**(a) 实现"特性(trait)的 `atk_scale`"**（远程攻击时按 `atk_scale` 缩放、近战目标全额；'
       '判据可用"目标距离 > 1.0"或"目标是否在自身相邻格"，参数化并保留开关）；'
       '**(b) 把"特性/trait"纳入信息查找链条的单位层**（呼应前提 1「单位关联机制须全量提取」）；'
       '**(c) 复测**：预期 `kill 猎狗` 由 439 推迟到 ~464、**帧464 偏差收敛到 ≤5**，'
       '且 `dmg 猎狗←芬` 出现**第二次**命中；目标 平均 ≤2 帧、最大 ≤5 帧；'
       '⑥**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
