# -*- coding: utf-8 -*-
"""AFA.exe PE reconnaissance - read-only."""
import os, sys, re, json, struct, collections, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from strings_lib import strings_from_bytes, grep
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

P = r'D:\__soft\ak\AFA.exe'
data = open(P, 'rb').read()
print('size', len(data), 'md5', hashlib.md5(data).hexdigest(), 'sha256', hashlib.sha256(data).hexdigest()[:32])

def hr(t): print('\n' + '='*20 + ' ' + t + ' ' + '='*20)

hr('PE headers')
e_lfanew = struct.unpack_from('<I', data, 0x3c)[0]
print('e_lfanew', hex(e_lfanew), 'sig', data[e_lfanew:e_lfanew+4])
coff = e_lfanew + 4
machine, nsec, tds, _, _, optsz, chars = struct.unpack_from('<HHIIIHH', data, coff)
print('machine', hex(machine), 'nSections', nsec, 'TimeDateStamp', tds, 'optHdrSize', optsz, 'characteristics', hex(chars))
opt = coff + 20
magic = struct.unpack_from('<H', data, opt)[0]
print('opt magic', hex(magic), '(0x10b=PE32, 0x20b=PE32+)')
entry = struct.unpack_from('<I', data, opt + 16)[0]
if magic == 0x10b:
    imagebase = struct.unpack_from('<I', data, opt + 28)[0]
    numdd = struct.unpack_from('<I', data, opt + 92)[0]
    dd_off = opt + 96
else:
    imagebase = struct.unpack_from('<Q', data, opt + 24)[0]
    numdd = struct.unpack_from('<I', data, opt + 108)[0]
    dd_off = opt + 112
subsystem = struct.unpack_from('<H', data, opt + (68 if magic == 0x20b else 68))[0]
print('entrypoint RVA', hex(entry), 'imagebase', hex(imagebase), 'subsystem', subsystem)
print('numDataDir', numdd)
import datetime
print('TimeDateStamp =', tds, datetime.datetime.utcfromtimestamp(tds).isoformat() + 'Z')

names = ['Export','Import','Resource','Exception','Certificate','Reloc','Debug','Arch','GlobalPtr','TLS','LoadConfig','BoundImport','IAT','DelayImport','CLRHeader','Reserved']
print('--- data directories ---')
for i in range(min(numdd, 16)):
    rva, size = struct.unpack_from('<II', data, dd_off + i*8)
    print('  [%2d] %-12s rva=%#010x size=%d %s' % (i, names[i], rva, size, '  <== CLR RUNTIME HEADER (nonzero = .NET)' if i == 14 and (rva or size) else ''))

hr('Sections')
sec_off = opt + optsz
secs = []
for i in range(nsec):
    o = sec_off + i*40
    nm = data[o:o+8].rstrip(b'\x00').decode('ascii','replace')
    vsize, vaddr, rsize, raddr = struct.unpack_from('<IIII', data, o+8)
    ch = struct.unpack_from('<I', data, o+36)[0]
    secs.append((nm, vaddr, vsize, raddr, rsize, ch))
    print('  %-9s VA=%#010x VSize=%-9d Raw=%#010x RawSize=%-9d (%.1f%%) ch=%#x' % (nm, vaddr, vsize, raddr, rsize, 100.0*rsize/max(vsize,1), ch))

hr('Overlay / trailing data check')
last_end = max(r + s for _, _, _, r, s, _ in secs)
print('last section raw end', hex(last_end), 'file size', hex(len(data)), 'trailing bytes', len(data) - last_end)
if len(data) > last_end:
    print('trailing head hex:', data[last_end:last_end+64].hex())
    print('trailing repr:', repr(data[last_end:last_end+200]))

hr('Framework marker strings (raw byte search)')
marks = [b'mscoree.dll', b'BSJB', b'#~', b'_CorExeMain', b'.NETCore', b'netstandard', b'System.Private.CoreLib',
         b'PYZ-00.pyz', b'pyi-', b'_MEIPASS', b'python3', b'PYTHONHOME', b'PyInstaller', b'pyinstaller',
         b'Go build ID', b'go1.', b'GOROOT', b'golang', b'rustc', b'cargo', b'.pdb', b'MSVC', b'MSVCRT',
         b'libcef', b'CEF', b'Electron', b'node.dll', b'v8_context', b'Qt5', b'Qt6', b'libgcc', b'MinGW',
         b'nuitka', b'cx_Freeze', b'UPX', b'MZ\x90\x00', b'This program cannot be run in DOS mode',
         b'Assembly-CSharp', b'UnityPlayer', b'duktape', b'QuickJS', b'luajit']
for m in marks:
    c = data.count(m)
    if c:
        idx = [i for i in range(len(data)) if data.startswith(m, i)][:4]
        print('  %-32s count=%-4d first_off=%s' % (m, c, [hex(i) for i in idx]))

hr('Rich header / linker hints')
ri = data.find(b'Rich')
print('Rich at', hex(ri) if ri > 0 else 'none')
pdb = re.findall(rb'[\x20-\x7e]{4,}\.pdb', data)
print('pdb strings:', [p.decode() for p in set(pdb)][:10])
# .NET metadata stream names
for m in (b'#~', b'#Strings', b'#US', b'#GUID', b'#Blob', b'#-'):
    print('  meta %-10s count=%d' % (m.decode(), data.count(m)))

hr('Strings: keyword hits (Arknights / asset pipeline)')
strs = strings_from_bytes(data, 4)
print('total extracted strings', len(strs))
kw = ['arknights','arknight','torappu','hypergryph','assetbundle','\\.ab\\b','skel','atlas','spine','flatbuffer',
      'flatbuf','lua','prts','gamedata','excel','\\.xlsx','\\.bundle','unity','assets','resversion','network_config',
      'aes','xxtea','decrypt','unpack','extract','combine','merge','skil','talent','buff','operators?','\\bchar_',
      'sprit','texture','png','webp','astc','etc2','dds','mtl','\\.json','\\.csv','\\.txt','\\.dat','\\.bin']
hits = grep(strs, kw, maxhits=500)
print('hits', len(hits))
for h in hits: print('   ', h)

hr('Strings: URLs / paths / file names')
u = grep(strs, [r'https?://', r'\\\\', r'[A-Za-z]:\\', r'\.exe\b', r'\.dll\b', r'\.py\b'], maxhits=200)
for h in u: print('   ', h)

hr('Strings: sample of longest strings (informational)')
uniq = sorted(set(s for s in strs if len(s) >= 6), key=len, reverse=True)
for s in uniq[:80]: print('   ', s[:220])
