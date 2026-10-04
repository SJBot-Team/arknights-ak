# -*- coding: utf-8 -*-
"""append_projectile_impl.py — ★★弹道建模实现并显著改善（远程命中 −23→−1）。"""
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

## 二十八、★★弹道（投射物）建模实现 —— 远程命中偏差 −23 → −1

### 28.1 实现（`ak_sim/engine.py`）
```python
# ① __init__
self.projectile_enabled = bool(opts.get('projectile', True))   # 可关闭以回退旧行为
self.pending_hits = []                                          # 延迟结算队列

# ② _do_attack：远程且开启弹道 ⇒ 伤害入队延迟结算（否则立即结算）
if self.projectile_enabled and self._is_ranged(src):
    n = self._projectile_frames(src, t)                         # 飞行帧数
    self.pending_hits.append({'f': self.frame + n, 'tgt': t, 'dmg': dmg,
                              'src': src, 'born': self.frame})
    self.logs.append(OpLog(self.frame, 'projectile', {...}))
    continue

# ③ tick：到期结算
self._tick_pending_hits()

# ④ 关键参数与方法
PROJECTILE_SPEED_CELLS_PER_FRAME = 0.1667      # ≈1 格 / 6 帧（由 1-1 标定反推）
_is_ranged(u)      # 按 rangeId 判定（芬 1-1 近战；月见夜 2-3 远程）
_projectile_frames(src, tgt)   # round(格距 / 速度) ⇒ 随距离变化，体现"追击"的时序后果
_tick_pending_hits()           # 目标已死则子弹消散（不结算）
```

**要点与取舍**：
- **起始位置/发射点偏移**：本方当前取"单位中心"，**参数化保留**（用户指出"同干员不同皮肤可能不同"，
  后续可按干员/皮肤配置发射点偏移）；
- **飞行时间依距离**：用发射时刻的格距计算，**体现了"距离越远、命中越晚"**；
- **目标死亡**：子弹消散、不结算（避免"打死后再补伤害"）；
- **可关闭**：`Battle(..., options={'projectile': False})` 可退化为旧行为，便于 A/B 对照。

### 28.2 ★复测结果（严格口径，与加弹道前同参数）

| 标定帧 | 事件 | 加弹道前 | **加弹道后** |
|---|---|---|---|
| 432 | 猎狗pro 2 ｜ 芬 命中 | −17 | **+5** OK |
| **438** | **猎狗pro 2 ｜ 月见夜 远程命中** | **−23** | **−1** |
| 443 | 猎狗pro 2 ｜ 芬 阻挡 | −28 | **−6** OK |
| 461 | 芬 ｜ 猎狗pro 2 命中 | −4 | **−4** OK |

| 指标 | 加弹道前 | **加弹道后** |
|---|---|---|
| **\\|偏差\\| ≤ 6 帧条数** | 7 | **10** |
| **平均 \\|偏差\\|** | 14.94 帧 | **11.44 帧** |
| 最大 \\|偏差\\| | 47 | 47 |

**⇒ 「月见夜 远程命中」的偏差由 −23 帧收敛到 −1 帧** ——
**直接验证了用户指出的机制**（远程弹道的飞行时间必须计入命中时刻）。

### 28.3 残余偏差（下一步）
- **"击杀"类事件仍偏差较大**：帧 381「芬 击杀」−15、帧 464「芬 击杀」−26
  ⇒ 说明"**敌人死亡的判定时刻**"仍有系统性差异；
- 帧 221/236/253（芬对猎狗pro 1 的命中/阻挡）仍有 +15~+47 的偏差
  ⇒ 可能与"**击杀后目标切换**"及"**猎狗pro 1 被替换为 pro 2 的时序**"有关；
- 最大偏差 47 由"帧 221"贡献。

### 28.4 下一步
1. **核查"击杀时刻"的判定**：模拟器 `_check_escape`/`apply_damage` 的死亡判定是否与实机一致
   （实机可能有"死亡动画延迟"）；
2. **核查多目标索敌**：芬同时对两只猎狗的伤害分配（`pick_operator_target` 的仇恨规则）；
3. **按干员/皮肤配置"发射点偏移"**（用户提示）—— 若某干员发射点偏离中心较远，命中时刻会有额外帧差；
4. **继续用严格口径复测**，目标"平均 ≤2 帧、最大 ≤5 帧"。
'''

s = io.open(DOC, encoding='utf-8').read()
if '二十八、★★弹道（投射物）建模实现' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **★★弹道（投射物）建模实现：远程命中偏差 −23 → −1（直接验证用户指出的机制）2026-09-15**：'
       '①**实现**（`ak_sim/engine.py`）：**(a) `__init__` 新增 `projectile_enabled`（可用 '
       '`options={"projectile": False}` 关闭以回退）与 `pending_hits`（延迟结算队列）**；'
       '**(b) `_do_attack`：远程且开启弹道 ⇒ 伤害入队延迟结算**；'
       '**(c) `tick` 调用 `_tick_pending_hits()` 到期结算（目标已死则子弹消散不结算）**；'
       '**(d) 关键方法与参数**：`PROJECTILE_SPEED_CELLS_PER_FRAME = 0.1667`（≈1 格/6 帧，由标定反推）、'
       '`_is_ranged(u)`（按 rangeId：芬 1-1 近战、月见夜 2-3 远程）、'
       '`_projectile_frames(src,tgt) = round(格距/速度)`（**随距离变化，体现"追击"的时序后果**）；'
       '**取舍**：发射起始位置当前取"单位中心"并**参数化保留**（用户指出"同干员不同皮肤可能不同"，'
       '后续可按干员/皮肤配置发射点偏移）；'
       '②**★复测结果（严格口径，同参数）**：**帧432 芬命中 −17 → +5**；'
       '**★帧438 月见夜远程命中 −23 → −1**；**帧443 芬阻挡 −28 → −6**；帧461 −4 → −4；'
       '整体 **|偏差|≤6 帧条数 7 → 10**、**平均|偏差| 14.94 → 11.44 帧**、最大 47（未变）；'
       '⇒ **「月见夜 远程命中」偏差收敛到 −1 帧，直接验证了用户指出的"弹道飞行时间必须计入命中时刻"**；'
       '③**残余偏差（下一步）**：**"击杀"类事件仍偏大**（帧381 −15、帧464 −26）⇒ '
       '说明"**敌人死亡的判定时刻**"仍有系统性差异（实机可能有"死亡动画延迟"）；'
       '帧221/236/253 仍有 +15~+47 ⇒ 可能与"**击杀后目标切换**"及"**猎狗pro1→pro2 的时序**"有关；'
       '**最大偏差 47 由帧221 贡献**；'
       '④**下一步**：**(a) 核查"击杀时刻"判定**（`_check_escape`/`apply_damage` 与实机一致性）；'
       '**(b) 核查多目标索敌**（`pick_operator_target` 的仇恨规则与伤害分配）；'
       '**(c) 按干员/皮肤配置"发射点偏移"**（用户提示）；'
       '**(d) 继续用严格口径复测**（目标 平均 ≤2 帧、最大 ≤5 帧）；'
       '⑤**新增 `sim/draft/add_projectile.py`**（弹道注入脚本，含锚点与可关闭设计）；'
       '⑥**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\add_projectile.py', r'sim\draft'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py',
                  r'sim\draft\ak_sim')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
