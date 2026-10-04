#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v14: 字段访问扫描（最终版）。

目标：找所有形如 `OP reg, [reg+disp32]` / `OP [reg+disp32], reg` 的指令，
      其中 disp32 == target，基址寄存器不是 rsp/rbp（排除栈帧巧合）。

实现细节（踩过的坑，务必保留）：
  * capstone 的 `ins.address` 会被按 32 位显示；因此反汇编时只能用 **blob 相对偏移** 作 base，
    最后再加方法 RVA 还原（若直接传 RVA 作 base，`ins.address` 会变成负数/被截断）。
  * IL2CPP 字段访问的操作数顺序是 [寄存器, 内存]（mov reg, [reg+disp]），
    v11 只看 operands[0] 导致全丢。
  * 假阳性来自"立即数里恰好含目标 4 字节"，用 `disp == target and mem.index == 0` 即可排除，
    不需要再做 ModRM 手工位运算（v13 的 base_ok 判据有 bug，误杀真命中）。

用法: python t200a_mscan5.py <target_hex> [--kind w|r|all] [--cls REGEX] [--max N] [--allow-stack]
"""
import sys, struct, io, re, os
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
OUTDIR = r"C:\Users\23922\Documents\ds_harness\ak\.tmp"
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM

STACK = {4, 5, 12, 13}   # rsp, rbp, r12, r13
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
    allow_stack = "--allow-stack" in sys.argv
    disp = struct.pack("<I", target)

    d = pefile.PE(DLL, fast_load=True)
    midx = method_index()
    mkeys = sorted(midx)
    res = []
    n_methods_with_disp = 0
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
            blob = sd[lo:mend - sva]
            if disp not in blob:
                continue
            n_methods_with_disp += 1
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
                mi = None
                for oi, o in enumerate(got.operands):
                    if (o.type == CS_OP_MEM and o.mem.disp == target and o.mem.index == 0):
                        mi = oi
                        break
                if mi is not None and not (got.operands[mi].mem.base in STACK and not allow_stack):
                    res.append((mstart, mstart + got.address, got, mi))
                cur = got.address + got.size
    seen = set()
    uniq = []
    for mstart, rva, ins, mi in sorted(res, key=lambda x: x[1]):
        if rva in seen:
            continue
        seen.add(rva)
        uniq.append((mstart, rva, ins, mi))
    nw = sum(1 for _, _, ins, mi in uniq if mi == 0)
    print("=== [reg+0x%X] 命中 %d (写 %d / 读 %d)；含该 disp 的方法 %d 个 ===" % (
        target, len(uniq), nw, len(uniq) - nw, n_methods_with_disp))
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
    outp = os.path.join(OUTDIR, "t200a_m5_%x_%s.txt" % (target, kind))
    with io.open(outp, "w", encoding="utf-8") as f:
        for rva, ins, label, delta, is_write in lines:
            f.write("%s 0x%08X\t%s\t%s %s\t%s\t+0x%X\n" % (
                "W" if is_write else "r", rva, ins.bytes.hex(), ins.mnemonic, ins.op_str, label, delta))
    print("（过滤后 %d 行）-> %s" % (len(lines), outp))


if __name__ == "__main__":
    main()
