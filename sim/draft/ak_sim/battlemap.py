# -*- coding: utf-8 -*-
"""
battlemap.py — 地图 / 坐标 / 寻路（复刻游戏寻路模型）

依据：
  knowledge/02_作战机制（地块、寻路）、knowledge/24（伪代码 §1/§3）、
  knowledge/23（nextnode 顺序依赖 K-007）、knowledge/20·21（SPFA 代价、避障、惯性）

坐标约定（与关卡 json 一致）：
  格点 (row, col) —— row 对应引擎 x（列向），col 对应引擎 y；世界坐标 = (col, row)，
  单位位置用 FP（Q32.32）表示，1 格 = 1.0。
  ⚠️ 坐标变换细节（tile 原点/翻转）标 🟡，待与游戏比对后再固化。

寻路模型：
  以路线【终点 + 每个 MOVE 检查点】为目标，做 SPFA 距离场：
    可通行 = 1；障碍(箱/tile_wall) = +1000；地穴(hole) = +1000000
    扩散顺序 上右下左（+y, +x, -y, -x）
  之后用"魔改 Bresenham"把 nextnode 拉远（顺序依赖，K-007 🟡）
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from . import fp

# 地块通行性
NON_BLOCKING_TILES = {'tile_road', 'tile_floor', 'tile_start', 'tile_end', 'tile_air'}
GROUND_BLOCKING_TILES = {'tile_wall', 'tile_forbidden'}
HOLE_TILES = {'tile_hole', 'tile_deepwater'}   # 掉坑类（🟡 名称待与客户端比对）

OBSTACLE_COST = 1000
HOLE_COST = 1_000_000

# 避障/惯性常量（knowledge/20 cv31743470；🟡 待 IDA 固化）
STEERING_FACTOR_GROUND = 8.0
STEERING_FACTOR_FLY = 20.0
MAX_STEERING_FORCE_GROUND = 10.0
MAX_STEERING_FORCE_FLY = 100.0


@dataclass
class Tile:
    key: str
    height_type: str          # HIGHLAND / LOWLAND
    buildable_type: str       # NONE / MELEE / RANGED / ALL
    passable_mask: str        # ALL / FLY_ONLY / WALK_ONLY / NONE
    row: int = 0
    col: int = 0

    @property
    def is_ground_passable(self) -> bool:
        if self.passable_mask in ('FLY_ONLY', 'NONE'):
            return False
        if self.key in GROUND_BLOCKING_TILES:
            return False
        return True

    @property
    def is_fly_passable(self) -> bool:
        if self.passable_mask == 'NONE':
            return False
        return self.key not in {'tile_forbidden'} or self.passable_mask != 'NONE'

    @property
    def is_hole(self) -> bool:
        return self.key in HOLE_TILES

    @property
    def is_buildable(self) -> bool:
        return self.buildable_type not in ('NONE', '', None)

    def to_dict(self):
        return {'row': self.row, 'col': self.col, 'key': self.key, 'height': self.height_type,
                'buildable': self.buildable_type, 'passable': self.passable_mask}


class BattleMap:
    """关卡地图：格点、通行性、部署合法性、寻路距离场。"""

    def __init__(self, level: dict):
        self.level = level
        md = level['mapData']
        raw = md['map']
        self.height = len(raw)                # rows
        self.width = len(raw[0])              # cols
        tiles_def = md['tiles']
        self.tiles: dict[tuple[int, int], Tile] = {}
        # ⚠ 关键：mapData.map 的**存储顺序与关卡自己的 row 坐标相反**。
        # 证据（h12-4，2026-09-14 实机+数据双向确认）：
        #  · tile_start 出现在 map 数组的 (3,0)/(6,0)/(7,0)，而 routes.startPosition 的 row 是
        #    (5,0)/(2,0)/(1,0) —— 恰好是 H-1-i；
        #  · tile_end 出现在 (0,8)/(0,10)/(0,11)，而 routes.endPosition 是 (8,8)/(8,10)/(8,11)；
        #  · tile_telout 在 (3,4) ↔ routes 的 APPEAR_AT_POS (5,4)；tile_telin 在 (7,11) ↔ 检查点 (1,11)；
        #  · 实机截图里两个「街头应急储备」并排出现在屏幕第 3 行，而 predefines 写的是 row 5。
        # 所以这里把 map 数组按行**反转**，让模拟内部坐标 == 关卡 row/col 坐标，
        # 之后 routes/waves/predefines/checkpoints 的 row 可以直接用，不再做任何翻转。
        for r, rowvals in enumerate(reversed(raw)):
            for c, idx in enumerate(rowvals):
                td = tiles_def[idx]
                self.tiles[(r, c)] = Tile(
                    key=td.get('tileKey', 'tile_forbidden'),
                    height_type=td.get('heightType', 'LOWLAND'),
                    buildable_type=td.get('buildableType', 'NONE'),
                    passable_mask=td.get('passableMask', 'ALL'),
                    row=r, col=c)
        self.disallow_locate = {(g['row'], g['col']) for g in (level.get('tilesDisallowToLocate') or [])}
        self._nav_cache: dict[tuple[int, int, bool], dict] = {}
        self.device_blocked: set[tuple[int, int]] = set()   # 预置装置占格（影响敌人寻路）
        # 红门/蓝门格（routes 的 startPosition/endPosition）：h12-4 里它们本来就是可通行地块
        # （tile_start / tile_end，mask=ALL），这里只是登记下来便于查询/绘图
        self.door_tiles: set[tuple[int, int]] = set()
        for rt in (level.get('routes') or []):
            if not rt:
                continue
            for f in ('startPosition', 'endPosition'):
                p = rt.get(f) or {}
                if 'row' in p and 'col' in p:
                    self.door_tiles.add((int(p['row']), int(p['col'])))

    # ---------- 查询 ----------
    def tile(self, row: int, col: int) -> Tile | None:        return self.tiles.get((row, col))

    def in_bounds(self, row: int, col: int) -> bool:
        return 0 <= row < self.height and 0 <= col < self.width

    def is_passable(self, row: int, col: int, flying: bool = False) -> bool:
        t = self.tile(row, col)
        if t is None:
            return False
        if (row, col) in getattr(self, 'door_tiles', ()):
            return True          # 红门/蓝门格在数据里是 tile_forbidden，但敌人确实从/往那里走
        return t.is_fly_passable if flying else t.is_ground_passable

    def can_deploy(self, row: int, col: int, melee: bool = True) -> bool:
        """部署合法性（简化：可部署类型 + 非禁止格）。🟡 高空/近战位判定待细化。"""
        t = self.tile(row, col)
        if t is None or not t.is_buildable:
            return False
        if (row, col) in self.disallow_locate:
            return False
        if melee:
            return t.buildable_type in ('MELEE', 'ALL')
        return t.buildable_type in ('RANGED', 'ALL')

    # ---------- 坐标 ----------
    @staticmethod
    def grid_to_world(row: float, col: float) -> tuple[int, int]:
        """格点 → 世界坐标（FP）。格中心 (col+0.5, row+0.5)。"""
        return fp.from_float(col + 0.5), fp.from_float(row + 0.5)

    @staticmethod
    def world_to_grid(x: int, y: int) -> tuple[int, int]:
        return int(math.floor(fp.to_float(y))), int(math.floor(fp.to_float(x)))

    # ---------- ★直线寻路辅助（对齐 routes 的 allowDiagonalMove / visitEveryTileCenter 语义） ----------
    def walkable_at(self, x: float, y: float, flying: bool = False) -> bool:
        """世界坐标 (col,row)（float）是否可通行。"""
        return self.is_passable(int(math.floor(y)), int(math.floor(x)), flying=flying)

    def line_is_clear(self, p0: tuple[float, float], p1: tuple[float, float],
                      flying: bool = False, step: float = 0.15) -> bool:
        """线段 p0→p1（世界坐标 (col,row)）是否**不穿过任何不可通行格**。

        用作"直线优先"的可行性判定：可通 ⇒ 敌人直接朝目标直线推进（允许斜向）；
        否则回退到 `build_navmap` 的逐格导航（贴墙/绕障）。
        """
        x0, y0 = p0
        x1, y1 = p1
        dist = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(dist / max(1e-6, step)))
        for i in range(n + 1):
            t = i / n
            x = x0 + (x1 - x0) * t
            y = y0 + (y1 - y0) * t
            if not self.walkable_at(x, y, flying=flying):
                return False
        return True

    # ---------- 寻路 ----------
    def build_navmap(self, target: tuple[int, int], flying: bool = False,
                     allow_diagonal: bool = True,
                     devices_block: bool = True) -> dict:
        """SPFA 距离场（从 target 反向扩散），返回 {(row,col): dist}。

        **不可通行格不可穿越**（地面单位不能穿墙/坑，装置占格也绕行）。
        早期实现把障碍记为有限代价 OBSTACLE_COST(1000)，导致敌人在 9×13 的小图上
        「走直线穿墙」抄近路——h12-4 里表现为 28s 就有人走到蓝门（见 §7.4x 的定位过程）。
        target 本身允许是被禁止格（红门/蓝门的 tile_forbidden 就是门格）。
        """
        target = (target[0], target[1])
        key = (target[0], target[1], flying, devices_block)
        if key in self._nav_cache:
            return self._nav_cache[key]
        dev = getattr(self, 'device_blocked', set()) if devices_block else set()
        dist: dict[tuple[int, int], float] = {target: 0.0}
        dq = deque([target])
        # 上右下左
        dirs = [(0, -1), (1, 0), (0, 1), (-1, 0)]
        diag = [(-1, -1), (1, -1), (-1, 1), (1, 1)] if allow_diagonal else []
        while dq:
            cur = dq.popleft()
            base = dist[cur]
            for dr, dc in dirs + diag:
                nr, nc = cur[0] + dr, cur[1] + dc
                if not self.in_bounds(nr, nc):
                    continue
                t = self.tiles[(nr, nc)]
                if (nr, nc) in dev or not self.is_passable(nr, nc, flying):
                    continue            # 硬障碍：不扩散、不可达（装置只是绕行障碍，见 §7.4x）
                step = 1 if (dr == 0 or dc == 0) else 1.4142
                # 斜向不允许「贴角穿过」两堵墙/两个障碍之间
                if dr != 0 and dc != 0:
                    if not self.is_passable(cur[0], nc, flying) and \
                            not self.is_passable(nr, cur[1], flying):
                        continue
                nd = base + step
                if nd < dist.get((nr, nc), float('inf')):
                    dist[(nr, nc)] = nd
                    dq.append((nr, nc))
        self._nav_cache[key] = dist
        return dist

    def cursor_tile(self, x: int, y: int) -> tuple[int, int]:
        """光标位置（世界坐标）→ 格点。"""
        return self.world_to_grid(x, y)

    NAV_DIRS8 = ((0, -1), (1, 0), (0, 1), (-1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1))

    def nav_step_target(self, cell: tuple[int, int], navmap: dict):
        """返回 (目标格, 是否需要把单位吸附到该格中心)。

        难点：单位被墙"夹"在格边界上时，`floor` 会把它算到**墙那一侧**，
        而墙格不在距离场里，`next_node` 于是返回自身 → 单位顶着墙原地不动（曾导致
        h12-4 大量敌人在 (2,1) 贴墙处永久卡死，见 §7.4x）。这里做两件兜底：
          1. 当前格在场里 → 选 dist 更小的相邻格；
          2. 当前格不在场里 → 选场里 dist 最小的相邻格，并要求把单位吸附过去。
        """
        cur = navmap.get(cell)
        best, bestd = None, float('inf')
        for dr, dc in self.NAV_DIRS8:
            nb = (cell[0] + dr, cell[1] + dc)
            d = navmap.get(nb)
            if d is None:
                continue
            if cur is not None and d >= cur:
                continue
            if d < bestd:
                best, bestd = nb, d
        if best is not None:
            return best, False
        if cur is None:
            best2, bestd2 = None, float('inf')
            for dr, dc in self.NAV_DIRS8:
                nb = (cell[0] + dr, cell[1] + dc)
                d = navmap.get(nb)
                if d is not None and d < bestd2:
                    best2, bestd2 = nb, d
            if best2 is not None:
                return best2, True
        return cell, False

    def next_node(self, pos: tuple[int, int], navmap: dict, flying: bool = False) -> tuple[int, int]:
        """按当前光标格在距离场中找下一个更近的相邻格（上右下左优先）。"""
        r, c = self.cursor_tile(*pos)
        cur = navmap.get((r, c))
        if cur is None:
            return (r, c)
        best = (r, c)
        bestd = cur
        for dr, dc in [(0, -1), (1, 0), (0, 1), (-1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            nr, nc = r + dr, c + dc
            d = navmap.get((nr, nc))
            if d is not None and d < bestd:
                bestd = d
                best = (nr, nc)
        return best

    def smooth_nextnode(self, navmap: dict, node: tuple[int, int], start: tuple[int, int]) -> tuple[int, int]:
        """魔改 Bresenham 拉远：沿直线找到最远连通格（K-007 🟡 顺序依赖）。

        简化复刻：从 start 向 node 方向逐格推进，直到下一步不可直达。
        """
        sr, sc = start
        tr, tc = node
        dr = tr - sr
        dc = tc - sc
        if dr == 0 and dc == 0:
            return node
        steps = max(abs(dr), abs(dc))
        best = node
        for i in range(1, steps + 1):
            r = sr + round(dr * i / steps)
            c = sc + round(dc * i / steps)
            if not self.is_passable(r, c):
                best = (sr + round(dr * (i - 1) / steps), sc + round(dc * (i - 1) / steps))
                break
        return best


@dataclass
class Route:
    """一条敌人路线：起点/终点 + 检查点序列（含等待时间）。"""
    index: int
    motion_mode: str
    start: tuple[int, int]
    end: tuple[int, int]
    checkpoints: list[dict] = field(default_factory=list)
    allow_diagonal: bool = True
    spawn_offset: tuple[float, float] = (0.0, 0.0)
    spawn_random_range: tuple[float, float] = (0.0, 0.0)


def build_routes(level: dict) -> list[Route]:
    out = []
    for i, r in enumerate(level.get('routes') or []):
        if not r:
            continue
        sp = r.get('startPosition') or {}
        ep = r.get('endPosition') or {}
        cps = []
        for cp in (r.get('checkpoints') or []):
            cps.append({
                'type': cp.get('type'),
                'time': cp.get('time', 0.0),
                # ⚠ position 必须保持 dict：早期版本存成了裸 row 整数，导致 engine._process_checkpoints
                #   的 isinstance(pos, dict) 判定失败 → **所有 MOVE 检查点被瞬间跳过**，敌人直接奔向
                #   route_end，绕开检查点绕行（里程 13.38 格 vs 折线 16.0 格，整条流水线偏快 7s，见 §7.51）
                'position': dict(cp.get('position') or {}),
                'row': (cp.get('position') or {}).get('row', 0),
                'col': (cp.get('position') or {}).get('col', 0),
                'reach_offset': (cp.get('reachOffset') or {}),
                'reach_distance': cp.get('reachDistance', 0.0),
            })
        out.append(Route(
            index=i,
            motion_mode=r.get('motionMode', 'WALK'),
            start=(sp.get('row', 0), sp.get('col', 0)),
            end=(ep.get('row', 0), ep.get('col', 0)),
            checkpoints=cps,
            allow_diagonal=bool(r.get('allowDiagonalMove', True)),
            spawn_offset=((r.get('spawnOffset') or {}).get('x', 0.0), (r.get('spawnOffset') or {}).get('y', 0.0)),
            spawn_random_range=((r.get('spawnRandomRange') or {}).get('x', 0.0),
                                (r.get('spawnRandomRange') or {}).get('y', 0.0)),
        ))
    return out


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    from .data import load_level
    lv = load_level('obt/main/level_main_01-07')
    m = BattleMap(lv)
    print(f'地图 {m.height}x{m.width}，格点 {len(m.tiles)}')
    routes = build_routes(lv)
    print(f'路线 {len(routes)} 条；route[1] start={routes[1].start} end={routes[1].end} cps={len(routes[1].checkpoints)}')
    nav = m.build_navmap(routes[1].end)
    print('导航距离场规模:', len(nav), '起点距离:', nav.get(routes[1].start))
    # 打印地图
    glyph = {'tile_forbidden': 'X', 'tile_road': '.', 'tile_wall': '#', 'tile_floor': '_',
             'tile_start': 'S', 'tile_end': 'E'}
    for r in range(m.height):
        print('  ' + ''.join(glyph.get(m.tiles[(r, c)].key, '?') for c in range(m.width)))
