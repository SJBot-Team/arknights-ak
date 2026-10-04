# -*- coding: utf-8 -*-
"""Raw XML inspection of the plan sheet: show cells with formulas (incl. shared)."""
import zipfile, re, io, sys

z = zipfile.ZipFile(sys.argv[1])
out = io.open(sys.argv[3], 'w', encoding='utf-8') if len(sys.argv) > 3 else sys.stdout
name = sys.argv[2]
x = z.read(name).decode('utf-8')

rows = re.findall(r'<row[^>]*r="(\d+)"[^>]*>(.*?)</row>', x, re.S)
for r, body in rows:
    print('--- ROW', r, '---', file=out)
    for c in re.findall(r'<c .*?(?:/>|</c>)', body, re.S):
        print('   ', c, file=out)
