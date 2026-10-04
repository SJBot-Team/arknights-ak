#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 搜 DLL 里 `mov r32, imm32` / `movss xmm, [rip+..]` 中出现的"帧长常数"，
并把命中点归属到方法。

用法: python t200a_const.py <value_hex>        # 例 0x3D088880 (1/30 s float bits)
"""
import sys, struct, io, re, bisect
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
import pefile

_idx = None


def mi():
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
    val = int(sys.argv[1], 16)
    pat = struct.pack("<I", val)
    d = pefile.PE(DLL, fast_load=True)
    idx = mi()
    keys = sorted(idx)
    n = 0
    for s in d.sections:
        if not (s.Characteristics & 0x20000000):
            continue
        sva = s.VirtualAddress
        sd = s.get_data()
        p = 0
        while True:
            i = sd.find(pat, p)
            if i < 0:
                break
            p = i + 1
            rva = sva + i
            k = bisect.bisect_right(keys, rva) - 1
            label = "?"
            if k >= 0 and rva - keys[k] < 0x4000:
                g = idx[keys[k]]
                label = g[0][0] + "." + g[0][1] + (" [+%d]" % (len(g) - 1) if len(g) > 1 else "") + " +0x%X" % (rva - keys[k])
            print("0x%08X  ctx=%s  | %s" % (rva, sd[i - 6:i + 6].hex(), label))
            n += 1
    print("--- 共 %d 处 ---" % n)


if __name__ == "__main__":
    main()
