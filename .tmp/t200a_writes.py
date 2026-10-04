#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 直接字节模式搜索 —�?�?`mov [reg+disp32], reg64/reg32` �?disp32 命中的点（写点扫描）�?不解码，只做模式匹配 + 事后反汇编确认�?""
import sys, struct, io, re, bisect, os
sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DLL = BASE + r"\GameAssembly.dll"
DUMP = BASE + r"\dump\dump.cs"
OUTDIR = r"C:\Users\23922\Documents\ds_harness\ak\.tmp"
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

def main():
    target = int(sys.argv[1], 16)
    pats = []
    disp = struct.pack("<I", target)
    # 89 /r   mov r/m32, r32   -> modrm = 10rrr100 = 0x80|(r<<3)|4
    # 89 /r with REX.W (48) -> mov r/m64, r64
    for r in range(8):
        m = 0x80 | (r << 3) | 4   # ModRM 编码：mod=10 reg=r r/m=100(SIB)
        # 注意：ModRM 字节的位序是 [mod:2][reg:3][r/m:3]�?        # �?mod=10(二进�?10) 落在最高两�?-> 数�?= 0x80|(reg<<3)|4 �?        # 之前误写�?0x89，导致漏扫（2026-09-29 修正�?        pats.append((bytes([0x89, m]) + disp, f"mov [r+0x{target:x}], r32(r{r})"))
        pats.append((bytes([0x48, 0x89, m]) + disp, f"mov [r+0x{target:x}], r64(r{r})"))
        pats.append((bytes([0x48, 0x8D, m]) + disp, f"lea r64, [r+0x{target:x}]"))
    d = pefile.PE(DLL, fast_load=True)
    segs = [(s.VirtualAddress, s.get_data()) for s in d.sections if s.Characteristics & 0x20000000]
    midx = build_index(); mkeys = sorted(midx)
    md = Cs(CS_ARCH_X86, CS_MODE_64); md.detail = True
    found = []
    for sva, sd in segs:
        for pat, desc in pats:
            p = 0
            while True:
                i = sd.find(pat, p)
                if i < 0: break
                p = i + 1
                # 反汇编确认：�?i 开始应为该条指�?                try:
                    lst = list(md.disasm(sd[i:i + 16], 0))
                except Exception:
                    continue
                if not lst: continue
                ins = lst[0]
                if ins.bytes.hex() != pat.hex(): continue
                if not ins.operands: continue
                o = ins.operands[0]
                if o.type != CS_OP_MEM or o.mem.disp != target or o.mem.index != 0: continue
                found.append((sva + i, ins, desc))
    seen = set(); uniq = []
    for rva, ins, desc in sorted(found):
        if rva in seen: continue
        seen.add(rva); uniq.append((rva, ins, desc))
    print(f"=== 写点 [reg+0x{target:X}] 模式命中 {len(uniq)} ===")
    lines = []
    for rva, ins, desc in uniq:
        k = bisect.bisect_right(mkeys, rva) - 1
        if k < 0: label = "?"; delta = rva
        else:
            g = midx[mkeys[k]]; delta = rva - mkeys[k]
            label = g[0][0] + "." + g[0][1] + (f" [+{len(g)-1}同构]" if len(g) > 1 else "")
            if delta > 0x4000: label = "⚠️未命�?
        s = f"W 0x{rva:08X}  {ins.bytes.hex():<18} {ins.mnemonic} {ins.op_str:<38} [{desc}] | {label} +0x{delta:X}"
        lines.append(s); print(s)
    with io.open(os.path.join(OUTDIR, "t200a_writes_%x.txt" % target), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

if __name__ == "__main__":
    main()
