# -*- coding: utf-8 -*-
"""append_round59.py — 第 59 轮：费用条采样自检落地（把失效变成显式失败）。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''
### 7.130 费用条采样自检落地：`plugins/clock/bar_sanity.py`（测试 3/3 PASS）

针对 §7.128 那类"ROI 失效却照常输出结论"的风险，新增自检模块，把失效**变成显式失败**：

| 规则 | 内容 |
|---|---|
| 1 | **费用非递减**（同局费用只涨或不变） |
| 2 | **费用不变时填充不应显著减小**（容差 40px，容忍回绕与动画） |
| 3 | **费用一次跳 >1** ⇒ 报"采样间隔 ≥1 秒或有漏读"（相位无法消歧） |
| 4 | **费用 +1 时推得帧数应 ≥30**（`30×Δc + Δ相位 mod 30`） |

**测试**（`apps/test_bar_sanity.py`，用两轮真实序列）：
```
OK  A 上一轮有效序列(连续段)     自检=True   期望=True
OK  B 本轮失效序列               自检=False  期望=False
      · #2: 费用不变（11）但填充从 180px 降到 100px（超过容差 40px）   ← 正是本轮失效的特征
OK  C 费用一次跳 2               自检=False  期望=False
汇总: 费用条自检 A/B/C 全部 PASS
```
⇒ 本轮那批无效样本，从此会被自检**当场拒绝**，不会再被当成"误差统计"输出。

（顺带修了我自己的一个公式错误：费用 +1 时相位必须**跨过一次回绕**，
即推得帧数 = 30×Δc + (Δ相位 mod 30) ≥ 30；我第一版写成 `30 + sub - psub`，
在 sub>psub 时给出个位数，把正例误判成失效。）

### 7.131 断点（下一轮）
1. **复核本轮链路**：`verify_phase_precision.py` 应打印 `UiState` 的命中证据（这次没打印，
   无法判断本轮实际进的是不是 H12-4 演习链路）；
2. **重定位费用条 ROI**：在"费用未满"窗口用 §7.68 的帧间差分法复核 `(1739,805,1919,818)`；
3. 把自检接进采样流程（不通过即**拒绝输出结论**）；
4. 实机相位精度：**§7.114 的 |误差| 中位 0.94 帧仍是当前唯一有效结论**（本轮样本已作废）。
'''

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.129 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, SEC + '\n### 7.132 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.130/§7.131')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第五十九轮（费用条采样自检落地）**：针对 §7.128"ROI 失效却照常输出结论"的风险，'
       '新增 `plugins/clock/bar_sanity.py`（费用非递减、费用不变时填充不显著减小、费用跳>1 报间隔过大、'
       '费用+1 时推得帧数须≥30）+ `apps/test_bar_sanity.py`，**用两轮真实序列做正反例，测试 3/3 PASS**：'
       'A 上一轮有效序列⇒通过；B 本轮失效序列⇒被抓出（"费用不变但填充 180→100"）；C 费用跳 2⇒报出；'
       '⇒ 本轮那批无效样本从此会被**当场拒绝**，不再被当成误差统计输出；'
       '②顺带修正我自己的公式错误：费用 +1 时相位必须跨过一次回绕，推得帧数 = 30×Δc + (Δ相位 mod 30) ≥ 30，'
       '我第一版写成 `30 + sub - psub`、在 sub>psub 时给出个位数，把正例误判为失效；'
       '③**断点**：复核本轮链路（脚本未打印 UiState 命中证据）、在未满窗口用帧间差分法重定位费用条 ROI、'
       '把自检接进采样流程（不通过即拒绝输出结论）；'
       '**§7.114 的 |误差| 中位 0.94 帧仍是当前唯一有效的实机精度结论**（本轮样本已作废）；'
       '④合规：仅演习、理智未消耗；不碰游戏内存。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第五十九轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
for rel in (r'code\vision\plugins\clock\bar_sanity.py', r'code\vision\apps\test_bar_sanity.py'):
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', rel), os.path.join(DST, rel))
print('同步完成')
