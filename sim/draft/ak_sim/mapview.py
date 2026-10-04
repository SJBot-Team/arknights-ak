# -*- coding: utf-8 -*-
"""mapview.py — **关卡地图可视化（ASCII）**：把 tile 网格、可部署性、路线与出怪画出来

## 用途
1. **排轴依据**：一眼看清哪些格可部署（近战/远程）、己方/敌方路线、出怪口位置；
2. **需求 6（理想目标）的第一步**：后续要做的"地图可视界面（标格子 A1/F3、单位名称、坐标点）"
   先以 ASCII 打底，几何/坐标数据也一并导出，便于将来接图形界面。

## 网格标号约定（与游戏一致）
- 列：A, B, C…（第 0 列 = A）
- 行：1, 2, 3…（第 0 行 = 1）

用法：python ak_sim/mapview.py 1-1 [--routes] [--spawn]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from ak_sim import data as D              # noqa: E402
from ak_sim.scenario import Scenario      # noqa: E402

# 游戏里的"可部署"判定字段（不同版本字段名可能不同，做多路回退）
BUILDABLE_KEYS = ('buildableType', 'buildable', 'canBuild')
HEIGHT_KEYS = ('heightType', 'height', 'tileHeight')
PASSABLE_KEYS = ('passableMask', 'passable', 'walkable')


def _pick(tile: dict, keys, default=None):
    for k in keys:
        if k in tile and tile[k] is not None:
            return tile[k]
    return default


def load_grid(stage: str):
    sc = Scenario(stage)
    lv = D.load_level(sc.stage_code)
    md = lv.get('mapData') or {}
    grid_codes = md.get('map') or []
    tiles = md.get('tiles') or []
    return sc, lv, md, grid_codes, tiles


def render(stage: str, show_routes=True, show_spawn=True):
    sc, lv, md, codes, tiles = load_grid(stage)
    R, C = len(codes), len(codes[0]) if codes else 0
    print(f'=== {stage}  ({sc.stage_code})  地图 {R}×{C} ===')
    # tile 定义样例（帮助确认字段名）
    if tiles:
        print('tile 定义样例:', json.dumps(tiles[0], ensure_ascii=False)[:220])
    # ★ mapData.map 里的整数就是 mapData.tiles 的**直接索引**（实测 1-1：code 0~62，tiles 63 个）
    def tile_of(code):
        return tiles[code] if isinstance(code, int) and 0 <= code < len(tiles) else {}
    hdr = '    ' + ''.join(f'{chr(65 + c):>3}' for c in range(C))
    print(hdr)
    for r in range(R):
        row = []
        for c in range(C):
            t = tile_of(codes[r][c])
            bt = _pick(t, BUILDABLE_KEYS, None)
            ht = _pick(t, HEIGHT_KEYS, None)
            # 显示：远程高台='^'，近战地面='.'，不可部署='#'
            if bt is None:
                ch = '?'
            elif str(bt).upper() in ('NONE', '0', 'FALSE'):
                ch = '#'
            elif str(bt).upper() in ('RANGED', '2') or (ht is not None and str(ht) == '1'):
                ch = '^'
            else:
                ch = '.'
            row.append(f'{ch:>3}')
        print(f'{r + 1:>3} ' + ''.join(row))
    # 路线
    if show_routes:
        rs = lv.get('routes') or []
        print(f'\n路线（共 {len(rs)} 条，显示前 12）：')
        for i, rt in enumerate(rs[:12]):
            sp = rt.get('startPosition') or {}
            ep = rt.get('endPosition') or {}
            cps = [(p.get('position') or p) for p in (rt.get('checkpoints') or [])][:6]
            def lbl(p):
                if not isinstance(p, dict):
                    return str(p)
                return f"{chr(65 + int(p.get('col', 0)))}{int(p.get('row', 0)) + 1}"
            print(f'  route{i:<2} {lbl(sp)} → {lbl(ep)}  检查点 {len(rt.get("checkpoints") or [])} '
                  f'{[lbl(p) for p in cps]}')
    # 出怪
    if show_spawn:
        spawns = []
        for wi, w in enumerate(lv.get('waves') or []):
            for fr in (w.get('fragments') or []):
                for a in (fr.get('actions') or []):
                    if a.get('actionType') == 'SPAWN':
                        ri = a.get('routeIndex')
                        rs = lv.get('routes') or []
                        pos = (rs[ri].get('startPosition') if isinstance(ri, int) and ri < len(rs) else None) or {}
                        lbl = f"{chr(65 + int(pos.get('col', 0)))}{int(pos.get('row', 0)) + 1}" if pos else '?'
                        spawns.append((wi, a.get('key'), a.get('preDelay'), a.get('count'), ri, lbl))
        print(f'\n出怪（共 {len(spawns)} 条，显示前 14）：')
        for wi, key, pre, cnt, ri, lbl in spawns[:14]:
            print(f'  wave{wi:<2} preDelay={pre:<6} x{cnt:<3} route{ri}({lbl})  {key}')
    return {'rows': R, 'cols': C, 'routes': len(lv.get('routes') or [])}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('stage')
    ap.add_argument('--no-routes', action='store_true')
    ap.add_argument('--no-spawn', action='store_true')
    a = ap.parse_args()
    render(a.stage, not a.no_routes, not a.no_spawn)
