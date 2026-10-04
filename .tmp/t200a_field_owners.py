#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""列出所有在 // 0x1A0 处有字段声明的类（排除栈/无关类），用于判断 disp=0x1A0 命中属于哪个结构。"""
import io, re, sys
DUMP = r"E:\__file\ak_kb\client_res\il2cpp\dump\dump.cs"
want = sys.argv[1] if len(sys.argv) > 1 else "1A0"
L = io.open(DUMP, encoding="utf-8", errors="replace").readlines()
rx_cls = re.compile(r"^public\s+(?:sealed\s+|abstract\s+|static\s+|partial\s+)*(?:class|struct|interface|enum)\s+([\w.<>`]+)")
rows = []
for i, l in enumerate(L):
    if re.search(r"// 0x" + want + r"\s*$", l.rstrip()):
        for j in range(i, -1, -1):
            m = rx_cls.match(L[j])
            if m:
                rows.append((j + 1, m.group(1), l.strip()))
                break
print(f"含 // 0x{want} 字段的类: {len(rows)}")
for r in rows:
    print(f"  dump.cs:{r[0]}  {r[1]}  ::  {r[2]}")
