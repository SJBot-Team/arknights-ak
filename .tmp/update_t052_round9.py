# -*- coding: utf-8 -*-
"""T-052 追加：第九轮（龙类事件 3/3 命中；全事件对照）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第九轮（龙类事件 3/3 命中 + 全事件对照）**：①把「全部弦惊落地」与作者记录比对，'
    '此前对不上的 `153.3过2合龙` 已由第 5 条召唤 **149.7s** 命中（Δ3.6s）；'
    '三条龙事件全部命中（66.1↔66.0 Δ0.1s、86.4↔89.0 Δ2.6s、153.3↔149.7 Δ3.6s），'
    '测试 `ak_sim/test_case_deferral.py` 已改为断言三条（阈值 4s）；'
    '②`verify_case_timeline.py` 增加**全部 14 条 Sheet1 事件**对照：中位偏差 7.7s，'
    '龙类 3/3 命中、炮类 2 条 ≤3s；偏差大的几条集中在对 `过1/过2`、`137.7过1令`（全轴仅一次令部署）'
    '等**标签语义**的解读上，非时间轴本身；③结论：案例前半段的时间轴（绝对时基 + 不足顺延 + 召唤物 23 费 + 回费 1/s）'
    '已与作者记录对齐，离线可解项基本收口。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第九轮（龙类事件 3/3 命中' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
