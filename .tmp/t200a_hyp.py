#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 用已知原文片段验证"UTF-8 字节流按 cp936 解码"这条假设。"""
import io

cases = {
    "目录": "e79bae",
    "导航": "e5afbce888aa",
    "数据": "e695b0e68dae",
    "核验": "e6a0b8e9aa8c",
    "全角（": "efbc88",
}
out = []
for txt, hx in cases.items():
    b = bytes.fromhex(hx)
    r = []
    for enc in ("gbk", "gb18030", "cp936"):
        try:
            r.append(enc + "=" + b.decode(enc))
        except Exception as e:
            r.append(enc + "=FAIL(" + str(e)[:30] + ")")
    out.append("%s [%s] -> %s" % (txt, hx, " | ".join(r)))
io.open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t200a_hyp.txt", "w", encoding="utf-8").write("\n".join(out))
print("ok")
