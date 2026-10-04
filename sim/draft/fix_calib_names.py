# -*- coding: utf-8 -*-
"""fix_calib_names.py — 按"实际出怪顺序"修正标定表里的敌人命名

## 依用户 2026-09-15 确认
> 「我确实混淆了猎狗与猎狗pro，按实际出怪顺序替换我的命名，修正」

## 实际出怪顺序（来自关卡 `waves[].fragments[].actions[]` 与模拟器实测）
| 顺序 | 帧 | key | 名称 | hp |
|---|---|---|---|---|
| 第 1 只 | 90 | `enemy_1000_gopro_2` | **猎狗pro** | 1700 |
| 第 2 只 | 360 | `enemy_1000_gopro` | **猎狗** | 820 |

## 修正内容
- 标定表中的 **「猎狗pro 1」→「猎狗pro」**（第 1 只，命名本就正确、仅去掉序号）；
- 标定表中的 **「猎狗pro 2」→「猎狗」**（第 2 只，此前误标为 pro）。

**安全**：先备份原文件到同目录 `1-1标定.bak-<ts>.xlsx`，再就地修正；只改"单位"与"动画层"两列中的敌人名。
"""
from __future__ import annotations

import os
import shutil
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

XLSX = r'C:\Users\23922\Desktop\1-1标定.xlsx'

REPL = [
    # 先长后短，避免"猎狗pro 2"被"猎狗"规则先行命中
    ('猎狗pro 2', '猎狗'),
    ('猎狗pro 1', '猎狗pro'),
]


def main():
    try:
        import openpyxl
    except Exception as e:
        print('需要 openpyxl:', e)
        return 1
    if not os.path.exists(XLSX):
        print('★标定表不存在:', XLSX)
        return 1
    ts = time.strftime('%Y%m%d_%H%M%S')
    bak = XLSX.replace('.xlsx', f'.bak-{ts}.xlsx')
    shutil.copy2(XLSX, bak)
    print('已备份 →', bak)

    wb = openpyxl.load_workbook(XLSX)
    ws = wb[wb.sheetnames[0]]
    changed = []
    for row in ws.iter_rows():
        for c in row:
            v = c.value
            if not isinstance(v, str) or not v:
                continue
            nv = v
            for a, b in REPL:
                if a in nv:
                    nv = nv.replace(a, b)
            if nv != v:
                changed.append((c.coordinate, v, nv))
                c.value = nv
    wb.save(XLSX)
    print(f'\n共修改 {len(changed)} 个单元格：')
    for coord, old, new in changed:
        print(f'  {coord}: "{old}" → "{new}"')
    print('\n修正规则:', REPL)


if __name__ == '__main__':
    raise SystemExit(main())
