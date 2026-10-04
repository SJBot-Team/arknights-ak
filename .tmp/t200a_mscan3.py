#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v12: 鏂规硶鍏ュ彛閿氬畾鐨勭簿纭壂鎻?鈥斺€?鎵炬墍鏈夋搷浣滄暟浣嶇Щ鎭颁负 target 鐨勬寚浠ゃ€?
鍒ゅ畾瑕佺偣锛坴11 鐨?bug 淇锛夛細
  * IL2CPP 鐨勫瓧娈佃闂舰濡?`mov reg, [reg+disp32]`锛宑apstone 鎶婂畠瑙ｇ爜涓?*涓や釜鎿嶄綔鏁?*
    锛坥p0=瀵勫瓨鍣紝op1=鍐呭瓨锛夛紝鍥犳涓嶈兘鍙湅 operands[0]锛?  * 蹇呴』瑕佹眰"璇ュ唴瀛樻搷浣滄暟鐨?disp32 瀛楄妭纭疄钀藉湪鏈寚浠ょ殑瀛楄妭閲?锛?    鍚﹀垯浼氭妸绔嬪嵆鏁伴噷鎭板ソ鍚?a0 01 00 00 鐨勬寚浠よ鍒わ紙v11 鐨勫亣闃虫€ф潵婧愶級銆?
鐢ㄦ硶: python t200a_mscan3.py <target_hex> [--kind w|r|all] [--cls REGEX] [--max N]
"""
import sys, struct, io, re, os
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
            cur = 0
            base_abs = sva + lo          # blob[0] 鐨勭粷瀵?RVA
            while cur < len(blob):
                got = None
                try:
                    # 娉ㄦ剰锛歝apstone 鐨?address 瀛楁浼氭寜 32 浣嶅鐞嗭紝鏁呰繖閲屼紶 blob 鐩稿鍋忕Щ锛?                    # 鏈€鍚庣敤 base_abs 杩樺師鎴?RVA锛?026-09-29 瀹炴祴韪╁潙锛?                    for ins in md.disasm(blob[cur:cur + 16], cur):
                        got = ins
                        break
                except Exception:
                    pass
                if got is None:
                    cur += 1
                    continue
                b = got.bytes
                if disp in b:
                    di = b.find(disp)
                    mi = None
                    for oi, o in enumerate(got.operands):
                        if (o.type == CS_OP_MEM and o.mem.disp == target
                                and o.mem.index == 0 and o.mem.base != 0):
                            mi = oi
                    if mi is not None:
                        # ModRM 鍦ㄦ寚浠ゅ熬閮ㄧ殑缁忓吀浣嶇疆锛歄P [REX] OPCODE MODRM [SIB] DISP32
                        # 鍗?disp 钀藉湪 b[di:di+4]锛屼笖 b[di-1] 鐨?r/m 瀛楁 == 鍐呭瓨鍩哄潃瀵勫瓨鍣?                        modrm = b[di - 1]
                        rm = modrm & 7
                        rex_b = 0
                        # REX 鍓嶇紑锛?x40-0x4F锛夊湪鎸囦护鍓嶉儴
                        for p in b[:4]:
                            if 0x40 <= p <= 0x4F:
                                rex_b = p & 1
                        base_ok = (rm | (rex_b << 3)) == got.operands[mi].mem.base
                        if base_ok or (rm == 4 and di - 1 >= 0):
                            res.append((mstart, base_abs + got.address, got, mi))
                cur = got.address + got.size
    seen = set()
    uniq = []
    for mstart, rva, ins, mi in sorted(res, key=lambda x: x[1]):
        if rva in seen:
            continue
        seen.add(rva)
        uniq.append((mstart, rva, ins, mi))
    nw = sum(1 for _, _, ins, mi in uniq if mi == 0)
    print(f"=== [reg+0x{target:X}] 绮剧‘鍛戒腑 {len(uniq)} (mem=op0 鍐?{nw} / mem=opN 璇?{len(uniq)-nw}) ===")
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
    outp = os.path.join(OUTDIR, "t200a_m3_%x_%s.txt" % (target, kind))
    with io.open(outp, "w", encoding="utf-8") as f:
        for rva, ins, label, delta, is_write in lines:
            f.write(f"{'W' if is_write else 'r'} 0x{rva:08X}\t{ins.bytes.hex()}\t{ins.mnemonic} {ins.op_str}\t{label}\t+0x{delta:X}\n")
    print(f"锛堣繃婊ゅ悗 {len(lines)} 琛岋級-> " + outp)


if __name__ == "__main__":
    main()

