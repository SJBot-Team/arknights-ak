# -*- coding: utf-8 -*-
"""append_t052_costbar.py — 追加"修好费用条识别器 + 实机取证"到 T-052 行。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
p = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
s = open(p, encoding='utf-8').read()
lines = s.split('\n')
i = next(k for k, l in enumerate(lines) if l.startswith('| T-052 |'))
row = lines[i]
assert row.endswith('|'), row[-20:]

entry = (
 '【第76轮】★★★★★**修好费用条识别器根因 bug，并在实机上完成"费用尺级帧时钟"的决定性验证**：'
 '①**★根因定位**：`plugins/recognize/cost_bar.py::run()` **完全没有使用 `spec[\'roi\']`**，'
 '而是 `gray.max(axis=0)` 对**整幅图**取列最大值 ⇒ `fill_px` 恒为 **1920**（HUD 右缘总有亮像素）'
 '⇒ 无标定时 `frames = 1920/1920×30 = 30` ⇒ **恒报"满条"**（这正是上一轮实机读数的真相）；'
 '②**修复**：**(a)** 新增 `_roi_px()`，支持**绝对像素**与**相对 0~1** 两种 ROI 写法，'
 '并对越界做钳位；**(b)** 新增实测默认 ROI `(1736,806,1876,822)` 与 `bar_px=132`（实测轨道长）；'
 '**(c)** 填充长度改为**自轨道左端起的连续亮列**计数（比"亮列总数"更抗噪，且保留兜底）；'
 '**(d)** 帧换算三选一：标定 `pixel_map` → `bar_px/total_frames` 比例 → 兜底；'
 '**(e)** 返回体补充 `bar_px` / `roi` 字段便于审计；'
 '③**新增回归 `apps/test_costbar_roi.py`（全部通过）**：实机战斗截图上 `roi_w=140`（**不再是 1920**）、'
 '`fill_px=63 ≤ bar_px=132`、**`frame=14`（不再是恒定的 30）**；'
 '**人为改造验证"确实在量填充"**：ROI 涂满 → `frame=30`，涂黑 → `frame=0`；'
 '绝对像素 ROI 与相对 ROI 结果一致；'
 '④**★★实机决定性验证（`apps/live_clock_probe.py`，1-1 演习）**：'
 '**运行态**采样 —— 相位 `9 → 30 →(回绕) 23 → 9 → 30 → 23`，'
 '**3.35 秒内满条 3 次、相位推进 104 帧 ⇒ 31.0 帧/秒**（1X 应为 30.0，偏差来自采样混叠）'
 '⇒ **用户方案第①步「统计费用条满的次数以记录绝对时间」在实机上成立**'
 '（绝对帧 = 满条次数×30 + 相位）；'
 '**暂停态**采样 —— 相位**冻结在 25**、推进 **0 帧/秒** ⇒ '
 '**正好支撑流程第④步「暂停定位到预定帧」**（暂停后读相位即可确认"现在就是目标帧"）；'
 '⑤**遗留精修项**：实测 31.0 帧/秒（≈3% 偏快）来自**采样混叠**（每次 adb 截图+识别约 0.65s）'
 '与**轨道长度微差**（bar_px=132 为目测，可用"填充比例 ↔ 费用数字跳变"两端对齐精修）；'
 '⑥**合规**：仅图形界面级点击与截图 + 只读识别；未登录、未消耗理智、未读改游戏文件/内存。 |'
)

lines[i] = row[:-1] + entry
open(p, 'w', encoding='utf-8').write('\n'.join(lines))
print('ok; new row length =', len(lines[i]))
