# -*- coding: utf-8 -*-
r"""read_mono.py —— Mono/.NET 程序集的 ECMA-335 元数据读取器（只读，零依赖）

定位：与 `read_cpp.py` 并列的"另一条腿"。
  · IL2CPP 目标（舟游客户端）→ `read_cpp.py` + dump.cs
  · **Mono 目标（如 ArknightR 的 Assembly-CSharp.dll）→ 本工具**
优势：**不需要 .NET SDK、不需要 ILSpy/dnSpy**，纯 struct 解析 PE + CLI 元数据表，
即可拿到类型/方法/用户字符串——足以做"识别 + 定位 + 抽表"。

来源与验证：2026-09-14 解析 ArknightR 时编写并实测通过
（读出 1,623 个 TypeDef / 6,684 个 MethodDef / 957 条用户字符串字面量，含全部中文文案）。
详见 `knowledge/04_数据对应与核验/40_外部工具解析_ArknightR与AFA.md`。

用法：
  python read_mono.py <dll或exe路径> [--no-methods] [--grep 关键词]
  python read_mono.py <路径> --dump-types      # 打印全部类型名
  python read_mono.py <路径> --dump-strings    # 打印全部用户字符串

编程接口：
  from read_mono import parse
  info, raw = parse(r"...\Assembly-CSharp.dll")
  info['md_version']    # 元数据版本（如 'v4.0.30319'）
  info['methods']       # [{'type':..., 'name':...}, ...]
  info['userstrings']   # [str, ...]  含中文 UI/日志文案
  info['sections']      # PE 节表
  info['cli']           # (rva, size)，为 (0,0) 表示**不是 .NET 程序集**
"""
import struct, sys, re, os

