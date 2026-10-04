#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 用已知原文片段反推"每个字节被映射成了什么字符"。"""
import io

expect = "# 00 目录 / 导航（数据对应与核验）"
raw = open(r"C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\00_目录.md", "rb").read().decode("utf-8").lstrip("\ufeff")

# ASCII 前缀 "# 00 " 应逐字节一致
print("prefix same:", raw[:5] == expect[:5], repr(raw[:5]))
ob = expect[5:].encode("utf-8")
cb = raw[5:5 + len(expect[5:])]
print("orig chars after prefix:", len(expect[5:]), "orig bytes:", len(ob), "cur chars:", len(cb))

lines = []
for i, ch in enumerate(cb):
    lines.append("%2d cur=U+%04X %-4s" % (i, ord(ch), ch if 0x20 <= ord(ch) < 0x7f else "."))
# 打印前 40 个原字节与对应字符
real = expect[5:]
for i, ch in enumerate(real):
    st = i * 3
    if st + 3 <= len(ob):
        b3 = ob[st:st + 3]
    print("orig[%d]=%s bytes=%s -> cur[%d]=U+%04X" % (
        i, ch, b3.hex(), st, ord(cb[st]) if st < len(cb) else -1))
