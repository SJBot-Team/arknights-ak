# extract_colliders.py — 批量提取干员/敌人 prefab 的碰撞体与组件摘要
# 输出：E:\__file\ak_kb\downloads\collider_report.json（干员+敌人碰撞半径表）
import json
import os
import sys

sys.path.insert(0, r"C:\Users\23922\Documents\ds_harness\ak\scripts")
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper
from ak_lz4ak import decompress_lz4ak

CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = decompress_lz4ak
import UnityPy

BASE = r"E:\__file\ak_kb\client_res"
OUT = r"E:\__file\ak_kb\downloads\collider_report.json"

report = {"charpack": {}, "enm_pfb": {}}


def analyze(path, store):
    try:
        env = UnityPy.load(path)
    except Exception as e:
        store["_error_" + os.path.basename(path)] = str(e)[:100]
        return
    entry = {"colliders": [], "gameobjects": []}
    for obj in env.objects:
        t = obj.type.name
        if "Collider" in t:
            d = obj.read()
            r = {}
            for f in ("m_Radius", "m_Size", "m_Offset", "m_Enabled"):
                if hasattr(d, f):
                    r[f] = str(getattr(d, f))
            entry["colliders"].append({"type": t, **r})
        elif t == "GameObject":
            d = obj.read()
            n = d.m_Name or ""
            if n.startswith(("char_", "enemy_")) or n in ("Body", "Attack", "Direction", "Modes", "Trigger"):
                entry["gameobjects"].append(n)
    key = os.path.basename(path).replace(".ab", "")
    store[key] = entry


# charpack
cp_dir = os.path.join(BASE, "charpack")
files = sorted(os.listdir(cp_dir))
for i, fn in enumerate(files):
    if not fn.endswith(".ab"):
        continue
    analyze(os.path.join(cp_dir, fn), report["charpack"])
    if (i + 1) % 50 == 0:
        print(f"charpack {i+1}/{len(files)}", flush=True)

# enm_pfb
en_dir = os.path.join(BASE, "enm_pfb")
for fn in sorted(os.listdir(en_dir)):
    if fn.endswith(".ab"):
        analyze(os.path.join(en_dir, fn), report["enm_pfb"])

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=0)
print("完成 ->", OUT)
print("charpack 条目:", len(report["charpack"]), "enm_pfb 条目:", len(report["enm_pfb"]))
