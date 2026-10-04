# -*- coding: utf-8 -*-
"""t200g_ver.py — 用「首指令 + 频率」判定字节码版本/对齐偏移。

思路：3.9 的模块级 co_code 必以 IMPORT 序列开头，且不含 CACHE 指令（3.11+ 才有）。
这里直接统计每个文件在两种可能 stride 下的「未知名数量」，未知名为 0 者即为正解。
"""
import importlib.util
import sys
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')
base = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


op39 = _load('op39', base + r'\t200g_op39.py')
rd = _load('rd', base + r'\t200g_read.py')

rec, off, ln = rd.load(base + r'\pyz\src_logic_calc_view.pyc')
print('co_code 前 48 字节:', rec.co_code[:48].hex(' '))
print()
for u16 in (False, True):
    i = 0
    cnt = Counter()
    bad = 0
    while i < len(rec.co_code) - 1:
        if u16:
            v = rec.co_code[i] | (rec.co_code[i + 1] << 8)
            op = v & 0xFF
            arg = v >> 8
            step = 2
        else:
            op = rec.co_code[i]
            arg = rec.co_code[i + 1]
            step = 2
        nm = op39.OPNAME[op]
        cnt[nm] += 1
        if nm.startswith('<'):
            bad += 1
        if op39.has_arg(op) and arg > 300:
            bad += 1
        i += step
    print(f'u16={u16} 未知/越界={bad} 前 12={cnt.most_common(12)}')
