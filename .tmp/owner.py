# -*- coding: utf-8 -*-
"""owner.py —— 在 dump.cs 里找某行号所属的类/结构体"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
p = r'E:\__file\ak_kb\client_res\il2cpp\dump\dump.cs'
target = int(sys.argv[1])
with open(p, encoding='utf-8', errors='replace') as f:
    lines = f.readlines()
i = target - 1
for j in range(i, max(0, i - 4000), -1):
    s = lines[j]
    if ('class ' in s or 'struct ' in s or 'enum ' in s) and '//' in s and 'TypeDefIndex' in s:
        print('OWNER 行', j + 1, ':', s.strip())
        break
for j in range(max(0, i - 2), min(len(lines), i + 4)):
    print(j + 1, lines[j].rstrip())
