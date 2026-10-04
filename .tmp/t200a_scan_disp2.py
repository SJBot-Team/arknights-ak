#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a v2: 稳健版 —— 对每个 4 字节 disp 匹配点，做 8 个起点的滑窗反汇编，
只接受"恰好自然结束于操作数 + 位移=target"的指令。"""
import sys, struct, bisect, io, re
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM

def build_index():
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

def scan(target):
    d = pefile.PE(DLL, fast_load=True); data = open(DLL, "rb").read(); base = d.OPTIONAL_HEADER.ImageBase
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
            for start in range(i - 1, max(-1, i - 9), -1):
                if start < 0: break
                try:
                    ins_list = list(md.disasm(sdata[start:i + 4], sva + start))
                except Exception:
                    continue
                if not ins_list: continue
                last = ins_list[-1]
                if last.address + last.size != sva + i + 4: continue
                if not last.operands: continue
                if last.operands[0].type != CS_OP_MEM: continue
                if last.operands[0].mem.disp != target: continue
                if last.operands[0].mem.index != 0: continue
                if last.operands[0].mem.base == 0: continue
                found = last; break
            if found is None: continue
            out.append(found)
    return out, base

if __name__ == "__main__":
    target = int(sys.argv[1], 16)
    ins_list, base = scan(target)
    # 去重(地址)
    seen = {}; res = []
    for ins in ins_list:
        if ins.address in seen: continue
        seen[ins.address] = 1
        res.append(ins)
    res.sort(key=lambda x: x.address)
    idx = build_index(); keys = sorted(idx)
    def owner(rva):
        i = bisect.bisect_right(keys, rva) - 1
        if i < 0: return [("?", "?", 0)], 0
        k = keys[i]; return idx[k], rva - k
    print(f"命中 {len(res)} 条（[reg+0x{target:X}] 精确位移）")
    lines = []
    for ins in res:
        rva = ins.address - base
        g, delta = owner(rva)
        write = ins.operands[0].type == CS_OP_MEM and ins.operands[0].mem.disp == target
        kind = "W" if write else "r"
        extra = f" [+{len(g)-1}同构]" if len(g) > 1 else ""
        s = (f"{kind} 0x{rva:08X}  {ins.bytes.hex():<18} {ins.mnemonic:<8} {ins.op_str:<42} "
             f"| {g[0][0]}.{g[0][1]} +0x{delta:X}{extra}")
        lines.append(s)
    for s in lines:
        print(s)
    with io.open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t200a_scan_%x.txt" % target, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
