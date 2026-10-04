#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v10-pass1: 以**每个方法入口为锚点**做线性反汇编，收集所有真实指令起点（uint32），
再与全段 sweep 的结果取并集，写成 .tmp/t200a_starts_a_<seg>.npy。

动机：整段单锚点 sweep（v7）会在 method 内部失步，导致真实指令起点漏采
（实测 0xA6EA2C `mov rax,[rbx+0x1a0]` 缺失，见 2026-09-29 记录）。
"""
import sys, io, re, time
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
OUTDIR = r"C:\Users\23922\Documents\ds_harness\ak\.tmp"
import pefile, numpy as np
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

rx_cls = re.compile(r"^public\s+(?:sealed\s+|abstract\s+|static\s+|partial\s+)*(?:class|struct|interface|enum)\s+([\w.<>`]+)")
rx_rva = re.compile(r"^\s*//\s*RVA:\s*0x([0-9A-Fa-f]+)")


def method_rvas():
    out = []
    with io.open(DUMP, encoding="utf-8", errors="replace") as f:
        for ln in f:
            m = rx_rva.match(ln)
            if m:
                out.append(int(m.group(1), 16))
    return sorted(set(out))


def main():
    t0 = time.time()
    ks = method_rvas()
    print(f"方法入口 {len(ks)} 个", flush=True)
    d = pefile.PE(DLL, fast_load=True)
    for s in d.sections:
        if not (s.Characteristics & 0x20000000):
            continue
        sva = s.VirtualAddress
        sd = s.get_data()
        seg_lo, seg_hi = sva, sva + len(sd)
        mine = [k for k in ks if seg_lo <= k < seg_hi]
        print(f"seg 0x{sva:X}: 方法 {len(mine)}", flush=True)
        chunks = []
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        for n, mstart in enumerate(mine):
            mend = mine[n + 1] if n + 1 < len(mine) else seg_hi
            lo = mstart - sva
            hi = min(len(sd), mend - sva, lo + 0x4000)
            starts = []
            cur = lo
            while cur < hi:
                got = None
                for ins in md.disasm(sd[cur:cur + 16], cur):
                    got = ins
                    break
                if got is None:
                    cur += 1
                    continue
                starts.append(cur + sva)
                cur += got.size
            if starts:
                chunks.append(np.array(starts, dtype=np.uint32))
        arr = np.unique(np.concatenate(chunks)) if chunks else np.zeros(0, np.uint32)
        # 与 v7 整段 sweep 并集
        p7 = OUTDIR + ("\\t200a_starts_%x.bin" % sva)
        try:
            b = open(p7, "rb").read()
            arr7 = np.frombuffer(b, dtype="<u4")
            arr = np.unique(np.concatenate([arr, arr7]))
        except Exception as e:
            print("  (no v7 cache:", e, ")")
        np.save(OUTDIR + ("\\t200a_starts_a_%x.npy" % sva), arr)
        print(f"  指令起点 {len(arr)} 用时 {time.time()-t0:.0f}s -> t200a_starts_a_{sva:x}.npy", flush=True)


if __name__ == "__main__":
    main()
