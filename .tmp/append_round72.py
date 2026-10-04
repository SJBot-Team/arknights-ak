# -*- coding: utf-8 -*-
"""append_round72.py — 第 72 轮：★--debug 揭示 PRTS+ 完整计时机制（验证用户说法）。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''
### 7.178 用户的两条纠正（本轮修正）
1. **"0 帧暂停"不必严格在第 0 帧**：我暂停时费用条已涨了一段，但这**不影响 PRTS+ 的时间识别** ——
   它**根据费用条的相对长度确定"位于这一秒的第几帧"**，**只要在第一秒内暂停即可**；
2. **启动逻辑要选对**：它区分"**局外自动进关**"与"**局内开始**"两种启动方式
   （命令行即 `--autoenter` 的有无），用户提醒我不要仍用局外模式。

### 7.179 【★★★关键】`--debug` 揭示 PRTS+ 的完整计时机制

在**演习中进关并在第一秒内暂停**后，用
`prts+.exe --xlsm D:\\__soft\\ak\\prts_plan_h124.xlsm --debug` 运行，输出如下（节选）：

```
INFO  - Excel file path: D:\\__soft\\ak\\prts_plan_h124.xlsm
INFO  - Connected to Excel file: ..., workbook owned: False, excel owned: False
DEBUG - Set minimum wait time to 0.02
DEBUG - Set frame wait time to 0.1
DEBUG - Set general wait time to 0.3
DEBUG - Set bullet threshold to 15.0          ← 子弹时间阈值
DEBUG - Set frame threshold to 2.0            ← 帧容差 = 2 帧（与我们的判据一致）
INFO  - Setting initial time counter to 0
INFO  - Setting initial tick to 18            ← ★★★ 从画面读出"当前费用条相位"！
INFO  - Loaded map data for H12-4
INFO  - Transformed map to view, size: 9x13
INFO  - Getting current action at row 2       ← ★ 直接从第 2 条开始（跳过 row1 令）
INFO  - Get action: Action(cost=20, tick=0, time=20, DEPLOY, 蕾缪安, G9, DOWN)
INFO  - Memorized 蕾缪安 location at (8, 2)
DEBUG - Performing action: ... 蕾缪安 G9 tile_pos=(8,2)
DEBUG - Too much time, resuming and entering bullet time   ← ★ 恢复 + 进入"子弹时间"
```

**由此得到它的完整机制**（与我们的方案高度同源）：
1. **`initial tick` 从画面读取** —— 即"**费用条相对长度 → 这一秒的第几帧**"，
   **完全印证用户说法**（这也是我暂停位置不影响它的原因）；
2. **内部计时 = `time counter`（秒） + `tick`（秒内帧）**，与我们"费用整数 + 相位"同构；
3. **核心手段是"子弹时间"（暂停）**：`Too much time ⇒ resuming and entering bullet time`
   ⇒ 它会**先恢复游戏、再重新进入暂停**来对齐时间（这也解释了我观察到"游戏被它恢复"）；
4. **`frame threshold = 2.0`** ⇒ 它的帧容差是 **2 帧**，与我们相位精度的 ±2 帧判据一致；
5. **`bullet threshold = 15.0`** ⇒ 距目标 15 帧以内才进入子弹时间。

### 7.180【待查】"操作顺序有误"的表现与本次未生效的操作
- 用户此前的判断是"**开局暂停次数错误导致它的操作顺序有误**"，本次 debug 里表现为
  **`Getting current action at row 2`** —— 它**直接从第 2 条（蕾缪安）开始，跳过了第 1 条（令）**；
- 同时我方图像识别显示：它执行该部署后**费用并未被扣掉**（费用仍涨到 20 封顶）
  ⇒ **它的这次部署没有真正生效**（或未被我采到）；
- 结合 §7.175（上次它部署"令"后卡死判负），可以确认：**在"费用必然封顶"的 H12-4 里，
  它的暂停/计时状态很容易错位**，这正是用户要我观察的核心现象。

### 7.181 下一步
1. **给出干净的观察环境**：进关后**在第一秒内暂停**（`apps/enter_and_pause.py` 已能做到），
   再以 `--debug` 从**局内**启动，并把它的 debug 日志与我们的逐帧识别**对齐到同一时间轴**；
2. **重点观察"费用封顶→重新流动"边界**处它的 `time/tick` 如何跳（验证"多记/少记一次"的方向）；
3. 也可改用一局**不会立刻封顶**的场景（或把轴表换成低费用起手的），以便它在正常区间内完整跑通。
'''

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.177 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, SEC + '\n### 7.182 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.178~§7.181')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第七十二轮（★--debug 揭示 PRTS+ 完整计时机制）**：'
       '①**用户两条纠正**：(a) "0 帧暂停"**不必严格第 0 帧**——它按**费用条相对长度**确定"这一秒的第几帧"，'
       '**只要在第一秒内暂停即可**；(b) 启动逻辑要选对（`--autoenter` 的有无 = 局外自动进关 / 局内开始）；'
       '②**★关键：`--debug` 输出揭示其完整机制**（在**演习中进关并在第一秒内暂停**后运行）：'
       '`Setting initial tick to 18` ⇒ **从画面读出当前费用条相位**（完全印证用户说法）；'
       '`Setting initial time counter to 0` ⇒ 内部计时 = **秒计数 + tick**（与我们"费用整数+相位"同构）；'
       '`Set frame threshold to 2.0` ⇒ **它的帧容差是 2 帧**（与我们的 ±2 帧判据一致）；'
       '`Set bullet threshold to 15.0` ⇒ 距目标 15 帧内进入"子弹时间"；'
       '`Too much time, resuming and entering bullet time` ⇒ **它的核心手段是"暂停（子弹时间）"**，'
       '且会"先恢复再重新暂停"来对齐（解释了我观察到游戏被它恢复）；'
       '③**"操作顺序有误"的表现**：debug 显示 `Getting current action at row 2` ⇒ **它直接从第 2 条（蕾缪安）开始、'
       '跳过第 1 条（令）**；且我方识别显示该次部署**费用未被扣掉**（费用仍涨到 20 封顶）⇒ 这次操作**未真正生效**；'
       '结合 §7.175（上次部署"令"后卡死判负）⇒ **在"费用必然封顶"的 H12-4 里它的暂停/计时状态很容易错位**；'
       '④**下一步**：进关后在第一秒内暂停（`apps/enter_and_pause.py` 已可做到）再以 `--debug` 从**局内**启动，'
       '把它的 debug 日志与我们的逐帧识别**对齐到同一时间轴**；重点观察"封顶→重新流动"边界处 `time/tick` 的跳变；'
       '或改用**不会立刻封顶**的场景让它完整跑通；'
       '⑤**合规**：全程在**演习**中进行，未消耗理智；已终止进程、未留后台任务。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第七十二轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
for rel in (r'code\vision\apps\enter_and_pause.py', r'code\vision\apps\run_prts_compare.py'):
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', rel), os.path.join(DST, rel))
print('同步完成')
