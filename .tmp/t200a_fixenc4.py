#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 反向修复 v3 —— 逐字符构造"损坏前的字节流"，再按 UTF-8 解回原文。

损坏链（实测推断）：
  原 UTF-8 字节流 B
    --[PS Get-Content 按 ANSI(cp936) 解码]--> 乱码串 S（含 U+E0xx~U+E7xx 私用区字符、U+20AC）
    --[PS Set-Content -Encoding utf8]--> 现状文件（UTF-8 + BOM）
反函数：对 S 的每个字符还原出它"当时吃掉的字节"
"""
import sys, io

p = sys.argv[1]
raw = open(p, "rb").read()
s = raw.decode("utf-8")
if s.startswith("\ufeff"):
    s = s[1:]

out = bytearray()
unresolved = []
for i, ch in enumerate(s):
    cp = ord(ch)
    if 0xE000 <= cp <= 0xF8FF or cp == 0x20AC:
        # 私用区 / 欧元符：还原为单字节
        out.append(cp & 0xFF)
    else:
        try:
            out += ch.encode("gbk")
        except UnicodeEncodeError:
            try:
                out += ch.encode("utf-8")
                unresolved.append((i, ch, hex(cp)))
            except Exception:
                unresolved.append((i, ch, "FAIL"))
try:
    fixed = bytes(out).decode("utf-8")
except UnicodeDecodeError as e:
    print("UTF-8 解码失败:", e)
    fixed = bytes(out).decode("utf-8", errors="replace")
with io.open(p + ".fix", "w", encoding="utf-8") as f:
    f.write(fixed)
with io.open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t200a_fix3.txt", "w", encoding="utf-8") as f:
    zh = sum(1 for c in fixed if "\u4e00" <= c <= "\u9fff")
    f.write("unresolved=%d 中文字符=%d 总长=%d\n" % (len(unresolved), zh, len(fixed)))
    f.write("\n".join(repr(t) for t in unresolved[:30]))
    f.write("\n---- 前 600 字 ----\n")
    f.write(fixed[:600])
print("unresolved=%d" % len(unresolved))
