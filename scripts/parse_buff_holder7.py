"""
parse_buff_holder7.py — 最终解析器 v3（段间跳跃 + 事件数限定）
结构：条目 = [键长<I][键][头部][(JSON长<I][JSON]) × N]，N = gamedata 事件数
      段间可能有跳跃字节（如 [int32 0][int32 1]）；条目间 = [int32 0]+填充+键长
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
    return len(v.get("eventToActions") or {}) or 1 if isinstance(v, dict) else 1


def next_key(p):
    for lead in range(0, 13):
        kl = struct.unpack_from("<I", raw, p + lead)[0]
        if not (1 <= kl <= 512) or p + lead + 4 + kl > len(raw):
            continue
        try:
            key = raw[p + lead + 4: p + lead + 4 + kl].decode("ascii")
        except Exception:
            continue
        if key in gd:
            return kl, key, p + lead
    return None


def read_seg(q):
    """从 q 起枚举跳跃 0-8B 读 [长<I][JSON] 段"""
    for skip in range(0, 9):
        jl = struct.unpack_from("<I", raw, q + skip)[0]
        if not (10 <= jl <= 5_000_000) or q + skip + 4 + jl > len(raw):
            continue
        try:
            obj = json.loads(raw[q + skip + 4: q + skip + 4 + jl].decode("utf-8"))
            return obj, q + skip + 4 + jl
        except Exception:
            continue
    return None


entries = {}
ok = 0
fail = 0
pos = 0x38
while pos + 8 <= len(raw) and ok < count:
    rk = next_key(pos)
    if rk is None:
        fail += 1
        break
    kl, key, kpos = rk
    N = ev_count(key)
    body = kpos + 4 + kl
    solved = None
    for off in range(8, 48):
        segs = []
        q = body + off
        good = True
        for _ in range(N):
            rs = read_seg(q)
            if rs is None:
                good = False
                break
            seg, q = rs
            segs.append(seg)
        if good:
            solved = (segs, q)
            break
    if solved is None:
        fail += 1
        break
    entries[key] = solved[0]
    pos = solved[1]
    ok += 1

print(f"count={count} 解析成功={ok} 失败={fail} 剩余={len(raw)-pos}")
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(entries, f, ensure_ascii=False, indent=0)

if "chiave_t_1" in entries:
    g = gd["chiave_t_1"]["eventToActions"]
    b = entries["chiave_t_1"]
    same = len(b) == len(g) and all(
        json.dumps(seg, ensure_ascii=False) == json.dumps(v, ensure_ascii=False)
        for seg, (e, v) in zip(b, g.items()))
    print("chiave_t_1 内容完全一致:", same)
