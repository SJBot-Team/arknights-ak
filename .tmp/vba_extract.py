# -*- coding: utf-8 -*-
"""最小 OLE(CFB) 读取 + MS-OVBA 解压，取出 xlsm 里 vbaProject.bin 的模块源码。

无第三方依赖（本机没装 olefile/oletools）。用途：查清 xlsm「控制台」到底读写哪些单元格
—— 这决定 agent 能否用 xlsm 当"可读写的状态/控制面"。
"""
import re
import struct
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------- CFB
class CFB:
    def __init__(self, data: bytes):
        self.d = data
        assert data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "不是 OLE 文件"
        self.sect_shift = struct.unpack_from("<H", data, 0x1E)[0]
        self.mini_shift = struct.unpack_from("<H", data, 0x20)[0]
        self.sect = 1 << self.sect_shift
        self.mini = 1 << self.mini_shift
        self.n_fat = struct.unpack_from("<I", data, 0x2C)[0]
        self.dir_start = struct.unpack_from("<I", data, 0x30)[0]
        self.cutoff = struct.unpack_from("<I", data, 0x38)[0]
        self.minifat_start = struct.unpack_from("<I", data, 0x3C)[0]
        self.n_minifat = struct.unpack_from("<I", data, 0x40)[0]
        self.difat_start = struct.unpack_from("<I", data, 0x44)[0]
        self.n_difat = struct.unpack_from("<I", data, 0x48)[0]
        self._difat = list(struct.unpack_from("<109I", data, 0x4C))
        self.fat = self._read_fat()
        self.entries = self._read_dir()
        # 迷你流 = 根项的流
        root = self.entries[0]
        self.ministream = self._read_chain(root["start"], root["size"], mini=False)

    def _sect_off(self, n: int) -> int:
        return (n + 1) * self.sect

    def _read_fat(self) -> list[int]:
        secs = [s for s in self._difat[: self.n_fat] if s < 0xFFFFFFFA]
        nxt = self.difat_start
        while nxt < 0xFFFFFFFA and len(secs) < self.n_fat:
            blk = self.d[self._sect_off(nxt): self._sect_off(nxt) + self.sect]
            vals = list(struct.unpack_from("<%dI" % (self.sect // 4), blk, 0))
            secs += [s for s in vals[:-1] if s < 0xFFFFFFFA]
            nxt = vals[-1]
        fat: list[int] = []
        for s in secs:
            blk = self.d[self._sect_off(s): self._sect_off(s) + self.sect]
            fat += list(struct.unpack_from("<%dI" % (self.sect // 4), blk, 0))
        return fat

    def _read_dir(self) -> list[dict]:
        raw = self._read_chain(self.dir_start, None, mini=False)
        out = []
        for i in range(0, len(raw) - 127, 128):
            e = raw[i:i + 128]
            nlen = struct.unpack_from("<H", e, 0x40)[0]
            name = e[:max(0, nlen - 2)].decode("utf-16-le", "replace") if nlen >= 2 else ""
            typ = e[0x42]
            out.append({"name": name, "type": typ,
                        "start": struct.unpack_from("<I", e, 0x74)[0],
                        "size": struct.unpack_from("<Q", e, 0x78)[0]})
        return out

    def _read_chain(self, start: int, size, mini: bool) -> bytes:
        out = b""
        n = start
        sec = self.mini if mini else self.sect
        fat = self._mini_fat() if mini else self.fat
        base = self.ministream if mini else None
        guard = 0
        while n < 0xFFFFFFFA and guard < 200000:
            guard += 1
            if mini:
                off = n * sec
                out += base[off:off + sec]
            else:
                off = self._sect_off(n)
                out += self.d[off:off + sec]
            n = fat[n] if n < len(fat) else 0xFFFFFFFE
        return out[:size] if size else out

    def _mini_fat(self) -> list[int]:
        if not hasattr(self, "_mfat"):
            raw = self._read_chain(self.minifat_start, None, mini=False)
            self._mfat = list(struct.unpack_from("<%dI" % (len(raw) // 4), raw, 0))
        return self._mfat

    def streams(self):
        for e in self.entries:
            if e["type"] == 2 and e["size"]:
                mini = e["size"] < self.cutoff
                yield e["name"], self._read_chain(e["start"], e["size"], mini=mini)


# ---------------------------------------------------------------- MS-OVBA
def ovba_decompress(data: bytes) -> bytes:
    out = bytearray()
    pos, n = 0, len(data)
    while pos < n:
        hdr = struct.unpack_from("<H", data, pos)[0]
        if (hdr & 0x7000) != 0x3000:      # 不是合法 chunk 头
            if data[pos] == 0x01:         # 新 container 签名
                pos += 1
                continue
            break
        pos += 2
        size = hdr & 0x0FFF
        if not (hdr & 0x8000):            # 未压缩原始块
            out += data[pos:pos + size]
            pos += size
            continue
        end = pos + size
        while pos < end:
            flag = data[pos]
            pos += 1
            for i in range(8):
                if pos >= end:
                    break
                if flag & (1 << i):
                    tok = struct.unpack_from("<H", data, pos)[0]
                    pos += 2
                    bc = 4 + (len(out) >> 12)
                    off = (tok & ((1 << bc) - 1)) + 1
                    ln = (tok >> bc) + 3
                    for _ in range(ln):
                        out.append(out[-off])
                else:
                    out.append(data[pos])
                    pos += 1
    return bytes(out)


def main(xlsm: str) -> None:
    z = zipfile.ZipFile(xlsm)
    vba = z.read("xl/vbaProject.bin")
    cfb = CFB(vba)
    print(f"=== OLE 流 ===（共 {len(list(cfb.streams()))} 个）")
    names = [n for n, _ in cfb.streams()]
    print(", ".join(names))
    out = []
    for name, blob in cfb.streams():
        if not blob or blob[0] != 0x01:
            continue
        try:
            src = ovba_decompress(blob)
        except Exception as e:                                    # noqa: BLE001
            print(f"  [{name}] 解压失败 {e!r}")
            continue
        txt = src.decode("cp1252", "replace")
        if len(txt) < 20:
            continue
        out.append(f"\n{'='*72}\n=== 模块/流: {name}  ({len(src)} 字节解压后)\n{'='*72}\n{txt}")
    dst = r"C:\Users\23922\Documents\ds_harness\ak\.tmp\vba_source.txt"
    open(dst, "w", encoding="utf-8").write("\n".join(out))
    print(f"\n写出 {dst}（{sum(len(o) for o in out)} 字符）")
    # 顺手把"像单元格引用"的 token 抽出来
    cells = sorted(set(re.findall(r"\b[A-Z]{1,3}\$?\d{1,5}\b", "\n".join(out))))
    print("单元格引用候选:", cells[:120])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1
         else r"C:\Users\23922\Documents\ds_harness\ak\.tmp\prts_plan_snapshot.xlsm")
