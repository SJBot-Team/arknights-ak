#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v7: 一次性线性反汇编全 il2cpp 段，建"真实指令起点"集合，然后按方法归属列 [reg+0x??] 读/写点。

用法:
  python t200a_sweep7.py build                      # 建指令起点缓存 .tmp/t200a_starts_<seg>.bin
  python t200a_sweep7.py scan <target_hex> [--w|--r] [--cls REGEX] [--max N]
"""
import sys, struct, bisect, io, re, os
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
OUTDIR = r"C:\Users\23922\Documents\ds_harness\ak\.tmp"
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM

def build_method_index():
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

def build_starts():
    d = pefile.PE(DLL, fast_load=True)
    midx_all = build_method_index()
    print(f"方法索引 {len(midx_all)} 个 RVA 起点", flush=True)
    for si, s in enumerate(d.sections):
        if not (s.Characteristics & 0x20000000): continue
        sva = s.VirtualAddress; sd = s.get_data()
        ks = sorted(k for k in midx_all if sva <= k < sva + len(sd))
        if not ks:
            print(f"seg {s.Name.decode(errors='replace').strip(chr(0))} VA=0x{sva:X} 无方法，跳过", flush=True)
            continue
        print(f"seg {s.Name.decode(errors='replace').strip(chr(0))} VA=0x{sva:X} 方法 {len(ks)} "
              f"首 0x{ks[0]:X} 末 0x{ks[-1]:X} size 0x{len(sd):X}", flush=True)
        # 线性反汇编 [ks[0]-? , 末方法+0x4000)
        lo = ks[0] - sva
        hi = min(len(sd), ks[-1] - sva + 0x4000)
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        t0 = __import__("time").time()
        cur = lo
        n = 0
        with io.open(os.path.join(OUTDIR, f"t200a_starts_{sva:x}.bin"), "wb") as f:
            buf = bytearray()
            while cur < hi:
                got = None
                for ins in md.disasm(sd[cur:cur + 15], cur):
                    got = ins; break
                if got is None:
                    cur += 1
                    continue
                buf += struct.pack("<I", cur)
                n += 1
                cur += got.size
                if len(buf) > 1 << 22:
                    f.write(buf); buf = bytearray()
            f.write(buf)
        print(f"  指令 {n} 条 用时 {__import__('time').time()-t0:.1f}s -> t200a_starts_{sva:x}.bin")

def load_starts():
    starts = {}
    d = pefile.PE(DLL, fast_load=True)
    for s in d.sections:
        if not (s.Characteristics & 0x20000000): continue
        p = os.path.join(OUTDIR, f"t200a_starts_{s.VirtualAddress:x}.bin")
        if not os.path.exists(p): continue
        b = open(p, "rb").read()
        arr = struct.unpack("<%dI" % (len(b) // 4), b)
        starts[s.VirtualAddress] = set(arr)
        print(f"载入 {p}: {len(arr)} 条指令起点")
    return starts

def owner(midx, mkeys, rva):
    i = bisect.bisect_right(mkeys, rva) - 1
    if i < 0: return [("?", "?", 0)], rva
    k = mkeys[i]
    return midx[k], rva - k

def scan(target, only=None, clsre=None, maxn=200):
    d = pefile.PE(DLL, fast_load=True)
    segs = [(s.VirtualAddress, s.get_data()) for s in d.sections if s.Characteristics & 0x20000000]
    disp = struct.pack("<I", target)
    starts = load_starts()
    midx = build_method_index(); mkeys = sorted(midx)
    # 把所有指令起点汇总到一个集合（带段前缀）
    allstarts = {}
    for sva, sd in segs:
        allstarts[sva] = starts.get(sva, set())
    md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True
    out = []
    for sva, sdata in segs:
        st = allstarts[sva]
        p = 0
        while True:
            i = sdata.find(disp, p)
            if i < 0: break
            p = i + 1
            # 操作数占 [i, i+4)；找一条指令结束于 i+4
            for back in range(4, 12):
                s0 = i - back
                if s0 < 0 or s0 not in st: continue
                try:
                    lst = list(md.disasm(sdata[s0:s0 + 16], s0))
                except Exception:
                    continue
                if not lst: continue
                ins = lst[0]
                if ins.address + ins.size != i + 4: continue
                if not ins.operands: continue
                o = ins.operands[0]
                if o.type != CS_OP_MEM: continue
                if o.mem.disp != target or o.mem.index != 0 or o.mem.base == 0: continue
                write = True
                out.append((sva + s0, ins, write)); break
    # 去重
    seen = set(); uniq = []
    for rva, ins, w in out:
        if rva in seen: continue
        seen.add(rva); uniq.append((rva, ins, w))
    uniq.sort(key=lambda x: x[0])
    lines = []
    n = 0
    for rva, ins, w in uniq:
        g, delta = owner(midx, mkeys, rva)
        label = g[0][0] + "." + g[0][1] + (f" [+{len(g)-1}同构]" if len(g) > 1 else "") if delta < 0x4000 else "⚠️未命中"
        if clsre and not clsre.search(label): continue
        s = f"{'W' if w else 'r'} 0x{rva:08X}  {ins.bytes.hex():<18} {ins.mnemonic:<8} {ins.op_str:<44} | {label} +0x{delta:X}"
        lines.append(s)
        if n < maxn:
            print(s); n += 1
    print(f"=== total {len(uniq)} / shown {n} ===")
    with io.open(os.path.join(OUTDIR, "t200a_scan_%x.txt" % target), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    if sys.argv[1] == "build":
        build_starts()
    else:
        t = int(sys.argv[2], 16)
        clsre = re.compile(sys.argv[sys.argv.index("--cls") + 1]) if "--cls" in sys.argv else None
        mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 200
        scan(t, clsre=clsre, maxn=mx)
