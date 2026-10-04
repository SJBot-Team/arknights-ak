# brute_parse_buff_holder.py — 暴力搜索 buff_template_holder 条目格式
import json
import struct

BIN = r"E:\__file\ak_kb\downloads\buff_template_holder.mono.raw.bin"
raw = open(BIN, "rb").read()
DATA = 0x34  # count 位置

count = struct.unpack_from("<I", raw, DATA)[0]


def try_parse(keylen_fmt, head_size, len_fmt):
    """keylen_fmt: '<I' 小端 / '>I' 大端 / '1B' 单字节+3填充
       head_size: 键后的固定头部字节数
       len_fmt: JSON 长度字段 '<I' / '>I'"""
    pos = DATA + 4
    parsed = []
    while pos + 8 <= len(raw) and len(parsed) < count:
        if keylen_fmt == "1B":
            kl = raw[pos]
            key = raw[pos + 4: pos + 4 + kl]
            pos += 4 + kl
        else:
            kl = struct.unpack_from(keylen_fmt, raw, pos)[0]
            key = raw[pos + 4: pos + 4 + kl]
            pos += 4 + kl
        if kl <= 0 or kl > 512:
            return parsed, pos, "keylen"
        try:
            k = key.decode("utf-8")
        except Exception:
            return parsed, pos, "key"
        pos += head_size
        jl = struct.unpack_from(len_fmt, raw, pos)[0]
        pos += 4
        if jl <= 0 or jl > 5_000_000 or pos + jl > len(raw):
            return parsed, pos, "jsonlen"
        try:
            json.loads(raw[pos:pos + jl].decode("utf-8"))
        except Exception:
            return parsed, pos, "json"
        parsed.append(k)
        pos += jl
    return parsed, pos, "end"


results = []
for kf in ("<I", ">I", "1B"):
    for hs in range(0, 40):
        for lf in ("<I", ">I"):
            parsed, pos, why = try_parse(kf, hs, lf)
            results.append((len(parsed), kf, hs, lf, why, pos))
results.sort(reverse=True)
print("=== Top 8 配置 ===")
for r in results[:8]:
    print(f"  条目数={r[0]} 键长格式={r[1]} 头大小={r[2]} 长度格式={r[3]} 停因={r[4]} 位置=0x{r[5]:X}")
