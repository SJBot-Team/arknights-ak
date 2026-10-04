# -*- coding: utf-8 -*-
"""
extract_level_map.py — 从客户端关卡场景 AB 提取地图 tile 网格（标准流程）
=====================================================================
用法:
    python extract_level_map.py <level.ab> [--out out.json] [--ascii-grid]

原理（2026-09-02 实测核验）:
    明日方舟关卡场景 AB（如 scenes/obt/main/level_main_01-07/level_main_01-07.ab）
    中的 GameObject 直接以 "(x,y)#tileKey" 命名（x/y 为引擎网格坐标），
    例如 "(3,0)#tile_end"、"(1,4)#tile_road"。
    因此只需枚举 GameObject 名即可还原完整 tile 布局，无需解析 MonoBehaviour。

输出 JSON:
    {
      "levelId": "obt/main/level_main_01-07",   // 由 --level-id 指定
      "source_ab": "...",
      "grid": {"x_min":..,"x_max":..,"y_min":..,"y_max":..},
      "tiles": [ {"x":..,"y":..,"key":"tile_road"}, ... ],
      "start": [[x,y],...], "end": [[x,y],...]
    }

坐标说明:
    场景名称为引擎坐标 (x,y)。MAA Arknights-Tile-Pos 的 JSON 使用展示坐标，
    行=本 x、列=本 y（即转置）。输出原样保留引擎坐标，如需对照 MAA 自行转置。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
from UnityPy.enums.BundleFile import CompressionFlags
from UnityPy.helpers import CompressionHelper
import ak_lz4ak

CompressionHelper.DECOMPRESSION_MAP[CompressionFlags.LZHAM] = ak_lz4ak.decompress_lz4ak
import UnityPy

TILE_RE = re.compile(r"^\((-?\d+),(-?\d+)\)#(.+)$")


def extract(ab_path):
    env = UnityPy.load(ab_path)
    tiles = {}
    for obj in env.objects:
        if obj.type.name != "GameObject":
            continue
        d = obj.read()
        m = TILE_RE.match(d.m_Name)
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            tiles[(x, y)] = m.group(3)
    if not tiles:
        raise SystemExit(f"未在 {ab_path} 中找到 tile GameObject（可能不是关卡场景 AB）")
    return tiles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ab_file")
    ap.add_argument("--out", default=None, help="输出 JSON 路径")
    ap.add_argument("--level-id", default=None, help="levelId 字符串（写进 JSON）")
    ap.add_argument("--ascii-grid", action="store_true", help="同时打印 ASCII 网格")
    args = ap.parse_args()

    tiles = extract(args.ab_file)
    xs = [p[0] for p in tiles]
    ys = [p[1] for p in tiles]
    x_min, x_max, y_min, y_max = min(xs), max(xs), min(ys), max(ys)

    tile_list = sorted(
        ({"x": x, "y": y, "key": k} for (x, y), k in tiles.items()),
        key=lambda t: (-t["y"], t["x"]),
    )
    out = {
        "levelId": args.level_id or os.path.basename(os.path.dirname(args.ab_file)),
        "source_ab": os.path.basename(args.ab_file),
        "grid": {"x_min": x_min, "x_max": x_max, "y_min": y_min, "y_max": y_max},
        "width": x_max - x_min + 1,
        "height": y_max - y_min + 1,
        "tiles": tile_list,
        "start": [[x, y] for (x, y), k in tiles.items() if k == "tile_start"],
        "end": [[x, y] for (x, y), k in tiles.items() if k == "tile_end"],
    }

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"OK {len(tiles)} tiles -> {args.out}")
    else:
        print(json.dumps(out, ensure_ascii=False, indent=1))

    if args.ascii_grid:
        glyph = {"tile_forbidden": "X", "tile_road": ".", "tile_wall": "#",
                 "tile_floor": "_", "tile_start": "S", "tile_end": "E",
                 "tile_air": "^", "tile_hole": "O"}
        print("\n=== ASCII 网格 (y 从上到下, x 从左到右) ===")
        for y in range(y_max, y_min - 1, -1):
            row = "".join(glyph.get(tiles.get((x, y), "?"), "?")
                          for x in range(x_min, x_max + 1))
            print(f"y={y:>3} {row}")


if __name__ == "__main__":
    main()
