import sys, zipfile, struct
sys.path.insert(0, r"C:\Users\23922\Documents\ds_harness\ak\.tmp")
sys.stdout.reconfigure(encoding="utf-8")

def decomp(data, start=0):
    out = bytearray(); pos = start; n = len(data)
    while pos < n:
        if pos + 2 > n: break
        hdr = struct.unpack_from("<H", data, pos)[0]
        if (hdr & 0x7000) != 0x3000:
            if data[pos] == 0x01: pos += 1; continue
            break
        pos += 2
        size = hdr & 0x0FFF
        if not (hdr & 0x8000):
            out += data[pos:pos+size]; pos += size; continue
        end = min(pos + size, n)
        while pos < end:
            flag = data[pos]; pos += 1
            for i in range(8):
                if pos >= end: break
                if flag & (1 << i):
                    if pos + 2 > n: break
                    tok = struct.unpack_from("<H", data, pos)[0]; pos += 2
                    bc = 4 + (len(out) >> 12)
                    off = (tok & ((1 << bc) - 1)) + 1
                    ln = (tok >> bc) + 3
                    if off > len(out): break
                    for _ in range(ln): out.append(out[-off])
                else:
                    out.append(data[pos]); pos += 1
    return bytes(out)

from vba_extract import CFB
z = zipfile.ZipFile(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\prts_plan_snapshot.xlsm")
cfb = CFB(z.read("xl/vbaProject.bin"))
streams = dict(cfb.streams())
d = decomp(streams["dir"])
print("dir decompressed:", len(d))
# 找 module name + TextOffset (0x34) / various
txt = d.decode("cp1252", "replace")
import re
mods = re.findall(r"([A-Za-z_][A-Za-z0-9_ ]{0,40})\x00", txt)
print("dir 内可见名字:", [m for m in mods if len(m) > 2][:30])
# MODULE records: 读每个 MODULE 结构的 TextOffset
# 布局: MODULENAME(unicode,z) MODULENAMEANSI... 简化：直接扫 TextOffset by structure
res = {}
for name in ("ThisWorkbook","Sheet1","Sheet2","Sheet3","ControlPanel"):
    blob = streams.get(name)
    if not blob: continue
    # 逐偏移尝试解压，找到能产出可读 VBA 的偏移
    best = None
    for off in (0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 48, 56, 64, 72, 80, 96, 112, 128, 160, 192, 256, 384, 512):
        if off >= len(blob) or blob[off] != 0x01: continue
        try: s = decomp(blob, off)
        except Exception: continue
        if len(s) > 50 and (b"Sub " in s or b"Attribute VB_" in s or b"Function " in s):
            best = (off, s); break
    res[name] = best
    print(f"{name:14} -> {'off='+str(best[0])+' len='+str(len(best[1])) if best else 'NOT FOUND'}")
out=[]
for k,(off,s) in res.items():
    if s:
        out.append("="*70+f"\n=== {k} (stream offset {off})\n"+"="*70+"\n"+s.decode("cp1252","replace"))
open(r"C:\Users\23922\Documents\ds_harness\ak\.tmp\vba_source.txt","w",encoding="utf-8").write("\n".join(out))
print("written vba_source.txt", sum(len(o) for o in out))
