# -*- coding: utf-8 -*-
"""append_round53.py — 第 53 轮：h12-4 首龙时刻的完整证据链（案例核心量化结论）。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''
### 7.111 【案例核心结论】作者记录的"29.0s 落首龙"是**按键意图时刻**，实际最早 38.0s（三方独立证据）

本轮把 §7.53 的悬案彻底量化。作者轴表的实际序列（`parse_cyberplastic` 读出）：

```
[0]  1.50s  令     deploy  C12   cost=11
[1] 20.00s  蕾缪安  deploy  G9    cost=20
[2] 25.13s  蕾缪安  skill
[3] 27.17s  蕾缪安  skill
[4] 28.77s  令     skill
[5] 29.00s  弦惊   deploy  D11   ← 争议点
```

#### 关键澄清：`cost` 字段是"**按键那一刻画面显示的费用**"，不是干员费用
- 令满潜是 **10 费**（我们 `UNIT_CONFIG`：令 potential=6），而轴表记 `cost=11`
  ⇒ 11 是 t=1.5s 时画面上的费用数字（10+1.5→显示 11），**不是**干员费用。
- 顺带印证：令@1.5s 部署后剩 1.5，攒到 t=20.0s 正好 **20**（= 轴表记的 `cost=20`）✓ 自洽。

#### 费用账本（cap=20、初始 10、+1/s；令 10、蕾缪安 20、弦惊 18）
| 时刻 | 事件 | 费用 |
|---|---|---|
| 1.5s | 部署令 | 11.5 → **1.5** |
| 20.0s | 部署蕾缪安（正好满） | 20.0 → **0** |
| **38.0s** | **弦惊最早可部署**（攒 18 需 18s） | 18 |
| 29.0s（作者记录） | 弦惊 | **只有 9** ✗ |

#### 三方独立证据完全一致
1. **费用账本（解析）**：29.0s 时费用 = 9，需 18 ⇒ 不可能；
2. **模拟器运行日志**：该时刻读出 `need=18, have=9`（**独立来源，数值完全相同**）；
3. **模拟器实跑**（本轮新增，参数化搜索 `sim/draft/probe_first_dragon.py`）：
   把弦惊排在 29.0s ⇒ **顺延到 38.8s 才落地**；而只上令时弦惊 **18.0s** 即可落地（与账本一致）。

⇒ **结论**：作者轴表里的时刻是**按键意图**（PRTS+ 在费用不足时会等待），
**实际最早可行落首龙 = 38.0s（账本）/ 38.8s（实跑，含部署帧对齐）**。
这也解释了案情里"模拟器 38.8s vs 作者 29.0s"的全部差异 —— **不是模拟器偏慢，而是作者记录的是按键时刻**。

#### 对后续打图的意义
- 若要与作者轴表对齐，**必须按"费用可行时刻"重排**（把每条部署的触发时刻顺延到费用足够那一刻），
  否则实机会表现为"按了但没放下去"，与 PRTS+ 的行为一致；
- `probe_first_dragon.py` 可复用于任意关卡的"最早可行时刻"求解。

### 7.112 本轮新增
`sim/draft/probe_first_dragon.py`：费用账本（解析）+ 模拟器实跑的参数化搜索，
输入令/蕾缪安/弦惊的部署时刻，输出首龙最早落地时刻与战果。
'''

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.110 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, SEC + '\n### 7.113 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.111/§7.112')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第五十三轮（案例核心结论：29.0s 是按键意图时刻，实际最早 38.0s，三方证据一致）**：'
       '①**读清作者轴表序列**：令@1.50s C12 cost=11 → 蕾缪安@20.00s G9 cost=20 → 弦惊@29.00s D11；'
       '②**关键澄清**：轴表 `cost` 字段是"**按键那一刻画面显示的费用**"，**不是干员费用**'
       '（令满潜实为 10 费；11 = t=1.5s 时画面数字）——顺带印证：令@1.5s 剩 1.5，攒到 t=20.0s 正好 20（= 轴表 cost=20）✓；'
       '③**费用账本**：1.5s 部署令(11.5→1.5) → 20.0s 部署蕾缪安(满 20→0) → **弦惊最早 38.0s**（攒 18 需 18s）；'
       '而作者记的 29.0s 时**费用只有 9** ✗；'
       '④**三方独立证据完全一致**：(a) 解析账本 9/18 不够；(b) 模拟器运行日志 `need=18, have=9`（数值完全相同）；'
       '(c) **本轮新增参数化实跑**：弦惊排 29.0s ⇒ **顺延到 38.8s 落地**，只上令时 **18.0s** 即可落地（与账本一致）；'
       '⑤**结论**：作者轴表时刻是**按键意图**（PRTS+ 费用不足时会等待），**实际最早可行落首龙 = 38.0s(账本)/38.8s(实跑)**；'
       '⇒ 案情"模拟器 38.8s vs 作者 29.0s"的全部差异**不是模拟器偏慢**，而是作者记的是按键时刻；'
       '⑥**对打图的意义**：与作者轴表对齐时必须按"**费用可行时刻**"重排（部署顺延到费用足够那一刻），'
       '否则实机表现为"按了但没放下去"（与 PRTS+ 行为一致）；'
       '⑦新增 `sim/draft/probe_first_dragon.py`（账本+实跑的可复用搜索）；'
       '⑧合规：仅模拟器侧计算与读轴表，未触碰游戏；未消耗理智。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第五十三轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
shutil.copy2(r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\probe_first_dragon.py',
             os.path.join(DST, 'sim', 'draft', 'probe_first_dragon.py'))
print('同步完成')
