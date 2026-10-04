#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T-200e 临时工具：按 RVA 反汇编一个方法体，并把每个 call/jmp 目标解析成 类.方法。

用法:
  python t200e_calls.py <rva_hex> [maxins]
读 read_cpp.py 的 Dll / rva_index 复用（只读 E 盘 dump/dll）。
"""
import sys, os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code", "tools"))
import read_cpp as R


def main():
    rva = int(sys.argv[1], 16)
    maxins = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    d = R.Dll()
    idx = R.rva_index()
    keys = sorted(idx)
    print(f"=== dis 0x{rva:X} (max {maxins} ins) ===")
    for ins, line in d.disasm(rva, maxins):
        extra = ""
        if ins.mnemonic in ("call", "jmp") and ins.op_str.startswith("0x"):
            tgt = int(ins.op_str, 16) - d.base
            hit = idx.get(tgt)
            if hit:
                extra = "   -> " + " | ".join(f"{c}.{s}" for c, s in hit[:3])
            else:
                cands = [k for k in keys if k <= tgt]
                near = max(cands) if cands else None
                if near is not None and tgt - near < 0x6000:
                    g = idx[near]
                    extra = (f"   -> [0x{tgt:X} 未索引] 近邻 0x{near:X}+0x{tgt-near:X} "
                             f"{g[0][0]}.{g[0][1]}")
                else:
                    extra = f"   -> [0x{tgt:X} ?]"
        print(line + extra)


if __name__ == "__main__":
    main()
