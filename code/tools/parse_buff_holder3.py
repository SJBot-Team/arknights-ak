"""
parse_buff_holder3.py — 鲁棒解析 buff_template_holder（三重验证自动消歧）
每条目 = [前导0..N][键长<I][键][头部off][JSON长<I][JSON]
策略：枚举 前导 0-12 × 头部偏移 12-28，用 JSON 校验 + 键 ASCII 双重过滤
"""
import json
import struct

BIN = r"E:\__file\ak_kb\downloads\buff_template_holder.mono.raw.bin"
OUT = r"E:\__file\ak_kb\downloads\buff_holder_full.json"
GD = r"E:\__file\ak_kb\gamedata\buff_template_data.json"

raw = open(BIN, "rb").read()
i = raw.find(b"buff_template_holder")
pos = i + len(b"buff_template_holder")
count = struct.unpack_from("<I", raw, pos)[0]
pos += 4


def try_entry(p):
    """尝试解析 p 处的一个条目，返回 (key, json_obj, next_pos) 或 None"""
    for lead in range(0, 13):
        kl = struct.unpack_from("<I", raw, p + lead)[0]
        if not (1 <= kl <= 512):
            continue
        if p + lead + 4 + kl > len(raw):
            continue
        kb = raw[p + lead + 4: p + lead + 4 + kl]
        if not all(32 <= b < 127 for b in kb):
            continue
        key = kb.decode("utf-8", "replace")
        body = p + lead + 4 + kl
        for off in range(12, 29):
            jl = struct.unpack_from("<I", raw, body + off)[0]
            if not (50 <= jl <= 5_000_000):
                continue
            if body + off + 4 + jl > len(raw):
                continue
            try:
                obj = json.loads(raw[body + off + 4: body + off + 4 + jl].decode("utf-8"))
                return key, obj, body + off + 4 + jl
            except Exception:
                continue
    return None


entries = {}
ok = 0
fail = 0
while pos + 8 <= len(raw) and ok < count:
    r = try_entry(pos)
    if r is None:
        fail += 1
        break
    key, obj, nxt = r
    entries[key] = obj
    ok += 1
    pos = nxt

print(f"count={count} 解析成功={ok} 失败={fail} 剩余={len(raw)-pos}")
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(entries, f, ensure_ascii=False, indent=0)

gd = json.load(open(GD, encoding="utf-8"))
common = set(entries) & set(gd)
only_bin = set(entries) - set(gd)
only_gd = set(gd) - set(entries)
print(f"共有={len(common)} 仅二进制={len(only_bin)} 仅gamedata={len(only_gd)}")
if "chiave_t_1" in entries:
    print("chiave_t_1 二进制 == gamedata:", entries["chiave_t_1"] == gd.get("chiave_t_1"))
    print("二进制:", json.dumps(entries["chiave_t_1"], ensure_ascii=False)[:300])
