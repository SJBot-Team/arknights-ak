# -*- coding: utf-8 -*-
"""append_t052_letterconv.py — 记录"格子表口径更正：列左→右从1、行下→上从A"。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第89轮】★★★★★**用户更正格子表口径：「列左→右从 1、行下→上从 A」—— 我方行方向整体反了，已全面修正**：'
 '①**用户更正**：「你读取 prts+ 查找格子表的机制与我实际使用 prts+ 时标的格子不同，'
 '**应为左到右从 1 开始，下到上从 A 开始**。我给你的标定表也遵守此规律」；'
 '②**我方原错误**：上一轮我答"1-1 对应 `rc_normal`（字母 A = mapData row 0 = **屏幕最上方**）" —— '
 '**把 A 当成了最上面一行**，实际应为**最下面一行** ⇒ **字母→行的方向整体反了**；'
 '**为何 1-1 未暴露**：1-1 是 7 行、且标定只用到**中间行 D**，翻转前后 D 都落在 mapData row 3 '
 '⇒ **像素与标定结论完全不变**；但换 9 行图（如 h12-4）或用到非中间行**必然出错**；'
 '③**修正（打图侧）** `code/vision/plugins/action/grid_px.py`：'
 '`COORD_TRANSFORM` 由 `rc_normal` 改为 **`rc_rowflip`**（`row_mapdata = (rows−1) − 字母序号`），'
 '并补 3 项**方向性自检**；**自检 14/14 通过**：'
 '绿格 6 连逐格重投影 ≤1px、额外绿格 (2,4)→(1057,364) 命中、route1 的 x 递增、'
 '**D6=(1182,502)**、**D4=(932,502)**（不变）；**F4=(932,226) 在屏幕上方**、'
 '**B4=(932,778) 在屏幕下方**、**A6=(1182,916) 在最底行** ✓；'
 '④**修正（模拟器侧）** `sim/draft/axis_io.py::cells_letter_to_rc`：新增 `rows` 参数并做同样的翻转，'
 '实测 `D6→(3,5)`、`D4→(3,3)`（不变）、**`F4→(1,3)`（上方）**、**`B4→(5,3)`（下方）**、'
 '`A6→(6,5)`、`G1→(0,0)`；'
 '⑤**回归（全部不变）**：轴表部署计划仍为 `{10: 芬@(3,5) 左 8费, 411: 月见夜@(3,3) 上 14费}`；'
 '`replay_axis` **18/18**、`replay_verify5` **16/16、平均 2.19 帧、最大 7**、`test_axis_io` 通过 '
 '⇒ **本次更正对 1-1 标定零影响，但修正了通用性**；'
 '⑥**合规**：纯本地计算与代码修正；未登录、未消耗资源、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
