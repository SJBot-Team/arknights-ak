# -*- coding: utf-8 -*-
"""append_windup_fixed.py — ★★攻击前摇修正生效：平均偏差 14.50→9.06 帧。"""
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

## 二十三、★★攻击前摇修正生效（平均偏差 14.50 → 9.06 帧）

### 23.1 数据层核查结果
- **干员表 `character_table.json`**：**没有攻击前摇字段**（只有 `phases`/`skills`/`talents`/`favorKeyFrames` 等）；
- **敌人表 `enemy_database.json`（1718 键）**：命中 `enemy_1000_gopro`，但**只有 `stats`（属性）**，
  同样**没有前摇字段**；
- ⇒ **前摇应源自动画资源**，数据表不提供 ⇒ 本方改用「**攻击周期比例**」参数化。

### 23.2 引擎修改（`ak_sim/engine.py`）
`_operator_tick` 原逻辑：**冷却归零即 `_do_attack` 结算**（前摇 0）。
改为：
```python
if u.attack_cd_frames <= 0:
    tgt = self.pick_operator_target(u)
    if tgt is None:
        u.attack_windup_left = None          # 目标丢失 ⇒ 前摇重置
    else:
        wl = getattr(u, 'attack_windup_left', None)
        if wl is None:
            u.attack_windup_left = self._windup_frames(u)     # 起手
        if u.attack_windup_left > 0:
            u.attack_windup_left -= 1
        if u.attack_windup_left > 0:
            pass                              # 仍在前摇，本帧不结算
        else:
            self._do_attack(u, tgt)           # 前摇结束 ⇒ 结算伤害
            u.attack_cd_frames = u.attack_interval_frames
            u.attack_windup_left = None

@staticmethod
def _windup_frames(u) -> int:
    ratio = float(getattr(u, '_windup_ratio', 0.4375))   # 由 1-1 标定反推：14/32
    return max(0, int(round(float(u.attack_interval_frames) * ratio)))
```
- **参数来源**：标定「帧207 芬 进入攻击前摇」→「帧221 芬首次命中」⇒ **前摇 14 帧**，
  攻击周期 32 帧 ⇒ **比例 0.4375**；
- 可用 `u._windup_ratio` 覆盖以便做敏感性验证；
- **注**：`Unit` 类定义不在 `engine.py` 中，故用 `getattr` 容错，避免依赖类属性初始化。

### 23.3 ★复测结果（`replay_verify.py`，同一复刻）

| 指标 | 修正前 | **修正后** | 改进 |
|---|---|---|---|
| **平均 \\|偏差\\|** | **14.50 帧** | **9.06 帧** | **↓ 37.5%** |
| **最大偏差** | **52 帧** | **23 帧** | **↓ 56%** |
| 偏差分布 | `0,1,2,4,5,7,9,10,11,11,13,14,19,19,23,29,32,52` | **`1,1,4,5,5,7,7,7,8,8,10,10,11,11,13,13,19,23`** | 明显集中 |
| ≤5 帧条数 | 5 | **5** | 持平 |

**典型改善**：标定「帧 349 芬 命中」的偏差由 **−19 帧 → +1 帧**。

### 23.4 残余偏差（下一步方向）
修正后仍有 **平均 9 帧**、**最大 23 帧** 的残差，且**后段（帧 432~464，涉及"猎狗pro 2"）偏差偏大**
⇒ 说明还有其他因素：
1. **第二只敌人的出场/入场**（`spawn` 时刻 −7 帧；其后相关事件偏差 8~19 帧）；
2. **敌人侧的普攻前摇**尚未处理（本轮只改了干员侧 `_operator_tick`，
   敌人侧 `_enemy_tick` 仍是"冷却归零即结算"）；
3. 月见夜（远程）的攻击前摇比例可能与近战不同（远程常更短/更长）；
4. `attack_interval_frames` 的取整（31.5 → 32）也可能带来 1 帧级差异。

### 23.5 下一步
1. **给敌人侧加同样的前摇**（`_enemy_tick`）——由标定"猎狗命中芬 = 帧255"（较芬出手晚）反推其前摇；
2. **按兵种细化前摇比例**（近战/远程/敌人），并逐类用标定校准；
3. 复测至 **平均偏差 ≤2 帧**；
4. 完成后把 `WINDUP_RATIO` 等参数写入「信息查找链条」的单位层，成为标准提取项。
'''

s = io.open(DOC, encoding='utf-8').read()
if '二十三、★★攻击前摇修正生效' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **★★攻击前摇修正生效：平均偏差 14.50→9.06 帧（↓37.5%）、最大 52→23 帧（↓56%）2026-09-15**：'
       '①**数据层核查**：**干员表与敌人表都没有"攻击前摇"字段**（干员只有 phases/skills/talents/favorKeyFrames；'
       '敌人 `enemy_1000_gopro` 只有 stats）⇒ **前摇源自动画资源** ⇒ 改用「**攻击周期比例**」参数化；'
       '②**引擎修改**（`ak_sim/engine.py::_operator_tick`）：原为"冷却归零即 `_do_attack` 结算"（前摇 0），'
       '改为**先置 `attack_windup_left`（= round(攻击间隔×0.4375)）并逐帧递减，到点才结算伤害**；'
       '目标丢失则前摇重置；参数 `0.4375` 由标定反推（前摇 14 帧 ÷ 周期 32 帧）；'
       '**注**：`Unit` 类定义不在 engine.py 中，故用 `getattr` 容错避免依赖类属性初始化；'
       '③**★复测结果**：**平均 |偏差| 14.50 → 9.06 帧（↓37.5%）**；**最大偏差 52 → 23 帧（↓56%）**；'
       '偏差分布由 `0,1,2,4,5,7,9,10,11,11,13,14,19,19,23,29,32,52` 变为 '
       '**`1,1,4,5,5,7,7,7,8,8,10,10,11,11,13,13,19,23`（明显集中）**；'
       '**典型改善**：标定「帧349 芬 命中」偏差由 **−19 帧 → +1 帧**；'
       '④**残余偏差与下一步**：仍有平均 9 帧、最大 23 帧残差，**后段（帧432~464，涉及猎狗pro 2）偏大** ⇒ '
       '**(a) 敌人侧普攻前摇尚未处理**（本轮只改干员侧 `_operator_tick`，`_enemy_tick` 仍是"冷却归零即结算"）；'
       '**(b) 第二只敌人的出场/入场**（spawn −7 帧，其后相关事件偏 8~19 帧）；'
       '**(c) 月见夜（远程）前摇比例可能与近战不同**；**(d) `attack_interval_frames` 取整（31.5→32）的 1 帧级差异**；'
       '⇒ **下一步：给敌人侧加同样前摇、按兵种细化比例、逐类用标定校准，复测目标"平均偏差 ≤2 帧"**，'
       '并把 `WINDUP_RATIO` 等参数写入「信息查找链条」的单位层成为标准提取项；'
       '⑤**新增 `sim/draft/probe_windup_field.py`**（数据层前摇字段核查）；'
       '⑥**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\probe_windup_field.py', r'sim\draft'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py',
                  r'sim\draft\ak_sim')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
