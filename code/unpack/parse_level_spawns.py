# -*- coding: utf-8 -*-
"""
parse_level_spawns.py — 解析关卡 json 的出怪时间轴与路线（模拟输入）
=====================================================================
用法: python parse_level_spawns.py <levelJson> [--out out.json] [--print]

输入: fetch_level.py 抓取的关卡完整 json（ArknightsGameData levels/ 或露托 API 同构）。
输出:
  {
    "levelId": ...,
    "tile": {...},                      # tileKey/height/buildable 网格（引擎坐标）
    "enemyDb": [ {key, level, ...} ],   # 关卡引用的敌人及等级
    "routes": [ {routeIndex, start:{row,col}, cps:[...]} ],  # 路线与检查点(引擎坐标)
    "timeline": [                        # ★ 出怪时间轴（秒）：模拟驱动核心
      { "t": 0.0, "type": "SPAWN", "enemy": "enemy_1027_mob", "count": 1,
        "route": 1, "interval": 1.0, "wave": 0, "frag": 1 },
      ...
    ]
  }

时间语义（源自 game data 结构，2026-09-02 按露托模拟器 parseWaves/parseActions 算法核验）:
  露托(lutonada) 模拟器源码算法（与游戏一致）:
    waveStart = wave.preDelay
    对每个 fragment（串行）: fragStart = t（上一 frag 结束时刻; 首 frag 为 waveStart）+ frag.preDelay
    对每个 action 的每只怪 c: 时刻 = fragStart + action.preDelay + action.interval * c
    fragment 结束时刻 = 本 frag 全部动作的最大时刻
  本脚本输出 timeline 即按此算法（含 count>1 展开为逐怪条目）。
"""
import argparse
import json
import os
import sys


def parse(path):
    d = json.load(open(path, encoding="utf-8"))
    out = {
        "levelId": d.get("levelId") or os.path.basename(path).replace(".json", ""),
        "options": d.get("options"),
        "mapData": d.get("mapData"),          # 原样保留（含 map 编号矩阵/tiles 定义）
        "enemyDb": d.get("enemyDbRefs"),
        "enemies": d.get("enemies"),
        "routes": d.get("routes"),
        "extraRoutes": d.get("extraRoutes"),
        "runes": d.get("runes"),
        "timeline": [],
    }
    for wi, w in enumerate(d.get("waves") or []):
        if not (w.get("fragments")):
            continue
        t_wave = w.get("preDelay", 0.0)
        t = t_wave
        for fi, frag in enumerate(w.get("fragments") or []):
            t += frag.get("preDelay", 0.0)          # fragStart
            frag_end = t
            for a in frag.get("actions") or []:
                cnt = a.get("count", 1)
                for c in range(cnt):
                    d_t = t + a.get("preDelay", 0.0) + a.get("interval", 0.0) * c
                    frag_end = max(frag_end, d_t)
                    entry = {
                        "t": round(d_t, 4),
                        "type": a.get("actionType"),
                        "enemy": a.get("key"),
                        "count": 1,
                        "route": a.get("routeIndex"),
                        "interval": a.get("interval", 0.0),
                        "wave": wi,
                        "frag": fi,
                        "managedByScheduler": a.get("managedByScheduler", False),
                        "randomType": a.get("randomType"),
                        "weight": a.get("weight", 0),
                        "hiddenGroup": a.get("hiddenGroup"),
                    }
                    out["timeline"].append(entry)
            t = frag_end                                # fragment 串行：下一 frag 从本 frag 结束开始
        # postDelay 只在 wave 级（露托里用于 waveDatas 后处理，对 spawn 时刻无影响）
    out["timeline"].sort(key=lambda e: e["t"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("level_json")
    ap.add_argument("--out", default=None)
    ap.add_argument("--print", action="store_true")
    args = ap.parse_args()
    out = parse(args.level_json)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"OK {len(out['timeline'])} 条出怪 -> {args.out}")
    if args.print:
        print(f"routes: {len(out['routes'] or [])}, enemyDb: {len(out['enemyDb'] or [])}")
        print("=== 出怪时间轴（前 40 条）===")
        for e in out["timeline"][:40]:
            print(f"  t={e['t']:>7} {e['type']:<14} {e['enemy']:<28} x{e['count']} route={e['route']} interval={e['interval']}")


if __name__ == "__main__":
    main()
