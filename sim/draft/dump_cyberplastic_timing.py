# -*- coding: utf-8 -*-
"""dump_cyberplastic_timing.py — 读出赛博塑料（PRTS+）轴表里的**内部计时**并与模拟器对照

## 背景（用户 2026-09-14 授权）
用户许可读取 PRTS+ 运行产生/使用的信息以便学习。轴表 `赛博塑料h12-4.xlsm` 的「作战记录」表
本身就带 PRTS+ 的计时列：**费用 | 帧数 | 绝对时间**，其中
  · `帧数`   = 费用条**相位**（0~29，即条内位置）
  · `绝对时间` = **秒**（PRTS+ 计时器的整数部分）
⇒ `精确时刻 = 绝对时间 + 帧数/30`，可与模拟器的帧号（`frame/30`）直接比对。

本脚本输出：
1. 全部记录的（费用、帧数、绝对时间）与换算出的精确秒；
2. **费用达到上限（封顶）附近**的行 —— 用来观察"封顶时它怎么记"（用户猜测它比实际跳动次数多记一秒）；
3. 「中转站」的运行状态与报错（PRTS+ 用它做进程通信）。
"""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding='utf-8')

XLSM = r'E:\__file\舟数据\关卡\h12-4\赛博塑料h12-4.xlsm'
FPS = 30


def main():
    import openpyxl
    wb = openpyxl.load_workbook(XLSM, read_only=True, data_only=True)
    ws = wb['作战记录']
    rows = list(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True))
    header = [str(c) if c is not None else '' for c in rows[0]]
    print('表头:', header)
    print()
    print(f'{"行":>3} {"费用":>4} {"帧数":>4} {"绝对时间":>7} {"精确秒":>7} {"Δ秒":>6}  {"操作":<4} {"干员":<8}')
    prev_exact = None
    for i, r in enumerate(rows[1:], start=2):
        vals = list(r) + [None] * 12
        _cur, cost, fr, t, op, unit = vals[:6]
        if op is None and t is None and fr is None:
            continue
        exact = None
        if isinstance(t, (int, float)) and isinstance(fr, (int, float)):
            exact = float(t) + float(fr) / FPS
        dt = ''
        if exact is not None and prev_exact is not None:
            dt = f'{exact - prev_exact:+6.2f}'
        if exact is not None:
            prev_exact = exact
        print(f'{i:>3} {str(cost):>4} {str(fr):>4} {str(t):>7} '
              f'{("" if exact is None else f"{exact:7.2f}")} {dt:>6}  {str(op or ""):<4} {str(unit or ""):<8}')

    # 中转站
    if '中转站' in wb.sheetnames:
        print('\n=== 中转站（PRTS+ 的进程通信区）===')
        for r in wb['中转站'].iter_rows(min_row=1, max_row=wb['中转站'].max_row, values_only=True):
            if any(v is not None for v in r):
                print('   ', [v for v in r if v is not None])
    wb.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
