# -*- coding: utf-8 -*-
r"""mono_il.py —— Mono/.NET 程序集的 IL 反汇编器 + 调用图（零依赖，纯 Python）

在 `ak\code\tools\read_mono.py`（元数据表读取）基础上补齐**方法体解码**：
  · 方法体头（tiny/fat）→ IL 字节
  · IL 指令解码（含 0xFE 前缀）
  · token 解析：MethodDef / MemberRef / MethodSpec / Field / TypeRef / TypeSpec / #US 字符串
  · 签名（blob）解析 → 可读类型名（含泛型）
  · 调用图：who（谁调用我）/ trace（我调用谁，递归）

用途：为 ArknightR（Mono 目标）建立"从底层代码到图形层"的调用链证据。
对照工具：IL2CPP 目标用 `ak\code\tools\read_cpp.py`。

用法：
  python mono_il.py <dll> --types [--grep KW]        # 列类型
  python mono_il.py <dll> --methods KW               # 列匹配方法
  python mono_il.py <dll> --dis "Ns.Class::Method"   # 反汇编某方法
  python mono_il.py <dll> --who "Method"             # 谁调用了它（全库扫描）
  python mono_il.py <dll> --trace "Ns.Class::Method" [--depth 4]  # 递归调用链
  python mono_il.py <dll> --strings KW
  python mono_il.py <dll> --fields "Class"
  python mono_il.py <dll> --stats
"""
import struct, sys, os, re, json, argparse
from collections import defaultdict

# ---------------------------------------------------------------- opcodes
N = 'InlineNone'; SI1 = 'ShortInlineI'; I4 = 'InlineI'; I8 = 'InlineI8'
SR = 'ShortInlineR'; R8 = 'InlineR'; M = 'InlineMethod'; F = 'InlineField'
T = 'InlineType'; TK = 'InlineTok'; S = 'InlineString'; SV = 'ShortInlineVar'
V = 'InlineVar'; SBT = 'ShortInlineBrTarget'; BT = 'InlineBrTarget'
SW = 'InlineSwitch'; SIG = 'InlineSig'

