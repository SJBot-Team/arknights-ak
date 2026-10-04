# -*- coding: utf-8 -*-
"""append_straight_path.py — ★直线寻路已实现且斜率吻合；但第2只仍在(4,4)被过早阻挡。"""
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

## 四十四、直线寻路已实现（斜率吻合）；但第 2 只仍在 (4,4) 被过早阻挡

### 44.1 实现
`_enemy_move` 增加「**直线优先**」分支（`add_straight_path.py`）：
```python
if self.straight_path:
    gx, gy = target_tile[1] + 0.5, target_tile[0] + 0.5          # 目标格中心
    if self.map.line_is_clear((ex, ey), (gx, gy), flying=e.flying):
        # 直接朝目标中心直线推进（允许斜向），并按 move_speed×FRAME_TIME 位移
        ...; return
# 否则回退到原 navmap 逐格导航（贴墙/绕障）
```
并在 `BattleMap` 新增 `walkable_at()` 与 `line_is_clear()`（按 0.15 格步长采样，判定线段是否穿过不可通行格）。
开关：`options={'straight_path': False}` 可回退。

### 44.2 ★轨迹验证：斜率与 route4 完全吻合
| 帧 | 格 | pos (col,row) |
|---|---|---|
| 360 | (6,4) | (4.51, 6.47) |
| 376 | (5,4) | (4.59, 5.97) |
| 408 | (4,4) | (4.76, 4.97) |

**斜率 = (4.76−4.51)/(6.47−4.97) = 0.167**，而 **route4 的斜率 = (5−4)/(6−0) = 0.167**
⇒ **直线寻路实现正确**（此前为 L 形：col 恒 4.50 后突然横移）。

### 44.3 复测结果（对照）

| 标定帧 | 说明 | 直线寻路后 | 偏差 |
|---|---|---|---|
| 221 / 253 | 芬命中 猎狗pro | 218 / 251 | **−3 / −2** |
| 285 / 317 / 349 | 芬命中 猎狗pro | 284 / **317** / 350 | **−1 / 0 / +1** |
| 255 / 298 / 340 | 猎狗pro 命中 芬 | 247 / 290 / 333 | **−8 / −8 / −7** |
| 381 | 芬 击杀 猎狗pro | 383 | +2 |
| 438 | 月见夜 远程命中 猎狗 | 438 | **0** |
| 432 / 461 | 芬命中猎狗 / 猎狗命中芬 | **(缺)** | — |
| 464 | 芬 击杀 猎狗 | 479 | **+15** |

**统计**：可对齐 14/16；**≤6 帧 9 条**；平均 **4.36**；最大 15
（**前段"芬打猎狗pro"明显改善**：−3/−2/−1/**0**/+1；**后段"猎狗pro打芬"略变差**：−8/−8/−7）

### 44.4 当前断点：第 2 只仍"过早被阻挡"
轨迹显示它**只走到格 (4,4)**（pos 约 (4.76,4.97)）就停下，**未走到应有的 (3,4)**。
而格 (4,4) 与芬格 (3,5) 是**对角**（曼哈顿 2、中心距 1.414）⇒ **按"欧氏 ≤1.0"本不应阻挡**。
⇒ 需查：
1. **究竟是谁阻挡了它**（打印该帧所有单位的 `blocking`/`blocked_by` 与相互距离）；
2. 是否 `_block_scan` 的 `BLOCK_DISTANCE=1.0` 之外还有**其它阻挡路径**（如 `_process_checkpoints`
   的 `WAIT`/`blockFragment`，或"红门/蓝门格"判定）；
3. 是否"直线分支"里的 `walkable_at` 判定使它提前停住（例如目标中心在墙内、线段被判不可通而回退 navmap，
   又因 navmap 以 `route_end` 为目标而走了别的路）。

### 44.5 下一步
1. 打印"帧 408~430 之间第 2 只的 `blocked_by`/各单位距离/`state`"，
   确认阻挡者与判定依据；
