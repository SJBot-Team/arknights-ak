#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 探测损坏链 —— 用已知原文片段试各种"被误读的编码"。"""
import io

expect = "# 00 目录 / 导航（数据对应与核验）"
raw = open(r"C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\00_目录.md", "rb").read().decode("utf-8").lstrip("\ufeff")
cur = raw[:20]
print("cur ascii-ish:", cur.encode("unicode_escape").decode())
orig_bytes = expect.encode("utf-8")
print("orig utf8 bytes:", orig_bytes.hex())
for enc in ("gbk", "cp936", "big5", "shift_jis", "cp932", "euc-kr", "utf-8"):
    try:
        s = orig_bytes.decode(enc, errors="replace")
    except Exception as e:
        print(enc, "fail", e)
        continue
    print("%-10s -> %s" % (enc, s[:16]))
    # 差异熵：统计私用区字符数
    pua = sum(1 for c in s if 0xE000 <= ord(c) <= 0xF8FF)
    print("            PUA 数 =", pua)
# 反向：现状字符 -> 哪些编码能编码
print("--- 现状前 20 字符可否被各编码编码 ---")
for enc in ("gbk", "cp936", "big5", "shift_jis", "cp932", "euc-kr", "latin1", "cp1252"):
    bad = 0
    for c in cur:
        try:
            c.encode(enc)
        except Exception:
            bad += 1
    print("%-10s bad=%d/%d" % (enc, bad, len(cur)))
