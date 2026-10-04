#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T-200e：在 dump.cs 里按"声明行包含某子串"反查它的 RVA（支持 private 嵌套类，read_cpp.py cls/m 不支持）。

用法: python t200e_sig.py <子串>   [最多输出条数]
"""
import io
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
DUMP = r"E:\__file\ak_kb\client_res\il2cpp\dump\dump.cs"


def main():
    needle = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    n = 0
    with io.open(DUMP, encoding="utf-8", errors="replace") as f:
        last_rva = None
        last_cls = "?"
        for idx, ln in enumerate(f, 1):
            s = ln.rstrip("\n")
            if "// RVA:" in s:
                last_rva = s.strip()
                continue
            if s.startswith("public ") or s.startswith("private ") or s.startswith("internal ") or s.startswith("protected "):
                if (" class " in s or " struct " in s or " interface " in s or " enum " in s):
                    last_cls = s.strip()
            if needle in s and last_rva:
                n += 1
                if n <= limit:
                    print(f"{idx}: {last_rva}  |  {s.strip()}")
                last_rva = None
    print(f"--- 共 {n} 处 ---")


if __name__ == "__main__":
    main()