OP1 = {
0x00:('nop',N),0x01:('break',N),
0x02:('ldarg.0',N),0x03:('ldarg.1',N),0x04:('ldarg.2',N),0x05:('ldarg.3',N),
0x06:('ldloc.0',N),0x07:('ldloc.1',N),0x08:('ldloc.2',N),0x09:('ldloc.3',N),
0x0A:('stloc.0',N),0x0B:('stloc.1',N),0x0C:('stloc.2',N),0x0D:('stloc.3',N),
0x0E:('ldarg.s',SV),0x0F:('ldarga.s',SV),0x10:('starg.s',SV),
0x11:('ldloc.s',SV),0x12:('ldloca.s',SV),0x13:('stloc.s',SV),
0x14:('ldnull',N),0x15:('ldc.i4.m1',N),0x16:('ldc.i4.0',N),0x17:('ldc.i4.1',N),
0x18:('ldc.i4.2',N),0x19:('ldc.i4.3',N),0x1A:('ldc.i4.4',N),0x1B:('ldc.i4.5',N),
0x1C:('ldc.i4.6',N),0x1D:('ldc.i4.7',N),0x1E:('ldc.i4.8',N),
0x1F:('ldc.i4.s',SI1),0x20:('ldc.i4',I4),0x21:('ldc.i8',I8),
0x22:('ldc.r4',SR),0x23:('ldc.r8',R8),
0x25:('dup',N),0x26:('pop',N),0x27:('jmp',M),0x28:('call',M),0x29:('calli',SIG),
0x2A:('ret',N),
0x2B:('br.s',SBT),0x2C:('brfalse.s',SBT),0x2D:('brtrue.s',SBT),0x2E:('beq.s',SBT),
0x2F:('bge.s',SBT),0x30:('bgt.s',SBT),0x31:('ble.s',SBT),0x32:('blt.s',SBT),
0x33:('bne.un.s',SBT),0x34:('bge.un.s',SBT),0x35:('bgt.un.s',SBT),
0x36:('ble.un.s',SBT),0x37:('blt.un.s',SBT),
0x38:('br',BT),0x39:('brfalse',BT),0x3A:('brtrue',BT),0x3B:('beq',BT),
0x3C:('bge',BT),0x3D:('bgt',BT),0x3E:('ble',BT),0x3F:('blt',BT),
0x40:('bne.un',BT),0x41:('bge.un',BT),0x42:('bgt.un',BT),0x43:('ble.un',BT),
0x44:('blt.un',BT),0x45:('switch',SW),
0x46:('ldind.i1',N),0x47:('ldind.u1',N),0x48:('ldind.i2',N),0x49:('ldind.u2',N),
0x4A:('ldind.i4',N),0x4B:('ldind.u4',N),0x4C:('ldind.i8',N),0x4D:('ldind.i',N),
0x4E:('ldind.r4',N),0x4F:('ldind.r8',N),0x50:('ldind.ref',N),
0x51:('stind.ref',N),0x52:('stind.i1',N),0x53:('stind.i2',N),0x54:('stind.i4',N),
0x55:('stind.i8',N),0x56:('stind.r4',N),0x57:('stind.r8',N),
0x58:('add',N),0x59:('sub',N),0x5A:('mul',N),0x5B:('div',N),0x5C:('div.un',N),
0x5D:('rem',N),0x5E:('rem.un',N),0x5F:('and',N),0x60:('or',N),0x61:('xor',N),
0x62:('shl',N),0x63:('shr',N),0x64:('shr.un',N),0x65:('neg',N),0x66:('not',N),
0x67:('conv.i1',N),0x68:('conv.i2',N),0x69:('conv.i4',N),0x6A:('conv.i8',N),
0x6B:('conv.r4',N),0x6C:('conv.r8',N),0x6D:('conv.u4',N),0x6E:('conv.u8',N),
0x6F:('callvirt',M),0x70:('cpobj',T),0x71:('ldobj',T),0x72:('ldstr',S),
0x73:('newobj',M),0x74:('castclass',T),0x75:('isinst',T),0x76:('conv.r.un',N),
0x79:('unbox',T),0x7A:('throw',N),0x7B:('ldfld',F),0x7C:('ldflda',F),
0x7D:('stfld',F),0x7E:('ldsfld',F),0x7F:('ldsflda',F),0x80:('stsfld',F),
0x81:('stobj',T),0x82:('conv.ovf.i1.un',N),0x83:('conv.ovf.i2.un',N),
0x84:('conv.ovf.i4.un',N),0x85:('conv.ovf.i8.un',N),0x86:('conv.ovf.u1.un',N),
0x87:('conv.ovf.u2.un',N),0x88:('conv.ovf.u4.un',N),0x89:('conv.ovf.u8.un',N),
0x8A:('conv.ovf.i.un',N),0x8B:('conv.ovf.u.un',N),0x8C:('box',T),0x8D:('newarr',T),
0x8E:('ldlen',N),0x8F:('ldelema',T),
0x90:('ldelem.i1',N),0x91:('ldelem.u1',N),0x92:('ldelem.i2',N),0x93:('ldelem.u2',N),
0x94:('ldelem.i4',N),0x95:('ldelem.u4',N),0x96:('ldelem.i8',N),0x97:('ldelem.i',N),
0x98:('ldelem.r4',N),0x99:('ldelem.r8',N),0x9A:('ldelem.ref',N),
0x9B:('stelem.i',N),0x9C:('stelem.i1',N),0x9D:('stelem.i2',N),0x9E:('stelem.i4',N),
0x9F:('stelem.i8',N),0xA0:('stelem.r4',N),0xA1:('stelem.r8',N),0xA2:('stelem.ref',N),
0xA3:('ldelem',T),0xA4:('stelem',T),0xA5:('unbox.any',T),
0xB3:('conv.ovf.i1',N),0xB4:('conv.ovf.u1',N),0xB5:('conv.ovf.i2',N),
0xB6:('conv.ovf.u2',N),0xB7:('conv.ovf.i4',N),0xB8:('conv.ovf.u4',N),
0xB9:('conv.ovf.i8',N),0xBA:('conv.ovf.u8',N),
0xC2:('refanyval',T),0xC3:('ckfinite',N),0xC6:('mkrefany',T),
0xD0:('ldtoken',TK),0xD1:('conv.u2',N),0xD2:('conv.u1',N),0xD3:('conv.i',N),
0xD4:('conv.ovf.i',N),0xD5:('conv.ovf.u',N),0xD6:('add.ovf',N),
0xD7:('add.ovf.un',N),0xD8:('mul.ovf',N),0xD9:('mul.ovf.un',N),
0xDA:('sub.ovf',N),0xDB:('sub.ovf.un',N),0xDC:('endfinally',N),
0xDD:('leave',BT),0xDE:('leave.s',SBT),0xDF:('stind.i',N),0xE0:('conv.u',N),
}
OP2 = {
0x00:('arglist',N),0x01:('ceq',N),0x02:('cgt',N),0x03:('cgt.un',N),
0x04:('clt',N),0x05:('clt.un',N),0x06:('ldftn',M),0x07:('ldvirtftn',M),
0x09:('ldarg',V),0x0A:('ldarga',V),0x0B:('starg',V),0x0C:('ldloc',V),
0x0D:('ldloca',V),0x0E:('stloc',V),0x0F:('localloc',N),0x11:('endfilter',N),
0x12:('unaligned.',SI1),0x13:('volatile.',N),0x14:('tail.',N),
0x15:('initobj',T),0x16:('constrained.',T),0x17:('cpblk',N),0x18:('initblk',N),
0x19:('no.',SI1),0x1A:('rethrow',N),0x1C:('sizeof',T),0x1D:('refanytype',N),
0x1E:('readonly.',N),
}
# 会"调用"的方法 token 所在操作码
CALL_OPS = {'call','callvirt','newobj','ldftn','ldvirtftn','jmp'}


