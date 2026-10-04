#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io
p = r'C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\00_目录.md.try_gbk'
L = io.open(p, encoding='utf-8').read().split('\n')
out = []
for i in range(min(10, len(L))):
    out.append("%d %s" % (i, L[i][:160]))
io.open(r'C:\Users\23922\Documents\ds_harness\ak\.tmp\t200a_try.txt', 'w', encoding='utf-8').write("\n".join(out))
print("ok", len(L))
