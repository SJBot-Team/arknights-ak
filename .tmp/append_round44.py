# -*- coding: utf-8 -*-
"""append_round44.py — 第四十四轮：渲染前置守卫落地；实机验证被"模拟器不渲染"阻塞。"""
import io
import os
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

DOC = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\41_模拟器与自动打图_首版实现.md'
REG = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
DST = r'E:\__file\ak_kb\kb'

DOC_SEC = '''
### 7.75 渲染前置守卫落地：`render_guard.py`（实机脚本的强制第一道关）

#### 本轮实测
给 `phase_precision_test.py` 补上渲染前置（先 `bring_to_front`，再做"画面在变"校验）后运行：

```
已把模拟器拉到前台（保证渲染）
渲染校验（画面在变）：★未通过 —— 模拟器可能被遮挡/最小化
⇒ 按 §7.72：直接退出，不把静止帧当成游戏状态
```

⇒ ①**规程生效**：脚本在"画面不动"时**拒绝做任何判断与注入**，而不是继续空点或把静止帧解释成游戏状态；
②**模拟器当前确实不在渲染**，且 `SetForegroundWindow` 未能恢复它（前台锁／窗口被最小化／被 DSH 覆盖）——
这一步需要**人在场把模拟器窗口恢复为可见**，属于外部前提，不是代码能单方面解决的。

#### 落地：`code/vision/plugins/capture/render_guard.py`
把规程固化成一行式守卫，供**所有**实机脚本复用：
- `ensure_foreground()`：尽力把模拟器拉回前台（失败不算错，只影响后续校验通过率）；
- `assert_rendering(cam, tries=4, interval=0.5, thresh=0.05)`：连采若干帧，
  相邻帧缩略图平均绝对差 > 0.05 即认为在渲染。阈值**极宽松**（正常战斗画面里飘字/特效/计时器远超它），
  而冻结帧是**精确的 0.0**（实测）⇒ 判据不会漏报、也不会误报；
- `guard_or_exit(cam)`：置前台 → 校验 → 不通过即 `SystemExit`。

#### 当前阻塞与后续
- **阻塞（外部前提）**：模拟器需保持可见/可渲染。恢复后即可直接接着跑
  `phase_precision_test.py`（脚本已具备：渲染前置 + 点击生效校验 + 章节回切 + 精度比对）。
- 不依赖模拟器渲染、可继续推进的部分：模拟器侧的轴表/坐标/伤害回归、文档与验收对照表整理。

### 7.76 待复核项（延续 §7.73，未变）
| 结论 | 状态 |
|---|---|
| 费用条 ROI ≈ y∈[805,817] | 大概率成立（该批帧费用单调变化 ⇒ 当时在渲染） |
| 费用封顶后相位停住 | **待复核**（需在确认渲染的前提下重测） |
| 相位↔墙钟精度（目标 ≤2 帧） | **未成立**（第四十一～四十四轮连续未跑通，根因＝模拟器不渲染） |
'''

REG_ADD = (
    ' **第四十四轮（渲染前置守卫落地；实机验证被"模拟器不渲染"阻塞）**：'
    '①给 `phase_precision_test.py` 补上渲染前置后运行：`已把模拟器拉到前台` → '
    '`渲染校验（画面在变）：★未通过` → **按规程直接退出**（不空点、不把静止帧当游戏状态）⇒ **规程生效**；'
    '②**模拟器当前确实不在渲染**，且 `SetForegroundWindow` 未能恢复（前台锁／最小化／被 DSH 覆盖）'
    '⇒ 这一步需要**人在场把模拟器窗口恢复为可见**，属外部前提，代码无法单方面解决；'
    '③**落地可复用守卫** `code/vision/plugins/capture/render_guard.py`：`ensure_foreground()` + '
    '`assert_rendering(cam, thresh=0.05)`（冻结帧是**精确 0.0**、正常画面远超 0.05 ⇒ 不漏报不误报）+ '
    '`guard_or_exit()` 一行式接入；供所有实机脚本复用；'
    '④**当前阻塞**：模拟器需保持可见/可渲染；恢复后即可直接接着跑 `phase_precision_test.py`'
    '（已具备渲染前置 + 点击生效校验 + 章节回切 + 精度比对）；'
    '⑤**可继续推进（不依赖渲染）**：模拟器侧轴表/坐标/伤害回归、验收对照表整理；'
    '⑥**待复核项未变**（见文档 §7.76）：费用条 ROI 大概率成立；"费用封顶后相位停住"待复核；'
    '相位↔墙钟精度**仍未成立**（第四十一～四十四轮，根因＝模拟器不渲染）；'
    '⑦合规：仅 adb/窗口接口与普通注入，不碰游戏内存；仅演习，未消耗理智。 | 2026-09-14 |'
)

s = io.open(DOC, encoding='utf-8').read()
anchor = '### 7.74 本轮新增/修改文件'
if anchor not in s:
    raise SystemExit('doc anchor not found')
s = s.replace(anchor, DOC_SEC + '\n### 7.77 本轮新增/修改文件', 1)
io.open(DOC, 'w', encoding='utf-8', newline='').write(s)
print('文档已追加 §7.75/§7.76')

r = io.open(REG, encoding='utf-8').read()
ra = '\n\n## 冲突记录'
if ra not in r:
    raise SystemExit('registry anchor not found')
r = r.replace(ra, REG_ADD + ra, 1)
io.open(REG, 'w', encoding='utf-8', newline='').write(r)
print('台账已追加第四十四轮')

shutil.copy2(DOC, os.path.join(DST, 'knowledge', '04_数据对应与核验', '41_模拟器与自动打图_首版实现.md'))
shutil.copy2(REG, os.path.join(DST, 'management', 'tasks_registry.md'))
shutil.copy2(r'C:\Users\23922\Documents\ds_harness\ak\code\vision\plugins\capture\render_guard.py',
             os.path.join(DST, 'code', 'vision', 'plugins', 'capture', 'render_guard.py'))
shutil.copy2(r'C:\Users\23922\Documents\ds_harness\ak\code\vision\apps\phase_precision_test.py',
             os.path.join(DST, 'code', 'vision', 'apps', 'phase_precision_test.py'))
print('同步完成')
