# -*- coding: utf-8 -*-
import struct, sys, os

p = sys.argv[1]
d = open(p, 'rb').read()
print("file size", len(d))
e_lfanew = struct.unpack_from('<I', d, 0x3C)[0]
print("e_lfanew", hex(e_lfanew), d[e_lfanew:e_lfanew+4])
coff = e_lfanew + 4
machine, nsec, tds, _, _, optsize, chars = struct.unpack_from('<HHIIIHH', d, coff)
print("machine", hex(machine), "nsec", nsec, "optsize", optsize)
opt = coff + 20
magic = struct.unpack_from('<H', d, opt)[0]
print("magic", hex(magic))
ddoff = opt + (112 if magic == 0x20b else 96)
nrva = struct.unpack_from('<I', d, opt + (108 if magic == 0x20b else 92))[0]
print("NumberOfRvaAndSizes", nrva)
exp_rva, exp_size = struct.unpack_from('<II', d, ddoff + 0)
print("export dir rva", hex(exp_rva), "size", exp_size)
secs = []
so = opt + optsize
for i in range(nsec):
    name, vsize, vaddr, rsize, raddr = struct.unpack_from('<8sIIII', d, so + i*40)
    secs.append((vaddr, vsize, raddr, rsize, name.rstrip(b'\0').decode('ascii','replace')))
    print("sec %-10s vaddr=0x%08X vsize=0x%08X raddr=0x%08X rsize=0x%08X end=0x%08X" % (name.rstrip(b'\0').decode('ascii','replace'), vaddr, vsize, raddr, rsize, raddr+rsize))

def rva2off(rva):
    for vaddr, vsize, raddr, rsize, nm in secs:
        if vaddr <= rva < vaddr + vsize:
            off = raddr + (rva - vaddr)
            return (off, nm, off < raddr + rsize)
    return (None, None, False)

o, nm, ok = rva2off(exp_rva)
print("export dir offset", hex(o) if o else None, "sec", nm, "inRaw", ok)
fields = struct.unpack_from('<IIIIIIIIIII', d, o)
labels = ['Characteristics','TimeDateStamp','MajorVersion','MinorVersion','Name','Base','NumberOfFunctions','NumberOfNames','AddressOfFunctions','AddressOfNames','AddressOfNameOrdinals']
for l, v in zip(labels, fields):
    print("  %-24s %s" % (l, hex(v)))

nfunc, nname = fields[6], fields[7]
for lbl, rv in (('AddressOfFunctions', fields[8]), ('AddressOfNames', fields[9]), ('AddressOfNameOrdinals', fields[10])):
    oo, sn, okk = rva2off(rv)
    print("%s -> off=%s sec=%s inRaw=%s" % (lbl, hex(oo) if oo else None, sn, okk))
