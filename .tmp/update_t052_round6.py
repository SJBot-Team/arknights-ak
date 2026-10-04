# -*- coding: utf-8 -*-
"""T-052 追加：第六轮（轴表时基联合求解 + 记账模型反解）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第六轮（轴表时基联合求解）**：①新增 `sim/draft/solve_axis_timeline.py`（时基×召唤物扣费×返还率 的'
    '联合求解，三类独立约束打分）与 `sim/draft/fit_axis_cost_model.py`（用 8 个记录读数反解作者记账模型）；'
    '②**判据①**：把 8 个读数放到表内「绝对时间」列上，**没有任何 (召唤物费用, 返还率) 能拟合**——'
    '最优 c=20 DP/ρ=0 时 RMSE 仍 16.5 DP，6/8 行残差 10~21 DP，末行模型读数 −3.4（物理不可能）'
    '⇒「绝对时间」列不是可信时间轴；③**判据②下调强度**：轴表里同一干员技能行相隔 0.2~3s 成对出现，'
    '任何技能模型都不可能 ⇒「技能」行不必然等于一次释放（很可能含多次 UI 点击），故上一轮'
    '「abs-seconds 12/21 vs cost-relative 4/21」只能作弱证据；④**判据③**：一旦允许「费用不足则顺延」'
    '（实机脚本必然如此），全轴**可执行**——仅 1 次部署顺延（弦惊 DP21/23，2.0s），但时间拉长到 490s（表内约 380s）；'
    '⑤**本轮结论**：轴表两列互不自洽，唯有加「不足顺延」的运行时语义才成为可执行剧本；'
    '离线推断到此为止，**实机（费用尺+逐帧记录）或对应录像是唯一能定案的手段**，已列为第一优先项。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第六轮（轴表时基联合求解）' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