def read_pe_cli(path):
    d = open(path, 'rb').read()
    e = struct.unpack_from('<I', d, 0x3c)[0]
    coff = e + 4
    nsec, optsz = struct.unpack_from('<H', d, coff + 2)[0], struct.unpack_from('<H', d, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from('<H', d, opt)[0]
    dd_off = opt + (96 if magic == 0x10b else 112)
    numdd = struct.unpack_from('<I', d, opt + (92 if magic == 0x10b else 108))[0]
    secs = []
    so = opt + optsz
    for i in range(nsec):
        o = so + i * 40
        nm = d[o:o+8].rstrip(b'\x00').decode('ascii', 'replace')
        vsize, vaddr, rsize, raddr = struct.unpack_from('<IIII', d, o + 8)
        secs.append((nm, vaddr, vsize, raddr, rsize))
    def rva2off(rva):
        for nm, va, vs, ra, rs in secs:
            if va <= rva < va + max(vs, rs):
                return ra + (rva - va)
        return None
    return d, dd_off, numdd, rva2off, secs

def parse(path, want_methods=True):
    d, dd_off, numdd, rva2off, secs = read_pe_cli(path)
    out = {'path': path, 'size': len(d), 'sections': secs}
    if numdd <= 14:
        out['cli'] = None; return out, d
    cli_rva, cli_size = struct.unpack_from('<II', d, dd_off + 14 * 8)
    out['cli'] = (cli_rva, cli_size)
    if not cli_rva:
        return out, d
    o = rva2off(cli_rva)
    cb, maj, minr = struct.unpack_from('<IHH', d, o)
    md_rva, md_size = struct.unpack_from('<II', d, o + 8)
    out['runtime_version'] = d[o+16:o+16+4].hex()
    mo = rva2off(md_rva)
    sig = d[mo:mo+4]
    out['md_sig'] = sig
    ver_len = struct.unpack_from('<I', d, mo + 12)[0]
    ver = d[mo+16:mo+16+ver_len].split(b'\x00')[0].decode('ascii','replace')
    out['md_version'] = ver
    nstreams = struct.unpack_from('<H', d, mo + 16 + ver_len + 2)[0]
    p = mo + 16 + ver_len + 4
    streams = {}
    for _ in range(nstreams):
        soff, ssize = struct.unpack_from('<II', d, p)
        p += 8
        nl = 0
        while d[p+nl] != 0: nl += 1
        name = d[p:p+nl].decode('ascii','replace')
        p += nl + 1
        p = (p + 3) & ~3
        streams[name] = (mo + soff, ssize)
    out['streams'] = {k: v[1] for k, v in streams.items()}
    if '#~' not in streams:
        return out, d
    t = streams['#~'][0]
    heap = d[t + 6]
    ssize_idx = 4 if heap & 1 else 2
    gsize_idx = 4 if heap & 2 else 2
    bsize_idx = 4 if heap & 4 else 2
    valid, sorted_ = struct.unpack_from('<QQ', d, t + 8)
    n = t + 24
    rowcounts = {}
    for i in range(64):
        if valid >> i & 1:
            rowcounts[i] = struct.unpack_from('<I', d, n)[0]; n += 4
    out['rowcounts'] = rowcounts
    out['heap_sizes'] = {'string': ssize_idx, 'guid': gsize_idx, 'blob': bsize_idx}

    def ridx(tbl):
        return 4 if rowcounts.get(tbl, 0) >= 0x10000 else 2
    def coded(tables, bits):
        mx = max([rowcounts.get(x, 0) for x in tables] + [0])
        return 4 if mx >= (1 << (16 - bits)) else 2

    tablesizes = {}
    # 0x00 Module
    tablesizes[0x00] = 2 + ssize_idx + 3 * gsize_idx
    # 0x01 TypeRef: ResolutionScope(ResolutionScope), Name, Namespace
    rs = coded([0x00, 0x1A, 0x23, 0x01], 2)
    tablesizes[0x01] = rs + 2 * ssize_idx
    # 0x02 TypeDef
    tdor = coded([0x02, 0x01, 0x1B], 2)
    tablesizes[0x02] = 4 + 2 * ssize_idx + tdor + ridx(0x04) + ridx(0x06)
    # 0x03 FieldPtr
    tablesizes[0x03] = ridx(0x04)
    # 0x04 Field
    tablesizes[0x04] = 2 + ssize_idx + bsize_idx
    # 0x05 MethodPtr
    tablesizes[0x05] = ridx(0x06)
    # 0x06 MethodDef
    tablesizes[0x06] = 8 + ssize_idx + bsize_idx + ridx(0x08)
    # 0x07 ParamPtr
    tablesizes[0x07] = ridx(0x08)
    # 0x08 Param
    tablesizes[0x08] = 4 + ssize_idx
    # 0x09 InterfaceImpl
    tablesizes[0x09] = ridx(0x02) + coded([0x02,0x01,0x1B], 2)
    # 0x0A MemberRef
    tablesizes[0x0A] = coded([0x02,0x01,0x1A,0x06,0x1B], 3) + ssize_idx + bsize_idx
    # 0x0B Constant
    tablesizes[0x0B] = 1 + 1 + coded([0x04,0x08,0x17], 2) + bsize_idx
    # 0x0C CustomAttribute
    tablesizes[0x0C] = coded([0x06,0x04,0x01,0x02,0x08,0x09,0x0A,0x00,0x0E,0x17,0x14,0x11,0x1A,0x1B,0x20,0x23,0x26,0x27,0x28,0x2A,0x2C], 5) + bsize_idx
    # 0x0D FieldMarshal
    tablesizes[0x0D] = coded([0x04,0x08], 1) + bsize_idx
    # 0x0E DeclSecurity
    tablesizes[0x0E] = 2 + coded([0x02,0x06,0x20], 2) + bsize_idx
    # 0x0F ClassLayout
    tablesizes[0x0F] = 2 + 4 + ridx(0x02)
    # 0x10 FieldLayout
    tablesizes[0x10] = 4 + ridx(0x04)
    # 0x11 StandAloneSig
    tablesizes[0x11] = bsize_idx
    # 0x12 EventMap
    tablesizes[0x12] = ridx(0x02) + ridx(0x14)
    # 0x13 EventPtr
    tablesizes[0x13] = ridx(0x14)
    # 0x14 Event
    tablesizes[0x14] = 2 + ssize_idx + coded([0x02,0x01,0x1B], 2)
    # 0x15 PropertyMap
    tablesizes[0x15] = ridx(0x02) + ridx(0x17)
    # 0x16 PropertyPtr
    tablesizes[0x16] = ridx(0x17)
    # 0x17 Property
    tablesizes[0x17] = 2 + ssize_idx + bsize_idx
    # 0x18 MethodSemantics
    tablesizes[0x18] = 2 + ridx(0x06) + coded([0x14,0x17], 1)
    # 0x19 MethodImpl
    tablesizes[0x19] = ridx(0x02) + coded([0x06,0x0A], 1) + coded([0x06,0x0A], 1)
    # 0x1A ModuleRef
    tablesizes[0x1A] = ssize_idx
    # 0x1B TypeSpec
    tablesizes[0x1B] = bsize_idx
    # 0x1C ImplMap
    tablesizes[0x1C] = 2 + coded([0x04,0x06], 1) + ssize_idx + ridx(0x1A)
    # 0x1D FieldRVA
    tablesizes[0x1D] = 4 + ridx(0x04)
    # 0x20 Assembly
    tablesizes[0x20] = 16 + bsize_idx + 2 * ssize_idx
    # 0x21 AssemblyProcessor
    tablesizes[0x21] = 4
    # 0x22 AssemblyOS
    tablesizes[0x22] = 12
    # 0x23 AssemblyRef
    tablesizes[0x23] = 12 + 2 * bsize_idx + 2 * ssize_idx
    # 0x24 AssemblyRefProcessor
    tablesizes[0x24] = 4 + ridx(0x23)
    # 0x25 AssemblyRefOS
    tablesizes[0x25] = 12 + ridx(0x23)
    # 0x26 File
    tablesizes[0x26] = 4 + ssize_idx + bsize_idx
    # 0x27 ExportedType
    tablesizes[0x27] = 8 + 2 * ssize_idx + coded([0x26,0x27,0x23], 2)
    # 0x28 ManifestResource
    tablesizes[0x28] = 8 + ssize_idx + coded([0x26,0x27], 1)
    # 0x29 NestedClass
    tablesizes[0x29] = 2 * ridx(0x02)
    # 0x2A GenericParam
    tablesizes[0x2A] = 4 + coded([0x02,0x06], 1) + ssize_idx
    # 0x2B MethodSpec
    tablesizes[0x2B] = coded([0x06,0x0A], 1) + bsize_idx
    # 0x2C GenericParamConstraint
    tablesizes[0x2C] = ridx(0x2A) + coded([0x02,0x01,0x1B], 2)

    offs = {}
    cur = n
    for i in sorted(rowcounts):
        offs[i] = cur
        cur += tablesizes.get(i, 0) * rowcounts[i]
    out['table_offsets'] = {hex(k): v for k, v in offs.items()}

    strbase = streams['#Strings'][0]
    def sget(idx):
        e = d.index(b'\x00', strbase + idx)
        return d[strbase+idx:e].decode('utf-8', 'replace')

    # TypeDef names
    types = []
    if 0x02 in rowcounts:
        o2 = offs[0x02]
        for i in range(rowcounts[0x02]):
            ro = o2 + i * tablesizes[0x02]
            flags = struct.unpack_from('<I', d, ro)[0]
            ni = struct.unpack_from('<I', d, ro + 4)[0] if ssize_idx == 4 else struct.unpack_from('<H', d, ro + 4)[0]
            no = struct.unpack_from('<I', d, ro + 4 + ssize_idx)[0] if ssize_idx == 4 else struct.unpack_from('<H', d, ro + 4 + ssize_idx)[0]
            types.append((sget(no), sget(ni)))
    out['typedefs'] = types

    def read_methods():
        if 0x06 not in rowcounts: return []
        o6 = offs[0x06]
        res = []
        for i in range(rowcounts[0x06]):
            ro = o6 + i * tablesizes[0x06]
            rva = struct.unpack_from('<I', d, ro)[0]
            ni = struct.unpack_from('<I', d, ro + 8)[0] if ssize_idx == 4 else struct.unpack_from('<H', d, ro + 8)[0]
            res.append((sget(ni), rva))
        return res
    out['methods'] = read_methods() if want_methods else []

    # #US user strings
    us = []
    if '#US' in streams:
        usb, ussz = streams['#US']
        blob = d[usb:usb+ussz]
        # sequential walk over length-prefixed UTF-16 blobs
        res = []
        i = 1
        while i < len(blob):
            # compressed uint length
            b0 = blob[i]
            if b0 & 0x80 == 0: ln, adv = b0, 1
            elif b0 & 0xC0 == 0x80: ln, adv = ((b0 & 0x3F) << 8) | blob[i+1], 2
            else: ln, adv = ((b0 & 0x1F) << 24) | (blob[i+1] << 16) | (blob[i+2] << 8) | blob[i+3], 4
            i += adv
            if ln == 0: continue
            chunk = blob[i:i+ln]
            i += ln
            if len(chunk) < 4: continue
            res.append(chunk[:-1].decode('utf-16-le', 'replace'))
        out['userstrings'] = res
    return out, d


# ---------------- CLI ----------------
def _main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__)
        return
    path = sys.argv[1]
    want_methods = "--no-methods" not in sys.argv
    info, _raw = parse(path, want_methods=want_methods)

    cli = info.get("cli")
    if not cli or not cli[0]:
        print(f"{path}: **不是 .NET/Mono 程序集**（CLR 数据目录为空）")
        return

    print(f"== {os.path.basename(path)} ==")
    print(f"大小         : {info.get('size'):,} B")
    print(f"元数据版本   : {info.get('md_version')}")
    print(f"CLI 目录     : rva=0x{cli[0]:X} size={cli[1]}")
    print(f"TypeDef      : {len(info.get('typedefs', []) or [])}")
    print(f"MethodDef    : {len(info.get('methods', []) or [])}")
    print(f"用户字符串   : {len(info.get('userstrings', []) or [])}")

    if "--dump-types" in sys.argv:
        print("\n--- 类型 ---")
        for t in (info.get("typedefs") or []):
            print(t if isinstance(t, str) else t)
    if "--dump-strings" in sys.argv:
        print("\n--- 用户字符串 ---")
        for s in (info.get("userstrings") or []):
            print(repr(s))
    if "--grep" in sys.argv:
        kw = sys.argv[sys.argv.index("--grep") + 1]
        print(f"\n--- 命中 '{kw}' ---")
        for t in (info.get("typedefs") or []):
            name = t if isinstance(t, str) else str(t)
            if kw in name:
                print("[类型] " + name)
        for m in (info.get("methods") or []):
            line = m if isinstance(m, str) else str(m)
            if kw in line:
                print("[方法] " + line)
        for s in (info.get("userstrings") or []):
            if kw in s:
                print("[字符串] " + repr(s))


if __name__ == "__main__":
    _main()
