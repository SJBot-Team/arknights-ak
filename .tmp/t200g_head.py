# -*- coding: utf-8 -*-
"""t200g_head.py — 打印 pyc 头部 32 字节并定位 'c' 起点。"""
import sys

sys.stdout.reconfigure(encoding='utf-8')
for p in sys.argv[1:]:
    d = open(p, 'rb').read()
    print(f'===== {p}  len={len(d)}')
    print('  头32:', d[:32].hex(' '))
    print('  前 16 字节中的 "c" 位置:', [i for i in range(16) if d[i] == 0x63])
