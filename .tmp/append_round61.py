# -*- coding: utf-8 -*-
"""append_round61.py — 第 61 轮：公式固化进代码 + 两轮实机数据互相印证（中位 0.59/0.80 帧）。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

SEC = '''
### 7.135 公式固化进代码并用两轮实机数据验证：**实机相位精度（中位 <1 帧）成立**

把 §7.133 修正后的公式固化进 `plugins/clock/frame_clock.py`：
```python
signed_phase_delta(p0, p1, modulus=30)   # 规范到 [-15,15)：算帧数必须用它，不能用 mod 30
frames_between(c0, p0, c1, p1)           # Δ费用×30 + 带符号Δ相位
```
并新增 `apps/test_frames_between.py`，用**手算样例 + 两轮真实实机样本**验证：

```
OK  手算 Δc=1 27→24 ⇒ 27（期望 27）
OK  手算 Δc=1 25→26 ⇒ 31（期望 31）
OK  手算 Δc=1  2→29 ⇒ 27（期望 27）      ← 关键方向：2→29 视为 −3，不是 +27
OK  B §7.114 真实样本: 7 对，|误差| 中位 0.59 帧
OK  C §7.128 真实样本: 10 对，|误差| 中位 0.80、最大 1.77 帧
汇总: 手算 PASS；B/C 全部 PASS
```

⇒ **两次独立实机测量（§7.114 与 §7.128）互相印证**，
共同支持结论：**"费用条相位 + 费用整数"可在真实战斗中把时间对齐到中位 <1 帧**
（判据 ≤2 帧）。§7.128 的"作废"判定正式撤回，那条记录保留作为**反面教材**
（说明"看起来不合理的数据"往往是自己的公式方向错了）。

### 7.136 剩余工作（与 §7.120 的上限锚点配合）
1. **封顶期间**仍不能由账本外推：必须用 `cost_cap_up`（上限突破）事件的精确帧作新锚点，
   且**锚点后要按新原点重新起算**（§7.124 实测锚点后首个 +1 间隔为 26 帧而非 30，说明相位被重置）；
   模拟器侧锚点已查明：**48.97s（上限 20→22）、53.03s（22→24）**；
2. **实机识别锚点**：候选为"费用数字由满/MAX 恢复增长、数字跳变、平民抵点提示、箱子爆炸"——
   这正是用户所说"图像识别只用于确定事件发生在哪一帧"的应用（§7.81）；
3. **链条收口**：把 `frames_between` 接进 `verify_phase_precision.py` 与自检（§7.130 规则 4），
   并把"上限锚点"做进费用尺，形成完整的"相位 + 锚点"时间轴。
'''

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.134 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, SEC + '\n### 7.137 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.135/§7.136')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
add = (' **第六十一轮（公式固化 + 两轮实机数据互相印证）**：'
       '①把修正后的公式固化进 `plugins/clock/frame_clock.py`：'
       '`signed_phase_delta(p0,p1)`（规范到 [-15,15)，**算帧数必须用它**）与 `frames_between(c0,p0,c1,p1)`；'
       '②新增 `apps/test_frames_between.py`，用**手算样例 + 两轮真实实机样本**验证并全部 PASS：'
       '手算 5/5（关键方向：`2→29` 视为 −3 ⇒ 27 帧，而非 +27）；'
       '**B §7.114 真实样本 7 对 |误差| 中位 0.59 帧**；**C §7.128 真实样本 10 对 中位 0.80、最大 1.77 帧**；'
       '③**结论**：两次独立实机测量互相印证 ⇒ **"费用条相位+费用整数"可在真实战斗中把时间对齐到中位 <1 帧**'
       '（判据 ≤2 帧）；**§7.128 的"作废"判定正式撤回**，该记录保留为反面教材'
       '（"看起来不合理的数据"往往是自己的公式方向错了）；'
       '④**剩余工作**：(a) 封顶期间不得由账本外推，须用 `cost_cap_up` 事件精确帧作新锚点、'
       '**锚点后按新原点重新起算**（模拟器锚点：48.97s 上限20→22、53.03s 22→24）；'
       '(b) 实机识别锚点候选=费用数字由满/MAX 恢复增长、数字跳变、平民抵点提示、箱子爆炸；'
       '(c) 把 `frames_between` 接进 `verify_phase_precision.py` 与 §7.130 自检规则 4，'
       '并把"上限锚点"做进费用尺，形成完整"相位+锚点"时间轴；'
       '⑤合规：仅演习、理智未消耗；不碰游戏内存。 | 2026-09-14 |')
r = r.replace(ra, add + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第六十一轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
for rel in (r'code\vision\apps\test_frames_between.py', r'code\vision\plugins\clock\frame_clock.py'):
    shutil.copy2(os.path.join(r'C:\Users\23922\Documents\ds_harness\ak', rel), os.path.join(DST, rel))
print('同步完成')
