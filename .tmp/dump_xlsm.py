# -*- coding: utf-8 -*-
"""Dump sheet names / headers / sample rows from an xlsm without Excel."""
import sys, zipfile, re, io, xml.etree.ElementTree as ET

path = sys.argv[1]
out = io.open(sys.argv[2], 'w', encoding='utf-8') if len(sys.argv) > 2 else sys.stdout
def print(*a, **k):
    k['file'] = out
    return __builtins__.print(*a, **k) if not isinstance(__builtins__, dict) else __builtins__['print'](*a, **k)
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}

z = zipfile.ZipFile(path)
names = z.namelist()
print("=== ZIP ENTRIES ===")
for n in names:
    print("  ", n, z.getinfo(n).file_size)

# shared strings
shared = []
if 'xl/sharedStrings.xml' in names:
    root = ET.fromstring(z.read('xl/sharedStrings.xml'))
    for si in root.findall('m:si', NS):
        txt = ''.join(t.text or '' for t in si.iter('{%s}t' % NS['m']))
        shared.append(txt)

# workbook -> sheet name / rid order
wb = ET.fromstring(z.read('xl/workbook.xml'))
rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
relmap = {r.get('Id'): r.get('Target') for r in rels}
print("\n=== SHEETS ===")
sheets = []
for sh in wb.find('m:sheets', NS):
    nm = sh.get('name'); rid = sh.get('{%s}id' % NS['r'])
    tgt = relmap.get(rid, '')
    tgt = tgt if tgt.startswith('xl/') else 'xl/' + tgt.lstrip('/')
    sheets.append((nm, tgt, sh.get('state')))
    print(f"  name={nm!r} state={sh.get('state')} target={tgt}")

def col_of(ref):
    m = re.match(r'([A-Z]+)', ref or '')
    return m.group(1) if m else ''

for nm, tgt, state in sheets:
    if tgt not in names:
        print(f"\n### SHEET {nm}: target {tgt} missing in zip")
        continue
    root = ET.fromstring(z.read(tgt))
    rows = root.findall('.//m:sheetData/m:row', NS)
    print(f"\n=== SHEET {nm!r} ({tgt}) rows={len(rows)} state={state} ===")
    dim = root.find('m:dimension', NS)
    if dim is not None:
        print("   dimension:", dim.get('ref'))
    for ri, row in enumerate(rows[:40]):
        cells = []
        for c in row.findall('m:c', NS):
            ref = c.get('r'); t = c.get('t')
            v = c.find('m:v', NS)
            isel = c.find('m:is', NS)
            val = ''
            if t == 's' and v is not None:
                val = shared[int(v.text)]
            elif t == 'inlineStr' and isel is not None:
                val = ''.join(x.text or '' for x in isel.iter('{%s}t' % NS['m']))
            elif v is not None:
                val = v.text
            f = c.find('m:f', NS)
            if f is not None and f.text:
                val = (val or '') + f"  [fx={f.text}]"
            cells.append(f"{ref}={val!r}")
        print(f"   r{row.get('r')}: " + " | ".join(cells))
