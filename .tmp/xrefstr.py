# -*- coding: utf-8 -*-
"""xrefstr.py 0x74DAE38 [...]  — find instructions in executable sections whose
rip-relative operand points at the given RVA (metadata usage slot / string literal)."""
import struct, sys, re
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, r"C:\Users\23922\Documents\ds_harness\ak\code\tools")
import read_cpp

def main():
    targets = set(int(a, 16) for a in sys.argv[1:])
    d = read_cpp.Dll()
    idx = read_cpp.rva_index(); keys = sorted(idx)
    hits = []
    for s in d.pe.sections:
        if not (s.Characteristics & 0x20000000):
            continue
        data = s.get_data()
        base = s.VirtualAddress
        for i in range(len(data) - 7):
            b0 = data[i]
            if not (0x48 <= b0 <= 0x4F):
                continue
            op = data[i+1]
            if op not in (0x8B, 0x8D, 0x89, 0x03, 0x2B, 0x33, 0x3B):
                continue
            modrm = data[i+2]
            if (modrm & 0xC7) != 0x05:
                continue
            disp = struct.unpack("<i", data[i+3:i+7])[0]
            insn_rva = base + i
            tgt = insn_rva + 7 + disp
            if tgt in targets:
                hits.append((insn_rva, tgt))
    for rva, tgt in hits:
        c = [k for k in keys if k <= rva]
        name = (f"{idx[max(c)][0]}.{idx[max(c)][1]} (+0x{rva-max(c):X})" if c else "?")
        print(f"ref@0x{rva:X} -> 0x{tgt:X}   in {name}")
    print(f"--- {len(hits)} hits ---")

main()
