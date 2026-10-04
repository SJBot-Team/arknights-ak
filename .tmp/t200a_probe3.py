#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 直接尝试"期望原文 -> 各种编码误解码"，找与现状一致的那个。"""
import io

expect = "# 00 目录 / 导航（数据对应与核验）"
raw = open(r"C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验\00_目录.md", "rb").read().decode("utf-8").lstrip("\ufeff")
cur = raw[:len(expect)]

res = []
for enc in ("gbk", "cp936", "gb18030", "big5", "cp950", "shift_jis", "cp932", "euc_jp",
            "euc_kr", "cp949", "cp1251", "cp1252", "koi8_r", "latin1", "mac_roman", "cp874"):
    try:
        s = expect.encode("utf-8").decode(enc)
    except Exception as e:
        res.append("%-10s FAIL %s" % (enc, e))
        continue
    same = sum(1 for a, b in zip(s, cur) if a == b)
    res.append("%-10s match=%d/%d  first=%s" % (enc, same, len(cur), s[:12]))
with io.open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t200a_probe3.txt", "w", encoding="utf-8") as f:
    f.write("cur = " + cur + "\n\n")
    f.write("\n".join(res))
print("done")
