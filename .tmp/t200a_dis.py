#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""反汇编一段 RVA 区间，输出每条指令 + 对 E8/E9 目标的 RVA + 目标方法名（用 dump.cs 索引）。"""
import sys, io, re, bisect
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

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


def name_of(idx, keys, rva):
    i = bisect.bisect_left(keys, rva)
    if i < len(keys) and keys[i] == rva:
        g = idx[keys[i]]
        return g[0][0] + "." + g[0][1] + (f" [+{len(g)-1}]" if len(g) > 1 else "")
    # 最近前驱
    j = bisect.bisect_right(keys, rva) - 1
    if j >= 0 and rva - keys[j] < 0x40:
        g = idx[keys[j]]
        return "~" + g[0][0] + "." + g[0][1] + f" +0x{rva-keys[j]:X}"
    return "?"


def main():
    lo = int(sys.argv[1], 16)
    hi = int(sys.argv[2], 16)
    d = pefile.PE(DLL, fast_load=True)
    data = open(DLL, "rb").read()
    off = d.get_offset_from_rva(lo)
    code = data[off:off + (hi - lo)]
    idx = build_index()
    keys = sorted(idx)
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    for ins in md.disasm(code, lo):
        tgt = ""
        if ins.mnemonic in ("call", "jmp") and ins.op_str.startswith("0x"):
            t = int(ins.op_str, 16)
            tgt = f"  -> 0x{t:X} {name_of(idx, keys, t)}"
        print(f"0x{ins.address:08X}  {ins.bytes.hex():<20} {ins.mnemonic:<7} {ins.op_str:<42}{tgt}")


if __name__ == "__main__":
    main()
