#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v4: 全 DLL 扫 `[reg+disp32=target]`（读+写），按 dump.cs 方法归属分类。

关键：capstone 的 address 只用于**在线性窗口内做相对算术**（base=窗口起点 RVA），
     最终 RVA = sva + (ins.address - (i-start))。

用法: python t200a_scan_disp4.py <target_hex> [--cls REGEX] [--mn REGEX] [--w|--r] [--max N]
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

# 栈指针相关基址：这些命中极可能是栈上巧合、不是字段访问
STACK = {4, 5, 12, 13}   # rsp, rbp, r12, r13

def scan(target):
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
            found = None
            for start in range(i - 1, max(-1, i - 11), -1):
                if start < 0: break
                try:
                    lst = list(md.disasm(sdata[start:min(len(sdata), i + 4 + 2)], i - start))
                except Exception:
                    continue
                if not lst: continue
                last = lst[-1]
                if last.address + last.size != i + 4: continue
                if not last.operands: continue
                o = last.operands[0]
                if o.type != CS_OP_MEM: continue
                if o.mem.disp != target or o.mem.index != 0: continue
                if o.mem.base == 0: continue
                # 窗口起点 RVA = sva+start - (i-start)；指令 RVA = 起点 + last.address
                winbase = sva + start - (i - start)
                out.append((winbase + last.address, last))
                found = last; break
    return out

def main():
    target = int(sys.argv[1], 16)
    clsre = re.compile(sys.argv[sys.argv.index("--cls") + 1]) if "--cls" in sys.argv else None
    mnre  = re.compile(sys.argv[sys.argv.index("--mn") + 1]) if "--mn" in sys.argv else None
    only_w = "--w" in sys.argv
    only_r = "--r" in sys.argv
    maxn = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 10**9
    include_stack = "--stack" in sys.argv

    res = scan(target)
    seen = {}; uniq = []
    for rva, ins in res:
        if rva in seen: continue
        seen[rva] = 1; uniq.append((rva, ins))
    uniq.sort(key=lambda x: x[0])
    idx = build_index(); keys = sorted(idx)
    def owner(rva):
        i = bisect.bisect_right(keys, rva) - 1
        if i < 0: return [("?", "?", 0)], rva
        k = keys[i]; return idx[k], rva - k
    lines = []
    n_shown = 0
    for rva, ins in uniq:
        o0 = ins.operands[0]
        stackhit = o0.type == CS_OP_MEM and o0.mem.base in STACK
        if stackhit and not include_stack: continue
        write = (o0.type == CS_OP_MEM and o0.mem.disp == target)
        if only_w and not write: continue
        if only_r and write: continue
        g, delta = owner(rva)
        if delta > 0x4000:
            label = "⚠️未命中(最近前驱>0x4000)"
        else:
            label = g[0][0] + "." + g[0][1] + (f" [+{len(g)-1}同构]" if len(g) > 1 else "")
        if clsre and not clsre.search(label): continue
        if mnre and not mnre.search(ins.mnemonic): continue
        kind = "W" if write else "r"
        s = (f"{kind} 0x{rva:08X}  {ins.bytes.hex():<18} {ins.mnemonic:<8} {ins.op_str:<44} "
             f"| {label} +0x{delta:X}")
        lines.append(s)
        if n_shown < maxn:
            print(s); n_shown += 1
    print(f"=== disp32=0x{target:X}: 命中 {len(uniq)} 条（已去栈）/ 显示 {n_shown} ===")
    p = r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t200a_scan_%x.txt" % target
    with io.open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("全量 -> " + p)

if __name__ == "__main__":
    main()
