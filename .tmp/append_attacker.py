# -*- coding: utf-8 -*-
"""append_attacker.py — ★伤害事件补"攻击者"字段；揭穿 +40 假偏差。"""
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

## 三十六、★伤害事件补「攻击者」字段 —— 揭穿 +40 帧的假偏差

### 36.1 问题
残差中"**帧 438「月见夜 远程命中」+40 帧**"看似是模拟器错误。追踪发现：
`extract_events` 的伤害事件是**由"血量变化"推断**的，**只有受害者、没有攻击者**
⇒ 无法区分"同一目标被谁打" ⇒ 对应表把"标定 432（芬打 pro2）"错配成"月见夜打 pro2"。

### 36.2 修正
从切片 `ops` 中取攻击者：
```python
# 切片的 ops 元素结构（实测）：{'kind': 'hit', 'detail': {'src','tgt','dmg','hp_after'}}
for o in (fr.get('ops') or []):
    if str(o.get('kind') or o.get('type')) != 'hit': continue
    payload = o.get('detail') or o.get('data') or o
    if 目标名匹配受害者: src_name = payload.get('src'); break
⇒ 伤害事件新增字段 `src`（攻击者）
```
（踩坑：一开始按 `o['type']`/`o['data']` 取值 ⇒ 全为 None；实际是 **`o['kind']`/`o['detail']`**。）

### 36.3 ★修正后的完整伤害表（1-1 复刻）

| 帧 | 受害者 | **攻击者** | 伤害 |
|---|---|---|---|
| 206 / 249 / 292 / 335 / 378 | 芬 | **猎狗pro** | 13 |
| **220 / 253 / 286 / 319 / 352** | 猎狗pro（EN1） | **芬** | 325 |
| 413 / 456 | 芬 | **猎狗**（EN2） | 9 |
| **438** | 猎狗（EN2） | **月见夜** | **569** |
| 478 | 猎狗（EN2） | 月见夜 | 251 |

### 36.4 ★结论：+40 是"对应表错配"，不是模拟器错误
- 标定「**帧 438 月见夜 远程命中**」↔ 模拟器「**帧 438 月见夜 → 猎狗 569**」
  ⇒ **完全一致（0 帧）**；
- 而**模拟器中并没有"芬打 EN2"的事件**（EN2 只被月见夜打了 2 次：438/478）
  ⇒ 标定「帧 432 芬 命中 猎狗pro 2」在模拟器侧**无对应事件**（或对应"芬打 EN1"的某次）。
- ⇒ 上一轮的 **+40** 是**对应表错配**造成的假偏差。

### 36.5 下一步
1. **对应表增加"攻击者"列**：`(标定帧, 说明, 类别, 目标, 攻击者, 序号)`
   ⇒ 用 `(受害者, 攻击者)` 共同定位事件，彻底消除歧义；
2. 重跑统计，预期残余仅剩：出怪时刻（−7）、以及"标定 432/464"等**标定与模拟器不一一对应**的条目；
3. 之后继续收敛（目标 平均 ≤2 帧、最大 ≤5 帧）。
'''

s = io.open(DOC, encoding='utf-8').read()
if '三十六、★伤害事件补「攻击者」字段' not in s:
    io.open(DOC, 'a', encoding='utf-8').write(EXTRA)
    print('已更新复刻报告')

ADD = (' **★伤害事件补「攻击者」字段 —— 揭穿 +40 帧的假偏差（2026-09-15）**：'
       '①**问题**：残差"帧438「月见夜远程命中」+40"看似模拟器错误；追踪发现 '
       '**`extract_events` 的伤害事件是由"血量变化"推断的，只有受害者、没有攻击者** ⇒ '
       '无法区分"同一目标被谁打" ⇒ 对应表把"标定432（芬打 pro2）"错配成"月见夜打 pro2"；'
       '②**修正**：从切片 `ops` 取攻击者 ⇒ 伤害事件新增 `src` 字段；'
       '**切片的 ops 实际结构为 `{"kind":"hit","detail":{"src","tgt","dmg","hp_after"}}`**'
       '（踩坑：一开始按 `o["type"]`/`o["data"]` 取值 ⇒ 全 None；实际是 **`o["kind"]`/`o["detail"]`**）；'
       '③**★修正后的完整伤害表**：**帧206/249/292/335/378 芬 ← 猎狗pro（13）**；'
       '**帧220/253/286/319/352 猎狗pro(EN1) ← 芬（325）**；'
       '**帧413/456 芬 ← 猎狗(EN2)（9）**；**帧438 猎狗(EN2) ← 月见夜（569）**；**帧478 猎狗 ← 月见夜（251）**；'
       '④**★结论：+40 是"对应表错配"而非模拟器错误** —— 标定「帧438 月见夜 远程命中」↔ '
       '模拟器「帧438 月见夜→猎狗 569」⇒ **完全一致（0 帧）**；而**模拟器中并无"芬打 EN2"的事件**'
       '（EN2 只被月见夜打了 2 次：438/478）⇒ 标定「帧432 芬 命中 猎狗pro 2」在模拟器侧无对应事件；'
       '⑤**下一步**：**对应表增加"攻击者"列** `(标定帧, 说明, 类别, 目标, 攻击者, 序号)`，'
       '用 `(受害者, 攻击者)` 共同定位事件以彻底消除歧义；重跑统计（预期残余仅剩出怪时刻 −7 与'
       '"标定与模拟器不一一对应"的条目）；**目标 平均 ≤2 帧、最大 ≤5 帧**；'
       '⑥**合规**：仅本地模拟计算与用户提供的数据；未触碰游戏文件/内存。 | 2026-09-15 |')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
r = r.replace(ra, ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已记录')
for src, sub in ((DOC, r'knowledge\04_数据对应与核验'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\probe_midn.py', r'sim\draft'),
                 (r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\events.py',
                  r'sim\draft\ak_sim')):
    d = os.path.join(DST, sub, os.path.basename(src))
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy2(src, d)
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
print('同步完成')
