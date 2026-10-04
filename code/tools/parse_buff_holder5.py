"""
parse_buff_holder5.py — 最终解析器
条目 = [键长<I][键][头部(含事件数)][(JSON长<I][JSON]) × 事件数]
前导：条目间可能有 0-12 字节 0（枚举）
事件数：从 gamedata 获取（权威）
键过滤：键必须在 gamedata 字典中（消除歧义）
"""
import json
import struct

BIN = r"E:\__file\ak_kb\downloads\buff_template_holder.mono.raw.bin"
OUT = r"E:\__file\ak_kb\downloads\buff_holder_full.json"
GD = r"E:\__file\ak_kb\gamedata\buff_template_data.json"

raw = open(BIN, "rb").read()
gd = json.load(open(GD, encoding="utf-8"))
i = raw.find(b"buff_template_holder")
pos = i + len(b"buff_template_holder")
count = struct.unpack_from("<I", raw, pos)[0]
pos += 4


def ev_count(key):
    v = gd.get(key)
    if isinstance(v, dict):
        return len(v.get("eventToActions") or {}) or 1
    return 1


def try_entry(p):
    for lead in range(0, 13):
        kl = struct.unpack_from("<I", raw, p + lead)[0]
        if not (1 <= kl <= 512) or p + lead + 4 + kl > len(raw):
            continue
        kb = raw[p + lead + 4: p + lead + 4 + kl]
        try:
            key = kb.decode("ascii")
        except Exception:
            continue
        if key not in gd:
            continue
        N = ev_count(key)
        body = p + lead + 4 + kl
        for off in range(8, 48):
            segs = []
            q = body + off
            ok = True
            for _ in range(N):
                jl = struct.unpack_from("<I", raw, q)[0]
                if not (10 <= jl <= 5_000_000) or q + 4 + jl > len(raw):
                    ok = False
                    break
                try:
                    segs.append(json.loads(raw[q + 4: q + 4 + jl].decode("utf-8")))
                except Exception:
                    ok = False
                    break
                q += 4 + jl
            if ok:
                return key, segs, q, lead, off
    return None


entries = {}
ok = 0
fail = 0
stats = {}
while pos + 8 <= len(raw) and ok < count:
    r = try_entry(pos)
    if r is None:
        fail += 1
        break
    key, segs, nxt, lead, off = r
    entries[key] = segs
    stats[(lead, off)] = stats.get((lead, off), 0) + 1
    ok += 1
    pos = nxt

print(f"count={count} 解析成功={ok} 失败={fail} 剩余={len(raw)-pos}")
print("前导/头部偏移分布:", dict(sorted(stats.items())))
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(entries, f, ensure_ascii=False, indent=0)

# chiave_t_1 完整比对
if "chiave_t_1" in entries:
    g = gd["chiave_t_1"]["eventToActions"]
    b = entries["chiave_t_1"]
    print("\nchiave_t_1: 二进制段数", len(b), "gamedata 事件数", len(g))
    same = True
    for (e, v), seg in zip(g.items(), b):
        if json.dumps(seg, ensure_ascii=False) != json.dumps(v, ensure_ascii=False):
            same = False
    print("事件内容完全一致:", same)
