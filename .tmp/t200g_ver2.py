# -*- coding: utf-8 -*-
"""t200g_ver2.py — 用 3.11 表复核 co_code 是否 3.11（并统计 CACHE 比例）。"""
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


op311 = _load('op311', base + r'\t200g_op311.py')
rd = _load('rd', base + r'\t200g_read.py')

for f in ('src_logic_calc_view', 'src_logic_perform_action', 'src_config'):
    rec, off, ln = rd.load(base + rf'\pyz\{f}.pyc')
    co = rec.co_code
    print(f'===== {f} co_code={len(co)}B 首 40B: {co[:40].hex(" ")}')
    for skip in (0, 1):
        i = skip
        cnt = Counter()
        bad = 0
        while i < len(co) - 1:
            op = co[i]
            nm = op311.OPNAME[op]
            cnt[nm] += 1
            if nm.startswith('<'):
                bad += 1
            elif nm in op311.CACHE_ENTRIES:
                i += 2 + 2 * op311.CACHE_ENTRIES[nm]
                continue
            i += 2
        total = sum(cnt.values()) or 1
        print(f'   skip={skip} 未知={bad} CACHE占比={cnt["CACHE"]/total:.2f} '
              f'前10={cnt.most_common(10)}')
