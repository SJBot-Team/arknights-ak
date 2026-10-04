#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 反向修复 —— 现状 UTF-8 文本 -> latin1/GBK 字节 -> UTF-8 原文。

损坏链（推断）：原 UTF-8(无BOM) --[PS Get-Content 按 ANSI(cp936) 读]--> 乱码串
              --[PS Set-Content -Encoding utf8]--> 现状 UTF-8(+BOM)
修复链：现状 --[UTF-8 解码]--> 乱码串 --[按损坏链的反函数重编码]--> 原字节 --[UTF-8 解码]--> 原文
"""
import sys, io, codecs

p = sys.argv[1]
raw = open(p, "rb").read()
s = raw.decode("utf-8")
if s.startswith("\ufeff"):
    s = s[1:]

cands = []
for enc in ("gbk", "cp936", "latin1", "cp1252"):
    try:
        b = s.encode(enc)
    except UnicodeEncodeError as e:
        cands.append((enc, None, "encode-fail: %s" % e))
        continue
    try:
        fixed = b.decode("utf-8")
        cands.append((enc, fixed, "ok"))
    except UnicodeDecodeError as e:
        cands.append((enc, None, "decode-fail: %s" % e))

rep = []
for enc, fixed, status in cands:
    rep.append("== %s : %s" % (enc, status))
    if fixed:
        rep.append(fixed[:200])
        with io.open(p + ".fix_" + enc, "w", encoding="utf-8") as f:
            f.write(fixed)
        # 统计中文字符比例
        zh = sum(1 for c in fixed if "\u4e00" <= c <= "\u9fff")
        rep.append("中文字符数=%d / 总长=%d" % (zh, len(fixed)))
    rep.append("")
with io.open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t200a_fix2.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(rep))
print("done")
