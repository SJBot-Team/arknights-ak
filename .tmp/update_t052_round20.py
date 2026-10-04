# -*- coding: utf-8 -*-
"""T-052 追加：第二十轮（正确模型下的 DP 账本 + 技能语义修正）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第二十轮（正确模型下的 DP 账本）**：①新增 `sim/draft/dp_ledger.py`——在**正确上限模型**'
    '（rune 20 + 两个储备各 +5）下跑轴表，输出逐条「计划帧/实际帧/顺延/触发前 DP/消耗/结果」；'
    '②**关键语义修正**：技能 SP 不足**不应阻塞轴**（实机脚本按一下就过），此前把 `sp` 纳入重试原因'
    '导致技能各卡 60s、整条轴被拖到 141s+；`run_axis` 新增 `retry_on_sp`（默认 **False**），'
    '只有部署费用不足才顺延；③修正后的弦惊落地 = **33.0 / 56.0 / 83.0 / 129.5 / 155.7s**，'
    '与作者 Sheet1 的 66.1 / 86.4 / 153.3s 对照：**83.0↔86.4（Δ3.4s）、155.7↔153.3（Δ2.4s）**，'
    '56.0↔66.1（Δ10.1s）；④这是**在同一套正确约束下**得到的对齐，比此前"错误上限下的 0.1s"更可信；'
    '⑤仍未对齐的部分：轴表技能行在模拟里因 SP 不足被大量跳过（令 `no_skill`、蕾缪安 `sp`），'
    '而作者显然放出了技能 ⇒ **SP 来源还差一块**（蕾缪安 S1 攻击回费节奏 / 令天赋触发更频繁 / 模组 SP），'
    '补齐后第一条龙有望前移到 ~66s。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第二十轮（正确模型下的 DP 账本）' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
