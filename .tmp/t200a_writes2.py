#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 直接字节模式搜索 —— 找 `mov/lea/cmp [reg+disp32]` 且 disp32 命中的点（写/读点扫描）。

ModRM 位序提醒：[mod:2][reg:3][r/m:3]；mod=10 -> 数值高位为 10b，即 0x80|(reg<<3)|r/m。
（2026-09-29 修正：初版误把 0x89 当 ModRM，导致漏扫）
"""
import sys, struct, io, re, bisect, os
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
OUTDIR = r"C:\Users\23922\Documents\ds_harness\ak\.tmp"
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM


def build_index():
    idx = {}
    cls = "?"
    rx_cls = re.compile(r"^public\s+(?:sealed\s+|abstract\s+|static\s+|partial\s+)*(?:class|struct|interface|enum)\s+([\w.<>`]+)")
    rx_rva = re.compile(r"^\s*//\s*RVA:\s*0x([0-9A-Fa-f]+)")
    pending = None
    with io.open(DUMP, encoding="utf-8", errors="replace") as f:
        for ln_no, ln in enumerate(f, 1):
            m = rx_cls.match(ln)
            if m:
                cls = m.group(1)
                continue
            m = rx_rva.match(ln)
            if m:
                pending = int(m.group(1), 16)
                continue
            if pending is not None:
                idx.setdefault(pending, []).append((cls, ln.strip(), ln_no))
                pending = None
    return idx


def build_patterns(target):
    disp = struct.pack("<I", target)
    pats = []
    for r in range(8):
        m = 0x80 | (r << 3) | 4
        for rex in (b"", b"\x48", b"\x4c"):
            pats.append((rex + bytes([0x89, m]) + disp, "mov  write"))
            pats.append((rex + bytes([0x8D, m]) + disp, "lea"))
            pats.append((rex + bytes([0x8B, m]) + disp, "mov  read"))
            pats.append((rex + bytes([0x39, m]) + disp, "cmp  read"))
    return pats


def main():
    target = int(sys.argv[1], 16)
    kind = sys.argv[2] if len(sys.argv) > 2 else "all"
    pats = build_patterns(target)
    if kind == "w":
        pats = [p for p in pats if p[1].startswith("mov  write") or p[1] == "lea"]
    elif kind == "r":
        pats = [p for p in pats if "read" in p[1]]
    d = pefile.PE(DLL, fast_load=True)
    segs = [(s.VirtualAddress, s.get_data()) for s in d.sections if s.Characteristics & 0x20000000]
    midx = build_index()
    mkeys = sorted(midx)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    found = []
    for sva, sd in segs:
        for pat, desc in pats:
            p = 0
            while True:
                i = sd.find(pat, p)
                if i < 0:
                    break
                p = i + 1
                try:
                    lst = list(md.disasm(sd[i:i + 16], 0))
                except Exception:
                    continue
                if not lst:
                    continue
                ins = lst[0]
                if ins.bytes.hex() != pat.hex():
                    continue
                if not ins.operands:
                    continue
                o = ins.operands[0]
                if o.type != CS_OP_MEM or o.mem.disp != target or o.mem.index != 0:
                    continue
                found.append((sva + i, ins, desc))
    seen = set()
    uniq = []
    for rva, ins, desc in sorted(found):
        if rva in seen:
            continue
        seen.add(rva)
        uniq.append((rva, ins, desc))
    print(f"=== [reg+0x{target:X}] 模式命中 {len(uniq)} (kind={kind}) ===")
    lines = []
    for rva, ins, desc in uniq:
        k = bisect.bisect_right(mkeys, rva) - 1
        label = "?"
        delta = rva
        if k >= 0:
            g = midx[mkeys[k]]
            delta = rva - mkeys[k]
            label = g[0][0] + "." + g[0][1] + (f" [+{len(g)-1}同构]" if len(g) > 1 else "")
            if delta > 0x4000:
                label = "UNMATCHED"
        s = f"0x{rva:08X}  {ins.bytes.hex():<20} {ins.mnemonic:<5} {ins.op_str:<42} [{desc}] | {label} +0x{delta:X}"
        lines.append(s)
        print(s)
    with io.open(os.path.join(OUTDIR, "t200a_writes_%x_%s.txt" % (target, kind)), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
