"""
parse_buff_holder.py — 解析 buff_template_holder MonoBehaviour 数据（客户端 buff 模板）
格式： [int32 条目数] 然后每个条目:
       [int32 key_len][key][int32×5 固定头][int32 json_len][JSON]
输出： ak_kb/downloads/buff_holder_parsed.json（全部条目），与 gamedata 比对
"""
import json
import os
import struct
import sys

BIN = r"E:\__file\ak_kb\downloads\buff_template_holder.mono.raw.bin"
OUT = r"E:\__file\ak_kb\downloads\buff_holder_parsed.json"


def main():
    raw = open(BIN, "rb").read()
    # 定位数据起点（MonoBehaviour 名后）
    i = raw.find(b"buff_template_holder")
    pos = i + len(b"buff_template_holder")
    data_start = pos
    count = struct.unpack_from("<I", raw, pos)[0]
    pos += 4
    print(f"数据起点 0x{data_start:X}, 声称条目数: {count}")

    entries = {}
    parsed = 0
    failed = 0
    while pos + 8 <= len(raw):
        key_len = struct.unpack_from("<I", raw, pos)[0]
        if key_len <= 0 or key_len > 256 or pos + 4 + key_len > len(raw):
            break
        key = raw[pos + 4: pos + 4 + key_len].decode("utf-8", "replace")
        pos += 4 + key_len
        # 固定头 5 个 int32
        head = struct.unpack_from("<5I", raw, pos)
        pos += 20
        json_len = struct.unpack_from("<I", raw, pos)[0]
        pos += 4
        if json_len <= 0 or pos + json_len > len(raw):
            failed += 1
            break
        blob = raw[pos: pos + json_len]
        pos += json_len
        try:
            j = json.loads(blob.decode("utf-8"))
            entries[key] = j
            parsed += 1
        except Exception:
            entries[key] = {"_raw": blob.decode("utf-8", "replace")[:200]}
            failed += 1
    print(f"解析成功: {parsed}, 失败: {failed}, 剩余字节: {len(raw) - pos}")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=0)
    print("已保存:", OUT)
    print("样例键:", list(entries.keys())[:8])


if __name__ == "__main__":
    main()
