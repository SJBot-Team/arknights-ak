# -*- coding: utf-8 -*-
"""T-052 追加：第七轮（时基定案：作者 Sheet1 时间点）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第七轮（时基定案）**：①**发现** xlsm 的 `Sheet1` 是作者记录的**关键事件绝对时刻**'
    '（14 条，如 `66.1过1下龙`/`140.2炮`/`172.6过2开蕾缪安`），底层另有总量行 ⇒ **整场≈366s**；'
    '这是独立于费用读数与「绝对时间」列的**第三方基准**；②新增 `sim/draft/match_sheet1_timeline.py`'
    '（事件按类型匹配到候选时间轴的全局最近同类操作 + 末尾时长双判据），并给 `resolve_frames` 增加 `hybrid` 时基；'
    '③**结果**：`abs-seconds` 中位偏差 **8.3s**、末尾 380.5s（距 366s 仅 14.5s）；'
    '旧默认 `cost-relative 静态` **20.0s / 269.6s（差 96.4s）最差**；蕾缪安用 S3 会把整轴拉到 490s（差 124s）⇒ '
    '**蕾缪安应为 S1**；④**模拟执行吻合度**：把绝对帧计划交给 `run_axis(schedule=…)` 后 '
    '**完全一致 43/50、±2 帧内 44/50**（旧相对时基仅 1~3 条），即费用锚点行与绝对时间行**互相印证**；'
    '⑤**两端交叉验证**：同一时基下执行端与模拟器 **19/19 落在 ±1 帧内（13 条完全相同）**；'
    '⑥据此把案例默认时基改为 `abs-seconds`（`configs/axis_h12-4.json`），三路证据一致；'
    '残留仅剩「首批召唤物 23 费落在 DP≈9 时刻」这一点，靠费用顺延可执行，留待实机复核。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第七轮（时基定案）' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
