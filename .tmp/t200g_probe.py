# -*- coding: utf-8 -*-
"""t200g_probe.py — 打印真实 co_code 的十六进制，用于人工核对 opcode 表偏移。"""
import importlib.util
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = r'C:\Users\23922\Documents\ds_harness\ak\.tmp'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


rd = _load('rd', BASE + r'\t200g_read.py')

rec, off, ln = rd.load(BASE + r'\pyz\src_logic_calc_view.pyc')
co = rec.co_code
print('calc_view co_code len', len(co))
print(co[:96].hex(' '))
print()
# 逐字节列出前 40
print([f'{i}:{b:02x}' for i, b in enumerate(co[:40])])
print()
# 找子函数
for c in rec.consts:
    if hasattr(c, 'co_code'):
        print('sub code:', c.name, 'argcount', c.argcount, 'len', len(c.co_code))
        print('  ', c.co_code[:120].hex(' '))
