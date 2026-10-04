# -*- coding: utf-8 -*-
import struct, sys, os

def load(path):
    d = open(path, 'rb').read()
    e = struct.unpack_from('<I', d, 0x3C)[0]
    coff = e + 4
    machine, nsec, _, _, _, optsize, _ = struct.unpack_from('<HHIIIHH', d, coff)
    opt = coff + 20
    magic = struct.unpack_from('<H', d, opt)[0]
    is64 = magic == 0x20b
    ddoff = opt + (112 if is64 else 96)
    exp_rva, exp_size = struct.unpack_from('<II', d, ddoff + 0)
    secs = []
    so = opt + optsize
    for i in range(nsec):
        nm, vsize, vaddr, rsize, raddr = struct.unpack_from('<8sIIII', d, so + i*40)
        secs.append((vaddr, vsize, raddr, rsize, nm.rstrip(b'\0').decode()))
    def rva2off(rva, strict=True):
        for vaddr, vsize, raddr, rsize, nm in secs:
            if vaddr <= rva < vaddr + (rsize if strict else vsize):
                return raddr + (rva - vaddr)
        return None
    return d, e, is64, machine, exp_rva, exp_size, rva2off, secs, opt, ddoff

def try_parse(d, eo, name):
    try:
        C, TDS, MajV, MinV, Name, Base, nfunc, nname, AOF, AON, AOO = struct.unpack_from('<11I', d, eo)
    except Exception as ex:
        return None
    if not (0 < nfunc < 2000 and 0 < nname <= nfunc):
        return None
    # validate: read name table
    try:
        # find rva2off again
        pass
    except Exception:
        return None
    return (C, TDS, MajV, MinV, Name, Base, nfunc, nname, AOF, AON, AOO)

p = sys.argv[1]
d, e, is64, machine, exp_rva, exp_size, rva2off, secs, opt, ddoff = load(p)
print("file", p, "size", len(d))
print("machine 0x%04X  is64=%s" % (machine, is64))
print("data-dir[0] export RVA=0x%08X size=%d -> file off 0x%08X" % (exp_rva, exp_size, rva2off(exp_rva) or 0))
print("raw at opt+112 (0x%X):" % (ddoff), ' '.join('%08X' % v for v in struct.unpack_from('<8I', d, ddoff)))
print("raw at opt+108:", ' '.join('%08X' % v for v in struct.unpack_from('<4I', d, opt+108)))

# brute force: search a window for a plausible IMAGE_EXPORT_DIRECTORY
best = None
start = max(0, (rva2off(exp_rva) or 0) - 64)
for cand in range(start, start + 128, 4):
    r = try_parse(d, cand, p)
    if not r: continue
    C, TDS, MajV, MinV, Name, Base, nfunc, nname, AOF, AON, AOO = r
    oaof, oaon = rva2off(AOF), rva2off(AON)
    if oaof is None or oaon is None: continue
    # first name must be printable ASCII
    try:
        firstrva = struct.unpack_from('<I', d, oaon)[0]
        fo = rva2off(firstrva)
        if fo is None: continue
        end = d.index(b'\0', fo)
        s = d[fo:end].decode('ascii')
    except Exception:
        continue
    if not s.isprintable(): continue
    print("CANDIDATE off=0x%X  nfunc=%d nname=%d Name=0x%X AOF=0x%X AON=0x%X AOO=0x%X firstname=%r" % (
        cand, nfunc, nname, Name, AOF, AON, AOO, s))
    if best is None and s.startswith('Asst'):
        best = (cand, r)
    elif best is None:
        best = (cand, r)

if best:
    cand, (C, TDS, MajV, MinV, Name, Base, nfunc, nname, AOF, AON, AOO) = best
    print("\n=== CHOSEN export dir file-offset 0x%X ===" % cand)
    print("dll name rva 0x%X -> %r" % (Name, d[rva2off(Name):d.index(b'\0', rva2off(Name))].decode('ascii','replace')))
    print("NumberOfFunctions=%d NumberOfNames=%d Base=%d" % (nfunc, nname, Base))
    oaof, oaon, oaoo = rva2off(AOF), rva2off(AON), rva2off(AOO)
    rows = []
    for i in range(nname):
        nrva = struct.unpack_from('<I', d, oaon + i*4)[0]
        no = rva2off(nrva)
        end = d.index(b'\0', no)
        nm = d[no:end].decode('ascii')
        ordv = struct.unpack_from('<H', d, oaoo + i*2)[0]
        frva = struct.unpack_from('<I', d, oaof + ordv*4)[0]
        rows.append((ordv + Base, nm, frva))
    rows.sort()
    print("--- %d named exports ---" % len(rows))
    for o, nm, frva in rows:
        print("%4d  0x%08X  %s" % (o, frva, nm))
    # also unnamed
    named_ords = set(r[0] - Base for r in rows)
    for i in range(nfunc):
        if i not in named_ords:
            frva = struct.unpack_from('<I', d, oaof + i*4)[0]
            if frva:
                print("%4d  0x%08X  <ordinal-only>" % (i + Base, frva))
