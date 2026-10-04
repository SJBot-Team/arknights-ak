# -*- coding: utf-8 -*-
"""append_runes.py — ★判别：runes 全属 FOUR_STAR ⇒ 普通模式不启用 ⇒ 排除；残余转向伤害公式。"""
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

## 四十八、判别：`runes` 全属 FOUR_STAR（普通模式不启用）⇒ 排除；残余转向伤害公式

### 48.1 1-1 的完整 runes（共 3 条）
| key | difficultyMask | blackboard |
|---|---|---|
| `gbuff_lifepoint` | **FOUR_STAR** | `{value: 1.0}`（我方生命点 +1） |
| **`ebuff_attribute`** | **FOUR_STAR** | **`{atk: 1.2, def: 1.2, max_hp: 1.2}`（敌方属性 ×1.2）** |
| `gbuff_placable_char_num` | **FOUR_STAR** | `{value: -4.0}`（可放置角色 −4） |

### 48.2 判别结论
- **三条 runes 的 `difficultyMask` 全部是 `FOUR_STAR`**（四星/突袭难度）；
- **标定视频为普通模式** ⇒ **不启用这些 runes**；
- ⇒ **本方复刻未应用 runes 是正确的**（若误加，敌人 max_hp ×1.2 ⇒ hp 984，
  反而会"死得更晚"）。
- 对照检查：`scenario.py` 中 `runes` 出现 7 处、`engine.py` 中 5 处（具备相关处理能力），
  但**默认未启用** ⇒ 与"普通模式"一致。

### 48.3 残余问题的方向修正
既然 runes 被排除，"第 2 只死得太早（模拟器 439 / 实机 464）"只能来自**伤害数值**：
- 实机：**432 芬命中 + 438 月见夜命中** 之后**并未致死**；
- 若第 2 只 hp 确为 820，且芬造成 325，则**月见夜的实际伤害必须 < 495**
  （325 + 495 = 820 恰好致死；否则更小）；
- 而本方模拟器中月见夜造成 **569 = 满额 atk** ⇒ **偏高约 74+**。

⇒ 需核对**伤害公式**（物理伤害减免 = 目标防御）：
`dmg = max(atk × scale − def, atk × scale × 0.05)`（AK 的物理伤害规则）；
若第 2 只的 `def` 较高，则 569 会被显著削减。

### 48.4 另一个待解线索：芬受伤 13 → 9
标定显示同一敌人对芬的伤害在**帧 413 起由 13 降为 9**（≈×0.69）。
- 这不可能是 runes（FOUR_STAR 未启用）；
- 可能是**关卡其它机制**或**我方某单位的减益**；
- 也可能是**敌人在战斗中获得了某种 buff/debuff**（或切换了攻击目标时用了不同的攻击值）。
⇒ 该现象可作为**伤害公式与状态机制的独立校验点**，下一轮一并核查。

### 48.5 下一步
1. **核对伤害公式的“防御减免”**：
   - 打印第 2 只（`enemy_1000_gopro`）与第 1 只（`_2`）的 `def`、`max_hp`（注意数据键名——
     本次 `get_enemy()` 返回的 `attrs` 里 `max_hp/atk` 为 None，说明**键名与假设不同，需按实际结构取**）；
   - 用"月见夜 atk 569、第 2 只 def X"反推实机伤害应约 <495；
2. **核对 13→9 的来源**（查我方单位的天赋/技能减益，或敌人的攻击力变化）；
3. 修正后复测，目标 **平均 ≤2 帧、最大 ≤5 帧**。
'''

s = io.open(DOC, encoding='utf-8').read()
if '四十八、判别：`runes` 全属' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **判别：runes 全属 FOUR_STAR ⇒ 普通模式不启用（排除）；残余转向伤害公式（2026-09-15）**：'
       '①**1-1 的 3 条 runes**：`gbuff_lifepoint{mask=FOUR_STAR, value 1.0}`、'
       '**`ebuff_attribute{mask=FOUR_STAR, atk/def/max_hp ×1.2}`**、'
       '`gbuff_placable_char_num{mask=FOUR_STAR, value −4.0}`；'
       '②**判别结论**：**三条 runes 的 `difficultyMask` 全部为 `FOUR_STAR`**（四星/突袭难度），'
       '而**标定视频是普通模式 ⇒ 不启用** ⇒ **本方复刻未应用 runes 是正确的**'
       '（若误加，敌人 max_hp×1.2 ⇒ hp 984，会"死得更晚"）；'
       '对照检查：`scenario.py` 中 `runes` 出现 7 处、`engine.py` 中 5 处（具备处理能力）但**默认未启用**；'
       '③**残余方向修正**：排除 runes 后，"第2只死得太早（模拟器 439 / 实机 464）"只能来自**伤害数值** —— '
       '实机"432 芬命中 + 438 月见夜命中"后**并未致死**；若第2只 hp 确为 820 且芬造成 325，'
       '则**月见夜实际伤害必须 < 495**（325+495=820 恰好致死）；而本方模拟器月见夜造成 **569 = 满额 atk**'
       '⇒ **偏高约 74+**；⇒ 需核对**物理伤害减免公式**（`dmg = max(atk×scale − def, atk×scale×0.05)`），'
       '若第2只 `def` 较高则 569 会被显著削减；'
       '④**另一待解线索**：标定显示同一敌人对芬的伤害**帧413 起由 13 降为 9**（≈×0.69），'
       '不可能是 runes（FOUR_STAR 未启用）⇒ 可能是关卡其它机制或我方某单位的减益，'
       '或敌人在战斗中获得了状态 ⇒ 可作为**伤害公式与状态机制的独立校验点**；'
       '⑤**下一步**：核对伤害公式的"防御减免"（注意本次 `get_enemy()` 返回的 `attrs` 里 `max_hp/atk` 为 None，'
       '说明**键名与假设不同，需按实际结构取**）；用"月见夜 atk 569、第2只 def X"反推实机伤害应约 <495；'
       '核对 13→9 的来源；修正后复测（目标 平均 ≤2 帧、最大 ≤5 帧）；'
       '⑥**新增 `sim/draft/probe_damage_values.py`**；'
       '⑦**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\probe_damage_values.py', r'sim\draft')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
