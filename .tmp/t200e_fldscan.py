#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T-200e：扫描"写某个字段偏移"的指令（movss/mov/mov imm → [reg+disp32]）。

用法: python t200e_fldscan.py <disp_hex> [lo] [hi]
命中类型：
  movss [r+d], xmm   = F3 0F 11 <modrm mod=10>
  mov   [r+d], r32   = 89 <modrm mod=10>
  mov   dword [r+d], imm32 = C7 <modrm mod=10>
"""
import struct
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code", "tools"))
import read_cpp as R

REGS = {0: "rax", 1: "rcx", 2: "rdx", 3: "rbx", 6: "rsi", 7: "rdi"}


def main():
    disp = int(sys.argv[1], 16)
    lo = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x2000000
    d = R.Dll()
    idx = R.rva_index()
    keys = sorted(idx)
    raw = struct.pack("<i", disp)
    found = []
    for s in d.pe.sections:
        if not (s.Characteristics & 0x20000000):
            continue
        base = s.VirtualAddress
        data = s.get_data()
        n = len(data)
        off = 0
        while True:
            i = data.find(raw, off)
            if i < 0:
                break
            off = i + 1
            kind = None
            start = None
            reg = "?"
            if i >= 4 and data[i - 4] == 0xF3 and data[i - 3] == 0x0F and data[i - 2] == 0x11:
                m = data[i - 1]
                if (m & 0xC0) == 0x80 and (m & 7) not in (4, 5):
                    kind, start, reg = "movss [r+d],xmm", i - 4, REGS.get(m & 7, "?")
            elif i >= 3 and data[i - 3] == 0x89:
                m = data[i - 2]
                if (m & 0xC0) == 0x80 and (m & 7) not in (4, 5):
                    kind, start, reg = "mov [r+d],r32", i - 3, REGS.get(m & 7, "?")
            elif i >= 3 and data[i - 3] == 0xC7:
                m = data[i - 2]
                if (m & 0xC0) == 0x80 and (m & 0x38) == 0 and (m & 7) not in (4, 5):
                    kind, start, reg = "mov dword [r+d],imm", i - 3, REGS.get(m & 7, "?")
            if kind is None:
                continue
            rva = base + start
            if lo <= rva <= hi:
                found.append((rva, kind, reg))
    print(f"共 {len(found)} 处写 [reg+0x{disp:X}]")
    for rva, kind, reg in found:
        cands = [k for k in keys if k <= rva]
        near = max(cands) if cands else None
        if near is not None and rva - near < 0x8000:
            g = idx[near]
            label = f"{g[0][0]}.{g[0][1]} (+0x{rva-near:X})"
            if len(g) > 1:
                label += f" [{len(g)} 同构]"
        else:
            label = "?"
        print(f"  {kind:<22} {reg:<4} @ 0x{rva:X}  ← {label}")


if __name__ == "__main__":
    main()
