# -*- coding: utf-8 -*-
"""add_range_distance.py — ★命中范围判定补充"距离条件"（依 1-1 标定）

## 依据（上一轮实测）
芬（格(3,5)、朝左、`range_grids={(3,5),(3,4)}`）面对第 2 只猎狗：
```
帧 428: 第2只格=(4,4) 格内=False 距离=1.09 → 芬选=None
帧 432: 第2只格=(4,4) 格内=False 距离=0.98 → 芬选=None    ← 距离已 <1.0 却仍不攻击
帧 434: 第2只格=(3,4) 格内=True  距离=1.00 → 芬选=猎狗     ← 吸附后才行
```
而**标定**：「**帧 432 芬 命中 猎狗**」⇒ **实机在帧 432（距离 0.98）就已能攻击**，
「帧 443 芬 阻挡」才发生阻挡。

⇒ **结论：攻击范围判定应同时接受"格在 range_grids 内"与"距离足够近"两种情况**；
后者正是"敌人在格内偏移/斜向接近"时实机仍能命中的原因。

## 实现
`enemies_in_range` 增加距离条件：
- 若敌人的**格**在 `cells_in_range` 内 ⇒ 命中（原有）；
- **或** 敌人与本单位的**欧氏距离 ≤ RANGE_DISTANCE_TOL**（默认 1.0，近战口径）⇒ 命中。

可用 `options={'range_distance_tol': None}` 关闭以回退为纯格判定。
"""
from __future__ import annotations

import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

ENGINE = r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py'

OLD = """    def enemies_in_range(self, u: Unit) -> list[Unit]:
        cells = self.cells_in_range(u)
        return [e for e in self.units.values() if e.side == 'ENEMY' and e.alive and e.grid() in cells]"""

NEW = """    def enemies_in_range(self, u: Unit) -> list[Unit]:
        \"\"\"范围内敌人：**格判定 或 距离判定**（依 1-1 标定）。

        1-1 实测：芬（近战 1 格、朝左）在一个"格为 (4,4)（不在 range_grids 内）但欧氏距离 0.98"
        的敌人面前，标定显示**帧 432 芬已能命中**（实机），说明命中不要求"格内对齐"；
        若只用格判定，需要等"阻挡吸附"把敌人对齐到 (3,4)（模拟器为帧 434）才攻击 ⇒ 晚约 20 帧。
        ⇒ 因此加入"距离 ≤ RANGE_DISTANCE_TOL"的补充条件。
        \"\"\"
        cells = self.cells_in_range(u)
        tol = getattr(self, 'range_distance_tol', 1.0)
        out = []
        for e in self.units.values():
            if e.side != 'ENEMY' or not e.alive:
                continue
            if e.grid() in cells:
                out.append(e)
                continue
            if tol is not None and e.dist_to(u) <= float(tol):
                out.append(e)
        return out"""


def main():
    s = io.open(ENGINE, encoding='utf-8').read()
    if '格判定 或 距离判定' in s:
        print('已存在距离判定')
        return
    if OLD not in s:
        print('★锚点未匹配')
        return
    s = s.replace(OLD, NEW, 1)
    if 'self.range_distance_tol' not in s:
        s = s.replace("        self.block_snap = bool(opts.get('block_snap', True))",
                      "        self.block_snap = bool(opts.get('block_snap', True))\n"
                      "        # ★命中范围容差（格）：敌人「格不在 range_grids 内但距离很近」时也可命中\n"
                      "        #   （依 1-1 标定：帧432 距离 0.98 时芬已能命中）；None = 关闭（纯格判定）\n"
                      "        self.range_distance_tol = opts.get('range_distance_tol', 1.0)", 1)
    io.open(ENGINE, 'w', encoding='utf-8', newline='').write(s)
    print('已加入距离判定')
    import ast
    ast.parse(io.open(ENGINE, encoding='utf-8').read())
    print('语法 OK')


if __name__ == '__main__':
    main()
