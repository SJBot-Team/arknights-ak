# -*- coding: utf-8 -*-
"""enumvals.py —— 读 Mono 程序集里某枚举类型的字段默认值（Constant 表）。"""
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from mono_il import Asm

DLL = r'D:\__soft\ak\ArknightR\ArknightR_Data\Managed\Assembly-CSharp.dll'
A = Asm(DLL)

# Constant 表: Type(1) Padding(1) Parent(HasConstant coded) Value(blob)
rc = A.rowcounts.get(0x0B, 0)
sz = A.tablesizes[0x0B]
ob = A.offs.get(0x0B, 0)
hasconst_bits = A._coded_sizes[0x0B]  # coded(HasConstant,2): 2 or 4


def cval(b, et):
    if et == 0x08: return struct.unpack_from('<i', b, 0)[0]
    if et == 0x09: return struct.unpack_from('<I', b, 0)[0]
    if et == 0x06: return struct.unpack_from('<h', b, 0)[0]
    if et == 0x07: return struct.unpack_from('<H', b, 0)[0]
    if et == 0x04: return struct.unpack_from('<b', b, 0)[0]
    if et == 0x05: return struct.unpack_from('<B', b, 0)[0]
    if et == 0x0A: return struct.unpack_from('<q', b, 0)[0]
    if et == 0x0B: return struct.unpack_from('<Q', b, 0)[0]
    return None


# 建 field_rid -> value
fv = {}
for i in range(rc):
    ro = ob + i * sz
    et = A.d[ro]
    pv = struct.unpack_from('<I', A.d, ro + 2)[0] if hasconst_bits == 4 else struct.unpack_from('<H', A.d, ro + 2)[0]
    tag = pv & 3
    rid = pv >> 2
    if tag != 0:      # 0=Field, 1=Param, 2=Property
        continue
    bidx = struct.unpack_from('<I', A.d, ro + 2 + hasconst_bits)[0] if A.bsize_idx == 4 else struct.unpack_from('<H', A.d, ro + 2 + hasconst_bits)[0]
    try:
        v = cval(A.blob(bidx), et)
    except Exception:
        v = None
    fv[rid] = v

for kw in sys.argv[1:]:
    for t in A.typedefs:
        if kw not in t['full']:
            continue
        print(f"--- {t['full']} (TD{t['rid']}) ---")
        for fr in t['fields']:
            f = A.fields[fr - 1]
            print(f"    {f['name']:20s} = {fv.get(fr)}")
