# -*- coding: utf-8 -*-
"""T-052 追加：第八轮（案例三方互验达成）"""
import io
import sys

sys.stdout.reconfigure(encoding='utf-8')
P = r'C:\Users\23922\Documents\ds_harness\management\tasks_registry.md'
ADD = (
    '**第八轮（案例精度互验达成）**：①由时基定案推出可证伪推论——绝对时基下表内召唤物时刻费用不足，'
    '按「不足则顺延」应落在 43.0 / 66.0 / 89.0s；②新增 `sim/draft/verify_case_timeline.py`（逐条打印'
    '「计划时刻→顺延后实际时刻」）与 `sim/draft/ak_sim/test_case_deferral.py`（端到端断言）；'
    '③**三方对照成立**：解析预测 43.0/66.0/89.0s ＝ 模拟器实际执行 1291/1981/2671 帧（43.03/66.03/89.03s）'
    '＝ 作者 Sheet1 记录 `66.1过1下龙`（**Δ0.1s**）、`86.4过2合龙`（Δ2.6s）；'
    '④该预测**无任何拟合参数**，同时检验四项假设：绝对时基、不足顺延语义、召唤物 23 费、回费 1/s；'
    '⑤原「召唤物费用与时序矛盾」开放问题**关闭**（§7.5 已更新），仅剩「实机最终确认」一项'
    '（核对首次召唤物 43.0s / 第二批 66.0s 与当时费用读数，同时验收费用尺时钟、同帧多操作、ADB 注入三条实机链路）。'
)
s = io.open(P, encoding='utf-8').read()
tail = ' | 2026-09-14 |'
idx = s.find('| T-052 ')
end = s.find('\n', idx)
row = s[idx:end]
assert row.rstrip().endswith(tail.strip())
assert '第八轮（案例精度互验达成）' not in row
row2 = row.rstrip()[:-len(tail.strip())].rstrip() + ' ' + ADD + tail
s = s[:idx] + row2 + s[end:]
io.open(P, 'w', encoding='utf-8').write(s)
print('已更新 T-052，长度', len(row), '→', len(row2))
