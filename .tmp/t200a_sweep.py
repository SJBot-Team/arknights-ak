#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v6: 按 dump.cs 方法归属，扫全 DLL 的 `[reg+disp32=target]` 读/写点。

思路（避开"盲目猜指令起点"）：
  1. 从 dump.cs 建 RVA -> 方法(sorted) 全量索引；
  2. 对每个方法区间，先在原始字节里 find disp32 模式（快）；
  3. 对每个命中点，从 max(mstart, hit-64) 起做一次线性反汇编，
     取"结束于 hit+4 且首操作数为 mem 且 disp==target 且无 index"的指令 —— 这就是指令边界证据；
  4. 按方法归属输出，标注 读(r)/写(W)。

用法: python t200a_sweep.py <target_hex> [--rva-lo X] [--rva-hi X] [--out FILE]
"""
import sys, struct, bisect, io, re
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
OUTDIR = r"C:\Users\23922\Documents\ds_harness\ak\.tmp"
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM

def build_method_index():
    """RVA -> [(class, sig, lineno)]，同时返回 sorted keys。"""
    idx = {}; cls = "?"
    rx_cls = re.compile(r"^public\s+(?:sealed\s+|abstract\s+|static\s+|partial\s+)*(?:class|struct|interface|enum)\s+([\w.<>`]+)")
    rx_rva = re.compile(r"^\s*//\s*RVA:\s*0x([0-9A-Fa-f]+)")
    pending = None
    with io.open(DUMP, encoding="utf-8", errors="replace") as f:
        for ln_no, ln in enumerate(f, 1):
            m = rx_cls.match(ln)
            if m: cls = m.group(1); continue
            m = rx_rva.match(ln)
            if m: pending = int(m.group(1), 16); continue
            if pending is not None:
                idx.setdefault(pending, []).append((cls, ln.strip(), ln_no)); pending = None
    return idx

def sweep(target, rva_lo=0, rva_hi=0):
    d = pefile.PE(DLL, fast_load=True)
    segs = []
    for s in d.sections:
        if s.Characteristics & 0x20000000:
            segs.append((s.VirtualAddress, s.get_data()))
    disp = struct.pack("<I", target)

    midx = build_method_index()
    mkeys = sorted(midx)
    print(f"方法索引 {len(mkeys)} 个 RVA 起点")

    hits = []
    md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True
    for si, (sva, sdata) in enumerate(segs):
        send = sva + len(sdata)
        # 只处理落在该方法起点范围内的方法
        ks = [k for k in mkeys if sva <= k < send]
        print(f"  seg {si} VA=0x{sva:X} 方法 {len(ks)}")
        for n, mstart in enumerate(ks):
            mend = min(mkeys[mkeys.index(mstart) + 1] if mkeys.index(mstart) + 1 < len(mkeys)
                       else send, mstart + 0x4000, send)
            if mstart >= rva_hi > 0: break
            if mend <= rva_lo: continue
            o0 = mstart - sva; o1 = mend - sva
            blob = sdata[o0:o1]
            p = 0
            while True:
                i = blob.find(disp, p)
                if i < 0: break
                p = i + 1
                hit = o0 + i
                start = max(o0, hit - 64)
                try:
                    md2 = Cs(CS_ARCH_X86, CS_MODE_64); md2.detail = True
                    lst = list(md2.disasm(sdata[start:hit + 4], 0))
                except Exception:
                    continue
                base_off = start
                got = None
                for ins in lst:
                    if ins.address + ins.size != hit + 4 - base_off: continue
                    if not ins.operands: continue
                    o = ins.operands[0]
                    if o.type != CS_OP_MEM: continue
                    if o.mem.disp != target or o.mem.index != 0 or o.mem.base == 0: continue
                    got = ins; break
                if got is None: continue
                hits.append((mstart, sva + got.address - base_off + base_off - base_off, got))
    return hits, midx

if __name__ == "__main__":
    target = int(sys.argv[1], 16)
    print("此脚本为半成品，见 v7")
