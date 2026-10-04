# -*- coding: utf-8 -*-
"""
fetch_level.py — 按 levelId 从 ArknightsGameData 主仓抓取关卡完整数据（标准流程）
================================================================================
用法: python fetch_level.py <levelId> [--out 保存路径] [--cdn jsdelivr|raw]

levelId 示例:
  obt/main/level_main_01-07          主线 1-7
  activities/a001/level_a001_01      GT-1（骑兵与猎人）
  obt/roguelike/ro1/level_rogue1_1-1 肉鸽（若主仓 levels 收录）

说明（2026-09-02 核验）:
  ArknightsGameData 主仓 zh_CN/gamedata/levels/ 共 3868 个关卡 json（约 500MB），
  包含完整关卡配置：mapData（tile 网格+定义）、routes（敌人路线+checkpoints 坐标）、
  waves（波次+SPAWN 出怪时序）、enemyDbRefs（敌人引用+关卡覆盖数值）、runes 等。
  与露托(lutonada) API /levels/{levelId}.json 数据逐字段一致（waves/routes 零差异）。

优先 CDN: jsDelivr（gh 前缀）。文件大时可用 tools/download_parallel.py 分块。
"""
import argparse
import json
import os
import sys
import urllib.request

BASE_JS = "https://cdn.jsdelivr.net/gh/Kengxxiao/ArknightsGameData@master/zh_CN/gamedata/levels/{}.json"
BASE_RAW = "https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/master/zh_CN/gamedata/levels/{}.json"

DEFAULT_OUT_DIR = r"E:\__file\ak_kb\gamedata\levels"


def fetch(level_id, cdn="jsdelivr", timeout=120):
    url = (BASE_JS if cdn == "jsdelivr" else BASE_RAW).format(level_id)
    req = urllib.request.Request(url, headers={"User-Agent": "ak-kb"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("level_id")
    ap.add_argument("--out", default=None, help="保存路径（默认 E:\\__file\\ak_kb\\gamedata\\levels\\<id>.json）")
    ap.add_argument("--cdn", default="jsdelivr", choices=["jsdelivr", "raw"])
    ap.add_argument("--print-head", action="store_true", help="打印结构概要")
    args = ap.parse_args()

    data = fetch(args.level_id, args.cdn)
    out = args.out or os.path.join(DEFAULT_OUT_DIR, args.level_id + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        f.write(data)
    print(f"OK {args.level_id} -> {out} ({len(data)} bytes)")

    if args.print_head:
        d = json.loads(data)
        print("keys:", list(d.keys()))
        print("routes:", len(d.get("routes") or []), "waves:", len(d.get("waves") or []),
              "enemyDbRefs:", len(d.get("enemyDbRefs") or []))
        md = d.get("mapData") or {}
        print("mapData:", {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in md.items() if k in ("map", "tiles")})


if __name__ == "__main__":
    main()
