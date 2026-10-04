# -*- coding: utf-8 -*-
"""T-052 追加：第三轮（两端时序交叉验证）结果"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第三轮（两端时序同构 + 交叉验证）**：①执行器 `axis_runner` 改为与模拟器 `Battle.run_axis` '
    '**完全同构**的调度语义——费用锚点行按「显示费用 + 费用内帧相位」判定（`anchor_ready`）、'
    '无锚点行以上一条**实际**触发帧 + foff、部署费用不足按 `cost_gate` 顺延（等价模拟器 `retry_on_cost`）、'
    '撤退按 50% 返还记账；②`sim/draft/compare_retry.py` 导出模拟侧逐条触发帧 '
    '`data/derived/sim_axis_frames_retry.json`，执行端用**确定性步进时钟**跑同一轴表逐条比对：'
    '**可比区间（前 19 条，模拟侧尚无费用相关失败）±2 帧内 19/19，最大帧差 1 帧**'
    '（#1 45/45、#2 601/600、#6 首次召唤物 1291/1290、#7 1981/1980）——两端独立实现落在同一物理时间线；'
    '③据此确认「费用不足顺延」是该轴唯一可行执行语义（首批召唤物在 43.0s/66.0s 落地，而非轴表相对帧链的 21s）；'
    '④区间外分歧**全部来自模拟器保真度缺口**（首个分歧 #20 撤退 U-Official：模拟器里该干员已在 f2671 阵亡 → 撤退失败；'
    '其后 #33 部署艾拉地块判定失败），即下一步「补齐技能/buff/召唤物」的直接依据；'
    '⑤离线自检扩到 **5 项全通过**（`apps/test_ruler_clock.py`：假尺子 HTTP/WS、轴表调度、虚拟时钟全轴、两端交叉验证）。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第三轮（两端时序同构' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
