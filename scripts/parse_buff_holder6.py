"""
parse_buff_holder6.py — 最终解析器 v2
结构：条目 = [键长<I][键][头部][(JSON长<I][JSON]) × 事件数]；条目间 = [int32 0]+对齐填充+键长
策略：读段直到"下一个 gamedata 键条目可解析"（不预设事件数）
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


def next_key(p):
    """检查 p 处（枚举前导 0-12）能否解析出 gamedata 键条目，返回 (键长, 键, 键位置)"""
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
    """读一个 [长<I][JSON] 段，返回 (obj, next_q) 或 None"""
    jl = struct.unpack_from("<I", raw, q)[0]
    if not (10 <= jl <= 5_000_000) or q + 4 + jl > len(raw):
        return None
    try:
        obj = json.loads(raw[q + 4: q + 4 + jl].decode("utf-8"))
        return obj, q + 4 + jl
    except Exception:
        return None


entries = {}
ok = 0
fail = 0
pos = 0x38  # count 后第一个条目（已验证 damage_block 键长 @0x38）
while pos + 8 <= len(raw) and ok < count:
    # 读键
    rk = next_key(pos)
    if rk is None:
        fail += 1
        break
    kl, key, kpos = rk
    body = kpos + 4 + kl
    # 枚举头部 off，读段1
    segs = None
    for off in range(8, 48):
        r1 = read_seg(body + off)
        if r1 is None:
            continue
        seg1, q = r1
        # 尝试继续读段，直到下一条目可解析
        trial = [(seg1, q)]
        while True:
            if next_key(q) is not None:
                segs = [s for s, _ in trial]
                pos = q
                break
            rn = read_seg(q)
            if rn is None:
                break
            trial.append(rn)
            q = rn[1]
        if segs is not None:
            break
    if segs is None:
        fail += 1
        break
    entries[key] = segs
    ok += 1

print(f"count={count} 解析成功={ok} 失败={fail} 剩余={len(raw)-pos}")
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(entries, f, ensure_ascii=False, indent=0)

if "chiave_t_1" in entries:
    g = gd["chiave_t_1"]["eventToActions"]
    b = entries["chiave_t_1"]
    print("chiave_t_1 段数:", len(b), "gamedata 事件数:", len(g))
    same = len(b) == len(g) and all(
        json.dumps(seg, ensure_ascii=False) == json.dumps(v, ensure_ascii=False)
        for seg, (e, v) in zip(b, g.items()))
    print("chiave_t_1 内容完全一致:", same)
    for (e, v), seg in zip(g.items(), b):
        print(f"  [{e}] gamedata={json.dumps(v, ensure_ascii=False)[:120]}")
        print(f"         二进制 ={json.dumps(seg, ensure_ascii=False)[:120]}")
