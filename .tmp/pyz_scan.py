# -*- coding: utf-8 -*-
"""Extract zlib-compressed PYZ entries from a PyInstaller onedir exe and search for strings.

Works without pyinstxtractor: PyInstaller's CArchive/PYZ entries are zlib streams.
We brute-force scan for zlib streams in the exe, decompress, and search the raw
marshalled-code bytes for ASCII markers (strings survive marshal as UTF-8).
"""
import sys, zlib, re, io

exe = sys.argv[1]
targets = [t.encode() for t in sys.argv[2:]] or [b'autoenter', b'xlsm']
data = open(exe, 'rb').read()
out = io.open(r'C:\Users\23922\Documents\ds_harness\ak\.tmp\pyz_scan.txt', 'w', encoding='utf-8')

hits = {t: [] for t in targets}
n_streams = 0
n_ok = 0
pos = 0
size = len(data)
while True:
    i = data.find(b'\x78', pos)
    if i < 0 or i > size - 2:
        break
    pos = i + 1
    if data[i + 1] not in (0x01, 0x5E, 0x9C, 0xDA):
        continue
    n_streams += 1
    try:
        d = zlib.decompressobj()
        blob = d.decompress(data[i:i + 40 * 1024 * 1024])
        blob += d.flush()
    except Exception:
        continue
    if len(blob) < 200:
        continue
    n_ok += 1
    for t in targets:
        if t in blob:
            hits[t].append((i, len(blob)))

print('scanned exe size', size, file=out)
print('candidate zlib streams:', n_streams, 'successfully inflated:', n_ok, file=out)
for t in targets:
    print(f'{t!r}: {len(hits[t])} stream hits; first offsets {hits[t][:8]}', file=out)

# Also show human-readable context for the biggest hits of the first target
t = targets[0]
for off, ln in hits[t][:3]:
    try:
        d = zlib.decompressobj()
        blob = d.decompress(data[off:off + 8 * 1024 * 1024]) + d.flush()
    except Exception:
        continue
    for m in list(re.finditer(re.escape(t), blob))[:5]:
        s = max(0, m.start() - 120)
        print('--- ctx in stream@%d (inflated %d) ---' % (off, ln), file=out)
        print(repr(blob[s:m.start() + 160]), file=out)
out.close()
print('done -> pyz_scan.txt')
