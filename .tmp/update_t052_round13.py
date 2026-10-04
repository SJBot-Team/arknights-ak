# -*- coding: utf-8 -*-
"""T-052 追加：第十三轮（四方一致 + 实机 RUNBOOK）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第十三轮（四方一致 + 实机 RUNBOOK）**：①`apps/test_ruler_clock.py` 新增段 G「案例里程碑」——'
    '用**执行端干跑**（步进时钟 + 绝对时基 + 费用门控）跑同一轴表，弦惊落地 = **[43.0, 66.0, 89.0]s**，'
    '与解析预测、模拟器执行（1291/1981/2671 帧）完全一致，而作者 Sheet1 记录为 66.1s（Δ0.1s）'
    '⇒ **四方独立来源（解析 / 模拟 / 执行端 / 作者记录）互相吻合**，自检总数增至 **7 项全通过**；'
    '②新增 `code/vision/RUNBOOK_实机验证.md`（一页式规程）：合规检查点 → 离线自检 → 启动费用尺并验证 API → '
    '`calibrate.py` 标定（含本机已知可复用 ROI：费用数字 `(1525,619,1565,670)`、卡槽行 y 684~891、12 槽 x 中心 66…1533）'
    '→ dry-run 对轴 → 实注入（合规守卫要求当场同意）→ 验收表 + 失败处置；'
    '③**离线部分至此收尾**，剩余唯一事项即实机验证（含登录逐次同意、仅限尾号 ****、MuMu12/PC 各 1 次）。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第十三轮（四方一致' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