class Asm:
    def __init__(self, path):
        self.path = path
        d = self.d = open(path, 'rb').read()
        # ---- PE
        e = struct.unpack_from('<I', d, 0x3c)[0]
        coff = e + 4
        nsec = struct.unpack_from('<H', d, coff + 2)[0]
        optsz = struct.unpack_from('<H', d, coff + 16)[0]
        opt = coff + 20
        magic = struct.unpack_from('<H', d, opt)[0]
        numdd = struct.unpack_from('<I', d, opt + (92 if magic == 0x10b else 108))[0]
        dd_off = opt + (96 if magic == 0x10b else 112)
        secs = []
        so = opt + optsz
        for i in range(nsec):
            o = so + i * 40
            nm = d[o:o+8].rstrip(b'\x00').decode('ascii', 'replace')
            vs, va, rs, ra = struct.unpack_from('<IIII', d, o + 8)
            secs.append((nm, va, vs, ra, rs))
        self.sections = secs
        def rva2off(rva):
            for nm, va, vs, ra, rs in secs:
                if va <= rva < va + max(vs, rs):
                    return ra + (rva - va)
            return None
        self.rva2off = rva2off
        cli_rva, cli_size = struct.unpack_from('<II', d, dd_off + 14 * 8)
        o = rva2off(cli_rva)
        md_rva, md_size = struct.unpack_from('<II', d, o + 8)
        mo = rva2off(md_rva)
        ver_len = struct.unpack_from('<I', d, mo + 12)[0]
        self.md_version = d[mo+16:mo+16+ver_len].split(b'\x00')[0].decode('ascii', 'replace')
        nstreams = struct.unpack_from('<H', d, mo + 16 + ver_len + 2)[0]
        p = mo + 16 + ver_len + 4
        streams = {}
        for _ in range(nstreams):
            soff, ssize = struct.unpack_from('<II', d, p); p += 8
            nl = 0
            while d[p+nl] != 0: nl += 1
            name = d[p:p+nl].decode('ascii', 'replace')
            p += nl + 1
            p = (p + 3) & ~3
            streams[name] = (mo + soff, ssize)
        self.streams = streams
        tname = '#~' if '#~' in streams else '#-'
        t = streams[tname][0]
        heap = d[t + 6]
        self.ssize_idx = 4 if heap & 1 else 2
        self.gsize_idx = 4 if heap & 2 else 2
        self.bsize_idx = 4 if heap & 4 else 2
        valid, _sorted = struct.unpack_from('<QQ', d, t + 8)
        n = t + 24
        self.rowcounts = {}
        for i in range(64):
            if valid >> i & 1:
                self.rowcounts[i] = struct.unpack_from('<I', d, n)[0]; n += 4
        self._build_tablesizes()
        cur = n
        self.offs = {}
        for i in sorted(self.rowcounts):
            self.offs[i] = cur
            cur += self.tablesizes.get(i, 0) * self.rowcounts[i]
        self.strbase = streams['#Strings'][0]
        self.blobbase = streams['#Blob'][0]
        self._read_strings()
        self._read_userstrings()
        self._read_types()
        self._read_methods()
        self._read_fields()
        self._read_typerefs()
        self._read_memberrefs()

    # -------- table layout (ECMA-335 II.22)
    def _build_tablesizes(self):
        ts = {}; rc = self.rowcounts; s = self.ssize_idx; g = self.gsize_idx; b = self.bsize_idx
        def ridx(tbl): return 4 if rc.get(tbl, 0) >= 0x10000 else 2
        def coded(tables, bits):
            mx = max([rc.get(x, 0) for x in tables] + [0])
            return 4 if mx >= (1 << (16 - bits)) else 2
        ts[0x00] = 2 + s + 3*g
        rs = coded([0x00,0x1A,0x23,0x01], 2)
        ts[0x01] = rs + 2*s
        tdor = coded([0x02,0x01,0x1B], 2)
        ts[0x02] = 4 + 2*s + tdor + ridx(0x04) + ridx(0x06)
        ts[0x03] = ridx(0x04)
        ts[0x04] = 2 + s + b
        ts[0x05] = ridx(0x06)
        ts[0x06] = 8 + s + b + ridx(0x08)
        ts[0x07] = ridx(0x08)
        ts[0x08] = 4 + s
        ts[0x09] = ridx(0x02) + tdor
        ts[0x0A] = coded([0x02,0x01,0x1A,0x06,0x1B], 3) + s + b
        ts[0x0B] = 1 + 1 + coded([0x04,0x08,0x17], 2) + b
        # ★ CustomAttribute = Parent(HasCustomAttribute) + Type(CustomAttributeType) + Value(Blob)
        ts[0x0C] = coded([0x06,0x04,0x01,0x02,0x08,0x09,0x0A,0x00,0x0E,0x17,0x14,0x11,0x1A,0x1B,0x20,0x23,0x26,0x27,0x28,0x2A,0x2C], 5) \
                   + coded([0x06,0x0A], 3) + b
        ts[0x0D] = coded([0x04,0x08], 1) + b
        ts[0x0E] = 2 + coded([0x02,0x06,0x20], 2) + b
        ts[0x0F] = 2 + 4 + ridx(0x02)
        ts[0x10] = 4 + ridx(0x04)
        ts[0x11] = b
        ts[0x12] = ridx(0x02) + ridx(0x14)
        ts[0x13] = ridx(0x14)
        ts[0x14] = 2 + s + tdor
        ts[0x15] = ridx(0x02) + ridx(0x17)
        ts[0x16] = ridx(0x17)
        ts[0x17] = 2 + s + b
        ts[0x18] = 2 + ridx(0x06) + coded([0x14,0x17], 1)
        ts[0x19] = ridx(0x02) + coded([0x06,0x0A], 1) + coded([0x06,0x0A], 1)
        ts[0x1A] = s
        ts[0x1B] = b
        ts[0x1C] = 2 + coded([0x04,0x06], 1) + s + ridx(0x1A)
        ts[0x1D] = 4 + ridx(0x04)
        ts[0x20] = 16 + b + 2*s
        ts[0x21] = 4
        ts[0x22] = 12
        ts[0x23] = 12 + 2*b + 2*s
        ts[0x24] = 4 + ridx(0x23)
        ts[0x25] = 12 + ridx(0x23)
        ts[0x26] = 4 + s + b
        ts[0x27] = 8 + 2*s + coded([0x26,0x27,0x23], 2)
        ts[0x28] = 8 + s + coded([0x26,0x27], 1)
        ts[0x29] = 2*ridx(0x02)
        ts[0x2A] = 4 + coded([0x02,0x06], 1) + s
        ts[0x2B] = coded([0x06,0x0A], 1) + b
        ts[0x2C] = ridx(0x2A) + tdor
        self.tablesizes = ts
        self._tdor_bits = 2
        self._coded_bits = {
            # 键 = coded index 的"种类号"（ECMA-335 II.24.2.6 的 TypeDefOrRef=2 等）
            0x02: ([0x02,0x01,0x1B], 2),
            0x01: ([0x00,0x1A,0x23,0x01], 2), 0x09: ([0x02,0x01,0x1B], 2),
            0x0A: ([0x02,0x01,0x1A,0x06,0x1B], 3), 0x0B: ([0x04,0x08,0x17], 2),
            0x0D: ([0x04,0x08], 1), 0x0E: ([0x02,0x06,0x20], 2),
            0x14: ([0x02,0x01,0x1B], 2), 0x18: ([0x14,0x17], 1),
            0x19: ([0x06,0x0A], 1), 0x1C: ([0x04,0x06], 1),
            0x27: ([0x26,0x27,0x23], 2), 0x28: ([0x26,0x27], 1),
            0x2A: ([0x02,0x06], 1), 0x2B: ([0x06,0x0A], 1),
        }
        self._coded_sizes = {}
        for k, (tabs, bits) in self._coded_bits.items():
            mx = max([rc.get(x, 0) for x in tabs] + [0])
            self._coded_sizes[k] = 4 if mx >= (1 << (16 - bits)) else 2

    # -------- heaps
    def _read_strings(self):
        pass

    def sget(self, idx):
        base = self.strbase
        e = self.d.index(b'\x00', base + idx)
        return self.d[base+idx:e].decode('utf-8', 'replace')

    def blob(self, idx):
        base = self.blobbase + idx
        b0 = self.d[base]
        if b0 & 0x80 == 0: ln, adv = b0, 1
        elif b0 & 0xC0 == 0x80: ln, adv = ((b0 & 0x3F) << 8) | self.d[base+1], 2
        else: ln, adv = ((b0 & 0x1F) << 24) | (self.d[base+1] << 16) | (self.d[base+2] << 8) | self.d[base+3], 4
        return self.d[base+adv:base+adv+ln]

    def _read_userstrings(self):
        self.us_map = {}
        self.us_list = []
        if '#US' not in self.streams: return
        usb, ussz = self.streams['#US']
        blob = self.d[usb:usb+ussz]
        i = 1
        while i < len(blob):
            off = i
            b0 = blob[i]
            if b0 & 0x80 == 0: ln, adv = b0, 1
            elif b0 & 0xC0 == 0x80: ln, adv = ((b0 & 0x3F) << 8) | blob[i+1], 2
            else: ln, adv = ((b0 & 0x1F) << 24) | (blob[i+1] << 16) | (blob[i+2] << 8) | blob[i+3], 4
            i += adv
            if ln == 0: continue
            chunk = blob[i:i+ln]; i += ln
            if not chunk: continue
            st = chunk[:-1].decode('utf-16-le', 'replace')
            self.us_map[off] = st
            self.us_list.append(st)

    # -------- rows
    def _u16(self, o): return struct.unpack_from('<H', self.d, o)[0]
    def _u32(self, o): return struct.unpack_from('<I', self.d, o)[0]
    def _str_idx(self, o): return self._u32(o) if self.ssize_idx == 4 else self._u16(o)
    def _blob_idx(self, o): return self._u32(o) if self.bsize_idx == 4 else self._u16(o)
    def _rid(self, o, tbl): return self._u32(o) if self.rowcounts.get(tbl, 0) >= 0x10000 else self._u16(o)

    def _read_types(self):
        self.typedefs = []
        rc = self.rowcounts.get(0x02, 0); sz = self.tablesizes[0x02]; o2 = self.offs.get(0x02, 0)
        for i in range(rc):
            ro = o2 + i * sz
            ni = self._str_idx(ro + 4)
            no = self._str_idx(ro + 4 + self.ssize_idx)
            ext = self._rid(ro + 4 + 2*self.ssize_idx, 0x02)  # TypeDefOrRef coded -> raw
            fl = self._rid(ro + 4 + 2*self.ssize_idx + self._coded_sizes[0x02], 0x04)
            ml = self._rid(ro + 4 + 2*self.ssize_idx + self._coded_sizes[0x02] + (4 if self.rowcounts.get(0x04,0)>=0x10000 else 2), 0x06)
            self.typedefs.append({'rid': i+1, 'ns': self.sget(no), 'name': self.sget(ni),
                                  'extends': ext, 'fieldlist': fl, 'methodlist': ml,
                                  'full': (self.sget(no) + '.' if self.sget(no) else '') + self.sget(ni)})
        # method/field ranges
        nm = self.rowcounts.get(0x06, 0)
        for i, td in enumerate(self.typedefs):
            nxt = self.typedefs[i+1]['methodlist'] if i+1 < len(self.typedefs) else nm + 1
            td['methods'] = list(range(td['methodlist'], nxt))
        nf = self.rowcounts.get(0x04, 0)
        for i, td in enumerate(self.typedefs):
            nxt = self.typedefs[i+1]['fieldlist'] if i+1 < len(self.typedefs) else nf + 1
            td['fields'] = list(range(td['fieldlist'], nxt))
        self.type_by_rid = {t['rid']: t for t in self.typedefs}

    def _read_methods(self):
        self.methods = []
        rc = self.rowcounts.get(0x06, 0); sz = self.tablesizes[0x06]; o6 = self.offs.get(0x06, 0)
        for i in range(rc):
            ro = o6 + i * sz
            rva = self._u32(ro)
            flags = self._u16(ro + 6)
            ni = self._str_idx(ro + 8)
            sig = self._blob_idx(ro + 8 + self.ssize_idx)
            self.methods.append({'rid': i+1, 'rva': rva, 'flags': flags,
                                 'name': self.sget(ni), 'sigidx': sig, 'type': None})
        for td in self.typedefs:
            for rid in td['methods']:
                if 1 <= rid <= rc:
                    self.methods[rid-1]['type'] = td
        self.method_by_rid = {m['rid']: m for m in self.methods}
        # 缓存签名字符串
        for m in self.methods:
            try: m['sig'] = self.sig_string(self.blob(m['sigidx']))
            except Exception: m['sig'] = '?'

    def _read_fields(self):
        self.fields = []
        rc = self.rowcounts.get(0x04, 0); sz = self.tablesizes[0x04]; o4 = self.offs.get(0x04, 0)
        for i in range(rc):
            ro = o4 + i * sz
            ni = self._str_idx(ro + 2)
            sig = self._blob_idx(ro + 2 + self.ssize_idx)
            self.fields.append({'rid': i+1, 'name': self.sget(ni), 'sigidx': sig, 'type': None})
        for td in self.typedefs:
            for rid in td['fields']:
                if 1 <= rid <= rc:
                    self.fields[rid-1]['type'] = td
        for f in self.fields:
            try: f['sig'] = self.field_sig(self.blob(f['sigidx']))
            except Exception: f['sig'] = '?'

    def field_sig(self, b):
        """字段签名：0x06 FIELD 后跟类型"""
        if not b: return '?'
        i = 1 if b[0] == 0x06 else 0
        nm, _ = self.sig_type(b, i)
        return nm

    def _read_typerefs(self):
        self.typerefs = []
        rc = self.rowcounts.get(0x01, 0); sz = self.tablesizes[0x01]; o1 = self.offs.get(0x01, 0)
        csz = self._coded_sizes[0x01]
        for i in range(rc):
            ro = o1 + i * sz
            ni = self._str_idx(ro + csz)
            no = self._str_idx(ro + csz + self.ssize_idx)
            ns, nm = self.sget(no), self.sget(ni)
            self.typerefs.append({'rid': i+1, 'ns': ns, 'name': nm,
                                  'full': (ns + '.' if ns else '') + nm,
                                  'scope': self._u32(ro) if csz == 4 else self._u16(ro)})
        self.typeref_by_rid = {t['rid']: t for t in self.typerefs}

    def _read_memberrefs(self):
        self.memberrefs = []
        rc = self.rowcounts.get(0x0A, 0); sz = self.tablesizes[0x0A]; oa = self.offs.get(0x0A, 0)
        csz = self._coded_sizes[0x0A]
        for i in range(rc):
            ro = oa + i * sz
            cls = self._u32(ro) if csz == 4 else self._u16(ro)
            ni = self._str_idx(ro + csz)
            sig = self._blob_idx(ro + csz + self.ssize_idx)
            self.memberrefs.append({'rid': i+1, 'cls': cls, 'name': self.sget(ni),
                                    'sigidx': sig, 'raw': struct.unpack_from('<I', self.d, ro)[0] if csz==4 else struct.unpack_from('<H', self.d, ro)[0]})
        self.memberref_by_rid = {m['rid']: m for m in self.memberrefs}

    # -------- signature parsing
    def _coded_resolve(self, val, tables, bits):
        tag = val & ((1 << bits) - 1); rid = val >> bits
        return (tables[tag], rid)

    def _tdor(self, val):
        if val == 0: return None
        tbl, rid = self._coded_resolve(val, [0x02, 0x01, 0x1B], 2)
        return self.type_name_of(tbl, rid)

    def type_name_of(self, tbl, rid):
        if tbl == 0x02:
            t = self.type_by_rid.get(rid)
            return t['full'] if t else f'<TypeDef{rid}>'
        if tbl == 0x01:
            t = self.typeref_by_rid.get(rid)
            return t['full'] if t else f'<TypeRef{rid}>'
        if tbl == 0x1B:
            return self.typespec_name(rid)
        return f'<tbl{tbl}:{rid}>'

    def typespec_name(self, rid):
        if not hasattr(self, '_tscache'): self._tscache = {}
        if rid in self._tscache: return self._tscache[rid]
        rc = self.rowcounts.get(0x1B, 0); sz = self.tablesizes[0x1B]; ob = self.offs.get(0x1B, 0)
        if not (1 <= rid <= rc): return f'<TypeSpec{rid}>'
        ro = ob + (rid-1) * sz
        sig = self.blob(self._blob_idx(ro))
        self._tscache[rid] = '<resolving>'
        try: nm = self.sig_type(sig, 0)[0]
        except Exception: nm = f'<TypeSpec{rid}>'
        self._tscache[rid] = nm
        return nm

    PRIM = {0x01:'void',0x02:'bool',0x03:'char',0x04:'sbyte',0x05:'byte',0x06:'short',
            0x07:'ushort',0x08:'int',0x09:'uint',0x0A:'long',0x0B:'ulong',0x0C:'float',
            0x0D:'double',0x0E:'string',0x16:'TypedReference',0x18:'IntPtr',0x19:'UIntPtr',
            0x1C:'object'}

    def sig_type(self, b, i):
        """返回 (类型名, 新下标)"""
        if i >= len(b): return ('?', len(b) + 1)
        et = b[i]; i += 1
        if et in self.PRIM: return (self.PRIM[et], i)
        if et in (0x11, 0x12):
            # ★ 签名内的 TypeDefOrRef 是**压缩**整数（ECMA-335 II.23.2.8），不是定长 coded index
            v, i = self._cu(b, i)
            return (self._tdor(v) or '?', i)
        if et == 0x0F:
            nm, i = self.sig_type(b, i); return (nm + '*', i)
        if et == 0x10:
            nm, i = self.sig_type(b, i); return (nm + '&', i)
        if et == 0x1D:
            nm, i = self.sig_type(b, i); return (nm + '[]', i)
        if et == 0x13:
            v, i = self._cu(b, i); return (f'!{v}', i)
        if et == 0x1E:
            v, i = self._cu(b, i); return (f'!!{v}', i)
        if et == 0x15:
            kind = b[i]; i += 1
            v, i = self._cu(b, i)
            base = self._tdor(v) or '?'
            n, i = self._cu(b, i)
            if n > 32: return (base + '<...>', len(b) + 1)
            args = []
            for _ in range(n):
                a, i = self.sig_type(b, i); args.append(a)
                if i > len(b): break
            return (f'{base}<{",".join(args)}>', i)
        if et == 0x14:
            nm, i = self.sig_type(b, i)
            rank, i = self._cu(b, i)
            ns, i = self._cu(b, i)
            for _ in range(min(ns, 32)): _x, i = self._cu(b, i)
            nl, i = self._cu(b, i)
            for _ in range(min(nl, 32)): _x, i = self._cu(b, i)
            if rank > 64: rank = 1
            return (f'{nm}[{",".join([""] * rank)}]', i)
        if et in (0x1F, 0x20):
            v, i = self._cu(b, i)
            return self.sig_type(b, i)
        if et == 0x45:
            return self.sig_type(b, i)
        if et == 0x1B:
            return ('fnptr', i)
        return (f'<et{et:#x}>', i)

    def _u32_at(self, b, i): return struct.unpack_from('<I', b, i)[0] if i+4 <= len(b) else 0
    def _u16_at(self, b, i): return struct.unpack_from('<H', b, i)[0] if i+2 <= len(b) else 0

    def _cu(self, b, i):
        """压缩无符号整数（ECMA-335 II.23.2）→ (值, 新下标)"""
        if i >= len(b): return (0, len(b) + 1)
        b0 = b[i]
        if b0 & 0x80 == 0: return (b0, i + 1)
        if b0 & 0xC0 == 0x80:
            return (((b0 & 0x3F) << 8) | (b[i+1] if i+1 < len(b) else 0), i + 2)
        v = ((b0 & 0x1F) << 24)
        for k in range(1, 4):
            v |= (b[i+k] if i+k < len(b) else 0) << (8 * (3 - k))
        return (v, i + 4)

    def sig_string(self, b):
        """方法签名 → 'ret (this a, b)'"""
        if not b: return '?'
        i = 0
        flags = b[i]; i += 1
        hasthis = bool(flags & 0x20)
        if flags & 0x10:  # GENERIC
            _n, i = self._cu(b, i)
        np, i = self._cu(b, i)
        if np > 64: return '<bad sig np=%d len=%d>' % (np, len(b))
        ret, i = self.sig_type(b, i)
        params = []
        for _ in range(np):
            if i < len(b) and b[i] == 0x41: i += 1
            p, i = self.sig_type(b, i)
            params.append(p)
            if i > len(b): break
        pre = 'this ' if hasthis else ''
        return f'{ret} ({pre}{", ".join(params)})'

    # -------- token resolution
    def method_token(self, tok):
        tbl = tok >> 24; rid = tok & 0xFFFFFF
        if tbl == 0x06:
            m = self.method_by_rid.get(rid)
            if not m: return f'<MethodDef{rid}>'
            t = m['type']['full'] if m['type'] else '?'
            return f'{t}::{m["name"]}'
        if tbl == 0x0A:
            mr = self.memberref_by_rid.get(rid)
            if not mr: return f'<MemberRef{rid}>'
            return f'{self.memberref_class(mr)}::{mr["name"]}'
        if tbl == 0x2B:
            rc = self.rowcounts.get(0x2B, 0); sz = self.tablesizes[0x2B]; o = self.offs.get(0x2B, 0)
            csz = self._coded_sizes[0x2B]
            if not (1 <= rid <= rc): return f'<MethodSpec{rid}>'
            ro = o + (rid-1)*sz
            v = self._u32(ro) if csz == 4 else self._u16(ro)
            t2, r2 = self._coded_resolve(v, [0x06, 0x0A], 1)
            base = self.method_token((t2 << 24) | r2)
            sig = self.blob(self._blob_idx(ro + csz))
            # 泛型实参
            try:
                n, i = self._cu(sig, 0)
                if n > 32: return base
                args = []
                for _ in range(n):
                    a, i = self.sig_type(sig, i); args.append(a)
                return f'{base}<{",".join(args)}>'
            except Exception:
                return base
        return f'<tok {tok:#010x}>'

    def memberref_class(self, mr):
        v = mr['raw']
        tbl, rid = self._coded_resolve(v, [0x02, 0x01, 0x1A, 0x06, 0x1B], 3)
        if tbl == 0x02:
            t = self.type_by_rid.get(rid); return t['full'] if t else f'<TD{rid}>'
        if tbl == 0x01:
            t = self.typeref_by_rid.get(rid); return t['full'] if t else f'<TR{rid}>'
        if tbl == 0x1B:
            return self.typespec_name(rid)
        if tbl == 0x06:
            m = self.method_by_rid.get(rid)
            return f'[var] {m["type"]["full"] if m and m["type"] else "?"}'
        return f'<cls tbl{tbl}:{rid}>'

    def field_token(self, tok):
        tbl = tok >> 24; rid = tok & 0xFFFFFF
        if tbl == 0x04:
            f = self.fields[rid-1] if 1 <= rid <= len(self.fields) else None
            if not f: return f'<Field{rid}>'
            t = f['type']['full'] if f['type'] else '?'
            return f'{t}::{f["name"]}'
        if tbl == 0x0A:
            mr = self.memberref_by_rid.get(rid)
            if not mr: return f'<MemberRef{rid}>'
            return f'{self.memberref_class(mr)}::{mr["name"]}'
        return f'<ftok {tok:#010x}>'

    def type_token(self, tok):
        tbl = tok >> 24; rid = tok & 0xFFFFFF
        return self.type_name_of(tbl, rid)

    # -------- method body + IL
    def body(self, rid):
        m = self.method_by_rid.get(rid)
        if not m or not m['rva']: return None
        o = self.rva2off(m['rva'])
        if o is None: return None
        b0 = self.d[o]
        if (b0 & 3) == 2:  # tiny
            size = b0 >> 2
            return self.d[o+1:o+1+size], 0
        # fat
        flags = struct.unpack_from('<H', self.d, o)[0]
        hsize = (flags >> 12) * 4
        code = struct.unpack_from('<I', self.d, o + 4)[0]
        if flags & 0x08:  # more sections
            pass
        return self.d[o+hsize:o+hsize+code], flags

    def disasm(self, rid, resolve=True):
        r = self.body(rid)
        if not r or r[0] is None: return None
        code = r[0]
        out = []
        i = 0
        while i < len(code):
            off = i
            op = code[i]; i += 1
            if op == 0xFE:
                if i >= len(code): break
                op2 = code[i]; i += 1
                nm, ot = OP2.get(op2, (f'<fe{op2:02x}>', N))
            else:
                nm, ot = OP1.get(op, (f'<{op:02x}>', N))
            val = None
            if ot == N: pass
            elif ot == SI1: val = struct.unpack_from('<b', code, i)[0]; i += 1
            elif ot == I4: val = struct.unpack_from('<i', code, i)[0]; i += 4
            elif ot == I8: val = struct.unpack_from('<q', code, i)[0]; i += 8
            elif ot == SR: val = struct.unpack_from('<f', code, i)[0]; i += 4
            elif ot == R8: val = struct.unpack_from('<d', code, i)[0]; i += 8
            elif ot in (M, F, T, TK, S, SIG):
                val = struct.unpack_from('<I', code, i)[0]; i += 4
            elif ot == SV: val = code[i]; i += 1          # ShortInlineVar = 1 字节
            elif ot == V: val = struct.unpack_from('<H', code, i)[0]; i += 2
            elif ot in (SBT,):
                d8 = struct.unpack_from('<b', code, i)[0]; i += 1; val = i + d8
            elif ot in (BT,):
                d32 = struct.unpack_from('<i', code, i)[0]; i += 4; val = i + d32
            elif ot == SW:
                n = struct.unpack_from('<I', code, i)[0]; i += 4
                val = [i + 4*n + struct.unpack_from('<i', code, i+4*k)[0] for k in range(n)]
                i += 4*n
            txt = ''
            if val is not None:
                if ot in (M,) or nm in ('newobj',):
                    txt = self.method_token(val) if resolve else f'{val:#010x}'
                elif ot == F:
                    txt = self.field_token(val) if resolve else f'{val:#010x}'
                elif ot in (T,):
                    txt = self.type_token(val) if resolve else f'{val:#010x}'
                elif ot == TK:
                    txt = self.token_any(val) if resolve else f'{val:#010x}'
                elif ot == S:
                    txt = repr(self.us_map.get(val & 0xFFFFFF, f'<us {val:#x}>'))
                elif ot == SIG:
                    txt = f'<sig {val:#010x}>'
                else:
                    txt = str(val)
            out.append((off, nm, txt))
        return out

    def token_any(self, tok):
        tbl = tok >> 24
        if tbl == 0x06 or tbl == 0x0A or tbl == 0x2B: return self.method_token(tok)
        if tbl == 0x04: return self.field_token(tok)
        if tbl in (0x01, 0x02, 0x1B): return self.type_token(tok)
        return f'<tok {tok:#010x}>'

    # -------- call graph
    def build_calls(self):
        """返回 {caller_rid: set(callee_name)} 与 {callee_name: set(caller_rid)}"""
        if getattr(self, '_calls', None) is not None: return self._calls, self._rev
        calls = defaultdict(set); rev = defaultdict(set)
        for m in self.methods:
            if m['flags'] & 0x0400:  # Abstract
                continue
            # 名字被混淆但保留的类名仍可用；无 RVA 的跳过
            r = self.body(m['rid'])
            if not r or not r[0]: continue
            try:
                ins = self.disasm(m['rid'])
            except Exception:
                continue
            if not ins: continue
            for off, nm, txt in ins:
                if nm in CALL_OPS and txt and not txt.startswith('<'):
                    calls[m['rid']].add(txt)
                    rev[txt].add(m['rid'])
        self._calls, self._rev = calls, rev
        return calls, rev

    def caller_name(self, rid):
        m = self.method_by_rid.get(rid)
        if not m: return f'<{rid}>'
        t = m['type']['full'] if m['type'] else '?'
        return f'{t}::{m["name"]}'

    def build_refs(self):
        """扫描全部 IL：索引 = token 文本子串 -> 使用它的方法 rid 集合。含 call/field/type/ldstr。
        这是应对"方法名被混淆、但类型名/字段名保留"的核心检索手段。"""
        if getattr(self, '_refs', None) is not None: return self._refs
        idx = defaultdict(set)
        for m in self.methods:
            if m['flags'] & 0x0400: continue
            try: ins = self.disasm(m['rid'])
            except Exception: continue
            if not ins: continue
            for off, nm, txt in ins:
                if not txt: continue
                idx[txt].add(m['rid'])
        self._refs = idx
        return idx

    def refs(self, kw, limit=200):
        """返回 [(token文本, [调用者名...]), ...]"""
        idx = self.build_refs()
        out = []
        for txt, rids in idx.items():
            if kw in txt:
                out.append((txt, sorted(self.caller_name(r) for r in rids)))
        out.sort(key=lambda x: -len(x[1]))
        return out[:limit]

    def find_types(self, kw):
        return [t for t in self.typedefs if kw in t['full']]

    def find_methods(self, kw):
        res = []
        for m in self.methods:
            full = self.caller_name(m['rid'])
            if kw in full:
                res.append(m)
        return res


