# -*- coding: utf-8 -*-
"""T-052 追加：第十一轮（技能栏识别器 skill_ready + 门控接入执行器）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第十一轮（技能栏识别器）**：①新增 `code/vision/plugins/recognize/skill_ready.py`——'
    '三种模式：`ready`（技能按钮三态：就绪金 / 充能暗 / 激活异色，用**色相**区分就绪与激活）、'
    '`sp_bar`（条状 SP 条填充比例，含"整条全暗→0"的绝对亮度判据）、'
    '`sp_arc`（环形 SP 表按角度采样取最长连续亮段占比）；'
    '②`apps/test_skill_ready.py` 合成图自检 **13/13 通过**（三态色相 42.5°/213.6° 正确区分；'
    '条状与环形 0/25/50/75/100% 全部命中）；③接入执行器：`axis_runner` 新增 `sp_gate_mode`'
    '（`analytic` 按表值推算 / `image` 点选干员后抓帧读技能按钮），并把"被门控顺延过的操作"'
    '从迟到统计中剔除（`gated` 标记），避免把设计内顺延误报为精度损失；'
    '④配置新增 `cost_gate/sp_gate/sp_gate_mode/unit_skills/token_owners/summon_lost_sp` 与待标定项 '
    '`ui.skill_sp_roi`、`skill_sp` 阈值；⑤**实机标定清单新增两项**：技能按钮/SP 条 ROI、就绪色相阈值。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第十一轮（技能栏识别器）' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
