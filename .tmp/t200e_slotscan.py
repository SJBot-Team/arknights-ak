#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T-200e：扫描 .text/il2cpp 段里所有 `call/jmp qword ptr [reg + imm32]`，
用于定位"按虚表槽调用"的调用点。

IL2CPP 虚表约定（本轮由 0x56D0 实证）：slot S 的方法指针位于
    *(void**)(klass + 0x138 + S*16)
⇒ Slot13（TargetTrigger.Search）= +0x208

用法:
  python t200e_slotscan.py <off_hex>          # 只找该偏移
  python t200e_slotscan.py <off_hex> <lo_rva> <hi_rva>
"""
import re
import struct
import sys
import os

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "code", "tools"))
import read_cpp as R

MODRM_REGS = {0: "rax", 1: "rcx", 2: "rdx", 3: "rbx", 5: "rbp", 6: "rsi", 7: "rdi"}


def main():
    off = int(sys.argv[1], 16)
    lo = int(sys.argv[2], 16) if len(sys.argv) > 2 else 0
    hi = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x2000000
    d = R.Dll()
    idx = R.rva_index()
    keys = sorted(idx)
    pat = struct.pack("<i", off)

    hits = []
    for s in d.pe.sections:
        if not (s.Characteristics & 0x20000000):
            continue
        base = s.VirtualAddress
        data = s.get_data()
        for i in range(len(data) - 8):
            # FF /2 (call) or FF /4 (jmp), mod=10 (disp32), rm=reg
            if data[i] != 0xFF:
                continue
            modrm = data[i + 1]
            if (modrm & 0xF8) not in (0x90, 0xA0):
                continue
            if (modrm & 0xC7) not in (0x80 | 2, 0x80 | 4):
                if not ((modrm & 0xC0) == 0x80 and (modrm & 0x38) in (0x10, 0x20)):
                    continue
            reg = MODRM_REGS.get(modrm & 7)
            if reg is None:
                continue
            if struct.unpack("<i", data[i + 2:i + 6])[0] != off:
                continue
            rva = base + i
            if not (lo <= rva <= hi):
                continue
            hits.append((rva, "call" if (modrm & 0x38) == 0x10 else "jmp", reg))

    print(f"共 {len(hits)} 处 [reg+0x{off:X}] 虚调用")
    for rva, kind, reg in hits:
        cands = [k for k in keys if k <= rva]
        near = max(cands) if cands else None
        if near is not None and rva - near < 0x8000:
            g = idx[near]
            label = f"{g[0][0]}.{g[0][1]} (+0x{rva-near:X})"
            if len(g) > 1:
                label += f" [{len(g)} 同构]"
        else:
            label = "?"
        print(f"  {kind} [{reg}+0x{off:X}] @ 0x{rva:X}  ← {label}")


if __name__ == "__main__":
    main()
