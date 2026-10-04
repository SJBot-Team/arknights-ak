# -*- coding: utf-8 -*-
"""Parse PE export table of a DLL without external deps."""
import struct, sys, os

def pe_exports(path):
    d = open(path, 'rb').read()
    e_lfanew = struct.unpack_from('<I', d, 0x3C)[0]
    assert d[e_lfanew:e_lfanew+4] == b'PE\0\0', "not PE"
    coff = e_lfanew + 4
    machine, nsec, _, _, _, optsize, _ = struct.unpack_from('<HHIIIHH', d, coff)
    opt = coff + 20
    magic = struct.unpack_from('<H', d, opt)[0]
    is64 = magic == 0x20b
    # data directory
    ddoff = opt + (112 if is64 else 96)
    nrva = struct.unpack_from('<I', d, opt + (108 if is64 else 92))[0]
    exp_rva, exp_size = struct.unpack_from('<II', d, ddoff + 0)
    secs = []
    so = opt + optsize
    for i in range(nsec):
        name, vsize, vaddr, rsize, raddr = struct.unpack_from('<8sIIII', d, so + i*40)
        secs.append((vaddr, vsize, raddr, rsize, name.rstrip(b'\0').decode()))
    def rva2off(rva):
        for vaddr, vsize, raddr, rsize, nm in secs:
            if vaddr <= rva < vaddr + max(vsize, rsize):
                return raddr + (rva - vaddr)
        return None
    eo = rva2off(exp_rva)
    (_, _, _, _, _, _, nfunc, nname, addr_func, addr_name, addr_ord) = struct.unpack_from('<IIIIIIIIIII', d, eo)
    offfunc, offname, offord = rva2off(addr_func), rva2off(addr_name), rva2off(addr_ord)
    out = []
    for i in range(nname):
        noff = rva2off(struct.unpack_from('<I', d, offname + i*4)[0])
        end = d.index(b'\0', noff)
        nm = d[noff:end].decode('ascii', 'replace')
        ordv = struct.unpack_from('<H', d, offord + i*2)[0]
        frva = struct.unpack_from('<I', d, offfunc + ordv*4)[0]
        out.append((nm, frva, ordv))
    return out, is64, machine, nfunc

for p in sys.argv[1:]:
    print("=" * 70)
    print("DLL:", p, "size=", os.path.getsize(p))
    try:
        exps, is64, machine, nfunc = pe_exports(p)
        print("machine=0x%04x (%s) 64bit=%s  number_of_functions=%d  named_exports=%d" % (
            machine, {0x8664:'x86-64', 0x14c:'i386', 0xaa64:'arm64'}.get(machine,'?'), is64, nfunc, len(exps)))
        print("--- exports (forwarded/ordinal as applicable) ---")
        for nm, rva, ordv in sorted(exps, key=lambda x: x[2]):
            print("%-5d 0x%08X  %s" % (ordv, rva, nm))
    except Exception as e:
        print("ERR", e)
