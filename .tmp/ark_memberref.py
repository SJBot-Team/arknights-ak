# -*- coding: utf-8 -*-
"""MemberRef/TypeRef mining for Assembly-CSharp + AFA resource internals."""
import os, sys, re, struct, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import dotnet_md

M = r'E:\__file\ak\ArknightR\ArknightR_Data\Managed'
def hr(t): print('\n' + '='*24 + ' ' + t + ' ' + '='*24)

# --- extend dotnet_md to expose raw table walking for TypeRef/MemberRef ---
def tables(path):
    md, d = dotnet_md.parse(path, want_methods=True)
    # rebuild internals
    e = struct.unpack_from('<I', d, 0x3c)[0]; coff = e + 4
    nsec = struct.unpack_from('<H', d, coff + 2)[0]; optsz = struct.unpack_from('<H', d, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from('<H', d, opt)[0]
    dd = opt + (96 if magic == 0x10b else 112)
    secs = []
    so = opt + optsz
    for i in range(nsec):
        o = so + i*40
        nm = d[o:o+8].rstrip(b'\x00').decode('ascii','replace')
        vs, va, rs, ra = struct.unpack_from('<IIII', d, o+8)
        secs.append((nm, va, vs, ra, rs))
    def r2o(rva):
        for nm, va, vs, ra, rs in secs:
            if va <= rva < va+max(vs, rs): return ra + (rva-va)
    cli, _ = struct.unpack_from('<II', d, dd + 14*8)
    o = r2o(cli)
    md_rva, md_size = struct.unpack_from('<II', d, o+8)
    mo = r2o(md_rva)
    vl = struct.unpack_from('<I', d, mo+12)[0]
    nst = struct.unpack_from('<H', d, mo+16+vl+2)[0]
    p = mo+16+vl+4
    st = {}
    for _ in range(nst):
        soff, ssz = struct.unpack_from('<II', d, p); p += 8
        nl = 0
        while d[p+nl]: nl += 1
        st[d[p:p+nl].decode()] = (mo+soff, ssz); p += nl+1; p = (p+3) & ~3
    return md, d, st, r2o, mo

md, d, st, r2o, mo = tables(os.path.join(M, 'Assembly-CSharp.dll'))
strbase = st['#Strings'][0]
def sget(i):
    e2 = d.index(b'\x00', strbase+i)
    return d[strbase+i:e2].decode('utf-8', 'replace')
blobb = st['#Blob'][0]
def bget(i):
    b0 = d[blobb+i]
    if b0 & 0x80 == 0: ln, adv = b0, 1
    elif b0 & 0xC0 == 0x80: ln, adv = ((b0 & 0x3f) << 8) | d[blobb+i+1], 2
    else: ln, adv = ((b0 & 0x1f) << 24) | (d[blobb+i+1] << 16) | (d[blobb+i+2] << 8) | d[blobb+i+3], 4
    return blobb+i+adv, ln

# recompute table offsets using dotnet_md internals by re-parsing
t = st['#~'][0]
heap = d[t+6]
si = 4 if heap & 1 else 2
gi = 4 if heap & 2 else 2
bi = 4 if heap & 4 else 2
valid, srt = struct.unpack_from('<QQ', d, t+8)
n = t+24
rc = {}
for i in range(64):
    if valid >> i & 1:
        rc[i] = struct.unpack_from('<I', d, n)[0]; n += 4
def ridx(x): return 4 if rc.get(x, 0) >= 0x10000 else 2
def coded(ts, bits):
    mx = max([rc.get(x, 0) for x in ts]+[0]); return 4 if mx >= (1 << (16-bits)) else 2
sz = {}
sz[0x00] = 2 + si + 3*gi
sz[0x01] = coded([0x00,0x1a,0x23,0x01],2) + 2*si
sz[0x02] = 4 + 2*si + coded([0x02,0x01,0x1b],2) + ridx(4) + ridx(6)
sz[0x03] = ridx(4)
sz[0x04] = 2 + si + bi
sz[0x05] = ridx(6)
sz[0x06] = 8 + si + bi + ridx(8)
sz[0x07] = ridx(8)
sz[0x08] = 4 + si
sz[0x09] = ridx(2) + coded([0x02,0x01,0x1b],2)
sz[0x0a] = coded([0x02,0x01,0x1a,0x06,0x1b],3) + si + bi
sz[0x0b] = 2 + coded([0x04,0x08,0x17],2) + bi
sz[0x0c] = coded([0x06,0x04,0x01,0x02,0x08,0x09,0x0a,0x00,0x0e,0x17,0x14,0x11,0x1a,0x1b,0x20,0x23,0x26,0x27,0x28,0x2a,0x2c],5) + coded([0x06,0x0a],3) + bi
sz[0x0d] = coded([0x04,0x08],1) + bi
sz[0x0e] = 2 + coded([0x02,0x06,0x20],2) + bi
sz[0x0f] = 2 + 4 + ridx(2)
sz[0x10] = 4 + ridx(4)
sz[0x11] = bi
sz[0x12] = ridx(2) + ridx(0x14)
sz[0x13] = ridx(0x14)
sz[0x14] = 2 + si + coded([0x02,0x01,0x1b],2)
sz[0x15] = ridx(2) + ridx(0x17)
sz[0x16] = ridx(0x17)
sz[0x17] = 2 + si + bi
sz[0x18] = 2 + ridx(6) + coded([0x14,0x17],1)
sz[0x19] = ridx(2) + coded([0x06,0x0a],1)*2
sz[0x1a] = si
sz[0x1b] = bi
sz[0x1c] = 2 + coded([0x04,0x06],1) + si + ridx(0x1a)
sz[0x1d] = 4 + ridx(4)
sz[0x20] = 16 + bi + 2*si
sz[0x21] = 4
sz[0x22] = 12
sz[0x23] = 12 + 2*bi + 2*si
sz[0x24] = 4 + ridx(0x23)
sz[0x25] = 12 + ridx(0x23)
sz[0x26] = 4 + si + bi
sz[0x27] = 8 + 2*si + coded([0x26,0x27,0x23],2)
sz[0x28] = 8 + si + coded([0x26,0x27],1)
sz[0x29] = 2*ridx(2)
sz[0x2a] = 4 + coded([0x02,0x06],1) + si
sz[0x2b] = coded([0x06,0x0a],1) + bi
sz[0x2c] = ridx(0x2a) + coded([0x02,0x01,0x1b],2)
off = {}
cur = n
for i in sorted(rc):
    off[i] = cur; cur += sz.get(i, 0)*rc[i]

hr('Assembly-CSharp: Assembly name + version')
o20 = off[0x20]
ver = struct.unpack_from('<HHHH', d, o20)[0:4]
print('assembly version', ver)
print('assembly name', sget(struct.unpack_from('<I', d, o20+16+bi)[0] if si == 4 else struct.unpack_from('<H', d, o20+16+bi)[0]))

hr('TypeRef namespaces (external dependencies)')
tr = collections.Counter()
if 0x01 in rc:
    o1 = off[0x01]
    for i in range(rc[0x01]):
        ro = o1 + i*sz[0x01]
        rs = struct.unpack_from('<I', d, ro)[0] if coded([0x00,0x1a,0x23,0x01],2) == 4 else struct.unpack_from('<H', d, ro)[0]
        no = ro + coded([0x00,0x1a,0x23,0x01],2)
        ni = struct.unpack_from('<I', d, no)[0] if si == 4 else struct.unpack_from('<H', d, no)[0]
        nso = struct.unpack_from('<I', d, no+si)[0] if si == 4 else struct.unpack_from('<H', d, no+si)[0]
        tr[sget(nso)] += 1
print(tr.most_common(50))

hr('MemberRef names (external API calls) - grouped')
mr = collections.Counter()
if 0x0a in rc:
    oa = off[0x0a]
    for i in range(rc[0x0a]):
        ro = oa + i*sz[0x0a]
        ni = struct.unpack_from('<I', d, ro+coded([0x02,0x01,0x1a,0x06,0x1b],3))[0] if si == 4 else struct.unpack_from('<H', d, ro+coded([0x02,0x01,0x1a,0x06,0x1b],3))[0]
        mr[sget(ni)] += 1
kw = ('Type', 'GetType', 'CreateInstance', 'Activator', 'Load', 'LoadAsset', 'Instantiate', 'Addressables',
      'Json', 'Convert', 'Serialize', 'Deserialize', 'Read', 'Write', 'Excel', 'SharpZip', 'Zip', 'Ionic',
      'Download', 'WebRequest', 'UnityWebRequest', 'GetString', 'CreateDirectory', 'GetFiles', 'Directory',
      'File', 'Path', 'Reflect', 'Field', 'Property', 'Method', 'Enum', 'Parse', 'Invoke')
sel = [(k, v) for k, v in mr.most_common() if any(x.lower() in k.lower() for x in kw)]
print('total MemberRefs', sum(mr.values()), 'unique', len(mr))
for k, v in sel[:160]:
    print('   %-45s %d' % (k, v))
print('--- reflection-specific ---')
for k, v in mr.items():
    if re.search(r'(GetType|CreateInstance|Activator|GetField|GetProperty|GetMethod|Invoke|Assembly|Reflect)', k):
        print('   %-45s %d' % (k, v))

hr('AFA.exe: RCDATA /10/1 header + AHK script storage')
P = r'D:\__soft\ak\AFA.exe'
a = open(P, 'rb').read()
# rdata area for /10/1 rva=0x1ad138 -> file offset
# .rsrc VA=0x135000 Raw=0x12e600
fo = 0x12e600 + (0x1ad138 - 0x135000)
print('offset', hex(fo), 'head64', a[fo:fo+64].hex())
print('head repr', repr(a[fo:fo+120]))
for sig in (b'configDir := A_AppData', b'class FileExtractor', b'AutoHotkey', b'LZNT', b'\x1f\xb8'):
    idx = a.find(sig)
    print('%-28s -> %s' % (sig[:24], hex(idx) if idx > 0 else 'none'))
i = a.find(b'class FileExtractor')
print('FileExtractor offset %#x ; rel to /10/1 start = %d' % (i, i - fo))
print('context:', repr(a[i-260:i+120]))
# version resource
vo = 0x12e600 + (0x1d20e0 - 0x135000)
print('--- RT_VERSION raw ---')
print(a[vo:vo+320].hex())
print(repr(a[vo:vo+320]))
# RGBA png check inside rsrc
for m in (b'\x89PNG\r\n\x1a\n',):
    poss = []
    s = 0
    while True:
        j = a.find(m, s)
        if j < 0: break
        poss.append(j); s = j+1
    print('PNG magic at', [hex(x) for x in poss[:10]])
