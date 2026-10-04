"""
parse_buff_holder4.py — 终极解析（gamedata 事件数驱动）
条目 = [键长<I][键][头部: 事件数+其他][(JSON长<I][JSON]) × 事件数]
事件数 = gamedata 对应模板的 eventToActions 数量（权威）
输出全部条目 → E:\__file\ak_kb\downloads\buff_holder_full.json
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


def event_count(key):
    v = gd.get(key)
    if isinstance(v, dict):
        return len(v.get("eventToActions") or {}) or 1
    return 1


def try_entry(p, key):
    """从键后 p 解析 N 个 JSON 段，返回 (json_list, next_pos)"""
    N = event_count(key)
    body = p
    for off in range(8, 40):
        segs = []
        q = body + off
        ok = True
        for _ in range(N):
            jl = struct.unpack_from("<I", raw, q)[0]
            if not (10 <= jl <= 5_000_000) or q + 4 + jl > len(raw):
                ok = False
                break
            try:
                obj = json.loads(raw[q + 4: q + 4 + jl].decode("utf-8"))
            except Exception:
                ok = False
                break
            segs.append(obj)
            q += 4 + jl
        if ok:
            return segs, q
    return None, None


entries = {}
ok = 0
fail = 0
detail = []
while pos + 8 <= len(raw) and ok < count:
    kl = struct.unpack_from("<I", raw, pos)[0]
    if not (1 <= kl <= 512):
        fail += 1
        break
    kb = raw[pos + 4: pos + 4 + kl]
    if not all(32 <= b < 127 for b in kb):
        fail += 1
        break
    key = kb.decode("utf-8", "replace")
    body = pos + 4 + kl
    segs, nxt = try_entry(body, key)
    if segs is None:
        fail += 1
        detail.append(f"FAIL at 0x{pos:X} key={key}")
        break
    entries[key] = segs
    ok += 1
    pos = nxt

print(f"count={count} 解析成功={ok} 失败={fail} 剩余={len(raw)-pos}")
print("失败详情:", detail[:3])
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(entries, f, ensure_ascii=False, indent=0)

common = set(entries) & set(gd)
print(f"共有键={len(common)}")
if "chiave_t_1" in entries:
    g = gd["chiave_t_1"]["eventToActions"]
    print("chiave_t_1 事件:", list(g.keys()))
    print("  gamedata:", json.dumps(g, ensure_ascii=False)[:200])
    print("  二进制  :", json.dumps(entries["chiave_t_1"], ensure_ascii=False)[:200])
    # 逐事件比对
    b = entries["chiave_t_1"]
    if len(b) == len(g):
        same = all(json.dumps(b[i], ensure_ascii=False) == json.dumps(v, ensure_ascii=False) for i, (e, v) in enumerate(g.items()))
        print("  二进制与 gamedata 事件内容完全一致:", same)