2. 若为"误阻挡"⇒ 修正；若为"路径回退"⇒ 修 `line_is_clear` 或用"分段直线"（先到检查点再转）；
3. 修正后复测：预期敌人经过 **(3,4)** ⇒ 进入芬（朝左）范围 ⇒
   **`dmg 猎狗←芬` 出现、标定帧 432/443/461/464 全部可对齐**；
4. **目标 平均 ≤2 帧、最大 ≤5 帧**。
'''

s = io.open(DOC, encoding='utf-8').read()
if '四十四、直线寻路已实现' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **直线寻路已实现且斜率吻合；第2只仍被过早阻挡（2026-09-15）**：'
       '①**实现**：`_enemy_move` 增加「**直线优先**」分支 —— 目标 = 当前目标格中心，'
       '`line_is_clear()` 判定线段可通则**直接朝目标直线推进（允许斜向）**，否则回退 navmap 逐格导航；'
       '并在 `BattleMap` 新增 `walkable_at()`/`line_is_clear()`（0.15 格步长采样）；'
       '开关 `options={"straight_path": False}` 可回退；'
       '②**★轨迹验证：斜率与 route4 完全吻合** —— 帧360(6,4) pos(4.51,6.47)、帧376(5,4) pos(4.59,5.97)、'
       '帧408(4,4) pos(4.76,4.97) ⇒ **斜率 (4.76−4.51)/(6.47−4.97)=0.167**，'
       '而 **route4 斜率 (5−4)/(6−0)=0.167** ⇒ **直线寻路实现正确**（此前为 L 形：col 恒 4.50 后突然横移）；'
       '③**复测**：**前段"芬打猎狗pro"明显改善**（帧221 **−3**、253 **−2**、285 **−1**、'
       '**317 0**、349 **+1**）；**后段"猎狗pro打芬"略变差**（255/298/340 ⇒ **−8/−8/−7**）；'
       '帧438 月见夜远程命中仍 **0**；帧381 **+2**；但 **帧432/461 仍缺**（芬仍未打第2只）、帧464 **+15**；'
       '**统计：可对齐 14/16、≤6 帧 9 条、平均 4.36、最大 15**；'
       '④**当前断点：第2只仍"过早被阻挡"** —— 轨迹显示它**只走到格 (4,4)**（pos≈(4.76,4.97)）就停下，'
       '**未走到应有的 (3,4)**；而格(4,4) 与芬格(3,5) 是**对角**（曼哈顿2、中心距1.414）⇒ '
       '**按"欧氏≤1.0"本不应阻挡**；'
       '⑤**需查**：**(a) 究竟是谁阻挡了它**（打印该帧所有单位的 `blocking`/`blocked_by` 与相互距离）；'
       '**(b) 是否有 `BLOCK_DISTANCE` 之外的阻挡路径**（如 `_process_checkpoints` 的 WAIT/`blockFragment`、'
       '红蓝门格判定）；**(c) 是否"直线分支"的 `walkable_at` 判定使其提前停住**'
       '（例如目标中心在墙内、线段被判不可通而回退 navmap，navmap 又以 `route_end` 为目标而绕路）；'
       '⑥**下一步**：打印帧408~430 之间第2只的 `blocked_by`/各单位距离/`state` 以确认阻挡者与依据；'
       '若误阻挡则修正；若路径回退则修 `line_is_clear` 或改用"分段直线"；'
       '修正后预期敌人经过 **(3,4)** ⇒ 进入芬朝左范围 ⇒ **`dmg 猎狗←芬` 出现、标定帧432/443/461/464 全部可对齐**；'
       '**目标 平均 ≤2 帧、最大 ≤5 帧**；'
       '⑦**新增 `sim/draft/add_straight_path.py`**；'
       '⑧**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\add_straight_path.py', r'sim\draft'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py',
                  r'sim\draft\ak_sim'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\battlemap.py',
                  r'sim\draft\ak_sim')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
