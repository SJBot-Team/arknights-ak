#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v9: 用指令起点缓存扫描 `[reg+disp32=target]`，**读/写双向枚举**（不用 ModRM 位序捷径）。

用法: python t200a_index9.py <target_hex> [--kind w|r|all] [--cls REGEX] [--max N]
"""
import sys, struct, bisect, io, re, os
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
OUTDIR = r"C:\Users\23922\Documents\ds_harness\ak\.tmp"
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG

_idx = None


def build_method_index():
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


def load_starts():
    starts = {}
    d = pefile.PE(DLL, fast_load=True)
    for s in d.sections:
        if not (s.Characteristics & 0x20000000):
            continue
        p = os.path.join(OUTDIR, "t200a_starts_%x.bin" % s.VirtualAddress)
        if not os.path.exists(p):
            continue
        b = open(p, "rb").read()
        starts[s.VirtualAddress] = list(struct.unpack("<%dI" % (len(b) // 4), b))
    return starts


def is_mem_at(o, target):
    return (o.type == CS_OP_MEM and o.mem.disp == target
            and o.mem.index == 0 and o.mem.base != 0)


def main():
    target = int(sys.argv[1], 16)
    kind = sys.argv[sys.argv.index("--kind") + 1] if "--kind" in sys.argv else "all"
    clsre = re.compile(sys.argv[sys.argv.index("--cls") + 1]) if "--cls" in sys.argv else None
    maxn = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 400

    d = pefile.PE(DLL, fast_load=True)
    segs = [(s.VirtualAddress, s.get_data()) for s in d.sections if s.Characteristics & 0x20000000]
    starts = load_starts()
    disp = struct.pack("<I", target)
    midx = build_method_index()
    mkeys = sorted(midx)
    out = []
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
    n_disp = 0
    for sva, sdata in segs:
        st = starts.get(sva)
        if not st:
            continue
        stset = set(st)
        p = 0
        while True:
            i = sdata.find(disp, p)
            if i < 0:
                break
            p = i + 1
            n_disp += 1
            for back in range(4, 12):
                s0 = i - back
                if s0 < 0 or s0 not in stset:
                    continue
                try:
                    lst = list(md.disasm(sdata[s0:s0 + 16], 0))
                except Exception:
                    continue
                if not lst:
                    continue
                ins = lst[0]
                if ins.address + ins.size != 4 + (i - s0):
                    continue
                if not ins.operands:
                    continue
                mem_idx = None
                for oi, o in enumerate(ins.operands):
                    if is_mem_at(o, target):
                        mem_idx = oi
                if mem_idx is None:
                    continue
                out.append((sva + s0, ins, mem_idx))
                break
    seen = set()
    uniq = []
    for rva, ins, mi in sorted(out):
        if rva in seen:
            continue
        seen.add(rva)
        uniq.append((rva, ins, mi))
    nw = sum(1 for _, ins, mi in uniq if mi == 0)
    nr = len(uniq) - nw
    print(f"=== [reg+0x{target:X}] disp 字节出现 {n_disp} 次，指令起点精确命中 {len(uniq)} "
          f"(写={nw} 读={nr}) ===")
    lines = []
    for rva, ins, mi in uniq:
        is_write = (mi == 0)
        if kind == "w" and not is_write:
            continue
        if kind == "r" and is_write:
            continue
        k = bisect.bisect_right(mkeys, rva) - 1
        if k < 0:
            label, delta = "?", rva
        else:
            g = midx[mkeys[k]]
            delta = rva - mkeys[k]
            label = g[0][0] + "." + g[0][1] + (f" [+{len(g)-1}同构]" if len(g) > 1 else "")
            if delta > 0x4000:
                label = "UNMATCHED"
        if clsre and not clsre.search(label):
            continue
        lines.append((rva, ins, label, delta, is_write))
    shown = 0
    for rva, ins, label, delta, is_write in lines:
        s = (f"{'W' if is_write else 'r'} 0x{rva:08X}  {ins.bytes.hex():<20} {ins.mnemonic:<7} "
             f"{ins.op_str:<44} | {label} +0x{delta:X}")
        if shown < maxn:
            print(s)
            shown += 1
    agg = {}
    for rva, ins, label, delta, is_write in lines:
        key = re.sub(r" \[\+\d+同构\]$", "", label)
        agg.setdefault(key, []).append((rva, ins, is_write))
    print(f"\n=== 按方法汇总（{len(agg)} 方法）===")
    for k, v in sorted(agg.items()):
        print(f"  {len(v):3d} 处  {k}")
    outp = os.path.join(OUTDIR, "t200a_idx9_%x_%s.txt" % (target, kind))
    with io.open(outp, "w", encoding="utf-8") as f:
        for rva, ins, label, delta, is_write in lines:
            f.write(f"{'W' if is_write else 'r'} 0x{rva:08X}\t{ins.bytes.hex()}\t{ins.mnemonic} {ins.op_str}\t{label}\t+0x{delta:X}\n")
    print("全量 -> " + outp)


if __name__ == "__main__":
    main()