def main():
    try: sys.stdout.reconfigure(encoding='utf-8')
    except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument('dll')
    ap.add_argument('--types', action='store_true')
    ap.add_argument('--grep', default=None)
    ap.add_argument('--methods', default=None)
    ap.add_argument('--dis', default=None)
    ap.add_argument('--who', default=None)
    ap.add_argument('--trace', default=None)
    ap.add_argument('--depth', type=int, default=3)
    ap.add_argument('--strings', default=None)
    ap.add_argument('--fields', default=None)
    ap.add_argument('--stats', action='store_true')
    ap.add_argument('--refs', default=None, help='扫描全库 IL，找引用含此子串的 token 的方法')
    ap.add_argument('--refs2', default=None, help='同上，但调用者名单里再过滤子串')
    ap.add_argument('--limit', type=int, default=200)
    a = ap.parse_args()
    A = Asm(a.dll)
    print(f'== {os.path.basename(a.dll)} ==  md={A.md_version} TypeDef={len(A.typedefs)} '
          f'MethodDef={len(A.methods)} Field={len(A.fields)} TypeRef={len(A.typerefs)} '
          f'MemberRef={len(A.memberrefs)} US={len(A.us_list)}')
    if a.stats:
        print('rowcounts:', {hex(k): v for k, v in sorted(A.rowcounts.items())})
        tb = defaultdict(int)
        for t in A.typedefs: tb[t['ns']] += 1
        for k, v in sorted(tb.items(), key=lambda x: -x[1])[:40]:
            print(f'  {k or "(global)"}: {v}')
        return
    if a.refs:
        for txt, callers in A.refs(a.refs, a.limit):
            if a.refs2 and not any(a.refs2 in c for c in callers):
                continue
            if a.refs2:
                callers = [c for c in callers if a.refs2 in c]
            print(f'--- {txt}   ({len(callers)} 处)')
            for c in callers[:40]:
                print('      ' + c)
        return
    if a.types:
        for t in A.typedefs:
            if a.grep and a.grep not in t['full']: continue
            print(f'TD{t["rid"]:5d} {t["full"]}  methods={len(t["methods"])} fields={len(t["fields"])}')
        return
    if a.methods:
        for m in A.find_methods(a.methods)[:a.limit]:
            print(f'MD{m["rid"]:5d} rva={m["rva"]:#08x} {A.caller_name(m["rid"])} : {m.get("sig")}')
        return
    if a.fields:
        for t in A.typedefs:
            if a.fields not in t['full']: continue
            print(f'--- {t["full"]} ---')
            for rid in t['fields']:
                f = A.fields[rid-1]
                print(f'  {f["sig"]} {f["name"]}')
        return
    if a.strings:
        for s in A.us_list:
            if a.strings in s: print(repr(s))
        return
    if a.dis:
        for m in A.find_methods(a.dis)[:a.limit]:
            print(f'\n===== {A.caller_name(m["rid"])} : {m.get("sig")}  [MD{m["rid"]}] =====')
            ins = A.disasm(m['rid'])
            if ins is None: print('  <no body>'); continue
            for off, nm, txt in ins:
                print(f'  IL_{off:04X}: {nm:14s} {txt}')
        return
    if a.who:
        calls, rev = A.build_calls()
        hits = [k for k in rev if a.who in k]
        for k in sorted(hits):
            print(f'--- {k}  <- {len(rev[k])} 调用点')
            for rid in sorted(rev[k])[:a.limit]:
                print('    ' + A.caller_name(rid))
        return
    if a.trace:
        calls, rev = A.build_calls()
        targets = [k for k in calls if a.trace in k] + [k for k in rev if a.trace in k]
        seen = set()
        def walk(name, d, indent):
            if d < 0 or name in seen and d < a.depth: 
                pass
            print('  ' * indent + name)
            if d == 0: return
            for c in sorted(calls.get(name, [])):
                if c in seen: 
                    print('  ' * (indent+1) + c + '   [已展开]')
                    continue
                seen.add(c)
                walk(c, d-1, indent+1)
        for t in sorted(set(targets)):
            print(f'\n===== TRACE {t} =====')
            seen.clear(); seen.add(t)
            walk(t, a.depth, 0)
        return
    print(__doc__)


if __name__ == '__main__':
    main()
