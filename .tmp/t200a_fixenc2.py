#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 反向修复 PS 双重编码；输出重编码后的原文（写文件，不打印中文）。"""
import sys, io

p = sys.argv[1]
raw = open(p, "rb").read()
s = raw.decode("utf-8")
if s.startswith("\ufeff"):
    s = s[1:]
ok = []
bad = []
for i, ch in enumerate(s):
    try:
        ch.encode("gbk")
        ok.append(i)
    except UnicodeEncodeError:
        bad.append((i, ch, hex(ord(ch))))
# 用 errors='replace' 先看整体可读性
b = s.encode("gbk", errors="replace")
try:
    fixed = b.decode("utf-8", errors="replace")
except Exception as e:
    print("decode fail", e)
    sys.exit(1)
with io.open(p + ".fixed", "w", encoding="utf-8") as f:
    f.write(fixed)
with io.open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t200a_fix_report.txt", "w", encoding="utf-8") as f:
    f.write("bad_count=%d\n" % len(bad))
    for t in bad[:80]:
        f.write(repr(t) + "\n")
    f.write("---- head 400 chars ----\n")
    f.write(fixed[:400])
print("bad_count=%d" % len(bad))
print("written", p + ".fixed")
