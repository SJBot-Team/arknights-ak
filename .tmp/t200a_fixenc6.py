#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 测试"现状 mojibake -> GB18030 解 -> UTF-8"的可逆性，并统计可读性。"""
import io

p = r"C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\00_目录.md"
s = open(p, "rb").read().decode("utf-8").lstrip("\ufeff")

for enc in ("gbk", "gb18030", "cp936"):
    b = bytearray()
    lost = 0
    for ch in s:
        cp = ord(ch)
        if 0xE000 <= cp <= 0xF8FF:
            b.append(cp & 0xFF)
        elif cp == 0x20AC:
            b.append(0x80)
        else:
            try:
                b += ch.encode(enc)
            except UnicodeEncodeError:
                lost += 1
                b.append(0x3F)   # '?'
    for err in ("strict", "replace"):
        try:
            f = bytes(b).decode("utf-8", errors=err)
        except UnicodeDecodeError as e:
            print("%-8s %-7s DECODE FAIL %s" % (enc, err, e))
            continue
        zh = sum(1 for c in f if "\u4e00" <= c <= "\u9fff")
        print("%-8s %-7s unencodable=%d U+FFFD=%d 汉字=%d 总长=%d" % (
            enc, err, lost, f.count("\ufffd"), zh, len(f)))
        io.open(p + ".try_" + enc, "w", encoding="utf-8").write(f)
