#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v3: 全 DLL 扫 `[reg+disp32=target]`（读+写）。

关键修正：capstone 的 address 字段在 print 时被截断为 32 位，
故 **以 RVA 作为 capstone address 基址**（而非 ImageBase），全部算术都走 RVA。

用法: python t200a_scan_disp3.py 0x1a0 [--cls REGEX] [--lo RVA] [--hi RVA]
"""
import sys, struct, bisect, io, re
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM

_idxc = None
def build_index():
    global _idxc
    if _idxc is not None: return _idxc
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
    _idxc = idx
    return idx

def scan(target, lo=0, hi=0):
    d = pefile.PE(DLL, fast_load=True)
    segs = [(s.VirtualAddress, s.get_data()) for s in d.sections if s.Characteristics & 0x20000000]
    disp = struct.pack("<I", target)
    md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True
    out = []
    for sva, sdata in segs:
        off = 0
        while True:
            i = sdata.find(disp, off)
            if i < 0: break
            off = i + 1
            rva_op = sva + i            # 操作数(disp32)结束后的 RVA
            if lo and rva_op < lo: continue
            if hi and rva_op > hi: continue
            found = None
            for start in range(i - 1, max(-1, i - 10), -1):
                if start < 0: break
                try:
                    lst = list(md.disasm(sdata[start:i + 4 + 2], i - start))
                except Exception:
                    continue
                if not lst: continue
                last = lst[-1]
                if last.address + last.size != i + 4: continue
                if not last.operands: continue
                o = last.operands[0]
                if o.type != CS_OP_MEM: continue
                if o.mem.disp != target or o.mem.index != 0: continue
                if o.mem.base == 0: continue          # 排除 rip 相对（IL2CPP 不用）
                if o.mem.base in (4, 5): continue     # rsp/rbp：栈上巧合，非字段
                if last.mnemonic in ("sub", "add", "cmp", "adc", "sbb", "and", "or", "xor",
                                     "movzx", "movsx", "lea", "test", "inc", "dec"):
                    # 保留 mov/cmp 之类，但 rsp/rbp 已排除；这里再排除纯栈运算残余
                    pass
                found = last; break
            if found is None: continue
            out.append((sva + i - 3, found))   # 粗存，稍后用"起点=-4后的字节数"修正
    return out

def report(target, clsre=None, lo=0, hi=0):
    res, = [scan(target, lo, hi)]
    seen = set(); uniq = []
    for ins in res:
        if ins.address in seen: continue
        seen.add(ins.address); uniq.append(ins)
    uniq.sort(key=lambda x: x.address)
    idx = build_index(); keys = sorted(idx)
    def owner(rva):
        i = bisect.bisect_right(keys, rva) - 1
        if i < 0: return [("?", "?", 0)], 0
        k = keys[i]; return idx[k], rva - k
    lines = []
    for ins in uniq:
        rva = ins.address
        g, delta = owner(rva)
        o0 = ins.operands[0]
        write = (o0.type == CS_OP_MEM and o0.mem.disp == target)
        kind = "W" if write else "r"
        excl = "" if delta < 0x4000 else "  ⚠️超出最近前驱4000"
        extra = f" [+{len(g)-1}同构]" if len(g) > 1 else ""
        s = (f"{kind} 0x{rva:08X}  {ins.bytes.hex():<18} {ins.mnemonic:<8} {ins.op_str:<44} "
             f"| {g[0][0]}.{g[0][1]} +0x{delta:X}{extra}{excl}")
        lines.append(s)
    print(f"=== disp32=0x{target:X} 命中 {len(uniq)} 条指令 ===")
    shown = 0
    for s in lines:
        if clsre and not clsre.search(s): continue
        print(s); shown += 1
    print(f"--- 按类过滤后显示 {shown} 条 / 共 {len(uniq)} ---")
    p = r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t200a_scan_%x.txt" % target
    with io.open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("全量 -> " + p)

if __name__ == "__main__":
    target = int(sys.argv[1], 16)
    clsre = re.compile(sys.argv[sys.argv.index("--cls") + 1]) if "--cls" in sys.argv else None
    lo = int(sys.argv[sys.argv.index("--lo") + 1], 16) if "--lo" in sys.argv else 0
    hi = int(sys.argv[sys.argv.index("--hi") + 1], 16) if "--hi" in sys.argv else 0
    report(target, clsre, lo, hi)
