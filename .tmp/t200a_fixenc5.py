#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 试"现状 UTF-8 -> 文本按 GBK/cp936 编码 -> 解 UTF-8"的还原，并报告坏点数。"""
import io, sys

p = sys.argv[1]
s = open(p, "rb").read().decode("utf-8").lstrip("\ufeff")
# 注意：cu = 现状；我们要的是把 cu 用 gbk 编回去
enc_map = {}
for enc in ("gbk", "gb18030", "cp936"):
    enc_map[enc] = codecs_errors = 0
import codecs
best = None
for enc in ("gbk", "gb18030"):
    b = bytearray()
    errs = 0
    for ch in s:
        try:
            b += ch.encode(enc)
        except UnicodeEncodeError:
            b += ch.encode("utf-8")   # 无法回编的按 UTF-8 原样塞回
            errs += 1
    try:
        fixed = bytes(b).decode("utf-8")
        dec_err = 0
    except UnicodeDecodeError as e:
        fixed = bytes(b).decode("utf-8", errors="replace")
        dec_err = 1
    zh = sum(1 for c in fixed if "\u4e00" <= c <= "\u9fff")
    repl = fixed.count("\ufffd")
    with io.open(p + ".restore_" + enc, "w", encoding="utf-8") as f:
        f.write(fixed)
    print("%-9s encode-fail=%d decode-fail=%d U+FFFD=%d 中文字符=%d 总长=%d" % (
        enc, errs, dec_err, repl, zh, len(fixed)))
