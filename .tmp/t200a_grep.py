#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 从 v9 扫描产物中筛出战斗相关方法的 [reg+disp] 访问。"""
import sys, io, re
p = sys.argv[1]
pat = re.compile(sys.argv[2]) if len(sys.argv) > 2 else None
kind = sys.argv[3] if len(sys.argv) > 3 else None
n = 0
with io.open(p, encoding="utf-8") as f:
    for ln in f:
        if kind and not ln.startswith(kind):
            continue
        if pat and not pat.search(ln):
            continue
        print(ln.rstrip())
        n += 1
print(f"--- {n} 行 ---")
