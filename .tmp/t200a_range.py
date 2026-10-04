#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 反汇编一段 RVA 区间，列出所有访问 [reg+disp] 的位置并标注所属方法。

用法: python t200a_range.py <lo_hex> <hi_hex> <disp_hex> [--max N]
"""
import sys, io, re, bisect
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM

_idx = None


def build_index():
    global _idx
    if _idx is not None:
        return _idx
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
    _idx = idx
    return idx


def main():
    lo = int(sys.argv[1], 16)
    hi = int(sys.argv[2], 16)
    disp = int(sys.argv[3], 16)
    maxn = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 400
    d = pefile.PE(DLL, fast_load=True)
    off = d.get_offset_from_rva(lo)
    data = open(DLL, "rb").read()
    code = data[off: off + (hi - lo)]
    idx = build_index()
    keys = sorted(idx)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    n = 0
    for ins in md.disasm(code, lo):
        if not ins.operands:
            continue
        hit = False
        for oi, o in enumerate(ins.operands):
            if o.type == CS_OP_MEM and o.mem.disp == disp and o.mem.index == 0:
                hit = True
        if not hit:
            continue
        k = bisect.bisect_right(keys, ins.address) - 1
        label = "?"
        delta = 0
        if k >= 0:
            g = idx[keys[k]]
            delta = ins.address - keys[k]
            label = g[0][0] + "." + g[0][1] + (f" [+{len(g)-1}同构]" if len(g) > 1 else "")
            if delta > 0x4000:
                label = "UNMATCHED"
        print(f"0x{ins.address:08X}  {ins.bytes.hex():<20} {ins.mnemonic:<7} {ins.op_str:<44} | {label} +0x{delta:X}")
        n += 1
        if n >= maxn:
            break
    print(f"--- 区间 0x{lo:X}-0x{hi:X} 内 [+0x{disp:X}] 访问 {n} 条 ---")


if __name__ == "__main__":
    main()
