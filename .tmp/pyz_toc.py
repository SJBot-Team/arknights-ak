# -*- coding: utf-8 -*-
"""Locate the PYZ blob directly (uncompressed in the exe), parse its TOC and dump src.* modules."""
import sys, os, zlib, marshal, io

exe = sys.argv[1]
outdir = sys.argv[2] if len(sys.argv) > 2 else r'C:\Users\23922\Documents\ds_harness\ak\.tmp\pyz'
os.makedirs(outdir, exist_ok=True)
data = open(exe, 'rb').read()

start = data.find(b'PYZ\x00')
print('PYZ header at raw offset', start)
pyz = data[start:]
print('pyz magic', pyz[4:8])
import struct
toc_pos = struct.unpack('!i', pyz[8:12])[0]
print('toc_pos', toc_pos, 'total pyz len', len(pyz))
seg = pyz[toc_pos:]
toc = marshal.loads(seg[:400000])
if isinstance(toc, list):
    toc = dict(toc)
print('toc type ok, entries', len(toc))

def probe(base):
    ty, pos, ln = toc['PIL.BmpImagePlugin']
    try:
        zlib.decompress(pyz[base + pos: base + pos + ln])
        return True
    except Exception:
        return False

for base in (0, 12, 16, 17, toc_pos):
    print('base guess', base, 'ok' if probe(base) else 'no')

print('module count', len(toc))
with io.open(os.path.join(outdir, 'module_list.txt'), 'w', encoding='utf-8') as f:
    for n in sorted(toc):
        f.write(f"{n}\n")
srclist = [n for n in sorted(toc) if n.startswith('src')]
print('src modules:')
for n in srclist:
    print('   ', n, toc[n])

for n in srclist:
    ent = toc[n]
    ty, pos, ln = ent[0], ent[1], ent[2]
    blob = pyz[pos:pos + ln]
    try:
        blob = zlib.decompress(blob)
    except Exception:
        pass
    open(os.path.join(outdir, n.replace('.', '_') + '.pyc'), 'wb').write(blob)
print('dumped to', outdir)
