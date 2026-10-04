#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T-200e：扫描 `mov r64,[r64+disp32]; call r64` 形式的虚表槽调用（IL2CPP 需要 methodInfo 时用它）。

用法: python t200e_slotscan2.py <off_hex> [lo] [hi]
"""
import struct
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code", "tools"))
import read_cpp as R

REGS = {0: "rax", 1: "rcx", 2: "rdx", 3: "rbx", 6: "rsi", 7: "rdi"}


def main():
    off = int(sys.argv[1], 16)
    lo = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x2000000
    d = R.Dll()
    idx = R.rva_index()
    keys = sorted(idx)
    disp = struct.pack("<i", off)
    hits = []
    for s in d.pe.sections:
        if not (s.Characteristics & 0x20000000):
            continue
        base = s.VirtualAddress
        data = s.get_data()
        n = len(data)
        for i in range(n - 12):
            # REX.W + 8B /r, mod=10, rm != 4(SIB), rm != 5(rip)
            if data[i] != 0x48 or data[i + 1] != 0x8B:
                continue
            modrm = data[i + 2]
            if (modrm & 0xC7) != 0x80:
                continue
            rm = modrm & 7
            if rm in (4, 5):
                continue
            if data[i + 3:i + 7] != disp:
                continue
            dst = (modrm >> 3) & 7
            # 往后 14 字节内找 call <dst>
            for j in range(i + 7, min(i + 21, n - 2)):
                if data[j] == 0xFF and (data[j + 1] & 0xF8) == 0xD0 and (data[j + 1] & 7) == dst:
                    rva = base + j
                    if lo <= rva <= hi:
                        hits.append((base + i, rva, REGS[rm], REGS.get(dst, "?")))
                    break
    print(f"共 {len(hits)} 处 mov->call [reg+0x{off:X}]")
    for mva, cva, src, dst in hits:
        cands = [k for k in keys if k <= cva]
        near = max(cands) if cands else None
        if near is not None and cva - near < 0x8000:
            g = idx[near]
            label = f"{g[0][0]}.{g[0][1]} (+0x{cva-near:X})"
            if len(g) > 1:
                label += f" [{len(g)} 同构]"
        else:
            label = "?"
        print(f"  mov {dst},[{src}+0x{off:X}] @ 0x{mva:X} ; call {dst} @ 0x{cva:X}  ← {label}")


if __name__ == "__main__":
    main()
