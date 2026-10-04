# -*- coding: utf-8 -*-
"""calc_view.py — 地图格子 → 屏幕比例坐标（PRTS+ `src/logic/calc_view.py` 的移植）

## 依据
PRTS+ 用 **3D 透视投影** 把战场格子映射为**屏幕比例坐标**（0~1），供 `mouseclick/mousemove` 使用：
```
perspective(20°) @ rotate_x(30°) @ [rotate_y(10°) if side] @ translate(view)
map_point = [j-(w-1)/2, (h-1)/2-i, heightType*-0.4, 1]
vp = M @ map_point;  vp /= vp[3];  vp = (vp+1)/2;  pos = (vp[0], 1-vp[1])
```
- **front**（正视，无 rotate_y）：用于"技能/撤退"时点干员；
- **side**（侧视，多一层 rotate_y(10°)）：用于**部署落点**（`view_pos_side`）。

## 与 PRTS+ 的差异
PRTS+ 的 `level["view"]` 取自它自己构造的地图对象；**我们的关卡 json 里没有 view 字段**
⇒ 本模块把 `view` 作为**可配置参数**，并支持**用实测点反推**（见 `calibrate_view`）。

## 用法
    from plugins.action.calc_view import CalcView
    cv = CalcView()                      # 默认 view=(0,0,0)
    grid = cv.build(tiles, side=True)    # 返回 [row][col] = (rx, ry) 比例坐标
    rx, ry = grid[3][4]                  # 第 3 行第 4 列的屏幕比例坐标
"""
from __future__ import annotations

import math

import numpy as np

DEG = math.pi / 180


class ViewConfig:
    FROM_RATIO = 9 / 16
    TO_RATIO = 3 / 4
    NEAR = 0.3
    FAR = 1000.0
    PERSPECTIVE_DEG = 20.0
    ROTATE_X_DEG = 30.0
    ROTATE_Y_DEG = 10.0
    HEIGHT_FACTOR = -0.4          # heightType * HEIGHT_FACTOR


class CalcView:
    def __init__(self, view=(0.0, 0.0, 0.0), cfg=ViewConfig):
        self.view = tuple(float(v) for v in view)
        self.cfg = cfg

    # ---------------- 核心：构建变换矩阵 ----------------
    def _matrix(self, side: bool):
        c = self.cfg
        x, y, z = self.view
        transform = np.array([[1, 0, 0, -x],
                              [0, 1, 0, -y],
                              [0, 0, 1, -z],
                              [0, 0, 0, 1]], dtype=float)
        t = math.tan(c.PERSPECTIVE_DEG * DEG)
        persp = np.array([[c.FROM_RATIO / t, 0, 0, 0],
                          [0, 1 / t, 0, 0],
                          [0, 0, -(c.FAR + c.NEAR) / (c.FAR - c.NEAR),
                           -(c.FAR * c.NEAR * 2) / (c.FAR - c.NEAR)],
                          [0, 0, -1, 0]], dtype=float)
        ca, sa = math.cos(c.ROTATE_X_DEG * DEG), math.sin(c.ROTATE_X_DEG * DEG)
        rx = np.array([[1, 0, 0, 0],
                       [0, ca, -sa, 0],
                       [0, -sa, -ca, 0],
                       [0, 0, 0, 1]], dtype=float)
        if not side:
            return persp @ rx @ transform
        cb, sb = math.cos(c.ROTATE_Y_DEG * DEG), math.sin(c.ROTATE_Y_DEG * DEG)
        ry = np.array([[cb, 0, sb, 0],
                       [0, 1, 0, 0],
                       [-sb, 0, cb, 0],
                       [0, 0, 0, 1]], dtype=float)
        return persp @ rx @ ry @ transform

    # ---------------- 单点投影 ----------------
    def project(self, row: int, col: int, height: int, rows: int, cols: int, side: bool):
        m = self._matrix(side)
        p = np.array([col - (cols - 1) / 2.0,
                      (rows - 1) / 2.0 - row,
                      height * self.cfg.HEIGHT_FACTOR,
                      1.0], dtype=float)
        v = m @ p
        if abs(v[3]) < 1e-9:
            return None
        v = v / v[3]
        v = (v + 1) / 2
        return (float(v[0]), float(1 - v[1]))

    # ---------------- 批量：整个地图 ----------------
    def build(self, tiles, side: bool, rows=None, cols=None):
        """tiles: 二维数组，元素含 heightType（'HIGHLAND'/'LOWLAND' 或 0/1）。"""
        rows = rows or len(tiles)
        cols = cols or (len(tiles[0]) if rows else 0)
        out = []
        for i in range(rows):
            line = []
            for j in range(cols):
                t = tiles[i][j]
                hv = t.get('heightType', 0) if isinstance(t, dict) else t
                h = 1 if (hv == 'HIGHLAND' or hv == 1) else 0
                line.append(self.project(i, j, h, rows, cols, side))
            out.append(line)
        return out

    # ---------------- 反推 view 参数（用实测点标定） ----------------
    def calibrate_view(self, samples, tiles, rows, cols, side=True,
                       bounds=(-30.0, 30.0), iters=4000, seed=0):
        """用若干"已知格子 → 实测屏幕比例坐标"的点，反推 view=(x,y,z)。

        samples: [((row,col), (rx,ry)), ...]
        ⇒ 这是"本方没有 view 字段"时的替代方案：网格搜索 + 局部细化。
        """
        rng = np.random.default_rng(seed)
        best, best_err = None, None

        def err(view):
            self.view = view
            total = 0.0
            for (rc, target) in samples:
                got = self.project(rc[0], rc[1],
                                   1 if (tiles[rc[0]][rc[1]] == 'HIGHLAND') else 0,
                                   rows, cols, side)
                if got is None:
                    return 1e9
                total += (got[0] - target[0]) ** 2 + (got[1] - target[1]) ** 2
            return total / max(1, len(samples))

        lo, hi = bounds
        span = (hi - lo) / 2
        center = (0.0, 0.0, 0.0)
        for _ in range(iters):
            view = tuple(center[k] + float(rng.uniform(-span, span)) for k in range(3))
            e = err(view)
            if best_err is None or e < best_err:
                best, best_err = view, e
            span *= 0.9995
        self.view = best or (0.0, 0.0, 0.0)
        return {'view': self.view, 'rmse': math.sqrt(best_err or 0.0)}


if __name__ == '__main__':
    import sys
    sys.path.insert(0, r'C:\Users\23922\Documents\ds_harness\ak\sim\draft')
    sys.stdout.reconfigure(encoding='utf-8')
    from ak_sim import data as D
    lv = D.load_level('obt/main/level_main_01-01')
    md = lv['mapData']
    tiles = md['tiles']
    codes = md['map']
    rows, cols = len(codes), len(codes[0])
    # map 里存的是 tiles 的索引
    grid_tiles = [[tiles[codes[i][j]] for j in range(cols)] for i in range(rows)]
    cv = CalcView(view=(0, 0, 0))
    for side in (False, True):
        g = cv.build(grid_tiles, side=side, rows=rows, cols=cols)
        print(f'--- side={side} ({("侧视/部署" if side else "正视/技能")}) ---')
        for i in range(rows):
            print('  ' + '  '.join(
                '  --  ' if p is None else f'({p[0]:.2f},{p[1]:.2f})' for p in g[i]))
