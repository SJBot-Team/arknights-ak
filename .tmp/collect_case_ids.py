# -*- coding: utf-8 -*-
"""从案例文档里收集出现过的 char_/token_ ID 及出处（只读），供人工补注 overlay 扩表。"""
import collections
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
D = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验'
FILES = ['50_实机与模拟器帧级对照_首次成功.md', '54a_日志_八费用差异完全定位20260915续.md',
         '54e_日志_四十八判别runes全属FOUR_STA.md', '41e_日志_案例结论与相位精度.md',
         '41f_日志_PRTS+与录像验证.md', '65_机制参数总表_代码结论转模拟参数.md']
pat = re.compile(r'\b((?:char|token|trap)_[0-9]+_[a-z0-9_]+)\b')
found = collections.defaultdict(set)
for fn in FILES:
    p = os.path.join(D, fn)
    if not os.path.exists(p):
        continue
    for line in open(p, encoding='utf-8'):
        for m in pat.finditer(line):
            found[m.group(1)].add(fn.split('_')[0])
print(f'涉及 {len(found)} 个 ID：')
for k in sorted(found):
    print(f'  {k:28} {"、".join(sorted(found[k]))}')
