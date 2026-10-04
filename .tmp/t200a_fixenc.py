#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 修复被 PowerShell Set-Content 双重编码破坏的 UTF-8 文件。

损坏链：原 UTF-8(无 BOM) --[PS 以 ANSI(GBK) 读]--> GBK 串 --[PS 写 UTF-8+BOM]--> 现状
修复链：现状 --[UTF-8 解码]--> GBK 串 --[GBK 编码]--> 原 UTF-8 字节 --[UTF-8 解码]--> 原文
"""
import sys, io, os

p = sys.argv[1]
raw = open(p, "rb").read()
s = raw.decode("utf-8")
try:
    b = s.encode("gbk")
except UnicodeEncodeError as e:
    print("GBK 编码失败（有不可逆字符）:", e)
    # 逐字符尝试，报告坏点
    bad = []
    for i, ch in enumerate(s):
        try:
            ch.encode("gbk")
        except UnicodeEncodeError:
            bad.append((i, repr(ch)))
    print("坏字符数:", len(bad), bad[:20])
    sys.exit(2)
try:
    fixed = b.decode("utf-8")
except UnicodeDecodeError as e:
    print("回解 UTF-8 失败:", e)
    sys.exit(3)
out = p + ".fixed"
io.open(out, "w", encoding="utf-8", newline="").write(fixed)
print("OK ->", out)
print("首 120 字:", fixed[:120].replace("\n", "\\n"))
