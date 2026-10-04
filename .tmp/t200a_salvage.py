#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从被破坏的 00_目录.md 中抢救出所有 ASCII/结构信息（表头、行数、字节数、编号顺序）。"""
import io, re

p = r"C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\00_目录.md"
s = open(p, "rb").read().decode("utf-8").lstrip("\ufeff")
lines = s.split("\n")
out = []
for i, ln in enumerate(lines):
    # 只保留 ASCII 可读部分 + 表格竖线结构
    asc = "".join(ch if 0x20 <= ord(ch) < 0x7f else ("\u00b7" if ch.strip() else "") for ch in ln)
    asc = re.sub(r"\u00b7{2,}", "\u00b7\u00b7", asc).strip()
    if not asc:
        continue
    out.append("%4d | %s" % (i + 1, asc))
io.open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t200a_salvage.txt", "w", encoding="utf-8").write("\n".join(out))
print("lines salvaged", len(out), "of", len(lines))
