#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""t200a: 全 DLL 扫 `[reg+disp32]` 且 disp32 == target 的指令，按方法归属分类 读/写。

用法:
  python t200a_scan_disp.py 0x1a0 [--class-regex Torappu.Battle] [--all]
原理:
  x86-64 里 mod=10(disp32) 的 ModRM，r/m 字段为 100 时表示存在 SIB，
  而 mod=10+r/m=100 是**非法**编码(会走 SIB)，故字节型 `10rrr100 + A0 01 00 00`
  是唯一确定的 `[reg+disp32=0x1a0]` 操作数模式。据此快速定位候选，再用 capstone 确认指令边界。
"""
import io
import re
import sys
import struct

sys.stdout.reconfigure(encoding="utf-8")
BASE = r"E:\__file\ak_kb\client_res\il2cpp"
DUMP = BASE + r"\dump\dump.cs"
DLL = BASE + r"\GameAssembly.dll"

import pefile
from capstone import Cs, CS_ARCH_X86, CS_MODE_64, CS_OP_MEM, CS_OP_REG


def build_index():
    """RVA -> (class, signature, line_no)；类名取最近的 public class/struct 声明（保留全名）。"""
    idx = {}
    cls = "?"
    rx_cls = re.compile(r"^public\s+(?:sealed\s+|abstract\s+|static\s+|partial\s+)*"
                        r"(?:class|struct|interface|enum)\s+([\w.<>`]+)")
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
    return idx


def main():
    target = int(sys.argv[1], 16)
    want_all = "--all" in sys.argv
    creg = None
    if "--class-regex" in sys.argv:
        creg = re.compile(sys.argv[sys.argv.index("--class-regex") + 1])
    lo = int(sys.argv[sys.argv.index("--lo") + 1], 16) if "--lo" in sys.argv else 0
    hi = int(sys.argv[sys.argv.index("--hi") + 1], 16) if "--hi" in sys.argv else 0

    print(f"=== 目标 disp32 = 0x{target:X} ===")
    d = pefile.PE(DLL, fast_load=True)
    data = open(DLL, "rb").read()
    base = d.OPTIONAL_HEADER.ImageBase
    segs = []
    for s in d.sections:
        print(f"  section {s.Name.decode(errors='replace').strip(chr(0)):8s} VA=0x{s.VirtualAddress:X} "
              f"VS=0x{s.Misc_VirtualSize:X} RAW=0x{s.SizeOfRawData:X} "
              f"X={bool(s.Characteristics & 0x20000000)}")
        if s.Characteristics & 0x20000000:
            segs.append((s.VirtualAddress, s.get_data()))

    disp = struct.pack("<I", target)
    pats = []
    for reg in range(8):
        for modrm in (0x80 | (reg << 3) | 0x04, 0xC0 | (reg << 3) | 0x04):
            pats.append((bytes([modrm]) + disp, reg))
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    idx = build_index()
    keys = sorted(idx)
    import bisect

    def owner(rva):
        i = bisect.bisect_right(keys, rva) - 1
        if i < 0:
            return None, 0
        k = keys[i]
        return idx[k][0], rva - k

    results = []
    for sva, sdata in segs:
        for pat, reg in pats:
            off = 0
            while True:
                i = sdata.find(pat, off)
                if i < 0:
                    break
                off = i + 1
                operand_pos = sva + i + 1   # disp32 起始
                if lo and operand_pos < lo:
                    continue
                if hi and operand_pos > hi:
                    continue
                # 反汇编窗口，找"恰好覆盖 operand 且 mem.disp==target"的指令
                start = max(0, i - 6)
                hits = []
                for ins in md.disasm(sdata[start:i + 5 + 4], sva + start):
                    a = ins.address - sva
                    if a + ins.size <= operand_pos:
                        continue
                    if a > operand_pos:
                        break
                    if a <= operand_pos < a + ins.size:
                        hits.append(ins)
                    if a + ins.size > operand_pos + 1:
                        break
                for ins in hits:
                    if not ins.operands:
                        continue
                    mems = [o for o in ins.operands if o.type == CS_OP_MEM]
                    if not mems:
                        continue
                    if not any(o.mem.disp == target and o.mem.base != 0 and o.mem.index == 0
                               for o in mems):
                        continue
                    # 只接受 disp 字段宽度 = 4 字节（排除 [reg+0x1a0] 由 mod=01? 不可能，
                    # 但要排除噪声：确认指令覆盖 operand_pos 且操作数就在这里）
                    op = ins.operands[0]
                    is_write = (op.type == CS_OP_MEM and op.mem.disp == target)
                    owner_group, delta = owner(ins.address - base)
                    results.append(dict(rva=ins.address - base, mnem=ins.mnemonic,
                                        opstr=ins.op_str, raw=ins.bytes.hex(),
                                        write=is_write,
                                        owner=owner_group, delta=delta,
                                        cls=owner_group[0][0] if owner_group else "?",
                                        sig=owner_group[0][1] if owner_group else "?",
                                        sig_extra=len(owner_group) - 1 if owner_group else 0))
                # 去重同一地址
        print(f"  seg 0x{sva:X} 扫完")

    # 去重
    seen = set()
    uniq = []
    for r in results:
        k = (r["rva"], r["mnem"], r["opstr"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    uniq.sort(key=lambda r: r["rva"])
    print(f"\n=== 命中 {len(uniq)} 条指令（去重后）===")
    for r in uniq:
        cls = r["cls"]
        if creg and not creg.search(cls):
            continue
        kind = "W" if r["write"] else "r"
        extra = f" [+{r['sig_extra']}同构]" if r["sig_extra"] > 0 else ""
        print(f"{kind} 0x{r['rva']:08X}  {r['raw']:<16} {r['mnem']:<7} {r['opstr']:<40} "
              f"| {cls}.{r['sig']} +0x{r['delta']:X}{extra}")
    if not want_all:
        pass
    with io.open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\t200a_scan_%x.txt" % target,
                 "w", encoding="utf-8") as f:
        for r in uniq:
            kind = "W" if r["write"] else "r"
            f.write(f"{kind} 0x{r['rva']:08X}  {r['raw']}\t{r['mnem']} {r['opstr']}\t"
                    f"{r['cls']}.{r['sig']}\t+0x{r['delta']:X}\n")
    print(f"\n全量写入 .tmp/t200a_scan_{target:x}.txt")


if __name__ == "__main__":
    main()
