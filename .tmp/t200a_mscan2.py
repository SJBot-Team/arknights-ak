#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v11: 鏃犻渶鍏ㄦ鎸囦护缂撳瓨鐨勭簿纭壂鎻?鈥斺€?瀵规瘡涓惈鐩爣 disp32 瀛楄妭鐨勬柟娉曪紝
鐢ㄦ柟娉曞叆鍙ｉ敋瀹氬弽姹囩紪鏁存鏂规硶锛屽彇"鑷劧缁撴潫浜?disp32 鏈熬涓旀搷浣滄暟浣嶇Щ鍛戒腑"鐨勬寚浠ゃ€?
鐢ㄦ硶: python t200a_mscan.py <target_hex> [--kind w|r|all] [--cls REGEX] [--max N]
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
            # 涓€娆￠敋瀹氭壂鎻忔暣娈垫柟娉曪紝鏀堕泦鎵€鏈夊懡涓?            cur = 0
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
                    if mi is not None and disp in got.bytes and got.bytes.find(disp) == got.bytes.find(b"\x24"):
                        res.append((mstart, sva + got.address, got, mi))
                cur = end_off
    # 鍘婚噸
    seen = set()
    uniq = []
    for mstart, rva, ins, mi in sorted(res, key=lambda x: x[1]):
        if rva in seen:
            continue
        seen.add(rva)
        uniq.append((mstart, rva, ins, mi))
    nw = sum(1 for _, _, ins, mi in uniq if mi == 0)
    print(f"=== [reg+0x{target:X}] 鏂规硶閿氬畾绮剧‘鍛戒腑 {len(uniq)} (mem鍦╫p0=鍐?{nw} / 鍏朵綑=璇?{len(uniq)-nw}) ===")
    lines = []
    for mstart, rva, ins, mi in uniq:
        is_write = (mi == 0)
        if kind == "w" and not is_write:
            continue
        if kind == "r" and is_write:
            continue
        g = midx[mstart]
        label = g[0][0] + "." + g[0][1] + (f" [+{len(g)-1}鍚屾瀯]" if len(g) > 1 else "")
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
    print(f"锛堣繃婊ゅ悗 {len(lines)} 琛岋級-> " + outp)


if __name__ == "__main__":
    main()

