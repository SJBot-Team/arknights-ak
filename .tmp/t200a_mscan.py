#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v11: 无需全段指令缓存的精确扫描 —— 对每个含目标 disp32 字节的方法，
用方法入口锚定反汇编整段方法，取"自然结束于 disp32 末尾且操作数位移命中"的指令。

用法: python t200a_mscan.py <target_hex> [--kind w|r|all] [--cls REGEX] [--max N]
"""
import sys, struct, io, re, os, bisect
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
OUTDIR = r"C:\Users\23922\Documents\ds_harness\ak\.tmp"
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM

_idx = None


def method_index():
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
    target = int(sys.argv[1], 16)
    kind = sys.argv[sys.argv.index("--kind") + 1] if "--kind" in sys.argv else "all"
    clsre = re.compile(sys.argv[sys.argv.index("--cls") + 1]) if "--cls" in sys.argv else None
    maxn = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 400
    disp = struct.pack("<I", target)

    d = pefile.PE(DLL, fast_load=True)
    midx = method_index()
    mkeys = sorted(midx)
    res = []
    for s in d.sections:
        if not (s.Characteristics & 0x20000000):
            continue
        sva = s.VirtualAddress
        sd = s.get_data()
        seg_hi = sva + len(sd)
        mine = [k for k in mkeys if sva <= k < seg_hi]
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        md.detail = True
        for n, mstart in enumerate(mine):
            mend = min(mine[n + 1] if n + 1 < len(mine) else seg_hi, mstart + 0x4000, seg_hi)
            lo = mstart - sva
            hi = mend - sva
            blob = sd[lo:hi]
            if disp not in blob:
                continue
            # 一次锚定扫描整段方法，收集所有命中
            cur = 0
            while cur < len(blob):
                got = None
                try:
                    for ins in md.disasm(blob[cur:cur + 16], cur):
                        got = ins
                        break
                except Exception:
                    pass
                if got is None:
                    cur += 1
                    continue
                end_off = got.address + got.size
                if got.operands:
                    mi = None
                    for oi, o in enumerate(got.operands):
                        if (o.type == CS_OP_MEM and o.mem.disp == target
                                and o.mem.index == 0 and o.mem.base != 0):
                            mi = oi
                            break
                    if mi is not None and disp in got.bytes:
                        res.append((mstart, sva + got.address, got, mi))
                cur = end_off
    # 去重
    seen = set()
    uniq = []
    for mstart, rva, ins, mi in sorted(res, key=lambda x: x[1]):
        if rva in seen:
            continue
        seen.add(rva)
        uniq.append((mstart, rva, ins, mi))
    nw = sum(1 for _, _, ins, mi in uniq if mi == 0)
    print(f"=== [reg+0x{target:X}] 方法锚定精确命中 {len(uniq)} (mem在op0=写 {nw} / 其余=读 {len(uniq)-nw}) ===")
    lines = []
    for mstart, rva, ins, mi in uniq:
        is_write = (mi == 0)
        if kind == "w" and not is_write:
            continue
        if kind == "r" and is_write:
            continue
        g = midx[mstart]
        label = g[0][0] + "." + g[0][1] + (f" [+{len(g)-1}同构]" if len(g) > 1 else "")
        if clsre and not clsre.search(label):
            continue
        lines.append((rva, ins, label, rva - mstart, is_write))
    shown = 0
    for rva, ins, label, delta, is_write in lines:
        s = (f"{'W' if is_write else 'r'} 0x{rva:08X}  {ins.bytes.hex():<20} {ins.mnemonic:<7} "
             f"{ins.op_str:<44} | {label} +0x{delta:X}")
        if shown < maxn:
            print(s)
            shown += 1
    outp = os.path.join(OUTDIR, "t200a_m_%x_%s.txt" % (target, kind))
    with io.open(outp, "w", encoding="utf-8") as f:
        for rva, ins, label, delta, is_write in lines:
            f.write(f"{'W' if is_write else 'r'} 0x{rva:08X}\t{ins.bytes.hex()}\t{ins.mnemonic} {ins.op_str}\t{label}\t+0x{delta:X}\n")
    print(f"（过滤后 {len(lines)} 行）-> " + outp)


if __name__ == "__main__":
    main()
