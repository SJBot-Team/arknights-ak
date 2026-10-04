"""
parse_buff_holder2.py — 解析 buff_template_holder MonoBehaviour 数据（v2：扫描 JSON 长度）
格式： [int32 count] 然后每条目 = [int32 键长][键][变长头部][int32 JSON 长][JSON]
      头部长度可变（16-19B），但 JSON 长度字段 = 键后扫描到的第一个"合理长度 + 合法 JSON"
输出： E:\__file\ak_kb\downloads\buff_holder_full.json + 与 gamedata 比对报告
"""
import json
import os
import struct

BIN = r"E:\__file\ak_kb\downloads\buff_template_holder.mono.raw.bin"
OUT = r"E:\__file\ak_kb\downloads\buff_holder_full.json"
GD = r"E:\__file\ak_kb\gamedata\buff_template_data.json"

raw = open(BIN, "rb").read()
i = raw.find(b"buff_template_holder")
pos = i + len(b"buff_template_holder")
count = struct.unpack_from("<I", raw, pos)[0]
pos += 4


def find_jsonlen(p):
    """从 p 扫描：4 字节 <I 值在 50..5M 且后跟合法 JSON 的开头"""
    for off in range(0, 48):
        v = struct.unpack_from("<I", raw, p + off)[0]
        if 50 <= v <= 5_000_000:
            jb = raw[p + off + 4: p + off + 4 + v]
            if len(jb) == v:
                try:
                    json.loads(jb.decode("utf-8"))
                    return off, v
                except Exception:
                    pass
    return None, None


entries = {}
ok = 0
fail = 0
head_lens = {}
while pos + 8 <= len(raw) and len(entries) < count:
    kl = struct.unpack_from("<I", raw, pos)[0]
    if kl <= 0 or kl > 512:
        fail += 1
        break
    key = raw[pos + 4: pos + 4 + kl].decode("utf-8", "replace")
    pos += 4 + kl
    off, jl = find_jsonlen(pos)
    if off is None:
        fail += 1
        break
    head_lens[off] = head_lens.get(off, 0) + 1
    pos += off + 4
    blob = raw[pos: pos + jl]
    pos += jl
    try:
        entries[key] = json.loads(blob.decode("utf-8"))
        ok += 1
    except Exception:
        entries[key] = {"_parse_error": True}
        fail += 1

print(f"count={count} 解析成功={ok} 失败={fail} 剩余={len(raw)-pos}")
print("头部偏移分布:", dict(sorted(head_lens.items())))

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(entries, f, ensure_ascii=False, indent=0)

# 与 gamedata 比对
gd = json.load(open(GD, encoding="utf-8"))
common = set(entries) & set(gd)
only_bin = set(entries) - set(gd)
only_gd = set(gd) - set(entries)
print(f"共有键: {len(common)}, 仅二进制: {len(only_bin)}, 仅 gamedata: {len(only_gd)}")
print("仅二进制样例:", list(only_bin)[:8])
print("仅 gamedata 样例:", list(only_gd)[:8])
# chiave_t_1 对比
if "chiave_t_1" in entries and "chiave_t_1" in gd:
    b = entries["chiave_t_1"]
    g = gd["chiave_t_1"]
    print("\nchiave_t_1 二进制:", json.dumps(b, ensure_ascii=False)[:200])
    print("chiave_t_1 gamedata:", json.dumps(g, ensure_ascii=False)[:200])
    print("一致:", b == g)
