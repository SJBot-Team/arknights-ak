# -*- coding: utf-8 -*-
"""暴力扫描每个 VBA 模块流中所有 0x01 偏移，找出能解压出可读 VBA 源码的那个。"""
import struct
import sys
import zipfile

sys.path.insert(0, r"C:\Users\23922\Documents\ds_harness\ak\.tmp")
sys.stdout.reconfigure(encoding="utf-8")
from vba_extract import CFB                                        # noqa: E402


def decomp(data, start=0):
    out = bytearray()
    pos, n = start, len(data)
    while pos < n:
        if pos + 2 > n:
            break
        hdr = struct.unpack_from("<H", data, pos)[0]
        if (hdr & 0x7000) != 0x3000:
            if data[pos] == 0x01:
                pos += 1
                continue
            break
        pos += 2
        size = hdr & 0x0FFF
        if not (hdr & 0x8000):
            out += data[pos:pos + size]
            pos += size
            continue
        end = min(pos + size, n)
        chunk_start = len(out)          # ★ bitCount 要用"本 chunk 内已解压长度"，不是总长度
        while pos < end:
            flag = data[pos]
            pos += 1
            for i in range(8):
                if pos >= end:
                    break
                if flag & (1 << i):
                    if pos + 2 > n:
                        break
                    tok = struct.unpack_from("<H", data, pos)[0]
                    pos += 2
                    bc = 4 + ((len(out) - chunk_start) >> 12)
                    off = (tok & ((1 << bc) - 1)) + 1
                    ln = (tok >> bc) + 3
                    if off > len(out):
                        break
                    for _ in range(ln):
                        out.append(out[-off])
                else:
                    out.append(data[pos])
                    pos += 1
    return bytes(out)


XL = r"C:\Users\23922\Documents\ds_harness\ak\.tmp\prts_plan_snapshot.xlsm"
z = zipfile.ZipFile(XL)
cfb = CFB(z.read("xl/vbaProject.bin"))
streams = dict(cfb.streams())

found = {}
for name, blob in streams.items():
    if not blob or len(blob) > 60000:
        continue
    offs = [i for i in range(len(blob)) if blob[i] == 0x01]
    for off in offs:
        try:
            s = decomp(blob, off)
        except Exception:                                         # noqa: BLE001
            continue
        if len(s) < 60:
            continue
        head = s[:400].decode("cp1252", "replace")
        if ("Attribute VB_Name" in head or "Sub " in head or "Private Sub" in head
                or "End Sub" in head):
            found[name] = (off, s)
            print(f"{name:22} offset={off:<7} len={len(s):<7} head={head[:70]!r}")
            break
    else:
        print(f"{name:22} -- 未找到可解压源码（{len(offs)} 个候选偏移）")

if found:
    parts = []
    for k, (off, s) in found.items():
        parts.append("=" * 74 + f"\n=== {k}  (stream offset {off})\n" + "=" * 74 + "\n"
                     + s.decode("cp1252", "replace"))
    dst = r"C:\Users\23922\Documents\ds_harness\ak\.tmp\vba_source.txt"
    open(dst, "w", encoding="utf-8").write("\n".join(parts))
    print("\n写出", dst, sum(len(p) for p in parts), "字符")
