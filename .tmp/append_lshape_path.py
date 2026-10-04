# -*- coding: utf-8 -*-
"""append_lshape_path.py — ★★★根因确认：寻路走"L 形（先列后行）"而 routes 要求"直线"。"""
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

## 四十三、★★★根因确认：寻路走「L 形」而 routes 要求「直线」

### 43.1 逐格实测（第 2 只，uid=3，route4）

| 帧 | 格 | pos (col,row) | 状态 |
|---|---|---|---|
| 360 | (6,4) | (4.50, 6.49) | MOVE |
| 377 | (5,4) | (4.50, 6.00) | MOVE |
| 409 | (4,4) | (4.50, 4.99) | MOVE |
| 415 | (4,4) | (**4.55**, 4.84) | MOVE ← **开始横移** |
| 430 | (4,4) | (**4.82**, 4.45) | MOVE |
| 445 | (4,4) | (**5.00**, 4.07) | MOVE ← **横移到 col=5.0** |
| 450 | **(3,5)** | (5.00, 4.00) | **BLOCKED** |

### 43.2 判读
- 前段（帧 360~409）：**col 恒为 4.50**（正是"格 4 的中心"）⇒ **沿格中心竖直向上**；
- 后段（帧 415~445）：**col 由 4.50 横移到 5.00**（row 只从 4.84 到 4.07）
  ⇒ **横向分量远大于纵向** ⇒ **典型的「L 形路径（先列后行）」**；
- 最终在 **(3,5)** 被阻挡 —— 而 **(3,5) 是芬所在格**（重叠）。

### 43.3 route4 的正确语义
关卡 `routes[4]`：`startPosition={row:6,col:4}` → `endPosition={row:0,col:5}`，且：
- **`allowDiagonalMove: true`**（允许斜向）
- **`visitEveryTileCenter: false`**、**`visitEveryNodeCenter: false`**（**不强制过格中心**）

⇒ 语义是"**从起点直线走向终点**"：
`row 6→0`、`col 4→5` ⇒ **row=3 时 col=4.5** ⇒ **经过格 (3,4)**
—— **正是芬（朝左）攻击范围内的格** ⇒ **按正确寻路，芬本应能打到它**。

### 43.4 结论
**根因：本方寻路实现成了「L 形（先对齐列、再走行）」，未按 routes 的"直线/斜向"语义**，
导致：
1. 敌人**沿格中心竖直行进**（col 固定在 4.5），直到接近终点才横移；
2. 因而**不会经过 (3,4)**，而是在 **(3,5) 与芬重叠**处才被阻挡；
3. **芬（朝左）的攻击范围 `{(3,5),(3,4)}` 里没有它** ⇒ 芬不攻击它
   ⇒ 标定「帧432 芬命中 / 443 芬阻挡 / 461 猎狗命中芬 / 464 芬击杀」全部缺失。

### 43.5 修正方向（下一轮）
1. **重写敌人在 route 上的推进**为"**朝"当前目标点"直线插值**"：
   - 目标点：`endPosition`（或检查点序列的下一个），**不强制经过格中心**；
   - 每帧按 `move_speed × FRAME_TIME` 沿"到目标点"的单位向量推进；
   - 抵达目标点（或检查点）后切换下一目标；
2. **保留** `visitEveryTileCenter` / `visitEveryNodeCenter` 为可配置项（默认 false），
   以兼容确有"必须过格中心"的关卡；
3. **修正后复测**：预期敌人经过 **(3,4)** ⇒ 被芬阻挡在 **(3,4) 附近** ⇒
   `dmg 猎狗←芬` 出现、`kill 猎狗` 变为被芬击杀、标定「帧432/443/461/464」全部可对齐；
4. 目标 **平均 ≤2 帧、最大 ≤5 帧**。
'''

s = io.open(DOC, encoding='utf-8').read()
if '四十三、★★★根因确认' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **★★★根因确认：寻路走「L 形」而 routes 要求「直线」2026-09-15**：'
       '①**逐格实测（第2只 uid=3，route4）**：帧360 格(6,4) pos(4.50,6.49)；帧377 格(5,4) pos(4.50,6.00)；'
       '**帧409 格(4,4) pos(4.50,4.99)**（**前段 col 恒为 4.50 = 格4中心，沿格中心竖直向上**）；'
       '帧415 pos(**4.55**,4.84)、帧430 pos(**4.82**,4.45)、**帧445 pos(5.00,4.07)**（**后段 col 由 4.50 横移到 5.00**，'
       '横向分量远大于纵向）⇒ **典型「L 形路径（先列后行）」**；帧450 格**(3,5)** pos(5.00,4.00) **BLOCKED**'
       '（**(3,5) 正是芬所在格** ⇒ 与芬重叠）；'
       '②**route4 的正确语义**：`startPosition={row6,col4}` → `endPosition={row0,col5}`，且 '
       '**`allowDiagonalMove: true`、`visitEveryTileCenter: false`、`visitEveryNodeCenter: false`** '
       '⇒ 应为"**从起点直线走向终点**"：**row=3 时 col=4.5 ⇒ 经过格 (3,4)** '
       '—— **正是芬（朝左）攻击范围内的格** ⇒ 按正确寻路**芬本应能打到它**；'
       '③**★结论：根因是本方寻路实现成了「L 形（先对齐列、再走行）」，未按 routes 的"直线/斜向"语义**，'
       '导致 **(a) 敌人沿格中心竖直行进**（col 固定 4.5）、**(b) 不会经过 (3,4)**、'
       '**(c) 在 (3,5) 与芬重叠处才被阻挡**、**(d) 芬朝左范围 {(3,5),(3,4)} 里没有它 ⇒ 芬不攻击它** ⇒ '
       '标定「帧432 芬命中/443 芬阻挡/461 猎狗命中芬/464 芬击杀」全部缺失；'
       '④**修正方向（下一轮）**：**(1) 重写敌人在 route 上的推进为"朝当前目标点直线插值"**'
       '（目标点 = `endPosition` 或检查点序列的下一个，**不强制经过格中心**；每帧按 '
       '`move_speed × FRAME_TIME` 沿"到目标点"的单位向量推进；抵达后切换下一目标）；'
       '**(2) 保留 `visitEveryTileCenter`/`visitEveryNodeCenter` 为可配置项**（默认 false）以兼容特殊关卡；'
       '**(3) 修正后复测**：预期敌人经过 **(3,4)** ⇒ 被芬阻挡在 (3,4) 附近 ⇒ '
       '`dmg 猎狗←芬` 出现、`kill 猎狗` 变为被芬击杀、标定「帧432/443/461/464」全部可对齐；'
       '**目标 平均 ≤2 帧、最大 ≤5 帧**；'
       '⑤**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
