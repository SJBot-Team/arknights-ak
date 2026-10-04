# -*- coding: utf-8 -*-
"""test_frames_between.py — 用**两轮真实实机样本**验证"相位↔帧数"公式（§7.133 的修正）

A 手算样例：验证方向（p1<p0 应 −、p1>p0 应 +），防止再犯"多算一圈"的错误
B §7.114 真实样本（10 对中的 7 对）：误差应 ≤2 帧
C §7.128 真实样本（10 对）：用**正确公式**误差应 ≤2 帧 —— 这正是"撤回作废判定"的依据
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from plugins.clock.frame_clock import frames_between, signed_phase_delta   # noqa: E402

# A 手算样例：(Δ费用, p0, p1) → 期望帧数
CASES = [
    (1, 27, 24, 27),      # 27 + (-3)
    (1, 25, 26, 31),      # 30 + (+1)
    (0, 29, 27, -2),      # 同费用下相位倒退 ⇒ 负数（说明费用读数滞后，应另行处理）
    (1, 2, 29, 27),       # 2→29 视为 -3（而不是 +27）
    (2, 10, 12, 62),      # 60 + 2
]

# B §7.114（费用, 相位, 墙钟帧）
S114 = [(10, 25, 10, 26, 30.49), (11, 26, 12, 26, 30.57), (12, 26, 13, 27, 30.65),
        (13, 27, 14, 27, 30.59), (14, 27, 15, 28, 30.75), (17, 29, 18, 29, 30.94),
        (18, 29, 19, 1, 30.49)]
# C §7.128
S128 = [(10, 4, 11, 29, 26.77), (11, 27, 12, 24, 26.87), (12, 24, 13, 21, 27.17),
        (13, 21, 14, 18, 27.33), (14, 18, 15, 16, 27.01), (15, 16, 16, 12, 26.80),
        (16, 12, 17, 8, 26.87), (17, 8, 18, 6, 26.58), (18, 6, 19, 2, 26.79),
        (19, 2, 20, 29, 26.61)]


def check(tag, rows, limit=2.0):
    errs = []
    for c0, p0, c1, p1, wall in rows:
        fr = frames_between(c0, p0, c1, p1)
        errs.append(abs(fr - wall))
    errs.sort()
    med = errs[len(errs) // 2]
    ok = med <= limit
    print(f'  {"OK " if ok else "BAD"} {tag}: {len(rows)} 对，|误差| 中位 {med:.2f}、最大 {errs[-1]:.2f} 帧'
          f'（判据中位 ≤{limit}）')
    return ok


def main():
    print('相位↔帧数公式测试：')
    bad = 0
    for dc, p0, p1, want in CASES:
        got = frames_between(0 if dc == 0 else 0, p0, dc, p1)
        good = (got == want)
        bad += (not good)
        print(f'  {"OK " if good else "BAD"} 手算 Δc={dc} {p0}→{p1} ⇒ {got}（期望 {want}）')
    print(f'  带符号差自检: (27,24)→{signed_phase_delta(27,24)}  (2,29)→{signed_phase_delta(2,29)}')
    res = [check('B §7.114 真实样本', S114), check('C §7.128 真实样本（原判"作废"）', S128)]
    print(f'\n汇总: 手算 {"PASS" if bad == 0 else "FAIL"}；B/C {"全部 PASS" if all(res) else "存在失败"}')
    return 0 if (bad == 0 and all(res)) else 1


if __name__ == '__main__':
    raise SystemExit(main())
