# -*- coding: utf-8 -*-
"""t200g_m3.py — 用 marshal9 的 Reader 扫描所有可能起点，找出可解析的偏移。"""
import sys
import importlib.util

sys.stdout.reconfigure(encoding='utf-8')
spec = importlib.util.spec_from_file_location(
    'm9', r'C:\Users\23922\Documents\ds_harness\ak\.tmp\marshal9.py')
m9 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m9)

for p in sys.argv[1:]:
    d = open(p, 'rb').read()
    print(f'===== {p} len={len(d)}')
    for off in range(0, 40):
        r = m9.Reader(d[off:])
        try:
            o = r.r_object()
        except Exception as e:
            continue
        if isinstance(o, m9.CodeRec):
            print(f'  ✅ off={off} name={o.name!r} argcount={o.argcount} nlocals={o.nlocals} '
                  f'file={o.filename!r} consts={len(o.consts)} names={len(o.names)} '
                  f'co_code_len={len(o.co_code)} end_p={r.p + off}')
