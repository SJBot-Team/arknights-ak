# -*- coding: utf-8 -*-
"""add_straight_path.py — ★改为"朝目标点直线插值"寻路（对齐 routes 的 allowDiagonalMove 语义）

## 问题（上一轮确认）
`_enemy_move` 每帧取"**下一格**"，并朝"**该格中心**"推进
⇒ 路径呈 **L 形（先横后竖）**，而关卡 `routes` 声明
`allowDiagonalMove: true`、`visitEveryTileCenter: false`、`visitEveryNodeCenter: false`
⇒ 语义应为"**从起点直线走向终点**"。

**实测后果**（1-1 第 2 只猎狗，route4 (6,4)→(0,5)）：
L 形路径使它沿格中心 col=4.5 竖直上行、接近终点时才横移，
⇒ **不经过 (3,4)**（芬朝左攻击范围内的格），而是在 **(3,5) 与芬重叠**处才被阻挡
⇒ 芬无法攻击它 ⇒ 标定「帧432 芬命中 / 443 芬阻挡 / 464 芬击杀」全部缺失。

## 修正
在 `_enemy_move` 中**优先尝试直线**：
- 目标点 = 当前目标格（检查点或终点）的**中心**；
- **若从当前位置到目标中心的线段不穿过不可通行格** ⇒ 直接朝它直线推进（斜向亦可）；
- 否则**回退**到原 `navmap` 逐格导航（贴墙、绕障时使用）。

可用 `Battle(..., options={'straight_path': False})` 关闭以回退旧行为。
"""
from __future__ import annotations

import io
import sys

sys.stdout.reconfigure(encoding='utf-8')

ENGINE = r'C:\Users\23922\Documents\ds_harness\ak\sim\draft\ak_sim\engine.py'

ANCHOR = """        r, c = e.grid()
        # 期望方向 = 朝下一节点（贴墙/边界时自动吸附回可走格，避免永久卡死）"""

NEW = """        r, c = e.grid()
        # ★直线优先（依 routes 的 `allowDiagonalMove: true` / `visitEveryTileCenter: false` 语义）：
        #   若"当前位置 → 目标格中心"的线段不穿过不可通行格，则直接朝目标中心直线推进；
        #   否则回退到 navmap 逐格导航（贴墙/绕障）。
        if getattr(self, 'straight_path', True):
            ex0, ey0 = fp.to_float(e.pos[0]), fp.to_float(e.pos[1])
            gx, gy = target_tile[1] + 0.5, target_tile[0] + 0.5
            if (abs(gx - ex0) + abs(gy - ey0)) > 1e-6 and \\
                    self.map.line_is_clear((ex0, ey0), (gx, gy), flying=e.flying):
                dvx, dvy = gx - ex0, gy - ey0
                norm = math.hypot(dvx, dvy) or 1.0
                speed = fp.to_float(e.move_speed) * self.move_multiplier
                e.inertia = (fp.from_float(dvx / norm * speed), fp.from_float(dvy / norm * speed))
                e.next_node = None
                dx = fp.to_float(fp.mul(e.inertia[0], fp.FRAME_TIME))
                dy = fp.to_float(fp.mul(e.inertia[1], fp.FRAME_TIME))
                nx = fp.to_float(e.pos[0]) + dx
                ny = fp.to_float(e.pos[1]) + dy
                if self.map.walkable_at(nx, ny, flying=e.flying):
                    e.pos = (fp.from_float(nx), fp.from_float(ny))
                else:
                    e.inertia = (0, 0)
                return
        # 期望方向 = 朝下一节点（贴墙/边界时自动吸附回可走格，避免永久卡死）"""


def main():
    s = io.open(ENGINE, encoding='utf-8').read()
    if '★直线优先' in s:
        print('已存在直线优先逻辑')
        return
    if ANCHOR not in s:
        print('★锚点未匹配')
        return
    s = s.replace(ANCHOR, NEW, 1)
    # 注入开关
    s = s.replace('        self.projectile_enabled = bool(opts.get(\'projectile\', True))',
                  '        self.projectile_enabled = bool(opts.get(\'projectile\', True))\n'
                  '        # ★直线寻路（对齐 routes 的 allowDiagonalMove 语义；False 回退逐格 navmap）\n'
                  '        self.straight_path = bool(opts.get(\'straight_path\', True))', 1)
    io.open(ENGINE, 'w', encoding='utf-8', newline='').write(s)
    print('已注入直线优先寻路')
    import ast
    ast.parse(io.open(ENGINE, encoding='utf-8').read())
    print('语法 OK')


if __name__ == '__main__':
    main()
