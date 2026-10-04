#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v13: 方法入口锚定的精确扫描 —— 找所有操作数位移恰为 target 的指令。

判定要点：
  * IL2CPP 字段访问形如 `mov reg, [reg+disp32]`，capstone 解码为两个操作数
    （op0=寄存器 / op1=内存），不能只看 operands[0]；
  * 要求内存操作数的 disp32 字节确实落在本指令字节内、且 ModRM 的 r/m(+REX.B)
    等于该内存操作数的基址寄存器 —— 用来排除"立即数里恰好含目标 4 字节"的假阳性；
  * capstone 的 address 字段按 32 位处理，故 window 用 blob 相对偏移，最后加 base 还原 RVA。

用法: python t200a_mscan4.py <target_hex> [--kind w|r|all] [--cls REGEX] [--max N]
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
            base_abs = mstart
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
                b = got.bytes
                if disp in b:
                    di = b.find(disp)
                    mi = None
                    for oi, o in enumerate(got.operands):
                        if (o.type == CS_OP_MEM and o.mem.disp == target
                                and o.mem.index == 0 and o.mem.base != 0):
                            mi = oi
                    if mi is not None and di >= 1:
                        modrm = b[di - 1]
                        rm = modrm & 7
                        rex_b = 0
                        for p in b[:4]:
                            if 0x40 <= p <= 0x4F:
                                rex_b = p & 1
                        base_ok = (rm | (rex_b << 3)) == got.operands[mi].mem.base
                        if base_ok or rm == 4:
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
    print("=== [reg+0x%X] 精确命中 %d (mem=op0 写 %d / mem=opN 读 %d) ===" % (target, len(uniq), nw, len(uniq) - nw))
    lines = []
    for mstart, rva, ins, mi in uniq:
        is_write = (mi == 0)
        if kind == "w" and not is_write:
            continue
        if kind == "r" and is_write:
            continue
        g = midx[mstart]
        label = g[0][0] + "." + g[0][1] + ((" [+%d同构]" % (len(g) - 1)) if len(g) > 1 else "")
        if clsre and not clsre.search(label):
            continue
        lines.append((rva, ins, label, rva - mstart, is_write))
    shown = 0
    for rva, ins, label, delta, is_write in lines:
        s = "%s 0x%08X  %-20s %-7s %-44s | %s +0x%X" % (
            "W" if is_write else "r", rva, ins.bytes.hex(), ins.mnemonic, ins.op_str, label, delta)
        if shown < maxn:
            print(s)
            shown += 1
    outp = os.path.join(OUTDIR, "t200a_m4_%x_%s.txt" % (target, kind))
    with io.open(outp, "w", encoding="utf-8") as f:
        for rva, ins, label, delta, is_write in lines:
            f.write("%s 0x%08X\t%s\t%s %s\t%s\t+0x%X\n" % (
                "W" if is_write else "r", rva, ins.bytes.hex(), ins.mnemonic, ins.op_str, label, delta))
    print("（过滤后 %d 行）-> %s" % (len(lines), outp))


if __name__ == "__main__":
    main()
