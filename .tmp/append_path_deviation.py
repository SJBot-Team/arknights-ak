# -*- coding: utf-8 -*-
"""append_path_deviation.py — ★★★真因：route4 寻路偏离直线（应经(3,4)，实走(4,5)）。"""
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

## 四十二、★★★真因：route4 寻路偏离直线（索敌与范围数据均无问题）

### 42.1 攻击范围表（数据本身正确）
```
1-1  = {direction:1, grids:[{row:0,col:0},{row:0,col:1}]}                      ← 2 格
1-2  = {direction:1, grids:[{row:1,col:0},{row:0,col:0},{row:0,col:1},{row:-1,col:0}]}
3-12 = {direction:1, grids:[8 格]}                                            ← 远程
```
⇒ **`1-1` 就是"自身格 + 朝向 1 格"（标准近战）**，本方的 `range_grids=[[0,0],[1,0]]` **无误**。

### 42.2 索敌实现（也正确）
```python
def enemies_in_range(self, u):
    cells = self.cells_in_range(u)     # range_grids 按朝向展开
    return [e for e in ... if e.grid() in cells]     # 用格坐标判定
def pick_operator_target(self, u):
    ...  # 优先级：被自己阻挡 > 剩余距离小 > 创建早
```
⇒ "按格判定"是 AK 的常规做法；**"芬（朝左）打不到正下方 (4,5) 的敌人"完全符合数据**。

### 42.3 ★真因：敌人在"错误的位置"被阻挡
- **route4 是 `(row6, col4) → (row0, col5)` 的直线**；
- 参数化：`row: 6→0`、`col: 4→5` ⇒ **当 row=3 时 t=(6−3)/6=0.5 ⇒ col = 4.5**
  ⇒ **敌人应在格 (3,4)** —— **正是芬（朝左）攻击范围内的格**；
- **但实测它停在 `pos=(5.00, 4.00)` 即格 (4,5)**（芬的**正下方**，不在朝左范围内）
  ⇒ **寻路结果偏离了 route4 的直线**。

### 42.4 为何会偏离（待核）
很可能与**寻路实现**有关：
1. 关卡 `routes` 中含 `visitEveryTileCenter: false`、`visitEveryNodeCenter: false`、`allowDiagonalMove: true`
   —— 语义上应"沿直线走、不强制过格中心"；
   若本方把它实现成"**格中心节点序列**"，路径就会变成阶梯状 ⇒ 位置系统性偏移；
2. `navmap`/`next_node` 的生成方式（是否把"格中心"当作必经点）；
3. `move_speed=1.0` 格/秒 ⇒ 每帧 1/30 格；若沿阶梯走，横向/纵向分量会被分解 ⇒ **到达次序改变**。

### 42.5 下一步
1. **打印 route4 实际经过的格序列**（模拟器中逐帧 `grid()` 去重），与"直线应为 (6,4)→(5,4.x)→…→(3,4.x)→…→(0,5)"对照；
2. 检查 `navmap`/`next_node`/`_enemy_move` 是否强制"过格中心"；
3. 修正为**直线寻路**（不强制过格中心）后复测：
   - 预期敌人在 **(3,4)** 附近被芬阻挡 ⇒ **进入朝左的攻击范围** ⇒
     `dmg 猎狗←芬` 出现、`kill 猎狗` 变为被芬击杀、标定「帧432/443/461/464」全部可对齐；
4. 目标 **平均 ≤2 帧、最大 ≤5 帧**。

### 42.6 方法论小结（本轮价值）
本轮依次**排除**了：
- 阻挡半径取值（两版实测对比）；
- 攻击范围表数据（`1-1` 只有 2 格，正确）；
- 索敌规则（按格判定，且"被自己阻挡者优先"，实现正确）；
最终定位到 **"寻路路径偏离 routes 直线"** —— 这是一个**与阻挡/索敌都无关**的独立缺陷。
⇒ 说明"以事件精确帧判定"能**逐层剥离假设**，最终指向真正的机制缺陷。
'''

s = io.open(DOC, encoding='utf-8').read()
if '四十二、★★★真因：route4 寻路' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **★★★真因定位：route4 寻路偏离直线（索敌与范围数据均无问题）2026-09-15**：'
       '①**攻击范围表数据正确**：`range_table.json` 中 **`1-1 = {direction:1, grids:[{0,0},{0,1}]}`（仅 2 格）**、'
       '`1-2`（4 格）、`3-12`（8 格）⇒ **`1-1` 就是"自身格+朝向 1 格"（标准近战），本方 `range_grids=[[0,0],[1,0]]` 无误**；'
       '②**索敌实现也正确**：`enemies_in_range` 用 `e.grid() in cells`（按格判定），'
       '`pick_operator_target` 优先级为"**被自己阻挡 > 剩余距离小 > 创建早**" ⇒ '
       '**"芬（朝左）打不到正下方 (4,5) 的敌人"完全符合数据**；'
       '③**★真因：敌人在"错误位置"被阻挡** —— **route4 是 (row6,col4)→(row0,col5) 的直线**，'
       '参数化后 **row=3 时 col=4.5 ⇒ 敌人应在格 (3,4)**（正是芬朝左范围之内）；'
       '**但实测它停在 pos=(5.00,4.00) 即格 (4,5)**（芬正下方、不在朝左范围）⇒ **寻路结果偏离直线**；'
       '④**可能原因（待核）**：**(a) 关卡 routes 含 `visitEveryTileCenter:false`/`visitEveryNodeCenter:false`/'
       '`allowDiagonalMove:true`** ⇒ 语义应"沿直线走、不强制过格中心"，若本方实现成"格中心节点序列"'
       '就会变成阶梯状路径 ⇒ 位置系统性偏移；**(b) `navmap`/`next_node` 的生成方式**（是否把格中心当必经点）；'
       '**(c) `move_speed=1.0` 格/秒（每帧 1/30 格）** ⇒ 沿阶梯走会分解横纵分量、改变到达次序；'
       '⑤**下一步**：打印 route4 实际经过的格序列（逐帧 `grid()` 去重）与"直线应为 (6,4)→…→(3,4.x)→…→(0,5)"对照；'
       '检查 `navmap`/`next_node`/`_enemy_move` 是否强制"过格中心"；**修正为直线寻路后复测**：'
       '预期敌人在 **(3,4)** 附近被芬阻挡 ⇒ 进入朝左攻击范围 ⇒ `dmg 猎狗←芬` 出现、'
       '`kill 猎狗` 变为被芬击杀、标定「帧432/443/461/464」全部可对齐；**目标 平均 ≤2 帧、最大 ≤5 帧**；'
       '⑥**方法论小结**：本轮依次**排除**了「阻挡半径取值」（两版对比）、「攻击范围表数据」（实测正确）、'
       '「索敌规则」（按格判定+被阻挡优先，正确），最终定位到「**寻路路径偏离 routes 直线**」——'
       '一个与阻挡/索敌都无关的独立缺陷 ⇒ **"以事件精确帧判定"能逐层剥离假设、指向真正的机制缺陷**；'
       '⑦**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', os.path.basename(DOC)))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
