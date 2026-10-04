# -*- coding: utf-8 -*-
"""Minimal PyInstaller onedir extractor: list PYZ module names, dump chosen module strings.

Usage: python pyz_extract.py <exe> [outdir]
"""
import sys, os, zlib, marshal, io, re

exe = sys.argv[1]
outdir = sys.argv[2] if len(sys.argv) > 2 else r'C:\Users\23922\Documents\ds_harness\ak\.tmp\pyz'
os.makedirs(outdir, exist_ok=True)
data = open(exe, 'rb').read()

MAGIC = b'MEI\x0c\x0b\x0a\x0b\x0e'
cookie_pos = data.rfind(MAGIC)
print('cookie at', cookie_pos)
import struct
(magic, pkg_len, toc_off, toc_len, pyvers) = struct.unpack('!8siiii', data[cookie_pos:cookie_pos + 24])
print('pkg_len', pkg_len, 'toc_off', toc_off, 'toc_len', toc_len, 'pyvers', pyvers)
pylib = data[cookie_pos + 24:cookie_pos + 24 + 64].split(b'\0')[0]
print('pylib', pylib)

base = cookie_pos - pkg_len
entries = []
for i in range(toc_len // 18):
    e = struct.unpack('!iIIIBc', data[cookie_pos + 24 + 64 + i * 18: cookie_pos + 24 + 64 + (i + 1) * 18])
    entries.append(e)
print('toc entries', len(entries), 'typecodes', sorted(set(chr(e[5]) for e in entries)))

pyz_blob = None
for (esz, epos, csize, usize, flag, tc) in entries:
    if tc == b'z':
        raw = data[base + epos: base + epos + csize]
        pyz_blob = zlib.decompress(raw) if flag else raw
        print('PYZ at', base + epos, 'size', len(pyz_blob))
print('names sample:', [e for e in entries[:12]])

if pyz_blob is None:
    sys.exit('no PYZ')

assert pyz_blob[:4] == b'PYZ\0'
magic4 = pyz_blob[4:8]
toc_pos = struct.unpack('!i', pyz_blob[8:12])[0]
print('pyz pyc magic', magic4, 'toc_pos', toc_pos)
toc_raw = pyz_blob[toc_pos:]
try:
    toc = marshal.loads(zlib.decompress(toc_raw))
except Exception:
    toc = marshal.loads(toc_raw)
    print('TOC not compressed')
print('modules', len(toc))

names = sorted(toc.keys())
with io.open(os.path.join(outdir, 'module_list.txt'), 'w', encoding='utf-8') as f:
    for n in names:
        f.write(n + '\n')
for n in names:
    if n.startswith('src'):
        print('  ', n, toc[n])

# dump inflated bytes of every src.* module so we can grep strings
for n in names:
    if not n.startswith('src'):
        continue
    ty, pos, ln = toc[n][0], toc[n][1], toc[n][2]
    blob = pyz_blob[pos:pos + ln]
    try:
        blob = zlib.decompress(blob)
    except Exception:
        pass
    fn = os.path.join(outdir, n.replace('.', '_') + '.bin')
    open(fn, 'wb').write(blob)
print('dumped src modules to', outdir)
