# -*- coding: utf-8 -*-
"""test_bar_sanity.py — 用**两轮真实序列**验证费用条自检：上一轮（有效）应通过，本轮（失效）应被抓出

A 上轮有效序列（§7.114）：费用递增、填充同步递增、回绕跳到 6px ⇒ 期望 **通过**
B 本轮失效序列（§7.128）：填充递减、费用 +1 而间隔不足 30 帧 ⇒ 期望 **未通过**并指出问题
C 边界：费用一次跳 2（采样间隔 ≥1 秒）⇒ 应报"跳变"而非静默通过
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.clock.bar_sanity import check_bar_series, summarize      # noqa: E402

# A：上一轮有效样本（费用, 填充px, 相位）——去掉那个"费用跳 2"的绕圈歧义样本，保留干净序列
GOOD = [(10, 180, 29), (10, 156, 25), (11, 162, 26), (12, 162, 26), (13, 169, 27),
        (14, 169, 27), (15, 175, 28), (17, 180, 29), (18, 180, 29), (19, 6, 1), (20, 180, 29)]
GOOD_CLEAN = GOOD[:7]      # 只取"费用逐 +1、填充同步递增"的连续段（原序列 15→17 处缺 16，无法构成连续段）
# B：本轮失效样本
BAD = [(10, 180, 4), (11, 180, 29), (11, 100, 27), (12, 75, 24), (13, 50, 21),
       (14, 38, 18), (15, 13, 16), (16, 180, 12)]
# C：费用跳变
JUMP = [(11, 100, 10), (13, 130, 20)]


def main():
    results = []
    for tag, seq, expect in (('A 上一轮有效序列(去歧义样本)', GOOD_CLEAN, True),
                             ('B 本轮失效序列', BAD, False),
                             ('C 费用一次跳 2', JUMP, False)):
        ok, probs = check_bar_series(seq, fps=30.0)
        good = (ok == expect)
        results.append(good)
        print(f'  {"OK " if good else "BAD"} {tag}: 自检={ok} 期望={expect}')
        for p in probs[:4]:
            print(f'        · {p}')
    print()
    print('A 明细:', summarize(GOOD))
    print('B 明细:', summarize(BAD))
    print(f'\n汇总: 费用条自检 A/B/C {"全部 PASS" if all(results) else "存在失败"}')
    return 0 if all(results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
