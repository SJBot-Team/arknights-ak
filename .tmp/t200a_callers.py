#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 全 DLL E8 rel32 调用点扫描 —— 给定若干目标 RVA，列出所有直接调用点及其所属方法。

用法: python t200a_callers.py 0x54E93E0 0x54E79F0 0x54E6BA0 [--cls REGEX] [--max N]
"""
import sys, struct, io, re, os, bisect, pickle
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
OUTDIR = r"C:\Users\23922\Documents\ds_harness\ak\.tmp"
import pefile

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


def build_calls():
    """扫出所有 E8 rel32 调用点，返回 {target_rva: [call_site_rva,...]}（缓存到 .tmp）。"""
    cache = os.path.join(OUTDIR, "t200a_calls.pkl")
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            return pickle.load(f)
    d = pefile.PE(DLL, fast_load=True)
    res = {}
    for s in d.sections:
        if not (s.Characteristics & 0x20000000):
            continue
        sva = s.VirtualAddress
        sd = s.get_data()
        p = 0
        while True:
            i = sd.find(b"\xe8", p)
            if i < 0 or i + 5 > len(sd):
                break
            p = i + 1
            rel = struct.unpack("<i", sd[i + 1:i + 5])[0]
            tgt = sva + i + 5 + rel
            res.setdefault(tgt, []).append(sva + i)
    with open(cache, "wb") as f:
        pickle.dump(res, f)
    return res


def main():
    targets = [int(a, 16) for a in sys.argv[1:] if a.startswith("0x")]
    clsre = None
    if "--cls" in sys.argv:
        clsre = re.compile(sys.argv[sys.argv.index("--cls") + 1])
    maxn = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 200
    calls = build_calls()
    midx = build_method_index()
    mkeys = sorted(midx)
    print(f"E8 调用目标 {len(calls)} 个（缓存）")
    for t in targets:
        sites = calls.get(t, [])
        print(f"\n=== 目标 0x{t:X}: E8 直接调用 {len(sites)} 处 ===")
        seen = {}
        for c in sites:
            k = bisect.bisect_right(mkeys, c) - 1
            if k < 0:
                label, delta = "?", c
            else:
                g = midx[mkeys[k]]
                delta = c - mkeys[k]
                label = g[0][0] + "." + g[0][1] + (f" [+{len(g)-1}同构]" if len(g) > 1 else "")
                if delta > 0x4000:
                    label = "UNMATCHED"
            seen.setdefault(label, []).append(c - mkeys[k] if k >= 0 else 0)
        n = 0
        for label, deltas in sorted(seen.items()):
            if clsre and not clsre.search(label):
                continue
            ds = ", ".join("+0x%X" % d for d in deltas[:6])
            print(f"  {len(deltas):4d} 处  {label}   [{ds}]")
            n += 1
            if n >= maxn:
                break


if __name__ == "__main__":
    main()
