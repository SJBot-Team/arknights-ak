#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""列出 04 目录所有 md 文件 + 其 H1 标题 + 行数/字节数，供重建 00_目录.md 用。"""
import io, os, re

D = r"C:\Users\23922\Documents\ds_harness\ak\knowledge\04_数据对应与核验"
rows = []
for name in sorted(os.listdir(D), key=lambda x: x.lower()):
    if not name.lower().endswith(".md"):
        continue
    if name.startswith("00_目录"):
        continue
    p = os.path.join(D, name)
    b = open(p, "rb").read()
    try:
        txt = b.decode("utf-8")
    except UnicodeDecodeError:
        txt = b.decode("utf-8", errors="replace")
    lines = txt.split("\n")
    h1 = ""
    for ln in lines[:6]:
        if ln.startswith("# "):
            h1 = ln[2:].strip()
            break
    rows.append((name, len(lines), len(b), h1))
with io.open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t200a_filelist.txt", "w", encoding="utf-8") as f:
    f.write("files=%d\n" % len(rows))
    for name, n, sz, h1 in rows:
        f.write("%-56s %5d行 %7dB  %s\n" % (name, n, sz, h1))
print("files", len(rows))
