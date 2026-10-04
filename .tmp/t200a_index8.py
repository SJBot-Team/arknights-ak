#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v8: 用"真实指令起点缓存"精确扫描 [reg+disp32=target] 的读/写点，并按方法归属汇总。

用法:
  python t200a_index8.py <target_hex> [--cls REGEX] [--kind w|r|all] [--max N]
"""
import sys, struct, bisect, io, re, os
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
OUTDIR = r"C:\Users\23922\Documents\ds_harness\ak\.tmp"
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM

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
        arr = list(struct.unpack("<%dI" % (len(b) // 4), b))
        starts[s.VirtualAddress] = arr
    return starts


def main():
    target = int(sys.argv[1], 16)
    kind = sys.argv[sys.argv.index("--kind") + 1] if "--kind" in sys.argv else "all"
    clsre = re.compile(sys.argv[sys.argv.index("--cls") + 1]) if "--cls" in sys.argv else None
    maxn = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 300

    d = pefile.PE(DLL, fast_load=True)
    segs = [(s.VirtualAddress, s.get_data()) for s in d.sections if s.Characteristics & 0x20000000]
    starts = load_starts()
    disp = struct.pack("<I", target)
    midx = build_method_index()
    mkeys = sorted(midx)
    out = []
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True
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
            for back in (4, 5, 6, 7, 8, 9, 10):
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
                o = ins.operands[0]
                if o.type != CS_OP_MEM or o.mem.disp != target or o.mem.index != 0:
                    continue
                out.append((sva + s0, ins))
                break
    seen = set()
    uniq = []
    for rva, ins in sorted(out):
        if rva in seen:
            continue
        seen.add(rva)
        uniq.append((rva, ins))

    # 归类：写 = 第 0 操作数是 mem；读 = 第 0 操作数是 reg（mem 在别处）
    lines = []
    stat = {"w": 0, "r": 0}
    for rva, ins in uniq:
        o0 = ins.operands[0]
        is_write = (o0.type == CS_OP_MEM)
        is_read = not is_write
        if kind == "w" and not is_write:
            continue
        if kind == "r" and not is_read:
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
        stat["w" if is_write else "r"] += 1

    print(f"=== [reg+0x{target:X}] 指令起点精确命中: 总 {len(uniq)} / 过滤后 {len(lines)} "
          f"(W={stat['w']} r={stat['r']}) ===")
    shown = 0
    for rva, ins, label, delta, is_write in lines:
        s = (f"{'W' if is_write else 'r'} 0x{rva:08X}  {ins.bytes.hex():<20} {ins.mnemonic:<7} "
             f"{ins.op_str:<44} | {label} +0x{delta:X}")
        if shown < maxn:
            print(s)
            shown += 1
    # 按方法去重汇总
    agg = {}
    for rva, ins, label, delta, is_write in lines:
        key = label.split(" +")[0]
        agg.setdefault(key, []).append((rva, ins, is_write))
    print(f"\n=== 按方法汇总（{len(agg)} 个方法）===")
    for k, v in sorted(agg.items(), key=lambda kv: -len(kv[1])):
        print(f"  {len(v):3d} 处  {k}")
    outp = os.path.join(OUTDIR, "t200a_idx_%x_%s.txt" % (target, kind))
    with io.open(outp, "w", encoding="utf-8") as f:
        f.write(f"target=0x{target:X} kind={kind}\n")
        for rva, ins, label, delta, is_write in lines:
            f.write(f"{'W' if is_write else 'r'} 0x{rva:08X}\t{ins.bytes.hex()}\t{ins.mnemonic} {ins.op_str}\t{label}\t+0x{delta:X}\n")
    print("全量 -> " + outp)


if __name__ == "__main__":
    main()
